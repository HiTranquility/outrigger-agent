"""Turn a stretch of the trace log into a DRAFT workflow (0.3.0, ADR-0009).

The draft is built only from what the guard recorded — the commands that ran, the files that changed, the sources
fetched, the points where a human had to approve — never from the agent's memory of what it did. A person reads it,
fills in the parts only a person knows (when to use it, what "done" means), and promotes it out of drafts/.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from . import state
from .config import Config

READ = {"read", "glob", "grep", "ls", "notebookread", "read_file", "read_many_files", "list_directory",
        "search_file_content"}
WRITE = {"write", "edit", "multiedit", "notebookedit", "write_file", "replace", "apply_patch", "create_file",
         "edit_file", "str_replace_editor"}
SHELL = {"bash", "powershell", "shell", "run_shell_command", "exec_command", "local_shell"}
FETCH = {"webfetch", "web_fetch", "fetch", "websearch", "google_web_search"}
SKIP = {"todowrite", "toolsearch"}


def _short(tool: str) -> str:
    t = tool.lower()
    return t.split("__")[-1] if t.startswith("mcp__") else t


def _field(summary: str, *keys: str) -> str:
    """The summary is the tool input as JSON, cut at 300 characters: parse it if whole, else pull the field out."""
    try:
        data = json.loads(summary)
        for k in keys:
            if isinstance(data.get(k), str):
                return data[k]
    except (json.JSONDecodeError, AttributeError):
        pass
    for k in keys:
        m = re.search(rf'"{k}"\s*:\s*"((?:[^"\\]|\\.)*)', summary)
        if m:
            return m.group(1).encode().decode("unicode_escape", errors="replace")
    return ""


def _rel(cfg: Config, path: str) -> str:
    r = cfg.rel(path)
    return r if r is not None else path


def steps_from(cfg: Config, records: list[dict]) -> tuple[list[dict], list[str], list[str]]:
    """-> (steps, files read, sources fetched). Consecutive edits merge into one step; reads are inputs, not steps."""
    steps: list[dict] = []
    reads: list[str] = []
    sources: list[str] = []
    for r in records:
        t = _short(r.get("tool", ""))
        s = str(r.get("summary", ""))
        gate = r.get("decision") == "blocked"
        if t in SKIP:
            continue
        if t in READ:
            p = _field(s, "file_path", "path", "pattern")
            if p and p not in reads:
                reads.append(_rel(cfg, p) if t in {"read", "read_file", "notebookread"} else p)
            continue
        if t in FETCH:
            u = _field(s, "url", "query")
            if u and u not in sources:
                sources.append(u)
            steps.append({"kind": "fetch", "level": "L3", "text": f"Look up `{u}`", "gate": gate, "ts": r["ts"]})
            continue
        if t in WRITE:
            p = _rel(cfg, _field(s, "file_path", "path", "notebook_path"))
            if steps and steps[-1]["kind"] == "edit" and not gate:
                if p not in steps[-1]["files"]:
                    steps[-1]["files"].append(p)
                continue
            steps.append({"kind": "edit", "level": "L0", "files": [p], "gate": gate, "ts": r["ts"]})
            continue
        if t in SHELL:
            c = _field(s, "command", "cmd").strip().splitlines()[0][:160] if _field(s, "command", "cmd") else "(command)"
            steps.append({"kind": "run", "level": "L1", "text": f"Run `{c}`", "gate": gate, "ts": r["ts"]})
            continue
        steps.append({"kind": "other", "level": "L2", "text": f"Use `{r.get('tool')}`", "gate": gate, "ts": r["ts"]})
    for st in steps:
        if st["kind"] == "edit":
            st["text"] = "Edit " + ", ".join(f"`{f}`" for f in st["files"][:6]) + (" …" if len(st["files"]) > 6 else "")
    return steps, reads, sources


def next_id(cfg: Config) -> str:
    wf = cfg.root / ".outrigger" / "local" / "workflows"
    nums = [int(m.group(1)) for p in wf.rglob("LOCAL-*.md") if (m := re.match(r"LOCAL-(\d+)", p.name))]
    return f"LOCAL-{max(nums, default=0) + 1:03d}"


def slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s[:40] or "workflow"


def render(cfg: Config, wid: str, title: str, records: list[dict]) -> str:
    steps, reads, sources = steps_from(cfg, records)
    levels = sorted({s["level"] for s in steps} | ({"L0"} if reads else set()))
    first, last = (records[0]["ts"], records[-1]["ts"]) if records else ("", "")
    gates = [i for i, s in enumerate(steps, 1) if s["gate"]]
    out = ["---", f"id: {wid}", f"title: {title}", "status: draft", "author: ai", "approved_by:",
           f"levels: [{', '.join(levels)}]", f"sources: [{', '.join(json.dumps(u) for u in sources[:10])}]",
           f"captured_from: trace log {first} .. {last} ({len(records)} calls)", "---", "",
           f"# {wid} — {title}", "",
           "> Captured by `cli.py capture` from the guard's trace log, not from memory. **A person must fill in the",
           "> two sections marked ✍️ and remove what was a detour, then move this file out of `drafts/`.**", "",
           "## When to use", "✍️ *(the situation that should make the agent pick this workflow)*", "",
           "## Inputs and preconditions"]
    out += [f"- `{p}`" for p in reads[:20]] or ["- (nothing was read)"]
    out += ["", "## Steps"]
    for i, s in enumerate(steps, 1):
        out.append(f"{i}. {s['text']} — level {s['level']} — gate: {'yes (the guard stopped here)' if s['gate'] else 'no'}")
    if not steps:
        out.append("1. (no commands or edits were recorded in this stretch)")
    out += ["", "## Gates"]
    out += [f"- Step {i}: the guard asked the human here. Keep asking, or `trust` the script if it is routine." for i in gates] \
        or ["- None recorded."]
    out += ["", "## Output", "✍️ *(files produced, what \"done\" looks like)*", "",
            "## Failure modes and rollback", "✍️ *(what went wrong during the captured run, and how to undo)*", "",
            "## Changelog", "| Date | Change | By |", "| :-- | :-- | :-- |",
            f"| {state.now():%Y-%m-%d} | Captured from the trace log | ai |", ""]
    return "\n".join(out)


def capture(cfg: Config, title: str, since: datetime | None = None, last: int | None = None,
            write: bool = True) -> tuple[Path, str]:
    records = state.read_trace(cfg, since)
    if last:
        records = records[-last:]
    wid = next_id(cfg)
    text = render(cfg, wid, title, records)
    dest = cfg.root / ".outrigger" / "local" / "workflows" / "drafts" / f"{wid}_{slug(title)}.md"
    if write:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
    return dest, text
