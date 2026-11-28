#!/usr/bin/env python3
"""Outrigger command line.  python .outrigger/engine/cli.py <command> ...

Agent may use:  status · pending · trash · trash-list · restore · archive · stop · scan · recon · capture · notify-test · selftest
                next-id · structure [--update] · onboard · import
Asks every time: export   (writes the personal library ~/.outrigger/, which every project reads — ADR-0016)
Human only:     approve · deny · resume · empty-trash · trust · untrust · rule accept · structure --seed   (the guard blocks the agent)
Anyone:         rule list · rule drop   (dropping a rule only makes the guard stricter)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from outrigger import __version__, config, learn, library, notify, packs, records, selftest, state, structure  # noqa: E402


def _cfg() -> config.Config:
    return config.load(Path.cwd())


def cmd_status(a) -> int:
    cfg = _cfg()
    trash = state.trash_entries(cfg)
    tsize = sum(f["size"] for m in trash for i in m["items"] for f in i["files"])
    print(f"Outrigger {__version__} · project: {cfg.project_name} · root: {cfg.root}")
    print(f"STOP: {'ON' if state.stop_file(cfg).exists() else 'off'} · pending approvals: {len(state.pending(cfg))}"
          f" · trash: {len(trash)} batch(es), {tsize / 1048576:.1f} MB")
    print("packs: " + (", ".join(sorted({p.name for p in cfg.packs})) or "none"))
    print(f"notify: {notify.settings(cfg).get('channel', 'toast')}")
    return 0


def cmd_pending(a) -> int:
    for p in state.pending(_cfg()):
        print(f"{p['id']}  [{p['risk']}]  {p['tool']}  {', '.join(p.get('codes', []))}\n    {p.get('summary', '')[:200]}")
        for r in p.get("reasons", [])[:4]:
            print(f"    - {r}")
    return 0


def cmd_approve(a) -> int:
    cfg = _cfg()
    for aid in a.ids:
        try:
            p = next((x for x in state.pending(cfg) if x["id"] == aid), None)
            if p:
                print(f"{aid} [{p['risk']}] {p['tool']}: {p.get('summary', '')[:300]}")
                for r in p.get("reasons", [])[:4]:
                    print(f"  - {r}")
            if not a.yes and sys.stdin.isatty():
                if input("Approve this exact action once? [y/N] ").strip().lower() != "y":
                    print("not approved")
                    continue
            d = state.approve(cfg, aid, a.minutes)
            state.log_decision(cfg, {"tool": d["tool"], "risk": d["risk"], "decision": "approval-granted", "id": aid,
                                     "summary": d.get("summary", ""), "sigs": d.get("sigs")})
            print(f"approved {aid} until {d['expires']}")
        except FileNotFoundError as exc:
            print(exc)
    for s in learn.suggestions(cfg):   # 0.3.2: the third approval of the same kind of action offers a standing rule
        if any(aid in s["approvals"] for aid in a.ids):
            print(f"\nYou have approved this kind of action {s['count']} times: {s['describe']}.\n"
                  f"To stop being asked for it: python .outrigger/engine/cli.py rule accept {s['id']}")
    return 0


def cmd_rule(a) -> int:
    """Standing rules learned from approvals (ADR-0011). list/drop: anyone · accept: the human only."""
    cfg = _cfg()
    if a.action == "list":
        act = learn.active(cfg)
        print("active rules:" if act else "active rules: none")
        for rid, r in act.items():
            print(f"  {rid}  {learn.describe(r['code'], r['target'])}  [{r['code']}]  until {r['expires'][:10]}")
        sugg = learn.suggestions(cfg)
        print("\nsuggestions:" if sugg else "\nsuggestions: none")
        for s in sugg:
            print(f"  {s['id']}  {s['describe']}  [{s['code']}]  approved {s['count']} times")
        return 0
    if not a.id:
        print("say which rule: rule accept L-xxxxxx")
        return 1
    if a.action == "drop":
        print(f"dropped {a.id}" if learn.drop(cfg, a.id) else f"no rule {a.id}")
        return 0
    s = next((x for x in learn.suggestions(cfg) if x["id"] == a.id), None)
    if s is None:
        print(f"{a.id} is not a current suggestion (see `cli.py rule list`)")
        return 1
    print(f"{a.id}: from now on, without asking: {s['describe']}  [{s['code']}]")
    print(f"You approved it {s['count']} times, e.g.:")
    for ex in s["examples"]:
        print(f"  - {ex}")
    print("High-risk actions are never covered. The rule expires; `rule drop` removes it at once.")
    if not a.yes and sys.stdin.isatty():
        if input("Accept this standing rule? [y/N] ").strip().lower() != "y":
            print("not accepted")
            return 0
    r = learn.accept(cfg, a.id)
    state.log_decision(cfg, {"tool": "cli", "risk": "medium", "decision": "rule-accepted", "id": a.id,
                             "summary": f"{r['code']} {r['target']} until {r['expires']}"})
    print(f"accepted {a.id} until {r['expires'][:10]}")
    return 0


def cmd_deny(a) -> int:
    cfg = _cfg()
    for aid in a.ids:
        state.deny(cfg, aid)
        state.log_decision(cfg, {"tool": "-", "risk": "-", "decision": "approval-denied", "id": aid})
        print(f"denied {aid}")
    return 0


def _rels(cfg, paths):
    out = []
    for p in paths:
        rel = cfg.rel(p, Path.cwd())
        if rel is None:
            raise SystemExit(f"refused: {p} is outside the project")
        out.append(rel)
    return out


def cmd_trash(a) -> int:
    cfg = _cfg()
    m = state.trash(cfg, _rels(cfg, a.paths), a.reason)
    state.log_decision(cfg, {"tool": "cli.trash", "risk": "low", "decision": "trashed", "id": m["id"],
                             "summary": f"{a.paths} — {a.reason}"})
    n = sum(len(i["files"]) for i in m["items"])
    print(f"moved {n} file(s) to trash {m['id']} — undo: python .outrigger/engine/cli.py restore {m['id']}")
    return 0


def cmd_trash_list(a) -> int:
    for m in state.trash_entries(_cfg()):
        n = sum(len(i["files"]) for i in m["items"])
        print(f"{m['id']}  {m['time']}  {n} file(s)  {', '.join(i['path'] for i in m['items'])[:120]}  — {m['reason']}")
    return 0


def cmd_restore(a) -> int:
    cfg = _cfg()
    done = state.restore(cfg, a.trash_id)
    state.log_decision(cfg, {"tool": "cli.restore", "risk": "low", "decision": "restored", "id": a.trash_id,
                             "summary": ", ".join(done)})
    print("restored: " + ", ".join(done))
    return 0


def cmd_archive(a) -> int:
    cfg = _cfg()
    m = state.archive(cfg, _rels(cfg, a.paths), a.reason)
    state.log_decision(cfg, {"tool": "cli.archive", "risk": "low", "decision": "archived", "id": m["id"],
                             "summary": f"{a.paths} — {a.reason}"})
    print(f"archived to archive/{m['id']}")
    return 0


def cmd_empty_trash(a) -> int:
    cfg = _cfg()
    if not sys.stdin.isatty():
        print("refused: empty-trash needs a human at an interactive terminal")
        return 1
    entries = [m for m in state.trash_entries(cfg)]
    n = sum(len(i["files"]) for m in entries for i in m["items"])
    print(f"{len(entries)} trash batch(es), {n} file(s). Batches older than {a.older_than} day(s) will be DELETED FOR GOOD.")
    phrase = "DELETE FOREVER"
    if input(f"Type '{phrase}' to continue: ").strip() != phrase:
        print("cancelled")
        return 1
    count, size = state.empty_trash(cfg, a.older_than)
    state.log_decision(cfg, {"tool": "cli.empty-trash", "risk": "high", "decision": "hard-deleted",
                             "summary": f"{count} files, {size} bytes"})
    print(f"deleted {count} file(s), {size / 1048576:.1f} MB")
    return 0


def cmd_stop(a) -> int:
    cfg = _cfg()
    state.stop_file(cfg).write_text(f"{state.now().isoformat(timespec='seconds')} {a.reason}\n", encoding="utf-8")
    state.log_decision(cfg, {"tool": "cli.stop", "risk": "high", "decision": "stop-on", "summary": a.reason})
    print("STOP is on — every non-read tool is blocked until a human runs `cli.py resume`.")
    return 0


def cmd_resume(a) -> int:
    cfg = _cfg()
    f = state.stop_file(cfg)
    if f.exists():
        f.unlink()
    state.log_decision(cfg, {"tool": "cli.resume", "risk": "high", "decision": "stop-off"})
    print("STOP removed.")
    return 0


def cmd_scan(a) -> int:
    cfg = _cfg()
    if not cfg.packs:
        print("no packs installed")
    for p in cfg.packs:
        hits = packs.scan_project(cfg, p)
        print(f"[{p.name}] {len(hits)} dangerous call(s)")
        for h in hits:
            print("  " + h)
    return 0


def cmd_trust(a) -> int:
    cfg = _cfg()
    for rel in _rels(cfg, a.paths):
        f = cfg.root / rel
        if not f.is_file():
            print(f"not a file: {rel}")
            continue
        danger: list[str] = []
        for p in cfg.packs:
            if f.suffix.lower() in p.scan_extensions:
                text = f.read_text(encoding="utf-8", errors="replace")
                for line, whole in packs.danger_lines(text, p, f.suffix.lower()):
                    print(f"  {rel}:{line}: {whole[:100]}")
                    danger.append(whole)
        note = ("in light mode a later edit asks again only if it adds a dangerous line"
                if cfg.light else "any later change removes the trust")
        if not a.yes and sys.stdin.isatty():
            if input(f"Trust {rel} as it is now ({note})? [y/N] ").strip().lower() != "y":
                continue
        sha = state.trust(cfg, rel, danger)
        state.log_decision(cfg, {"tool": "cli.trust", "risk": "medium", "decision": "trusted",
                                 "summary": f"{rel} {sha[:12]}"})
        print(f"trusted {rel} ({sha[:12]})")
    return 0


def cmd_untrust(a) -> int:
    cfg = _cfg()
    for rel in _rels(cfg, a.paths):
        print(("untrusted " if state.untrust(cfg, rel) else "was not trusted: ") + rel)
    return 0


def cmd_capture(a) -> int:
    """Turn recent work into a draft workflow in .outrigger/local/workflows/drafts/ (0.3.0)."""
    from datetime import datetime
    from outrigger import capture
    cfg = _cfg()
    since = None
    if a.since:
        since = datetime.fromisoformat(a.since)
        if since.tzinfo is None:
            since = since.astimezone()
    if not since and not a.last:
        print("say which stretch of work: --since 2026-11-15T09:30  or  --last 40 (calls)")
        return 1
    dest, text = capture.capture(cfg, a.title, since=since, last=a.last, write=not a.dry)
    if a.dry:
        print(text)
    else:
        print(f"draft written: {dest.relative_to(cfg.root).as_posix()} — a person fills in the ✍️ parts and promotes it")
    return 0


def cmd_recon(a) -> int:
    """Copy someone else's code into the quarantine zone and scan it without running any of it (ADR-0012)."""
    from outrigger import recon
    cfg = _cfg()
    src = a.source
    if "://" in src:
        target, sha = recon.clone(cfg, src, a.ref)
    else:
        path = Path(src).expanduser().resolve()
        if not path.is_dir():
            print(f"not a folder or https URL: {src}")
            return 1
        rel = cfg.rel(path)
        if recon.in_quarantine(cfg, rel) and rel.count("/") >= 2:   # already quarantined: scan again in place
            target, sha = path, "(unchanged)"
        else:
            target, sha = recon.copy_local(cfg, path)
    renamed = recon.neutralize(target)
    scan = recon.scan_tree(target)
    report = recon.write_report(cfg, target, src, sha, renamed, scan)
    state.log_decision(cfg, {"tool": "cli.recon", "risk": "low", "decision": "recon",
                             "summary": f"{src} -> {target.relative_to(cfg.root).as_posix()} "
                                        f"warn={scan['warn']} info={scan['info']}"})
    print(f"quarantined: {target.relative_to(cfg.root).as_posix()}  (commit {sha})")
    print(f"agent instruction files renamed: {len(renamed)} · runnable files listed: {len(scan['runnable'])}")
    print(f"findings: {scan['warn']} warning(s), {scan['info']} note(s)")
    print(f"report: {report.relative_to(cfg.root).as_posix()}  (read the report first, then the code — never run it)")
    return 0


