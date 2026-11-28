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
LIB_TEXT = re.compile(r"\.outrigger\W{0,6}library|(?:\$\{?|\benv:)(?:env:)?outrigger_home\b", re.IGNORECASE)
HOME_VAR = re.compile(r"outrigger_home", re.IGNORECASE)          # named in code: judged together with WRITE_WORDS
WRITE_WORDS = re.compile(r"['\"][wax][bt]?\+?['\"]|write|rename|replace|copy|move|mkdir|makedirs|symlink|link|"
                         r"touch|set-content|out-file|new-item|unlink|remove|rmtree|dump|save|extract",
                         re.IGNORECASE)
PROMOTE_IN_CODE = re.compile(r"(\.outrigger[\\/]+local(?:[\\/]+workflows(?![\\/]+drafts)[^'\"\s]*)?)", re.IGNORECASE)
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
# Run INSIDE the library these only read. Their arguments are still judged (`git diff --output=<library>`).
GIT_READS = {"status", "log", "diff", "show", "grep", "blame", "describe", "rev-parse", "ls-files", "shortlog",
             "help", "version"}
ARCHIVERS = {"tar", "bsdtar", "zip", "7z", "7za"}
LINKERS = {"ln", "mklink", "new-item", "ni"}
PATCH_TARGET = re.compile(r"^(?:\+\+\+ b/|diff --git a/\S+ b/|rename to |copy to )(\S+)", re.MULTILINE)


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


# `NAME=` followed by ONE shell word, which may join quoted and bare pieces: `D="$HOME"/.outrigger/library`
ASSIGN = re.compile(r"(?:^|[;&|\s])([A-Za-z_]\w*)(\+?)=(\([^)]*\)|(?:\"[^\"]*\"|'[^']*'|[^\s;&|\"'()])+)")
# variables a tool WRITES a file to: `GIT_TRACE=<library>/x git status` puts agent-chosen text there
FILE_VARS = re.compile(r"^(GIT_TRACE\w*|GIT_INDEX_FILE|HISTFILE|\w*_(FILE|LOG|LOGFILE|OUTPUT|DUMP|TRACE))$")
VAR = re.compile(r"\$\{?([A-Za-z_]\w*)\}?")
RUN_VARS = re.compile(r"^(GIT_(PAGER|SSH|SSH_COMMAND|EXTERNAL_DIFF|EDITOR|SEQUENCE_EDITOR|ASKPASS|PROXY_COMMAND)|"
                      r"SSH_ASKPASS|PAGER|EDITOR|VISUAL|LESSOPEN|LESSCLOSE|MANPAGER)$")


def _raw_value(command: str, name: str) -> str:
    vals = [m.group(3) for m in ASSIGN.finditer(command) if m.group(1) == name]
    raw = vals[-1] if vals else ""
    return raw[1:-1] if len(raw) > 1 and raw[0] == raw[-1] == '"' else raw


def mentions_library(text: str) -> bool:
    return bool(LIB_TEXT.search(text)) or any(h in text.lower() for h in _home_texts())


