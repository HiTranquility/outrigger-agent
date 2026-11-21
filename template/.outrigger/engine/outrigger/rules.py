"""Risk rules for shell commands. Each rule returns Findings; the decision takes the worst one."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
import json
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from . import packs, state
from .config import Config
from .shell import WRAPPERS, ParseError, base, split_commands, strip_heredocs

RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


@dataclass
class Finding:
    risk: str
    code: str
    reason: str
    app: str | None = None


DELETE = {"rm", "del", "erase", "rd", "rmdir", "remove-item", "ri", "unlink", "shred", "srm", "trash-put", "rimraf"}
READ_ONLY = {"cat", "type", "get-content", "gc", "less", "more", "head", "tail", "grep", "rg", "findstr",
             "select-string", "ls", "dir", "get-childitem", "gci", "wc", "stat", "file", "test-path", "echo",
             # 0.3.1 (ADR-0010 C): comparing files changes nothing — a `diff` of two engines was blocked as high risk
             "diff", "cmp", "comm", "fc", "compare-object", "sha256sum", "md5sum", "get-filehash"}
# Commands that write their path arguments (ADR-0010 A). Before 0.3.1 only `>` redirects into protected zones were
# checked, so `cp x protected/y` passed. MOVE-like commands also change their source; COPY-like ones only the target.
MOVE_LIKE = {"mv", "move", "move-item", "mi", "rename-item", "rni", "ren", "rename"}
COPY_LIKE = {"cp", "copy", "copy-item", "cpi", "xcopy", "robocopy", "install", "ln"}
WRITE_ALL = {"tee", "touch", "truncate", "set-content", "add-content", "out-file", "new-item", "ni", "clear-content"}
HELP_FLAGS = {"-h", "--help", "/?"}
SYSTEM_HIGH = {"format", "diskpart", "bcdedit", "shutdown", "restart-computer", "stop-computer", "regedit",
               "set-mppreference", "add-mppreference", "vssadmin", "mkfs", "dd", "runas", "su", "takeown",
               "set-executionpolicy", "cipher", "__sudo__", "iex", "invoke-expression", "__encoded__"}
SCHEDULE = {"schtasks", "register-scheduledtask", "set-scheduledtask", "unregister-scheduledtask",
            "new-scheduledtask", "new-scheduledtasktrigger", "new-scheduledtaskaction", "crontab", "at", "launchctl"}
NET = {"curl", "wget", "invoke-webrequest", "iwr", "invoke-restmethod", "irm", "bitsadmin",
       "start-bitstransfer", "certutil"}
NET_OUT = {"scp", "sftp", "ftp", "rsync", "nc", "ncat", "telnet", "ssh"}
INSTALLERS = {
    "pip": {"install"}, "pip3": {"install"}, "uv": {"add", "pip"}, "pipx": {"install"},
    "npm": {"install", "i", "add"}, "pnpm": {"add", "install", "i"}, "yarn": {"add", "install"},
    "bun": {"add", "install", "i"}, "winget": {"install", "upgrade"}, "choco": {"install", "upgrade"},
    "scoop": {"install"}, "conda": {"install", "create"}, "mamba": {"install"}, "apt": {"install"},
    "apt-get": {"install"}, "brew": {"install"}, "gem": {"install"}, "cargo": {"install"},
    "install-module": None, "install-package": None, "npx": None,
}
APPS = {"start", "start-process", "saps", "explorer", "invoke-item", "ii", "code", "notepad", "open",
        "xdg-open", "simulink", "msedge", "chrome", "firefox"}
UPLOAD_FLAGS = {"-d", "--data", "--data-raw", "--data-binary", "--data-urlencode", "-f", "--form", "-t",
                "--upload-file", "--post-data", "--post-file", "-body", "-infile"}
UPLOAD_METHODS = {"post", "put", "patch", "delete"}
OUTRIGGER_HUMAN_ONLY = re.compile(r"cli\.py[\"']?\s+(?:-\S+\s+)*(approve|resume|empty-trash|deny|trust|untrust|rule\s+accept)\b",
                                  re.IGNORECASE)
OUTRIGGER_SELF = re.compile(r"\.outrigger[\\/](engine|state|outrigger\.toml|local[\\/]notify\.toml)|\.claude[\\/]settings"
                       r"|\.mcp\.json|\.codex[\\/]|\.agents[\\/]hooks\.json|\.cursor[\\/]hooks\.json", re.IGNORECASE)
PIPE_TO_SHELL = re.compile(r"(curl|wget|iwr|irm|invoke-webrequest|invoke-restmethod)\b[^|\n]*\|\s*"
                           r"(sudo\s+)?(sh|bash|zsh|python3?|iex|invoke-expression|pwsh|powershell)\b", re.IGNORECASE)
PY_DELETE = re.compile(r"shutil\.rmtree|os\.(remove|unlink|rmdir)|Path\([^)]*\)\.unlink|\.rmdir\(", re.IGNORECASE)
ROOTLIKE = {"/", "\\", "~", "~/", "*", "/*", ".", "./", "..", "../", "c:", "c:\\", "c:/", "$home", "%userprofile%"}


def worst(findings: list[Finding]) -> str:
    return max((f.risk for f in findings), key=RISK_ORDER.get, default="low")


OUTRIGGER_CLI = re.compile(r"\.outrigger[\\/]engine[\\/]cli\.py", re.IGNORECASE)
REDIRECT_TARGET = re.compile(r"(?:^|[^<0-9&])\d?>>?\s*(\"[^\"]+\"|'[^']+'|[^\s;&|]+)")


CD = {"cd", "pushd", "set-location", "sl", "chdir"}
MSYS_DRIVE = re.compile(r"^/([a-zA-Z])(/|$)")


def _as_path(token: str, cwd: Path) -> Path:
    p = MSYS_DRIVE.sub(lambda m: m.group(1) + ":/", token.strip("\"'"))   # Git Bash: /c/Users -> c:/Users
    p = Path(os.path.expandvars(os.path.expanduser(p)))
    return p if p.is_absolute() else cwd / p


def _self_hit(command: str, segments: list[list[str]], cfg: Config, cwd: Path) -> str | None:
    """A path to Outrigger's own engine / config / state / hook settings OF THE GUARDED PROJECT, used by a command
    that is not read-only. Before 0.3.0 this matched the raw text, so a read-only `git log` in ANOTHER repository
    whose path happened to contain `.outrigger/engine` was blocked as high risk (FP-6, ROADMAP 2026-11-12).
    `cd` is followed so relative paths resolve where they will run. Unparsed commands keep the old raw match."""
    if not segments:
        m = OUTRIGGER_SELF.search(OUTRIGGER_CLI.sub("", command))
        return m.group(0) if m else None
    cur = cwd
    for seg in segments:
        if not seg:
            continue
        head = base(seg[0])
        if head in CD and len(seg) > 1:
            cur = _as_path(seg[1], cur)
            continue
        if head in READ_ONLY:
            continue
        # R-24: the installer rewrites the engine, rules and hooks of its --target. Run by the agent against the
        # guarded project (not --dry), it is an edit to the guard that the path check above cannot see.
        if any(Path(t).name.lower() == "install.py" for t in seg) and "--dry" not in seg:
            low = [t.lower() for t in seg]
            tgt = seg[low.index("--target") + 1] if "--target" in low and low.index("--target") + 1 < len(seg) else None
            if tgt is not None and cfg.rel(_as_path(tgt, cur)) is not None:
                return "install.py --target <this project>"
        for tok in seg:
            for part in tok.split("="):
                if OUTRIGGER_CLI.search(part) or not OUTRIGGER_SELF.search(part):
                    continue
                if cfg.rel(_as_path(part, cur)) is not None:        # inside the guarded project
                    return OUTRIGGER_SELF.search(part).group(0)
    return None


def check_raw(command: str, segments: list[list[str]], cfg: Config, cwd: Path) -> list[Finding]:
    out = []
    if PIPE_TO_SHELL.search(command):
        out.append(Finding("high", "pipe-to-shell", "download piped straight into a shell or interpreter"))
    if OUTRIGGER_HUMAN_ONLY.search(command) and not _only_help(command, segments):
        out.append(Finding("high", "self-approval", "approve/deny/resume/empty-trash/trust are human-only commands"))
    hit = _self_hit(command, segments, cfg, cwd)
    if hit:
        out.append(Finding("high", "outrigger-self", f"command touches Outrigger or hook configuration ({hit})"))
    for t in _redirect_targets(command, segments):
        t = t.strip("\"'")
        if t.lower() in {"/dev/null", "nul", "&1", "&2"}:
            continue
        rel = cfg.rel(t, cwd)
        if rel is None:
            if cfg.outside_kind(t) == "agent-config":
                out.append(Finding("medium", "agent-config", f"redirects output into agent configuration `{t}`"))
            elif not cfg.outside_allowed(t):
                out.append(Finding("medium", "write-outside", f"redirects output outside the project: `{t}`"))
        elif cfg.zone_of(rel) in {"red", "protected", "originals"}:
            out.append(Finding("high", "write-protected", f"redirects output into `{rel}` ({cfg.zone_of(rel)} zone)"))
    if re.search(r"base64\s+(-d|--decode)[^|\n]*\|\s*(sh|bash)", command, re.IGNORECASE):
        out.append(Finding("high", "encoded-exec", "decoded payload piped into a shell"))
    if PY_INLINE.search(command) and PY_DELETE.search(command):   # `-c` and, from 0.3.4, a heredoc fed to python
        out.append(Finding("medium", "delete-redirect", "inline python deletes files — use `cli.py trash`"))
    return out


PY_INLINE = re.compile(r"\bpython3?(?:\.exe)?\b[^\n|;&]*(?:\s-c\s|<<)", re.IGNORECASE)
NESTED_SHELL = re.compile(r"\$\(|`|\beval\b|\bsource\b|(?:^|[\s;&|(/\\])(?:" + "|".join(sorted(WRAPPERS))
                          + r")(?:\.exe)?\s", re.IGNORECASE)




def _mask_quotes(command: str) -> str | None:
    """Same-length copy with the inside of '…' and "…" blanked, so a `>` in a quoted grep pattern is not a redirect.
    None when quotes do not balance (caller fails closed)."""
    out, quote, i = list(command), None, 0
    while i < len(command):
        c = command[i]
        if quote is None:
            if c in "'\"":
                quote = c
            elif c == "\\":
                i += 1
        elif c == quote:
            quote = None
        elif quote == '"' and c == "\\" and i + 1 < len(command):
            out[i] = out[i + 1] = "_"
            i += 1
        else:
            out[i] = "_"
        i += 1
    return None if quote else "".join(out)


def _redirect_targets(command: str, segments: list[list[str]]) -> list[str]:
    """Redirect targets outside quotes (FP-7). A quoted string can still run as code when the line holds a nested
    shell (`bash -c`, `$(…)`, backticks, `eval`) — then every `>` counts, as before.
    A heredoc body is data for the program reading it (FP-8: `len(x)>2` in `python - <<EOF`), unless a shell reads it:
    then the nested-shell test above already keeps every `>`."""
    if NESTED_SHELL.search(command):
        return REDIRECT_TARGET.findall(command)
    flat = strip_heredocs(command)
    masked = _mask_quotes(flat)
    if masked is None:
        return REDIRECT_TARGET.findall(command)
    return [flat[m.start(1):m.end(1)] for m in REDIRECT_TARGET.finditer(masked)]


def _only_help(command: str, segments: list[list[str]]) -> bool:
    """`cli.py trust --help` only prints argparse help and exits before any command runs (ADR-0010 C).
    True when EVERY segment that names a human-only subcommand carries a help flag as its own token.
    Unparsed commands and commands nested in quotes (`bash -c "…"`) never count as help-only: fail closed."""
    if not segments:
        return False
    hits = [seg for seg in segments if OUTRIGGER_HUMAN_ONLY.search(" ".join(seg))]
    if not hits or len(hits) != len(OUTRIGGER_HUMAN_ONLY.findall(command)):
        return False
    return all(any(t.lower() in HELP_FLAGS for t in seg) and
               all(not OUTRIGGER_HUMAN_ONLY.search(t) for t in seg) for seg in hits)


def _write_targets(head: str, args: list[str]) -> list[str]:
    """Paths a write-like command changes. Unknown shapes return every non-flag argument (fail closed)."""
    pos = [a for a in args if not a.startswith("-")]
    low = [a.lower() for a in args]
    if head in MOVE_LIKE or head in WRITE_ALL:
        return pos
    if head == "robocopy":
        return pos[1:2]
    for flag in ("-t", "--target-directory", "-destination"):
        if flag in low and low.index(flag) + 1 < len(args):
            return [args[low.index(flag) + 1]]
    return pos[-1:]


def _guarded_writes(head: str, args: list[str], cfg: Config, cwd: Path) -> list[Finding]:
    if head == "sed" and not any(a == "-i" or a.startswith("-i") or a == "--in-place" for a in args):
        return []
    if head not in MOVE_LIKE | COPY_LIKE | WRITE_ALL | {"sed"}:
        return []
    out = []
    for t in _write_targets(head, args) if head != "sed" else [a for a in args if not a.startswith("-")]:
        rel = cfg.rel(_as_path(t, cwd))
        if rel is not None and cfg.zone_of(rel) in {"protected", "originals"}:
            out.append(Finding("high", "write-protected", f"`{head}` changes `{rel}` ({cfg.zone_of(rel)} zone)"))
    return out


# 0.4.0 (ADR-0012): code in the quarantine zone is someone else's, copied in to be READ. Reading, listing, comparing
# and `git log` are fine; anything that would run, build, install or serve it is high risk, whatever the wording.
QUARANTINE_READ = READ_ONLY | CD | {"find", "tree", "sort", "uniq", "cut", "jq", "xxd", "od", "hexdump", "strings",
                                    "du", "pwd", "realpath", "basename", "dirname", "nl", "tac", "column"}
QUARANTINE_GIT_READ = {"log", "show", "diff", "status", "rev-parse", "ls-files", "ls-tree", "blame", "grep",
                       "cat-file", "describe", "shortlog"}
EXEC_HEADS = WRAPPERS | {"python", "python3", "py", "node", "deno", "bun", "ruby", "perl", "php", "iex",
                         "invoke-expression", "source", ".", "npx", "pnpx", "java", "dotnet", "go", "cargo", "make",
                         "cmake", "docker", "docker-compose", "podman", "matlab", "octave", "rscript", "uv", "uvx",
                         "pipx", "poetry", "xargs"}


def quarantine_touch(seg: list[str], cfg: Config, cwd: Path) -> bool:
    """Does this segment run inside, or name a path inside, the quarantine zone?"""
    zone = cfg.section("zones").get("quarantine", [])
    if not zone or not seg:
        return False
    from .config import match_any
    here = cfg.rel(cwd)
    if here is not None and match_any(here, zone):
        return True
    # A path inside code text (`matlab -batch "run('sandbox/quarantine/x/a.m')"`, `python -c "...")` is not an argument
    # of its own, so the zone's folder is also looked for as text (found by the live check with the MATLAB pack).
    prefixes = [p.lower().split("*", 1)[0].rstrip("/") + "/" for p in zone if p.split("*", 1)[0].strip("/")]
    for a in seg:
        text = a.replace("\\", "/").lower()
        if any(pre in text for pre in prefixes):
            return True
        if a.startswith("-") or "://" in a:
            continue
        rel = cfg.rel(a.strip("\"'"), cwd)
        if rel is not None and match_any(rel, zone):
            return True
    return False


ASK_RUNNERS = {"npx", "pnpx", "bunx", "pnpm", "yarn", "bun", "exec", "dlx", "uv", "uvx", "run", "poetry", "pipenv",
               "python", "python3", "py", "-m", "bundle", "sudo"}


def _ask_matches(toks: list[str], pattern: list[str]) -> bool:
    """`pattern[0]` is the program, found among the first tokens so that runners (`npx`, `pnpm exec`, `uv run`,
    `python -m`, `yarn`) do not hide it; the rest must follow in order, other words and flags may sit between."""
    for start in range(min(4, len(toks))):
        if toks[start] != pattern[0]:
            if toks[start] not in ASK_RUNNERS:   # `echo prisma migrate` prints; only a runner may come first
                return False
            continue
        i = start + 1
        for want in pattern[1:]:
            while i < len(toks) and toks[i] != want:
                i += 1
            if i == len(toks):
                break
            i += 1
        else:
            return True
    return False


def _pack_asks(seg: list[str], cfg: Config) -> list[Finding]:
    if not seg or not cfg.asks:
        return []
    toks = [base(seg[0])] + [base(t) if i < 3 else t.lower() for i, t in enumerate(seg[1:])]
    out = []
    for ask in cfg.asks:
        hit = next((p for p in ask.commands if _ask_matches(toks, p)), None)
        if hit:
            out.append(Finding(ask.risk, "pack-ask", f"{ask.reason} (`{' '.join(hit)}`, {ask.pack} pack: asks every time)"))
    return out


def is_recon(seg: list[str]) -> bool:
    """`python .outrigger/engine/cli.py recon …` — the one command that may name a quarantined path to scan it."""
    at = next((i for i, a in enumerate(seg) if base(a) == "cli.py" and OUTRIGGER_CLI.search(a.replace("\\", "/"))), None)
    return at is not None and len(seg) > at + 1 and seg[at + 1].lower() == "recon"


def _git_sub(low: list[str]) -> str:
    i = 0
    while i < len(low):
        if low[i] in {"-c", "--git-dir", "--work-tree"}:   # `low` is lower-cased, so `-C <dir>` arrives as `-c`
            i += 2
            continue
        if low[i].startswith("-"):
            i += 1
            continue
        return low[i]
    return ""


def check_quarantine(seg: list[str], cfg: Config, cwd: Path) -> list[Finding]:
    if not quarantine_touch(seg, cfg, cwd):
        return []
    head = base(seg[0])
    low = [a.lower() for a in seg[1:]]
    if head in QUARANTINE_READ or head in DELETE or head in MOVE_LIKE:   # delete/move: the normal rules judge them
        return []
    if head == "sed" and not any(a.startswith("-i") or a == "--in-place" for a in low):
        return []
    if head == "git" and _git_sub(low) in QUARANTINE_GIT_READ:
        return []
    if is_recon(seg):
        return []
    if head in COPY_LIKE:
        return [Finding("medium", "quarantine-copy", "copies code out of the quarantine zone — review it before it "
                                                     "joins the project")]
    return [Finding("high", "quarantine-exec", f"`{head}` would run, build or install code from the quarantine zone "
                                               "— read it, never run it (ADR-0012)")]


def check_segment(seg: list[str], cfg: Config, cwd: Path, depth: int = 0) -> list[Finding]:
    if not seg:
        return []
    head = base(seg[0])
    args = seg[1:]
    low = [a.lower() for a in args]
    out: list[Finding] = []

    out.extend(_pack_asks(seg, cfg))   # every depth: `npm run db:migrate` hides `prisma migrate deploy` (ADR-0014)
    if depth == 0:   # lines inside a quarantined script are not each "run from quarantine": the outer run is judged
        out.extend(check_quarantine(seg, cfg, cwd))
    out.extend(_script_files(seg, head, cfg, cwd, depth))
    if head in NPM_RUNNERS:
        out.extend(_npm_script(head, args, cfg, cwd, depth))


    # secrets: any argument pointing into the red zone
    for a in args:
        if a.startswith("-"):
            continue
        rel = cfg.rel(a, cwd)
        if rel is not None and cfg.zone_of(rel) == "red":
            out.append(Finding("high", "secret", f"touches a secret file: {rel}"))
    out.extend(_guarded_writes(head, args, cfg, cwd))

    if head in SYSTEM_HIGH:
        out.append(Finding("high", "system", f"`{head}` changes the system, raises privilege or runs hidden code"))
    elif head == "reg" and low and low[0] in {"add", "delete", "import", "load", "restore", "unload"}:
        out.append(Finding("high", "registry", "registry change"))
    elif head == "netsh" and any("firewall" in a for a in low):
        out.append(Finding("high", "firewall", "firewall change"))
    elif head == "sc" and low and low[0] in {"delete", "config", "stop", "create"}:
        out.append(Finding("high", "service", "Windows service change"))
    elif head in {"chmod", "chown", "icacls"} and any(a in {"-r", "777", "/grant", "/reset", "/remove"} or a.startswith("/grant") for a in low):
        out.append(Finding("high", "permissions", "recursive or world-writable permission change"))
    elif head in {"set-itemproperty", "new-itemproperty", "remove-itemproperty"} and any(a.startswith(("hklm", "hkcu")) for a in low):
        out.append(Finding("high", "registry", "registry change"))

    if head in SCHEDULE:
        if not (head == "schtasks" and low and low[0] in {"/query", "/?"}) and not (head == "crontab" and low == ["-l"]):
            out.append(Finding("high", "schedule", "creates or changes a scheduled task"))

    if head == "git":
        out.extend(_git(low))
        if low[:1] == ["commit"]:
            out.extend(_staged_secrets(low, cfg, cwd))

    if head in DELETE or (head == "find" and ("-delete" in low or "-exec" in low and any(base(a) in DELETE for a in args))):
        out.append(_delete(args, cfg, cwd))

    if head in NET:
        out.append(_net(head, args, low, cfg))
    elif head in NET_OUT:
        out.append(Finding("high", "upload", f"`{head}` can send data off this machine"))

    if head in INSTALLERS:
        verbs = INSTALLERS[head]
        sub = low[0] if low else ""
        if verbs is None or sub in verbs:
            out.append(Finding("medium", "install", f"installs software (`{head} {sub}`) — supply-chain check first"))
    if head in {"python", "python3", "py"} and "-m" in low:
        i = low.index("-m")
        if i + 2 < len(low) and low[i + 1] in {"pip", "pipx"} and low[i + 2] == "install":
            out.append(Finding("medium", "install", "pip install — supply-chain check first"))

    cli_at = next((i for i, a in enumerate(seg) if base(a) == "cli.py" and OUTRIGGER_CLI.search(a.replace("\\", "/")) or
                   (i == 0 and base(a) == "cli.py")), None)
    if cli_at is not None:
        out.extend(_outrigger_cli(seg[cli_at:], cfg, cwd))

    if head in APPS and not any(head in p.commands for p in cfg.packs):   # a pack that knows the app judges it
        out.append(Finding("medium", "app", f"opens an interactive app (`{' '.join(seg[:3])}`) — L2", app=" ".join(seg[:3])))

    for pack in cfg.packs:
        if head in pack.commands:
            out.extend(_pack_run(pack, seg, low, cfg, cwd))

    return out


def _git(low: list[str]) -> list[Finding]:
    if not low:
        return []
    sub, rest = low[0], low[1:]
    if sub == "push":
        if any(a in {"--force", "-f", "--force-with-lease", "--mirror", "--delete", "-d", "--prune"} or a.startswith("--force") or a.startswith(":") for a in rest):
            return [Finding("high", "git-force", "force/delete push rewrites shared history")]
        return [Finding("medium", "git-push", "push sends code off this machine")]
    if sub == "reset" and "--hard" in rest:
        return [Finding("high", "git-hard", "`git reset --hard` discards work")]
    if sub == "clean" and any(a.startswith("-") and "f" in a for a in rest):
        return [Finding("high", "git-clean", "`git clean -f` deletes untracked files for good")]
    if sub == "branch" and any(a in {"-d", "--delete"} for a in rest):
        return [Finding("medium", "git-branch", "deletes a branch")]
    if sub in {"filter-branch", "filter-repo"}:
        return [Finding("high", "git-rewrite", "rewrites history")]
    if sub in {"checkout", "restore"} and ("." in rest or "--" in rest):
        return [Finding("medium", "git-discard", "discards uncommitted changes")]
    if sub == "stash" and rest[:1] in (["drop"], ["clear"]):
        return [Finding("medium", "git-stash", "drops stashed work")]
    if sub == "clone":
        return [Finding("medium", "git-clone", "downloads a repository — check the source tier")]
    return []


def _delete(args: list[str], cfg: Config, cwd: Path) -> Finding:
    targets = [a for a in args if not a.startswith("-") and not (len(a) <= 3 and a.startswith("/") and a[1:].isalpha())]
    for t in targets:
        if t.lower().rstrip("\\/") in {x.rstrip("\\/") for x in ROOTLIKE} or t.lower() in ROOTLIKE:
            return Finding("high", "delete-root", f"delete aimed at a root-like path `{t}`")
        rel = cfg.rel(t, cwd)
        if rel is None:
            return Finding("high", "delete-outside", f"delete outside the project: `{t}`")
        if rel in ("", ".") or rel == "":
            return Finding("high", "delete-root", "delete aimed at the project root")
        from .config import match_any
        if match_any(rel, cfg.section("zones").get("never_delete", [])):
            return Finding("high", "never-delete", f"`{rel}` is never_delete (ADRs, logs)")
    return Finding("medium", "delete-redirect",
                   "hard delete — use `python .outrigger/engine/cli.py trash <paths> --reason \"...\"` (restorable)")


def _net(head: str, args: list[str], low: list[str], cfg: Config) -> Finding:
    if any(a in UPLOAD_FLAGS for a in low) or any(a.startswith(("--data", "--form", "--upload")) for a in low):
        return Finding("high", "upload", f"`{head}` sends data to a server")
    for i, a in enumerate(low):
        if a in {"-x", "--request", "-method"} and i + 1 < len(low) and low[i + 1] in UPLOAD_METHODS:
            return Finding("high", "upload", f"`{head}` uses method {low[i + 1].upper()}")
    if head == "certutil" and "-urlcache" in low:
        return Finding("high", "download-lolbin", "certutil download (common malware technique)")
    hosts = [urlparse(a).hostname for a in args if "://" in a]
    hosts = [h for h in hosts if h]
    if hosts and all(cfg.host_allowed(h) for h in hosts):
        return Finding("low", "net-allowed", f"download from allow-listed host {hosts[0]}")
    return Finding("medium", "net-unknown",
                   f"download from a host not on the allow-list ({', '.join(hosts) or 'unknown'}) — T4 until checked")


def _outrigger_cli(args: list[str], cfg: Config, cwd: Path) -> list[Finding]:
    sub = args[1].lower() if len(args) > 1 else ""
    if any(a.lower() in HELP_FLAGS for a in args[1:]):   # argparse prints help and exits before running (ADR-0010 C)
        return []
    if sub in {"approve", "resume", "empty-trash", "deny", "trust", "untrust"}:
        return [Finding("high", "self-approval", f"`{sub}` is human-only")]
    if sub == "rule" and len(args) > 2 and args[2].lower() == "accept":   # 0.3.2 (ADR-0011)
        return [Finding("high", "self-approval", "`rule accept` is human-only — a standing rule is a standing approval")]
    if sub == "recon":   # 0.4.0 (ADR-0012): the clone runs inside cli.py, so the hook judges its source here
        urls = [a for a in args[2:] if "://" in a]
        if any(not a.lower().startswith("https://") for a in urls):
            return [Finding("high", "recon-scheme", "recon clones over https only")]
        hosts = [urlparse(a).hostname or "" for a in urls]
        bad = [h for h in hosts if not cfg.host_allowed(h)]
        if bad:
            return [Finding("medium", "net-unknown", f"recon downloads from `{bad[0]}` — not on the allow-list")]
        return [Finding("low", "recon", f"recon into quarantine{': ' + hosts[0] if hosts else ''}")]
    if sub in {"trash", "archive"}:
        paths = [a for a in args[2:] if not a.startswith("-")]
        if "--reason" in args:
            i = args.index("--reason")
            paths = [a for a in args[2:i] if not a.startswith("-")] + [a for a in args[i + 2:] if not a.startswith("-")]
        files, size = 0, 0
        from .config import match_any
        for p in paths:
            rel = cfg.rel(p, cwd)
            if rel is None:
                return [Finding("high", "trash-outside", f"`{p}` is outside the project")]
            if match_any(rel, cfg.section("zones").get("never_delete", [])) and sub == "trash":
                return [Finding("high", "never-delete", f"`{rel}` is never_delete")]
            full = cfg.root / rel
            for f in ([full] if full.is_file() else full.rglob("*") if full.is_dir() else []):
                if f.is_file():
                    files += 1
                    size += f.stat().st_size
        if files > cfg.limit("trash_max_files") or size > cfg.limit("trash_max_mb") * 1024 * 1024:
            return [Finding("medium", "bulk", f"bulk {sub}: {files} files, {size / 1048576:.1f} MB")]
    return []


def _pack_run(pack, seg: list[str], low: list[str], cfg: Config, cwd: Path) -> list[Finding]:
    headless = pack.always_headless or any(f in low for f in pack.headless_flags)
    if not headless:
        if pack.gui_always_ask:   # 0.4.1 (ADR-0013): the pack says opening this app costs something (a licence seat)
            risk = "high" if pack.gui_level == "high" else "medium"
            return [Finding(risk, "app-ask", f"opens {pack.name} interactively — L2; this pack asks every time "
                                             "(gui_always_ask)", app=f"{pack.name} (GUI)")]
        return [Finding(pack.gui_level, "app", f"opens {pack.name} interactively — L2", app=f"{pack.name} (GUI)")]
    ext = pack.scan_extensions[0] if pack.scan_extensions else ""
    if pack.scan_scope == "target":
        return _pack_target(pack, seg, low, cfg, cwd, ext)
    inline = " ".join(seg[1:])
    hits = [f"<command>: {s}" for _, s in packs.scan_text(inline, pack, ext)]
    hits += packs.scan_project(cfg, pack)
    if hits:
        shown = "; ".join(hits[:8]) + (f"; … +{len(hits) - 8} more" if len(hits) > 8 else "")
        return [Finding("medium", "pack-danger",
                        f"{pack.name} headless run, but the code contains dangerous calls: {shown}",
                        app=f"{pack.name} (headless)")]
    return [Finding("low", "pack-headless", f"{pack.name} headless run (L1), code scan clean", app=f"{pack.name} (headless)")]


def _pack_target(pack, seg: list[str], low: list[str], cfg: Config, cwd: Path, ext: str) -> list[Finding]:
    """Scan only what this command runs: inline code (`-c "..."`) and the script files it names.

    Outrigger's own engine is trusted (it is protected from edits). Modules run with `-m` are not scanned:
    that is a documented limit (R-07 in docs/RISK_REGISTER.md)."""
    hits: list[str] = []
    notes: list[Finding] = []
    for i, flag in enumerate(low):  # `low` is seg[1:] lower-cased, so the code follows at seg[i + 2]
        if flag in {"-c", "-e", "--eval", "-p", "--print"} and i + 2 < len(seg):
            hits += [f"<{flag}>: {s}" for _, s in packs.scan_text(seg[i + 2], pack, ext)]
    for a in seg[1:]:
        if not a.lower().endswith(tuple(pack.scan_extensions)):
            continue
        rel = cfg.rel(a, cwd)
        if rel is not None and (rel.lower().startswith(".outrigger/engine/") or state.is_trusted(cfg, rel)):
            continue
        p = (cfg.root / rel) if rel is not None else Path(a)
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return [Finding("medium", "pack-unreadable", f"cannot read `{a}` to check it")]
        # 0.3.1 (ADR-0010 B): a trusted script that was edited asks again only for dangerous lines it did not have
        # when the human trusted it. Light mode only; strict keeps whole-file hashing. The snapshot holds the full
        # text of each dangerous line, so changing the ARGUMENT of an old call (`os.remove(a)` → `os.remove(b)`)
        # is a new line and asks. Not caught: changing a variable on another line that an old call uses (R-25).
        snap = state.trusted_danger(cfg, rel) if (rel is not None and cfg.light) else None
        if snap is not None:
            new = packs.new_danger_lines(text, pack, p.suffix.lower(), snap)
            if not new:
                notes.append(Finding("low", "trusted-drift",
                                     f"{rel} changed since it was trusted but adds no dangerous line (diff-scoped trust)"))
                continue
            hits += [f"{rel}:{n}: new since trust: {s}" for n, s in new]
            continue
        hits += [f"{rel or a}:{n}: {s}" for n, s in packs.scan_text(text, pack, p.suffix.lower())]
    if hits:
        shown = "; ".join(hits[:8]) + (f"; … +{len(hits) - 8} more" if len(hits) > 8 else "")
        return notes + [Finding("medium", "pack-danger", f"{pack.name} script contains dangerous calls: {shown}")]
    return notes


# ---------------------------------------------------------------------------------------------
# Scripts: what a command RUNS matters as much as the command itself (risk R-07, gap G-1).
# Shell-like scripts are parsed and judged with the same rules as a typed command.
# ---------------------------------------------------------------------------------------------

SCRIPT_POSIX = {".sh", ".bash", ".zsh"}
SCRIPT_WINDOWS = {".ps1", ".psm1", ".bat", ".cmd"}
SCRIPT_EXTS = SCRIPT_POSIX | SCRIPT_WINDOWS
SCRIPT_RUNNERS = {"bash", "sh", "zsh", "dash", "source", "powershell", "pwsh", "cmd"}
NPM_RUNNERS = {"npm", "pnpm", "yarn", "bun"}
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
    found = check_raw(text, segments, cfg, cwd)
    for seg in segments:
        for i, tok in enumerate(seg):
            if i == 0 or base(tok) in INTERESTING:      # also catches `if (...) { Remove-Item x }`
                found += check_segment(seg[i:], cfg, cwd, depth + 1)
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
