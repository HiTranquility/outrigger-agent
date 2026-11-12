#!/usr/bin/env python3
"""Install or update Outrigger in a project.

    python install.py --target <project folder> [--pack <pack folder>]... [--update] [--yes] [--dry]

Never installs Python packages, never touches the network. Asks before writing anything.
Never overwrites: .outrigger/local/ (your own workflows and settings), an existing .outrigger/outrigger.toml,
an existing AGENTS.md / CLAUDE.md / GEMINI.md (it keeps them and appends a short pointer block to .outrigger/OUTRIGGER.md).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "template"
HOOKS = HERE / "adapters" / "claude" / "settings.hooks.json"
MARK_START, MARK_END = "<!-- outrigger:start -->", "<!-- outrigger:end -->"
BLOCK = f"""{MARK_START}
## 🛶 Outrigger guard

This project is also protected by **Outrigger**. Read `.outrigger/OUTRIGGER.md` and follow it. Where Outrigger is stricter than the
rules above, Outrigger wins; where the rules above are stricter, they win. The Outrigger guard hook enforces its part
whatever this file says.

@.outrigger/OUTRIGGER.md
{MARK_END}
"""
GITIGNORE_LINES = [".outrigger/state/", ".outrigger/local/notify.toml", "STOP"]
NOTIFY_DEFAULT = """# Outrigger notifications (this file is git-ignored; it may hold your ntfy topic).
# channel = "toast"  -> Windows desktop notification (default, nothing leaves this computer)
# channel = "ntfy"   -> phone push via ntfy (install the ntfy app, subscribe to the same topic)
# channel = "none"
channel = "toast"

