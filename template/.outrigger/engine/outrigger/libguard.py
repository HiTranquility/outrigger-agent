"""0.7.0 (ADR-0016): guard rules for the personal workflow library and for promoting workflows.

The library (`[zones] library`, default `~/.outrigger/**` and `$OUTRIGGER_HOME/**`) is read by every project, so a
write into it spreads to all of them. Writes the path rules already see (Write/Edit, redirects, cp/mv/tee) are judged
there, destination-aware. This module is the backstop for the other writers (`tar -C`, `unzip -d`, `mkdir`, `ln`,
`mklink`, `git -C`, `New-Item`, `[IO.File]`, code given to an interpreter with `-c` or a heredoc, a `cd` into the
library): they ask with `library-write`. `cli.py export` asks however cli.py is reached (`library-export`).
A workflow outside `drafts/` counts as promoted by the user, so the agent writing one asks too (`workflow-promote`).

Known limit (G-5): a path assembled at run time from pieces that never spell the library is not seen. That is why
`import` always lands in `drafts/` as a draft: the library is defended where it is read, not only where it is written.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from .common import CD, COPY_LIKE, Finding, MOVE_LIKE, READ_ONLY, _as_path, cd_target
from .config import Config
from .shell import base

# `.outrigger/library`, `.outrigger\\library`, `'.outrigger', 'library'`, `.outrigger./library` … and the variable.
LIB_TEXT = re.compile(r"\.outrigger\W{0,6}library|outrigger_home", re.IGNORECASE)
EXPORT = re.compile(r"cli\.py[\"']?\s+(?:-\S+\s+)*[\"']?export\b", re.IGNORECASE)
SAFE_CLI = {"import", "onboard", "status", "selftest", "pending", "next-id"}
HELP = {"-h", "--help"}
WORKFLOWS = ".outrigger/local/workflows"
INTERPRETERS = {"python", "python3", "py", "node", "deno", "bun", "ruby", "perl", "php", "powershell", "pwsh",
                "bash", "sh", "zsh", "iex", "invoke-expression"}
CODE_FLAGS = {"-c", "-e", "--eval", "-command", "-encodedcommand", "-r"}
# Judged destination-aware by rules._guarded_writes (a copy FROM the library only reads it) — except `ln`, whose
# first argument is what the link points at.
DEST_AWARE = (MOVE_LIKE | COPY_LIKE | {"tee", "touch", "truncate", "set-content", "add-content", "out-file",
                                         "sed"}) - {"ln"}
OPENERS = {"start", "start-process", "saps", "explorer", "invoke-item", "ii", "code", "notepad", "open", "xdg-open"}
UNPACKERS = {"tar", "bsdtar", "unzip", "7z", "7za", "rsync", "expand-archive"}
GIT_WRITES = {"mv", "restore", "checkout", "apply", "am"}


def promotes(rel: str | None) -> bool:
    """A project path that is a promoted workflow, its folder, or `.outrigger/local` itself — not a draft."""
    if rel is None:
        return False
    r = rel.lower().rstrip("/")
    if r == ".outrigger/local":
        return True
    return (r == WORKFLOWS or r.startswith(WORKFLOWS + "/")) and not (r == WORKFLOWS + "/drafts"
                                                                       or r.startswith(WORKFLOWS + "/drafts/"))


def promote_finding(rel: str, how: str) -> Finding:
    return Finding("medium", "workflow-promote", f"{how} `{rel}`: a workflow outside drafts/ is one the user "
                                                 "promoted — only with their approval")


def _cli_sub(seg: list[str]) -> str | None:
    for i, tok in enumerate(seg):
        if base(tok) == "cli.py":
            rest = [a for a in seg[i + 1:] if not a.startswith("-")]
            return rest[0].strip("\"'").lower() if rest else ""
    return None


def _home_texts() -> list[str]:
    out = []
    for raw in (os.environ.get("OUTRIGGER_HOME", ""), "~/.outrigger"):
        if raw.strip():
            p = Path(os.path.expanduser(raw.strip())).resolve(strict=False).as_posix().lower()
            out += [p, p.replace("/", "\\")]
    return out


ASSIGN = re.compile(r"(?:^|[;&|\s])([A-Za-z_]\w*)=(\"[^\"]*\"|'[^']*'|[^\s;&|]+)")
VAR = re.compile(r"\$\{?([A-Za-z_]\w*)\}?")


def _tokens(seg: list[str], assigned: dict[str, str] | None = None) -> list[str]:
    """Arguments split at `=`, with shell variables assigned earlier in the command filled in
    (`D=~/.outrigger; tar -C $D/library` — the splitter drops the assignment itself)."""
    assigned = assigned or {}
    out = []
    for tok in seg[1:]:
        tok = VAR.sub(lambda m: assigned.get(m.group(1), m.group(0)), tok)
        out += [part.strip("\"'") for part in tok.split("=") if part.strip("\"'")]
    return out


def _kind(part: str, cfg: Config, cur: Path) -> str | None:
    p = _as_path(part, cur)
    return "inside" if cfg.rel(p) is not None else cfg.outside_kind(p)


def check(command: str, segments: list[list[str]], cfg: Config, cwd: Path) -> list[Finding]:
    out: list[Finding] = []
    export_segs = [s for s in segments if _cli_sub(s) == "export"]
    if (EXPORT.search(command) or export_segs) and not (export_segs and all(HELP & {a.lower() for a in s}
                                                                              for s in export_segs)):
        out.append(Finding("medium", "library-export", "`export` copies a workflow into your personal library, "
                                                       "which every project can import — only with your approval"))
    homes = _home_texts()

    def mentions(text: str) -> bool:
        return bool(LIB_TEXT.search(text)) or any(h in text.lower() for h in homes)

    heredoc = "<<" in command and mentions(command)   # a heredoc body is not in the segments
    assigned = {m.group(1): m.group(2).strip("\"'") for m in ASSIGN.finditer(command)}
    cur, lib_hit, promo = cwd, None, None
    for seg in segments:
        if not seg:
            continue
        head = base(seg[0])
        low = [a.lower() for a in seg[1:]]
        if head in CD:
            cur = cd_target(seg, cur)
            continue
        if head in READ_ONLY or head in OPENERS or _cli_sub(seg) in SAFE_CLI:
            continue
        in_lib = cfg.rel(cur) is None and cfg.outside_kind(cur) == "library"
        if head in DEST_AWARE:
            hit = in_lib
        elif head in INTERPRETERS:
            code = [seg[i + 1] for i, a in enumerate(low[:-1], 1) if a in CODE_FLAGS]
            hit = in_lib or heredoc or any(mentions(c) for c in code) or any(
                _kind(t, cfg, cur) == "library" for t in _tokens(seg, assigned) if not t.startswith("-"))
        elif head == "git":
            hit = any(_kind(t, cfg, cur) == "library" for t in _tokens(seg, assigned) if not t.startswith("-"))
            sub = next((a for a in low if not a.startswith("-")), "")
            if sub in GIT_WRITES and promo is None:
                promo = next((t for t in _tokens(seg, assigned) if promotes(cfg.rel(_as_path(t, cur)))), None)
        else:   # tar, unzip, mkdir, curl -o, ln, mklink, New-Item, [IO.File]::…, an assignment
            hit = in_lib or mentions(" ".join(seg)) or any(_kind(t, cfg, cur) == "library"
                                                           for t in _tokens(seg, assigned) if not t.startswith("-"))
            if head in UNPACKERS and promo is None:
                promo = next((t for t in _tokens(seg, assigned) if promotes(cfg.rel(_as_path(t, cur)))), None)
        if hit and lib_hit is None:
            lib_hit = head
    if lib_hit:
        out.append(Finding("medium", "library-write", f"`{lib_hit}` names your personal workflow library, read by "
                                                      "every project — only with your approval"))
    if promo:
        out.append(promote_finding(cfg.rel(_as_path(promo, cwd)) or promo, "writes"))
    return out