def cmd_notify_test(a) -> int:
    cfg = _cfg()
    print(notify.send(cfg, "high", "Outrigger: test", f"{cfg.project_name}: notification test"))
    return 0


def cmd_next_id(a) -> int:
    """0.6.0 (ADR-0015): next free record number, counted across month folders and git branches."""
    try:
        rid, warnings = records.next_id(_cfg(), a.kind)
    except ValueError as exc:
        print(exc)
        return 2
    for w in warnings:
        print(f"WARN {w}")
    print(rid)
    return 0


def cmd_structure(a) -> int:
    """0.6.0 (ADR-0015): file-size ratchet. --seed (human, once) · default: check · --update (only lowers)."""
    cfg = _cfg()
    s = structure.settings(cfg)
    try:
        baseline = structure.read_baseline(cfg)
        current = structure.measure_project(cfg)
    except structure.StructureError as exc:
        print(f"ERROR {exc}")
        return 1
    if a.seed:
        if (cfg.root / structure.BASELINE_REL).is_file():
            print(f"ERROR {structure.BASELINE_REL} exists; use --update to lower it, never seed again")
            return 1
        structure.write_baseline(cfg, current)
        print(f"OK seeded {len(current)} files. Switch the commit gate on with [structure] enabled = true")
        return 0
    if a.update and not (cfg.root / structure.BASELINE_REL).is_file():
        print("ERROR no baseline yet: the human seeds it once with `cli.py structure --seed`")
        return 1
    errors, lowered = structure.compare(current, baseline, s, a.update)
    for e in errors:
        print(f"ERROR {e}")
    if a.update and not errors:
        structure.write_baseline(cfg, lowered)
        print(f"OK updated: {len(lowered)} files in the baseline")
    elif not errors:
        print(f"OK {len(baseline)} files in the baseline, nothing grew" + ("" if s["enabled"] else " (gate off)"))
    return 1 if errors else 0


