"""Risk rules for shell commands. Each rule returns Findings; the decision takes the worst one."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from .config import Config
from .shell import WRAPPERS, base, strip_heredocs
from .common import cd_target, CD, COPY_LIKE, DELETE, Finding, INSTALLERS, MOVE_LIKE, NET, NET_OUT, OUTRIGGER_CLI, READ_ONLY, SCHEDULE, SYSTEM_HIGH, _as_path
from .packrules import _pack_asks, _pack_run
from . import libguard
from .quarantine import check_quarantine
from .scripts import _npm_script, _script_files, _staged_secrets, _worktree_secrets
from .structure import staged_findings as _structure_findings
from .common import worst  # noqa: F401 — re-exported for decide.py
from .quarantine import quarantine_touch, is_recon  # noqa: F401 — re-exported for decide.py

DEVICES = {"/dev/null", "/dev/stdout", "/dev/stderr", "nul", "nul:", "con", "$null"}
WRITE_ALL = {"tee", "touch", "truncate", "set-content", "add-content", "out-file", "new-item", "ni", "clear-content"}
HELP_FLAGS = {"-h", "--help", "/?"}
APPS = {"start", "start-process", "saps", "explorer", "invoke-item", "ii", "code", "notepad", "open",
        "xdg-open", "simulink", "msedge", "chrome", "firefox"}
UPLOAD_FLAGS = {"-d", "--data", "--data-raw", "--data-binary", "--data-urlencode", "-f", "--form", "-t",
                "--upload-file", "--post-data", "--post-file", "-body", "-infile"}
UPLOAD_METHODS = {"post", "put", "patch", "delete"}
OUTRIGGER_HUMAN_ONLY = re.compile(r"cli\.py[\"']?\s+(?:-\S+\s+)*(approve|resume|empty-trash|deny|trust|untrust|rule\s+accept|[\"']?structure[\"']?(?:\s+[^\s;&|]+)*?\s+[\"']?--se\w*)\b",
                                  re.IGNORECASE)
OUTRIGGER_SELF = re.compile(r"\.outrigger[\\/](engine|state|outrigger\.toml|local[\\/]notify\.toml|local[\\/]structure-baseline\.json)|\.claude[\\/]settings"
                       r"|\.mcp\.json|\.codex[\\/]|\.agents[\\/]hooks\.json|\.cursor[\\/]hooks\.json", re.IGNORECASE)
PIPE_TO_SHELL = re.compile(r"(curl|wget|iwr|irm|invoke-webrequest|invoke-restmethod)\b[^|\n]*\|\s*"
                           r"(sudo\s+)?(sh|bash|zsh|python3?|iex|invoke-expression|pwsh|powershell)\b", re.IGNORECASE)
PY_DELETE = re.compile(r"shutil\.rmtree|os\.(remove|unlink|rmdir)|Path\([^)]*\)\.unlink|\.rmdir\(", re.IGNORECASE)
ROOTLIKE = {"/", "\\", "~", "~/", "*", "/*", ".", "./", "..", "../", "c:", "c:\\", "c:/", "$home", "%userprofile%"}
REDIRECT_TARGET = re.compile(r"(?:^|[^<0-9&])\d?>>?\s*(\"[^\"]+\"|'[^']+'|[^\s;&|]+)")


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
        if head in CD:
            cur = cd_target(seg, cur)
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
    out.extend(libguard.check(command, segments, cfg, cwd))   # 0.7.0 (ADR-0016)
    hit = _self_hit(command, segments, cfg, cwd)
    if hit:
        out.append(Finding("high", "outrigger-self", f"command touches Outrigger or hook configuration ({hit})"))
    for t in _redirect_targets(command, segments):
        t = t.strip("\"'")
        if t.lower() in {"/dev/null", "nul", "&1", "&2"}:
            continue
        rel = cfg.rel(t, cwd)
        if rel is None:
            if cfg.outside_kind(t) == "library":
                out.append(Finding("medium", "library-write", f"redirects output into the personal library `{t}`"))
            elif cfg.outside_kind(t) == "agent-config":
                out.append(Finding("medium", "agent-config", f"redirects output into agent configuration `{t}`"))
            elif not cfg.outside_allowed(t):
                out.append(Finding("medium", "write-outside", f"redirects output outside the project: `{t}`"))
        elif cfg.zone_of(rel) in {"red", "protected", "originals"}:
            out.append(Finding("high", "write-protected", f"redirects output into `{rel}` ({cfg.zone_of(rel)} zone)"))
        elif libguard.promotes(rel):
            out.append(libguard.promote_finding(rel, "redirects output into"))
    if re.search(r"base64\s+(-d|--decode)[^|\n]*\|\s*(sh|bash)", command, re.IGNORECASE):
        out.append(Finding("high", "encoded-exec", "decoded payload piped into a shell"))
    out.extend(_add_then_commit(segments, cfg, cwd))
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
    for a in args:   # `--target-directory=DIR`, `-t=DIR`, `-Destination:DIR`
        for flag in ("--target-directory=", "-t=", "-destination:", "-destination="):
            if a.lower().startswith(flag):
                return [a[len(flag):]]
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
        elif libguard.promotes(rel):
            out.append(libguard.promote_finding(rel, f"`{head}` writes"))
        elif rel is None and t.strip("\"'").lower() in DEVICES:
            continue
        elif rel is None:   # 0.7.0: `cp`/`mv`/`tee` into a folder outside the project was not judged before
            kind = cfg.outside_kind(_as_path(t, cwd))
            if kind == "library":
                out.append(Finding("medium", "library-write", f"`{head}` writes into the personal library `{t}`"))
            elif kind == "agent-config":
                out.append(Finding("medium", "agent-config", f"`{head}` changes agent configuration `{t}`"))
            elif kind not in {"allow", "memory"}:
                out.append(Finding("medium", "write-outside", f"`{head}` writes outside the project: `{t}`"))
    return out
EXEC_HEADS = WRAPPERS | {"python", "python3", "py", "node", "deno", "bun", "ruby", "perl", "php", "iex",
                         "invoke-expression", "source", ".", "npx", "pnpx", "java", "dotnet", "go", "cargo", "make",
                         "cmake", "docker", "docker-compose", "podman", "matlab", "octave", "rscript", "uv", "uvx",
                         "pipx", "poetry", "xargs"}


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
        sub, gcwd = _git_split(args, cwd)   # `git -C dir -c k=v push --force` is still a force push
        out.extend(_git(sub))
        if sub[:1] == ["commit"]:
            out.extend(_staged_secrets(sub, cfg, gcwd))
            out.extend(_structure_findings(sub, cfg, gcwd))   # ADR-0015, opt-in via [structure] enabled

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


GIT_GLOBAL_VALUE = {"-c", "--git-dir", "--work-tree", "--namespace", "--config-env", "--super-prefix", "--exec-path"}


def _git_split(args: list[str], cwd: Path) -> tuple[list[str], Path]:
    """Skip git's global options (`-C <dir>`, `-c k=v`, `--git-dir …`, `--no-pager`, `-p` …); return the lower-cased
    subcommand with its arguments and the directory git will run in (`-C` may repeat and is relative)."""
    i, gcwd, git_dir, work_tree = 0, cwd, None, None
    while i < len(args):
        a = args[i]
        if a == "-C" and i + 1 < len(args):
            gcwd = _as_path(args[i + 1], gcwd)
            i += 2
            continue
        key, eq, val = a.partition("=")
        if key.lower() in GIT_GLOBAL_VALUE:
            if not eq:
                val = args[i + 1] if i + 1 < len(args) else ""
            if key.lower() == "--git-dir":
                git_dir = _as_path(val, gcwd)
            elif key.lower() == "--work-tree":
                work_tree = _as_path(val, gcwd)
            i += 1 if eq else 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        break
    if work_tree is not None:                # the files a commit carries live in the work tree
        gcwd = work_tree
    elif git_dir is not None:
        gcwd = git_dir.parent if git_dir.name.lower() == ".git" else git_dir
    return [x.lower() for x in args[i:]], gcwd


def _add_then_commit(segments: list[list[str]], cfg: Config, cwd: Path) -> list[Finding]:
    """`git add x && git commit` in one command: the guard runs before `git add`, so the index does not hold the new
    content yet. Judge what is on disk instead (secrets and, when on, file size)."""
    staged_before, cur = False, cwd
    out: list[Finding] = []
    for seg in segments:
        if seg and base(seg[0]) in CD:      # `cd nested && git add … && git commit`
            cur = cd_target(seg, cur)
            continue
        if not seg or base(seg[0]) != "git":
            continue
        sub, gcwd = _git_split(seg[1:], cur)
        if sub[:1] in (["add"], ["stage"], ["mv"], ["rm"], ["apply"], ["update-index"]):
            staged_before = True
        elif sub[:1] == ["commit"] and staged_before:
            out.extend(_worktree_secrets(cfg, gcwd))
            out.extend(_structure_findings(sub, cfg, gcwd, force_disk=True, untracked=True))
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
            if libguard.promotes(rel) or rel.lower().rstrip("/") == ".outrigger":   # 0.7.0 (ADR-0016)
                return [libguard.promote_finding(rel, f"`{sub}` removes")]
            full = cfg.root / rel
            for f in ([full] if full.is_file() else full.rglob("*") if full.is_dir() else []):
                if f.is_file():
                    files += 1
                    size += f.stat().st_size
        if files > cfg.limit("trash_max_files") or size > cfg.limit("trash_max_mb") * 1024 * 1024:
            return [Finding("medium", "bulk", f"bulk {sub}: {files} files, {size / 1048576:.1f} MB")]
    return []
NPM_RUNNERS = {"npm", "pnpm", "yarn", "bun"}
