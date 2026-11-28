"""Quarantine zone (ADR-0012): what may touch `sandbox/quarantine/**` and what `recon` is."""
from __future__ import annotations

from pathlib import Path

from .config import Config
from .shell import base
from .common import CD, COPY_LIKE, DELETE, Finding, MOVE_LIKE, OUTRIGGER_CLI, READ_ONLY

# 0.4.0 (ADR-0012): code in the quarantine zone is someone else's, copied in to be READ. Reading, listing, comparing
# and `git log` are fine; anything that would run, build, install or serve it is high risk, whatever the wording.
QUARANTINE_READ = READ_ONLY | CD | {"find", "tree", "sort", "uniq", "cut", "jq", "xxd", "od", "hexdump", "strings",
                                    "du", "pwd", "realpath", "basename", "dirname", "nl", "tac", "column"}
QUARANTINE_GIT_READ = {"log", "show", "diff", "status", "rev-parse", "ls-files", "ls-tree", "blame", "grep",
                       "cat-file", "describe", "shortlog"}


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
