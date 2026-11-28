"""Rules a pack declares (ADR-0013, ADR-0014): commands that must always ask, pack runners and targets."""
from __future__ import annotations

from pathlib import Path

from . import packs, state
from .config import Config
from .shell import base
from .common import Finding

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