def cmd_selftest(a) -> int:
    return selftest.run(a, _cfg())


def main() -> int:
    ap = argparse.ArgumentParser(prog="cli.py", description="Outrigger guard CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    sub.add_parser("pending").set_defaults(fn=cmd_pending)
    p = sub.add_parser("approve"); p.add_argument("ids", nargs="+"); p.add_argument("--minutes", type=int)
    p.add_argument("--yes", action="store_true"); p.set_defaults(fn=cmd_approve)
    p = sub.add_parser("deny"); p.add_argument("ids", nargs="+"); p.set_defaults(fn=cmd_deny)
    p = sub.add_parser("trash"); p.add_argument("paths", nargs="+"); p.add_argument("--reason", required=True)
    p.set_defaults(fn=cmd_trash)
    sub.add_parser("trash-list").set_defaults(fn=cmd_trash_list)
    p = sub.add_parser("restore"); p.add_argument("trash_id"); p.set_defaults(fn=cmd_restore)
    p = sub.add_parser("archive"); p.add_argument("paths", nargs="+"); p.add_argument("--reason", required=True)
    p.set_defaults(fn=cmd_archive)
    p = sub.add_parser("empty-trash"); p.add_argument("--older-than", type=int, default=30); p.set_defaults(fn=cmd_empty_trash)
    p = sub.add_parser("stop"); p.add_argument("reason", nargs="?", default="manual stop"); p.set_defaults(fn=cmd_stop)
    sub.add_parser("resume").set_defaults(fn=cmd_resume)
    sub.add_parser("scan").set_defaults(fn=cmd_scan)
    p = sub.add_parser("trust"); p.add_argument("paths", nargs="+"); p.add_argument("--yes", action="store_true")
    p.set_defaults(fn=cmd_trust)
    p = sub.add_parser("untrust"); p.add_argument("paths", nargs="+"); p.set_defaults(fn=cmd_untrust)
    p = sub.add_parser("rule"); p.add_argument("action", choices=["list", "accept", "drop"]); p.add_argument("id", nargs="?")
    p.add_argument("--yes", action="store_true"); p.set_defaults(fn=cmd_rule)
    p = sub.add_parser("capture"); p.add_argument("--title", required=True); p.add_argument("--since")
    p.add_argument("--last", type=int); p.add_argument("--dry", action="store_true"); p.set_defaults(fn=cmd_capture)
    p = sub.add_parser("recon", help="quarantine and scan someone else's repository (never runs it)")
    p.add_argument("source", help="https URL of a git repository, or a local folder")
    p.add_argument("--ref", help="branch or tag to clone (default: the repository's default branch)")
    p.set_defaults(fn=cmd_recon)
    sub.add_parser("notify-test").set_defaults(fn=cmd_notify_test)
    p = sub.add_parser("next-id"); p.add_argument("kind", help="ADR · REQ · ISSUE · BUG · SPIKE · PM"); p.set_defaults(fn=cmd_next_id)
    p = sub.add_parser("structure", allow_abbrev=False); g = p.add_mutually_exclusive_group()   # `--se` must not mean --seed
    g.add_argument("--update", action="store_true"); g.add_argument("--seed", action="store_true"); p.set_defaults(fn=cmd_structure)
    library.register(sub, _cfg)   # 0.7.0 (ADR-0016): onboard · import · export
    p = sub.add_parser("selftest"); p.add_argument("-v", "--verbose", action="store_true"); p.set_defaults(fn=cmd_selftest)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
