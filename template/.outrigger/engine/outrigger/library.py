"""0.7.0 (ADR-0016): first run and the personal workflow library.

* **New project** = no `.outrigger/state/onboarded.json`. `state/` is git-ignored, so a fresh clone on another machine
  is a new project too. The session-start hook then says OUTRIGGER FIRST RUN and the agent asks the user ONE question
  before anything else; `cli.py onboard --done "<answer>"` records the answer so it is not asked again.
* **New machine** = no personal library folder (`<home>/library/`; home is `$OUTRIGGER_HOME`, default `~/.outrigger/`). The library holds the
  workflows the user chose to carry between projects: `<home>/library/workflows/*.md`. Moving to another machine is
  copying (or syncing) that folder.
* `import` copies workflows from the library, another project or a quarantined repository into this project's
  `drafts/` with `status: draft`: nothing imported is trusted until the user promotes it. Text aimed at an agent
  (hidden characters, directives) is not imported at all.
* `export` copies a workflow the user already promoted into the library. The library reaches every project, so the
  guard asks about `export` and about any other write into the library in light mode too.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

from . import recon, state
from .config import Config

MARKER = "onboarded.json"
MAX_FILES = 100
MAX_BYTES = 256 * 1024
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}\.md$")
FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)
LIBRARY_README = """# Outrigger personal library