def _assignments(command: str) -> dict[str, str]:
    """`NAME=value` in order; `NAME+=more` appends to the earlier value (`D=~/.outrigger; D+=/library`)."""
    out: dict[str, str] = {}
    for m in ASSIGN.finditer(command):
        val = re.sub(r"[\"']", "", m.group(3))
        if val.startswith("("):                       # array `A=(x y)`: `$A` is its first element
            items = val[1:-1].split()
            val = items[0] if items else ""
        out[m.group(1)] = out.get(m.group(1), "") + val if m.group(2) else val
    return out


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

    def code_mentions(text: str) -> bool:   # code may read the variable by name: `os.environ['OUTRIGGER_HOME']`
        return mentions(text) or bool(HOME_VAR.search(text) and WRITE_WORDS.search(text))

    def promoted_in(paths: list[str], where: Path) -> str | None:
        for t in paths:
            rel = cfg.rel(_as_path(t, where))
            if promotes(rel):
                return rel
        return None

    heredoc = "<<" in command and code_mentions(command)   # a heredoc body is not in the segments
    # `echo <library path> | xargs touch`: the path reaches the writer through stdin, not as an argument
    piped = bool(re.search(r"\|\s*xargs\b", command, re.IGNORECASE)) and (mentions(command)
                                                                          or bool(HOME_VAR.search(command)))
    assigned = _assignments(command)
    cur, lib_hit, promo = cwd, None, None
    # A variable whose value lands in the library or a promoted folder, followed by a command that is not read-only:
    # tools take their folders from variables too (`HOME=…`, `TMPDIR=…`, `XDG_CONFIG_HOME=…`) — review round 10
    writer_follows = any(seg and base(seg[0]) not in READ_ONLY | CD for seg in segments)
    if segments:
        for name, val in assigned.items():
            if (FILE_VARS.match(name) or writer_follows) and val:
                if _kind(val, cfg, cwd) == "library":
                    lib_hit = lib_hit or name
                elif promotes(cfg.rel(_as_path(val, cwd))):
                    promo = promo or cfg.rel(_as_path(val, cwd))
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
        toks = [t for t in _tokens(seg, assigned) if not t.startswith("-")]
        lead = [seg[0].strip("\"'")] if re.search(r"[\\/~]", seg[0]) else []   # `env -C DIR cmd` → [DIR, cmd…]
        if head in DEST_AWARE:
            hit = in_lib or piped
        elif head in INTERPRETERS:
            code = [seg[i + 1] for i, a in enumerate(low[:-1], 1) if a in CODE_FLAGS]
            hit = in_lib or heredoc or any(code_mentions(c) for c in code) or any(
                _kind(t, cfg, cur) == "library" for t in toks)
            if promo is None:
                cur_rel = (cfg.rel(cur) or "").lower().rstrip("/")
                in_local = cur_rel in {".outrigger", ".outrigger/local"} or promotes(cur_rel or None)
                for c in code:
                    if not WRITE_WORDS.search(c):
                        continue
                    norm = re.sub(r"[\\/]\.(?=[\\/])", "", c)          # `.outrigger/./local` is `.outrigger/local`
                    promo = next(iter(PROMOTE_IN_CODE.findall(norm)), None) or (
                        f"{cur_rel}/…" if in_local and re.search(r"workflows|['\"][^'\"]+\.md['\"]", norm) else None)
                    if promo:
                        break
        elif head == "git":
            gcwd, msg_vals, messages, config_vals = cur, set(), set(), []
            for i in range(1, len(seg) - 1):         # `git -C dir …` resolves paths from dir; messages are text
                if seg[i] == "-C":
                    gcwd = _as_path(seg[i + 1], gcwd)
                    msg_vals.add(i + 1)              # judged as the folder git runs in (g_lib), not as a target
                if seg[i].lower() in {"-m", "--message"}:
                    msg_vals.add(i + 1)
                    messages.add(i + 1)
                if seg[i] in {"-c", "--config-env"}:   # `-c core.pager="cp … <library>"` runs a command
                    config_vals.append(seg[i + 1])
            config_vals += [t for t in seg[1:] if t.startswith("--config-env=")]
            sub = _git_sub(seg)
            msg_vals.add(next((j for j, t in enumerate(seg[1:], 1) if t.lower() == sub and j not in msg_vals), -1))
            # every argument, split at `=` (`--output=<path>`), except commit messages
            paths = [part.strip("\"'") for j, t in enumerate(seg[1:], 1) if j not in msg_vals
                     for part in t.split("=") if part.strip("\"'") and not part.startswith("-")]
            g_lib = cfg.rel(gcwd) is None and cfg.outside_kind(gcwd) == "library"
            hit = (sub not in GIT_READS and (in_lib or g_lib)) or any(_kind(t, cfg, gcwd) == "library" for t in paths) \
                or any(mentions(v) for v in config_vals) \
                or any(_runs_text(t) and mentions(t) for j, t in enumerate(seg[1:], 1) if j not in messages)
            if promo is None and (sub in GIT_WRITES or any(a.startswith(("--output", "--file")) or a == "-o"
                                                           for a in low)):
                promo = promoted_in(paths, gcwd) or _patch_promotes(sub, paths, gcwd, cfg)
        else:   # tar, unzip, mkdir, curl -o, ln, mklink, New-Item, [IO.File]::…, cmd /c "…"
            words = [w.strip("\"'") for tok in seg for w in re.split(r"\s+", tok) if w]   # `cmd /c "mklink /J a b"`
            out_files = _archive_output(head, seg) if head in ARCHIVERS and _archive_creates(head, low) else None
            if out_files:   # packing only READS its inputs; output not found → the general rule below
                # …but an option can run a command (`--checkpoint-action=exec=…`, `-I "tee …"`, zip `-TT "…"`)
                hit = any(_kind(t, cfg, cur) == "library" for t in out_files) or in_lib or any(
                    (t.startswith("-") or _runs_text(t)) and mentions(t) for t in seg[1:])
            else:
                hit = in_lib or piped or mentions(" ".join(seg)) or any(
                    _kind(t, cfg, cur) == "library" for t in toks + lead)
            if promo is None and (head in UNPACKERS | LINKERS or any(base(w) in LINKERS for w in words)):
                promo = promoted_in(words[1:], cur)
        if hit and lib_hit is None:
            lib_hit = head
    if lib_hit:
        out.append(Finding("medium", "library-write", f"`{lib_hit}` names your personal workflow library, read by "
                                                      "every project — only with your approval"))
    if promo:
        out.append(promote_finding(promo, "writes"))
    return out


