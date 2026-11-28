"""Record numbering (ADR-0015): next free number per record type, counted across month folders AND git branches.

A number is taken when a file or folder named `<KIND>-<NNN>-<slug>` exists anywhere under the record roots, or a
branch (local or remote) carries `<KIND>-<NNN>`. Counting branches matters: a record created on a branch that is not
merged yet is invisible in the working tree, and two sessions would otherwise take the same number.
"""
from __future__ import annotations

import os
import re
import subprocess

from .config import Config

WIDTH = {"ADR": 4, "REQ": 3, "ISSUE": 3, "BUG": 3, "SPIKE": 3, "PM": 3}
ROOTS = ("docs", "reports", "sandbox/spikes")
SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", "quarantine"}


def _numbers_in_tree(cfg: Config, kind: str) -> dict[int, set[str]]:
    pat = re.compile(rf"^{kind}-(\d{{1,{WIDTH[kind]}}})(?!\d)(?:-(.+?))?(?:\.md)?$", re.IGNORECASE)
    found: dict[int, set[str]] = {}
    for root in ROOTS:
        base = cfg.root / root
        if not base.is_dir():
            continue
        for top, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in dirs + files:
                m = pat.match(name)
                if m:
                    found.setdefault(int(m.group(1)), set()).add(m.group(2) or "")
    return found


def _numbers_in_branches(cfg: Config, kind: str) -> tuple[dict[int, set[str]], str]:
    """Numbers carried by branch names; the second value is a warning when branches could not be read."""
    try:
        inside = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=cfg.root, capture_output=True,
                                text=True, timeout=20)
        if inside.returncode != 0:
            return {}, ""                    # not a git project: nothing to count

        r = subprocess.run(["git", "branch", "-a", "--format=%(refname:short)"], cwd=cfg.root, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=20)
    except (OSError, subprocess.SubprocessError) as exc:
        return {}, f"could not read branches ({type(exc).__name__}); numbers on unmerged branches were not counted"
    if r.returncode != 0:
        return {}, "could not read branches; numbers on unmerged branches were not counted"
    # the number has the type's width at most and is not the year of a `YYYY-MM` date (`ISSUE-2026-11-x`)
    pat = re.compile(rf"(?<![A-Za-z]){kind}-(\d{{1,{WIDTH[kind]}}})(?!\d)(?!-\d{{2}}(?:-|$))", re.IGNORECASE)
    found: dict[int, set[str]] = {}
    for line in r.stdout.splitlines():
        for m in pat.finditer(line.strip()):
            found.setdefault(int(m.group(1)), set()).add("branch:" + line.strip())
    return found, ""


def next_id(cfg: Config, kind: str) -> tuple[str, list[str]]:
    """Return (next id, warnings about numbers used twice with different slugs)."""
    kind = kind.upper()
    if kind not in WIDTH:
        raise ValueError(f"unknown record type {kind}; one of {', '.join(sorted(WIDTH))}")
    tree = _numbers_in_tree(cfg, kind)
    branches, branch_warning = _numbers_in_branches(cfg, kind)
    taken = set(tree) | set(branches)
    warnings = [f"{kind}-{n:0{WIDTH[kind]}d} used twice in the tree: {', '.join(sorted(s))}"
                for n, s in sorted(tree.items()) if len({x for x in s if x}) > 1]
    if branch_warning:
        warnings.append(branch_warning)
    return f"{kind}-{(max(taken) + 1 if taken else 1):0{WIDTH[kind]}d}", warnings