Workflows you chose to carry between projects. Written by `cli.py export`; read by `cli.py import library`.
To use them on another machine, copy or sync this whole folder to `~/.outrigger/` there (or point `OUTRIGGER_HOME`
at it). Every import lands in the project's `drafts/` and waits for you to promote it.
"""


class LibraryError(Exception):
    pass


def home() -> Path:
    env = os.environ.get("OUTRIGGER_HOME", "").strip()
    return Path(os.path.expanduser(env or "~/.outrigger")).resolve(strict=False)


def library_dir() -> Path:
    return home() / "library" / "workflows"


def marker(cfg: Config) -> Path:
    return cfg.state_dir / MARKER


def local_dir(cfg: Config) -> Path:
    return cfg.root / ".outrigger" / "local" / "workflows"


def _workflows(folder: Path) -> list[Path]:
    """Top-level `*.md` in a workflows folder; README and anything that is not a plain file are skipped."""
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.suffix.lower() == ".md" and p.name.lower() != "readme.md"
                  and not p.is_symlink() and p.is_file())


def status(cfg: Config) -> dict:
    lib = library_dir()
    return {"new_project": not marker(cfg).is_file(), "new_machine": not lib.parent.is_dir(), "home": str(lib.parent),
            "library": [p.name for p in _workflows(lib)], "local": [p.name for p in _workflows(local_dir(cfg))],
            "drafts": [p.name for p in _workflows(local_dir(cfg) / "drafts")]}


def first_run_lines(cfg: Config) -> list[str]:
    """What the session-start hook prints while the project has not been onboarded."""
    if not status(cfg)["new_project"]:
        return []
    s = status(cfg)
    where = (f"the personal library {s['home']} holds {len(s['library'])} workflow(s)" if not s["new_machine"]
             else f"this machine has no personal library yet ({s['home']} does not exist)")
    return ["OUTRIGGER FIRST RUN: Outrigger has not been set up in this project yet — " + where + ". Before any other "
            "work, ask the user ONE question: import workflows (from the library, another project folder, or a "
            "repository read through `cli.py recon`), or start empty? Do what they choose with "
            "`python .outrigger/engine/cli.py import <library|path>` (lands in drafts/), then record the answer with "
            "`python .outrigger/engine/cli.py onboard --done \"<their answer>\"`. Never mark it done without asking."]


def mark_done(cfg: Config, answer: str) -> Path:
    m = marker(cfg)
    m.parent.mkdir(parents=True, exist_ok=True)
    m.write_text(json.dumps({"ts": state.now().isoformat(timespec="seconds"), "answer": answer[:300]},
                            ensure_ascii=False) + "\n", encoding="utf-8")
    return m


def _source_folder(cfg: Config, source: str) -> tuple[Path, str]:
    if source.lower() == "library":
        return library_dir(), "library"
    p = Path(os.path.expanduser(source))
    p = (p if p.is_absolute() else Path.cwd() / p).resolve(strict=False)
    if (p / ".outrigger" / "local" / "workflows").is_dir():
        p = p / ".outrigger" / "local" / "workflows"
    if not p.is_dir():
        raise LibraryError(f"{source}: not a folder (give `library`, a project folder or a workflows folder)")
    if p == local_dir(cfg).resolve() or p == (local_dir(cfg) / "drafts").resolve():
        raise LibraryError("that is this project's own workflows folder")
    label = p.parent.parent.parent.name if p.name == "workflows" and p.parent.name == "local" else p.name
    return p, re.sub(r"[^A-Za-z0-9._-]+", "_", label)[:60] or "folder"   # a recon'd repo chooses its folder name


def _as_draft(text: str, label: str) -> str:
    m = FRONT.match(text)
    if not m:
        return f"---\nstatus: draft\nimported_from: {label}\n---\n\n{text}"
    body = [l for l in m.group(1).split("\n") if not re.match(r"^(status|approved_by|imported_from)\s*:", l)]
    head = "\n".join(body + ["status: draft", "approved_by:", f"imported_from: {label}"])
    return f"---\n{head}\n---\n{text[m.end():]}"


def _free(folder: Path, name: str) -> Path:
    dest, n = folder / name, 2
    while dest.exists():
        dest, n = folder / f"{Path(name).stem}.imported-{n}.md", n + 1
    return dest


def _read(p: Path) -> str:
    if p.stat().st_size > MAX_BYTES:
        raise LibraryError(f"{p.name}: larger than {MAX_BYTES // 1024} KB")
    return p.read_bytes().decode("utf-8", errors="replace").replace("\r\n", "\n")


def _is_link(d: Path) -> bool:
    isjunction = getattr(os.path, "isjunction", None)   # Python 3.12+; on 3.11 resolve() still follows a junction
    return d.is_symlink() or bool(isjunction and isjunction(d)) or (d.exists() and d.resolve() != d)


def _real_drafts(cfg: Config) -> Path:
    """drafts/ itself, never through a link or junction that leads out of the project (into the library, say)."""
    root = cfg.root.resolve()
    want = root / ".outrigger" / "local" / "workflows" / "drafts"
    for d in (want.parent.parent, want.parent, want):
        if _is_link(d):
            raise LibraryError(f"{d.relative_to(root).as_posix()} is a link or junction — refusing to write through it")
    want.mkdir(parents=True, exist_ok=True)
    return want


def import_from(cfg: Config, source: str, only: list[str] | None = None) -> tuple[list[str], list[str]]:
    """Copy workflows into drafts/. Returns (imported file names, skipped with reason)."""
    folder, label = _source_folder(cfg, source)
    files = _workflows(folder)
    if only:
        files = [p for p in files if p.name in only or p.stem in only]
    if len(files) > MAX_FILES:
        raise LibraryError(f"{len(files)} workflows in {folder}: more than {MAX_FILES}, pick some with --only")
    drafts = _real_drafts(cfg)
    done, skipped = [], []
    for p in files:
        if not SAFE_NAME.match(p.name):
            skipped.append(f"{p.name}: unusual file name")
            continue
        try:
            text = _read(p)
        except (LibraryError, OSError) as exc:
            skipped.append(str(exc))
            continue
        warn = [h for h in recon.scan_text(text, full=True) if h.level == recon.WARN]
        if warn:
            skipped.append(f"{p.name}: text aimed at an agent at line {warn[0].line} ({warn[0].kind}) — read it yourself")
            continue
        dest = _free(drafts, p.name)
        if dest.resolve().parent != drafts:
            raise LibraryError(f"{dest.name}: would land outside drafts/")
        dest.write_text(_as_draft(text, label), encoding="utf-8", newline="\n")
        done.append(dest.name)
    return done, skipped


def _is_draft(text: str) -> bool:
    m = FRONT.match(text)
    return bool(m and re.search(r"^status\s*:\s*draft\s*$", m.group(1), re.M))


def export(cfg: Config, names: list[str], replace: bool = False) -> list[str]:
    """Copy promoted workflows (`.outrigger/local/workflows/*.md`, not drafts) into the library."""
    local = {p.name: p for p in _workflows(local_dir(cfg))}
    local.update({p.stem: p for p in list(local.values())})
    picked = []
    for n in names:
        p = local.get(n)
        if p is None:
            raise LibraryError(f"{n}: not a promoted workflow in .outrigger/local/workflows/ (drafts are never exported)")
        text = _read(p)
        if _is_draft(text):
            raise LibraryError(f"{p.name}: still `status: draft` — the user promotes it first")
        warn = [h for h in recon.scan_text(text, full=True) if h.level == recon.WARN]
        if warn:
            raise LibraryError(f"{p.name}: text aimed at an agent at line {warn[0].line} ({warn[0].kind}) — not exported")
        picked.append((p, text))
    lib = library_dir()
    lib.mkdir(parents=True, exist_ok=True)
    readme = lib.parent / "README.md"
    if not readme.exists():
        readme.write_text(LIBRARY_README, encoding="utf-8", newline="\n")
    out = []
    for p, text in picked:
        dest = lib / p.name
        if dest.exists() and _read(dest) != text:
            if not replace:
                raise LibraryError(f"{p.name}: the library already has a different version — add --replace "
                                   "(the old one goes to library/.history/)")
            hist = lib.parent / ".history" / f"{state.now():%Y%m%d-%H%M%S}"
            hist.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest, hist / p.name)
        dest.write_text(text, encoding="utf-8", newline="\n")
        out.append(p.name)
    return out


# ---------------------------------------------------------------- CLI (kept here so cli.py does not grow)

def cmd_onboard(a) -> int:
    cfg = a.cfg()
    if a.done is not None:
        if not a.done.strip():
            print("ERROR give the user's answer: onboard --done \"imported 3 from library\"")
            return 2
        print(f"OK onboarded: {cfg.rel(mark_done(cfg, a.done.strip()))}")
        return 0
    s = status(cfg)
    print(f"project: {'NEW (not onboarded)' if s['new_project'] else 'onboarded'} · machine: "
          f"{'NEW (no library)' if s['new_machine'] else 'library at ' + s['home']}")
    print(f"library workflows: {len(s['library'])}  " + ", ".join(s["library"][:10]))
    print(f"this project: {len(s['local'])} promoted, {len(s['drafts'])} draft(s)")
    return 0


def cmd_import(a) -> int:
    try:
        done, skipped = import_from(a.cfg(), a.source, a.only)
    except LibraryError as exc:
        print(f"ERROR {exc}")
        return 1
    for n in done:
        print(f"imported drafts/{n}")
    for s in skipped:
        print(f"SKIP {s}")
    print(f"OK {len(done)} imported as drafts, {len(skipped)} skipped. The user reviews and promotes them.")
    return 0 if not skipped else 1


def cmd_export(a) -> int:
    try:
        out = export(a.cfg(), a.names, a.replace)
    except LibraryError as exc:
        print(f"ERROR {exc}")
        return 1
    print(f"OK exported to {library_dir()}: " + ", ".join(out))
    return 0


def register(sub, cfg_loader) -> None:
    p = sub.add_parser("onboard", help="first-run status; --done records the user's answer")
    p.add_argument("--done", metavar="ANSWER")
    p.set_defaults(fn=cmd_onboard, cfg=cfg_loader)
    p = sub.add_parser("import", help="copy workflows into drafts/ from `library`, a project or a folder")
    p.add_argument("source")
    p.add_argument("--only", nargs="+")
    p.set_defaults(fn=cmd_import, cfg=cfg_loader)
    p = sub.add_parser("export", allow_abbrev=False, help="copy promoted workflows into the personal library (asks)")
    p.add_argument("names", nargs="+")
    p.add_argument("--replace", action="store_true")
    p.set_defaults(fn=cmd_export, cfg=cfg_loader)