TAR_EXEC = ("--checkpoint-a", "--to-c", "--use-c", "--rsh", "--info-s", "--new-v")   # GNU tar takes abbreviations
GIT_EXEC_KEY = re.compile(r"^(core\.(pager|sshcommand|editor|fsmonitor|askpass)|sequence\.editor|diff\.external|"
                          r"credential\.helper|gpg\.(\w+\.)?program|alias\..+|.+\.(command|cmd|textconv|driver|"
                          r"process|clean|smudge|tool|path))$", re.IGNORECASE)


def hidden_commands(command: str, segments: list[list[str]]) -> list[str]:
    """Command lines a tool will run that the splitter cannot see as segments (0.7.0 review rounds 6–7):
    the whole command again with `X=value` assignments filled in; `tar --checkpoint-action=exec=…`, `--to-command`,
    `-I`/`--use-compress-program`, `-F`; `zip -TT …`; `git -c core.pager=… / alias.x=!… / --config-env`."""
    assigned = _assignments(command)
    whole = []
    if assigned:
        expanded = command
        for _ in range(8):                           # a chain `A=…; B=$A; C=$B` resolves step by step, bounded
            nxt = VAR.sub(lambda m: assigned.get(m.group(1), m.group(0)), expanded)
            if nxt == expanded or len(nxt) > 4 * len(command) + 4096:
                break
            expanded = nxt
        if expanded != command:
            whole.append(expanded)
    out = []
    # variables that git, less and editors RUN: `GIT_PAGER="cp … <library>" git log`, `EDITOR=… git commit`
    for name, val in assigned.items():
        if RUN_VARS.match(name):
            # `GIT_SSH_COMMAND="ssh -i ~/.ssh/key"` is how git is told which key to use: plain ssh is not a hidden
            # command (the network rule judges the git command itself); anything more is judged
            if name.startswith("GIT_SSH") and re.fullmatch(r"(ssh|plink)(\.exe)?(\s+-[\w-]+(\s+[^\s;&|`$()<>]+)?)*\s*",
                                                           val.strip(), re.IGNORECASE) and not mentions_library(val):
                continue
            out.append(val)
    keys = {m.group(1): v for m, v in ((re.match(r"GIT_CONFIG_KEY_(\d+)$", n), v) for n, v in assigned.items()) if m}
    for n, v in assigned.items():
        m = re.match(r"GIT_CONFIG_VALUE_(\d+)$", n)
        if m and GIT_EXEC_KEY.match(keys.get(m.group(1), "alias.x")):
            out.append(v.lstrip("!"))
    params = _raw_value(command, "GIT_CONFIG_PARAMETERS")   # quotes matter here: `'k'='v'` or `'k=v'`
    for key, val in re.findall(r"'([^'=]+)'='([^']*)'", params) + re.findall(r"'([^'=]+)=([^']*)'", params):
        if GIT_EXEC_KEY.match(key):
            out.append(val.lstrip("!"))
    for seg in segments:
        if not seg:
            continue
        head, args = base(seg[0]), seg[1:]
        for i, a in enumerate(args):
            nxt = args[i + 1] if i + 1 < len(args) else ""
            low = a.lower()
            if head in {"tar", "bsdtar"}:
                if low.startswith(TAR_EXEC):
                    val = a.split("=", 1)[1] if "=" in a else nxt
                    out.append(val[5:] if val.lower().startswith("exec=") else val)
                elif a in {"-I", "-F"} and nxt:
                    out.append(nxt)
            elif head == "zip" and (a == "-TT" or low.startswith("--unzip-command")):
                out.append(a.split("=", 1)[1] if "=" in a else nxt)
            elif head == "git":
                pair = nxt if a == "-c" else a[2:] if a.startswith("-c") and len(a) > 2 and "=" in a else ""
                if low.startswith("--config-env"):
                    env = (a.split("=", 1)[1] if "=" in a else nxt).split("=", 1)
                    pair = f"{env[0]}={assigned.get(env[-1], '')}" if len(env) == 2 else ""
                key, _, val = pair.partition("=")
                if val and GIT_EXEC_KEY.match(key.strip()):
                    out.append(val.lstrip("!"))
    return whole + [c.strip().strip("\"'") for c in out if c and c.strip().strip("\"'")]


