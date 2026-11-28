"""Scripts are judged like typed commands: .sh/.ps1/.bat files, package.json scripts, staged secrets."""
from __future__ import annotations

import re
import json
import subprocess
from pathlib import Path

from . import state
from .config import Config
from .shell import ParseError, base, split_commands
from .common import DELETE, Finding, INSTALLERS, NET, NET_OUT, SCHEDULE, SYSTEM_HIGH
from . import rules  # check_raw/check_segment: mutual recursion, resolved at call time

# ---------------------------------------------------------------------------------------------
# Scripts: what a command RUNS matters as much as the command itself (risk R-07, gap G-1).
# Shell-like scripts are parsed and judged with the same rules as a typed command.
# ---------------------------------------------------------------------------------------------

SCRIPT_POSIX = {".sh", ".bash", ".zsh"}
SCRIPT_WINDOWS = {".ps1", ".psm1", ".bat", ".cmd"}
SCRIPT_EXTS = SCRIPT_POSIX | SCRIPT_WINDOWS
SCRIPT_RUNNERS = {"bash", "sh", "zsh", "dash", "source", "powershell", "pwsh", "cmd"}
NPM_LIFECYCLE = {"test", "start", "build", "stop", "restart"}
INTERESTING = DELETE | SYSTEM_HIGH | SCHEDULE | NET | NET_OUT | set(INSTALLERS) | {"git", "reg", "netsh", "sc"}
MAX_SCRIPT_DEPTH = 3
MAX_SCRIPT_BYTES = 400_000


def _ext(token: str) -> str:
    return Path(token.strip("\"'")).suffix.lower()


def _script_files(seg: list[str], head: str, cfg: Config, cwd: Path, depth: int) -> list[Finding]:
    candidates = [seg[0]] if _ext(seg[0]) in SCRIPT_EXTS else []
    if head in SCRIPT_RUNNERS:
        candidates += [a for a in seg[1:] if _ext(a) in SCRIPT_EXTS]
    out: list[Finding] = []
    for c in candidates:
        out.extend(_scan_script(c.strip("\"'"), cfg, cwd, depth))
    return out


def _strip_script_comments(text: str, ext: str) -> str:
    if ext in {".bat", ".cmd"}:
        return re.sub(r"(?im)^\s*(rem\b|::).*$", "", text)
    if ext in {".ps1", ".psm1"}:
        text = re.sub(r"(?s)<#.*?#>", "", text)
    return re.sub(r"(?m)(^|\s)#.*$", r"\1", text)


def _judge_text(text: str, posix: bool, cfg: Config, cwd: Path, depth: int) -> list[Finding]:
    """Run the command rules over a piece of script text. Raises ParseError when it cannot be read safely."""
    segments = split_commands(text, posix=posix)
    found = rules.check_raw(text, segments, cfg, cwd)
    for seg in segments:
        for i, tok in enumerate(seg):
            if i == 0 or base(tok) in INTERESTING:      # also catches `if (...) { Remove-Item x }`
                found += rules.check_segment(seg[i:], cfg, cwd, depth + 1)
    seen, out = set(), []
    for f in found:
        if f.risk != "low" and (f.code, f.reason) not in seen:
            seen.add((f.code, f.reason))
            out.append(f)
    return out


def _scan_script(arg: str, cfg: Config, cwd: Path, depth: int) -> list[Finding]:
    rel = cfg.rel(arg, cwd)
    label = rel or arg
    if rel is not None and (rel.lower().startswith(".outrigger/engine/") or state.is_trusted(cfg, rel)):
        return []
    p = (cfg.root / rel) if rel is not None else Path(arg)
    if not p.is_file():
        return []
    if depth >= MAX_SCRIPT_DEPTH:
        return [Finding("medium", "script-depth", f"`{label}`: scripts call each other too deeply to check")]
    try:
        if p.stat().st_size > MAX_SCRIPT_BYTES:
            return [Finding("medium", "script-too-large", f"`{label}` is too large to check")]
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [Finding("medium", "script-unreadable", f"cannot read `{label}` to check it")]
    ext = p.suffix.lower()
    try:
        found = _judge_text(_strip_script_comments(text, ext), ext in SCRIPT_POSIX, cfg, p.parent, depth)
    except ParseError as exc:
        return [Finding("medium", "script-unparsed", f"`{label}` cannot be parsed safely ({exc}) — review it, then `cli.py trust` it")]
    return [Finding(f.risk, f.code if f.code.startswith("script") else f"script:{f.code}", f"`{label}` → {f.reason}", f.app)
            for f in found[:12]]


