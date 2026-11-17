"""Pack scanners: find dangerous calls in code a pack's software is about to run."""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from . import state
from .config import Config, Pack

SKIP_DIRS = {".git", ".outrigger", "node_modules", ".venv", "venv", "__pycache__", "archive"}


def compile_patterns(pack: Pack) -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in pack.dangerous]


def strip_comments(text: str, ext: str) -> str:
    if ext == ".m":
        # %{ block %} and % line comments; keeps strings mostly intact (heuristic)
        text = re.sub(r"(?ms)^\s*%\{.*?^\s*%\}", "", text)
        text = re.sub(r"(?m)(^|[^'\"])%.*$", r"\1", text)
    elif ext == ".py":
        text = re.sub(r"(?m)#.*$", "", text)
    return text


def scan_text(text: str, pack: Pack, ext: str) -> list[tuple[int, str]]:
    hits = []
    clean = strip_comments(text, ext)
    for pat in compile_patterns(pack):
        for m in pat.finditer(clean):
            line = clean.count("\n", 0, m.start()) + 1
            hits.append((line, m.group(0).strip()[:60]))
    return sorted(set(hits))


def danger_lines(text: str, pack: Pack, ext: str) -> list[tuple[int, str]]:
    """(line number, whole line with whitespace collapsed) for every line holding a dangerous call — the snapshot
    `cli.py trust` stores, so a later edit can be judged by what it ADDS (ADR-0010 B)."""
    lines = strip_comments(text, ext).splitlines()
    seen = sorted({n for n, _ in scan_text(text, pack, ext)})
    return [(n, " ".join(lines[n - 1].split())) for n in seen if 0 < n <= len(lines)]


def new_danger_lines(text: str, pack: Pack, ext: str, snapshot: list[str]) -> list[tuple[int, str]]:
    """Dangerous lines of `text` that the trusted snapshot did not contain (counted, so a copied call is new)."""
    budget = Counter(snapshot)
    out = []
    for n, line in danger_lines(text, pack, ext):
        if budget[line] > 0:
            budget[line] -= 1
        else:
            out.append((n, line[:80]))
    return out


def scan_project(cfg: Config, pack: Pack) -> list[str]:
    """Return `relpath:line: match` strings for every dangerous call in the project's pack files."""
    found: list[str] = []
    budget = cfg.limit("scan_max_files")
    for path in _walk(cfg.root, pack.scan_extensions):
        if state.is_trusted(cfg, path.relative_to(cfg.root).as_posix()):
            continue
        budget -= 1
        if budget < 0:
            found.append(f"(scan stopped after {cfg.limit('scan_max_files')} files — raise limits.scan_max_files)")
            break
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line, snippet in scan_text(text, pack, path.suffix.lower()):
            found.append(f"{path.relative_to(cfg.root).as_posix()}:{line}: {snippet}")
    return found


def _walk(root: Path, exts: list[str]):
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            entries = list(d.iterdir())
        except OSError:
            continue
        for e in entries:
            if e.is_dir():
                if e.name.lower() not in SKIP_DIRS:
                    stack.append(e)
            elif e.suffix.lower() in exts:
                yield e