def _runs_text(token: str) -> bool:
    """A token that holds a command line rather than one path (`"cp a.md ~/x"`, `!cp …`)."""
    return bool(re.search(r"\s", token.strip())) or token.lstrip("\"'").startswith("!")


def _git_sub(seg: list[str]) -> str:
    i = 1
    while i < len(seg):
        a = seg[i]
        if a in {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}:
            i += 2
        elif a.startswith("-"):
            i += 1
        else:
            return a.lower()
    return ""


def _patch_promotes(sub: str, paths: list[str], gcwd: Path, cfg: Config) -> str | None:
    """`git apply p.patch` / `git am`: read the patch and judge the files it writes."""
    if sub not in {"apply", "am"}:
        return None
    for p in paths:
        f = _as_path(p, gcwd)
        try:
            if not f.is_file() or f.stat().st_size > 2_000_000:
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for target in PATCH_TARGET.findall(text):
            rel = cfg.rel(_as_path(target, gcwd))
            if promotes(rel):
                return rel
    return None


def _archive_creates(head: str, low: list[str]) -> bool:
    """`tar -czf out.tgz …` / `zip -r out.zip …` / `7z a out.7z …` only READ what they pack."""
    # these delete what they pack: tar `--remove-files` (any abbreviation `--remove…`), zip `-m` (also bundled: `-rm`)
    if any(a.startswith("--rem") or a in {"--move", "-sdel"} for a in low) or (
            head == "zip" and any(re.fullmatch(r"-[a-z0-9]*m[a-z0-9]*", a) for a in low)):
        return False
    if head == "zip":
        return True
    if head in {"7z", "7za"}:
        return bool(low) and low[0] == "a"
    first = next((a for a in low if not a.startswith("--")), "").lstrip("-")
    return ("c" in first and "x" not in first) or "--create" in low


def _archive_output(head: str, seg: list[str]) -> list[str]:
    """Every file or folder the archiver WRITES; [] when it cannot be told (the caller then judges everything)."""
    args = seg[1:]
    low = [a.lower() for a in args]
    out: list[str] = []
    if head == "zip":
        for i, a in enumerate(args):                 # `--out NEW.zip`, `--out=NEW.zip`, `-O NEW.zip`
            if low[i].startswith("--out="):
                out.append(a[6:])
            elif a in {"--out", "-O"} and i + 1 < len(args):
                out.append(args[i + 1])
        pos = [a for a in args if not a.startswith("-")]
        return out + pos[:1]
    if head in {"7z", "7za"}:
        out += [a[2:] for a in args if a.lower().startswith("-o") and len(a) > 2]   # `-o<dir>`
        pos = [a for a in args[1:] if not a.startswith("-")]
        return out + pos[:1]
    for i, a in enumerate(args):                     # tar: -f FILE, -czf FILE, --file=FILE, old style `cf FILE`
        if a.startswith("--file="):                  # every -f counts: a later one is the next volume
            out.append(a[7:])
        elif a == "--file" and i + 1 < len(args):
            out.append(args[i + 1])
        # the value follows only when `f` ends the bundle (`-czf X`, `cvf X`); `-cfv` would name the file `v`
        elif (a.startswith("-") and not a.startswith("--") and a.endswith("f") or
              i == 0 and re.fullmatch(r"[A-Za-z]+", a) and a.endswith("f")) and i + 1 < len(args):
            out.append(args[i + 1])
        elif a.startswith("-") and not a.startswith("--") and "f" in a[1:]:
            return []                                # unusual bundle: judge everything
    return out