def _npm_script(head: str, args: list[str], cfg: Config, cwd: Path, depth: int) -> list[Finding]:
    """`npm run clean` is only as safe as the `clean` entry in package.json."""
    if not args or depth >= MAX_SCRIPT_DEPTH:
        return []
    first = args[0].lower()
    if first in {"run", "run-script"} and len(args) > 1:
        name = args[1]
    elif first in NPM_LIFECYCLE or (head != "npm" and not first.startswith("-")):
        name = args[0]
    else:
        return []
    pkg = cwd / "package.json"
    rel = cfg.rel(pkg, cwd)
    if not pkg.is_file() or (rel is not None and state.is_trusted(cfg, rel)):
        return []
    try:
        scripts = json.loads(pkg.read_text(encoding="utf-8", errors="replace")).get("scripts", {})
    except (OSError, ValueError):
        return [Finding("medium", "script-unreadable", "cannot read package.json to check the script")]
    out: list[Finding] = []
    for n in (f"pre{name}", name, f"post{name}"):
        body = scripts.get(n) if isinstance(scripts, dict) else None
        if not isinstance(body, str):
            continue
        try:
            found = _judge_text(body, True, cfg, cwd, depth)
        except ParseError as exc:
            found = [Finding("medium", "script-unparsed", f"cannot be parsed safely ({exc})")]
        out += [Finding(f.risk, f.code if f.code.startswith("script") else f"script:{f.code}",
                        f"package.json script `{n}` → {f.reason}", f.app) for f in found[:8]]
    return out


# ---------------------------------------------------------------------------------------------
# Secrets must not enter git history: once pushed they cannot be taken back (risk R-19).
# ---------------------------------------------------------------------------------------------

SECRET_COMMIT = [
    ("AWS access key", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})")),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("API key (sk-…)", re.compile(r"\bsk-[A-Za-z0-9_-]{32,}")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("password inside a URL", re.compile(r"[a-z][a-z0-9+.-]*://[^/\s:@'\"]+:[^/\s:@'\"${}<>*]{6,}@[^\s/]+")),
]


def _staged_secrets(low: list[str], cfg: Config, cwd: Path) -> list[Finding]:
    include_unstaged = any(a == "--all" or re.fullmatch(r"-[a-z]*a[a-z]*", a) for a in low[1:])
    diffs = [["git", "diff", "--cached", "-U0", "--no-color"]]
    if include_unstaged:
        diffs.append(["git", "diff", "-U0", "--no-color"])
    hits: list[str] = []
    for cmd in diffs:
        try:
            r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
        except (OSError, subprocess.SubprocessError) as exc:
            return [Finding("medium", "secret-scan-failed", f"could not check the commit for secrets ({type(exc).__name__})")]
        if r.returncode != 0:      # not a repository etc. — git itself will refuse the commit
            continue
        current = "?"
        for line in r.stdout.splitlines():
            if line.startswith("+++ "):
                current = line[6:] if line.startswith("+++ b/") else line[4:]
                if current != "/dev/null" and cfg.zone_of(current) == "red":
                    hits.append(f"{current} (secret file)")
            elif line.startswith("+"):
                for label, pat in SECRET_COMMIT:
                    if pat.search(line):
                        hits.append(f"{current} ({label})")
    hits = sorted(set(hits))
    if not hits:
        return []
    shown = "; ".join(hits[:6]) + (f"; … +{len(hits) - 6} more" if len(hits) > 6 else "")
    return [Finding("high", "secret-commit",
                    f"the commit would put secrets into git history: {shown}. Remove them (and rotate the key if it was real)")]