[ntfy]
server = "https://ntfy.sh"   # or your own ntfy server
topic = ""                   # long random string, e.g. outrigger-7f3k9q2m8x — treat it like a password
"""


def main() -> int:
    if sys.version_info < (3, 11):
        print(f"Outrigger needs Python 3.11 or newer; this is {sys.version.split()[0]}.")
        print("Install it yourself from https://www.python.org/downloads/ — Outrigger will not install anything for you.")
        return 1
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--pack", action="append", default=[])
    ap.add_argument("--builder", help="Outrigger Pro builder folder (copied to .outrigger/builder/)")
    ap.add_argument("--update", action="store_true", help="refresh engine/rules/templates/packs of an existing install")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    target = Path(a.target).resolve()
    if not target.is_dir():
        print(f"target folder does not exist: {target}")
        return 1
    outrigger = target / ".outrigger"
    plan: list[tuple[str, callable]] = []
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = outrigger / "state" / "backups" / f"install-{stamp}"

    def backup(path: Path):
        if path.exists():
            dest = backup_root / path.relative_to(target)
            dest.parent.mkdir(parents=True, exist_ok=True)
            (shutil.copytree if path.is_dir() else shutil.copy2)(path, dest)

    def copy_dir(src: Path, dst: Path):
        def run():
            backup(dst)
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
        return run

    for name in ("engine", "rules", "templates"):
        plan.append((f"{'refresh' if (outrigger / name).exists() else 'create'} .outrigger/{name}/",
                     copy_dir(TEMPLATE / ".outrigger" / name, outrigger / name)))
    if not (outrigger / "outrigger.toml").exists():
        plan.append(("create .outrigger/outrigger.toml", lambda: shutil.copy2(TEMPLATE / ".outrigger/outrigger.toml", outrigger / "outrigger.toml")))
    else:
        plan.append(("keep your .outrigger/outrigger.toml; write the new default as .outrigger/outrigger.toml.new",
                     lambda: shutil.copy2(TEMPLATE / ".outrigger/outrigger.toml", outrigger / "outrigger.toml.new")))
    plan.append(("create .outrigger/local/ (yours — never overwritten)",
                 lambda: (outrigger / "local" / "workflows" / "drafts").mkdir(parents=True, exist_ok=True)))
    if not (outrigger / "local" / "notify.toml").exists():
        plan.append(("create .outrigger/local/notify.toml (toast by default)",
                     lambda: (outrigger / "local" / "notify.toml").write_text(NOTIFY_DEFAULT, encoding="utf-8")))
    for core_pack in sorted((TEMPLATE / ".outrigger" / "packs").glob("*/pack.toml")):
        src = core_pack.parent
        plan.append((f"{'refresh' if (outrigger / 'packs' / src.name).exists() else 'install'} core pack {src.name}",
                     copy_dir(src, outrigger / "packs" / src.name)))
    for p in a.pack:
        src = Path(p).resolve()
        if not (src / "pack.toml").is_file():
            print(f"not a pack (no pack.toml): {src}")
            return 1
        plan.append((f"install pack {src.name} -> .outrigger/packs/{src.name}/", copy_dir(src, outrigger / "packs" / src.name)))
    if a.builder:
        src = Path(a.builder).resolve()
        if not (src / "INTERVIEW.md").is_file():
            print(f"not a builder folder (no INTERVIEW.md): {src}")
            return 1
        plan.append(("install builder -> .outrigger/builder/", copy_dir(src, outrigger / "builder")))

    plan.append(("write Outrigger rules to .outrigger/OUTRIGGER.md", lambda: shutil.copy2(TEMPLATE / "AGENTS.md", outrigger / "OUTRIGGER.md")))
    for fname in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
        dst = target / fname
        if not dst.exists():
            plan.append((f"create {fname}", lambda f=fname: shutil.copy2(TEMPLATE / f, target / f)))
            continue
        text = dst.read_text(encoding="utf-8", errors="replace")
        if text == (TEMPLATE / fname).read_text(encoding="utf-8") or MARK_START in text:
            continue                                   # ours already, or the pointer block is already there
        if fname == "CLAUDE.md" and "@AGENTS.md" in text:
            continue                                   # it imports AGENTS.md, which carries the block
        plan.append((f"keep your {fname}; append an Outrigger pointer block (backup first)",
                     lambda d=dst: append_block(d, backup)))
    for d in ("sandbox", "reports", "docs/decisions"):
        plan.append((f"ensure {d}/", lambda d=d: (target / d).mkdir(parents=True, exist_ok=True)))
    plan.append(("merge Outrigger hooks into .claude/settings.json (backup first)", lambda: merge_hooks(target, backup)))
    plan.append(("add Outrigger state lines to .gitignore", lambda: gitignore(target)))

    print(f"Outrigger {'update' if a.update else 'install'} -> {target}\n")
    for i, (label, _) in enumerate(plan, 1):
        print(f"  {i:2}. {label}")
    if a.dry:
        return 0
    if not a.yes and input("\nProceed? [y/N] ").strip().lower() != "y":
        print("nothing changed")
        return 1
    for label, fn in plan:
        fn()
    print("\nRunning selftest in the target project...\n", flush=True)
    r = subprocess.run([sys.executable, "-X", "utf8", str(outrigger / "engine" / "cli.py"), "selftest"], cwd=target)
    print("\nNext: open .outrigger/local/notify.toml to set up phone notifications (ntfy), then do the LIVE CHECK above.")
    return r.returncode


def append_block(path: Path, backup) -> None:
    backup(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    with path.open("a", encoding="utf-8", newline="") as fh:
        fh.write(("" if text.endswith("\n") else "\n") + "\n" + BLOCK)


def merge_hooks(target: Path, backup) -> None:
    settings = target / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if settings.exists():
        backup(settings)
        data = json.loads(settings.read_text(encoding="utf-8") or "{}")
    ours = json.loads(HOOKS.read_text(encoding="utf-8"))["hooks"]
    hooks = data.setdefault("hooks", {})
    for event, entries in ours.items():
        existing = hooks.setdefault(event, [])
        if any(".outrigger/engine/hook.py" in h.get("command", "") for e in existing for h in e.get("hooks", [])):
            continue
        existing.extend(entries)
    settings.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def gitignore(target: Path) -> None:
    gi = target / ".gitignore"
    lines = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    add = [l for l in GITIGNORE_LINES if l not in lines]
    if add:
        with gi.open("a", encoding="utf-8") as fh:
            fh.write(("\n" if lines and lines[-1] else "") + "# Outrigger\n" + "\n".join(add) + "\n")


if __name__ == "__main__":
    sys.exit(main())
