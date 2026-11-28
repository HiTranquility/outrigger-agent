"""git rules: global options before the subcommand, `git add … && git commit`, history-changing commands."""
from __future__ import annotations

import re
from pathlib import Path

from .common import CD, Finding, _as_path, cd_target
from .config import Config
from .scripts import _worktree_secrets
from .shell import base
from .structure import staged_findings as _structure_findings

# GIT_DIR=… in front of the command (the splitter drops it) or --git-dir without --work-tree, on a commit
# Linear checks only: a look-ahead `(?=.*…)` with .search re-scans from every position, and a padded command that
# outlasts the hook timeout RUNS (review round 8, P0).
_GIT_ENV = re.compile(r"\bGIT_(?:DIR|WORK_TREE|INDEX_FILE)=", re.IGNORECASE)


def git_env_commit(command: str) -> bool:
    low = command.lower()
    if not re.search(r"\bcommit\b", low):
        return False
    return bool(_GIT_ENV.search(command)) or ("--git-dir" in low and "--work-tree" not in low)

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
    added: bool | list[str] = []          # 0.7.0: which untracked files `git add` brings in (True = any of them)
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
            if sub[:1] in (["add"], ["stage"]) and added is not True:
                specs = [a for a in seg[len(seg) - len(sub) + 1:] if not a.startswith("-")]
                flags = {a.lower() for a in sub[1:] if a.startswith("-")}
                # anything the shell or git may widen counts every new file: globs, braces, variables, magic
                # pathspecs and folders; named files are measured from disk (`-f` adds ignored ones too)
                if not specs or flags & {"-a", "--all", "--pathspec-from-file"} or any(
                        any(c in a for c in "*?[:{$`") or a in {".", "./"} or _as_path(a, gcwd).is_dir() for a in specs):
                    added = True
                else:
                    added += [_as_path(a, gcwd).resolve(strict=False).as_posix() for a in specs]
            elif sub[:1] in (["apply"], ["update-index"]):
                added = True
        elif sub[:1] == ["commit"] and staged_before:
            out.extend(_worktree_secrets(cfg, gcwd))
            out.extend(_structure_findings(sub, cfg, gcwd, force_disk=True, untracked=added if added else False))
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
