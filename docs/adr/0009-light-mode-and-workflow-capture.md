# ADR-0009 — Light mode by default, and capture workflows from the trace log

- Status: Accepted · 2026-11-15 · **amends [ADR-0003](0003-python-guard-fail-closed.md)** (every medium risk needs a terminal approval) for new installs
- Decided by: the owner, after the first install in a non-code project (a research vault)

## Context
After three days in the research vault, 20 blocks were waiting; about 4 were real danger. The rest were false
positives (a read-only `git log` in another repo matched `.outrigger/engine`; a memory note that only *described*
`cli.py approve`; `__import__('datetime')`) or routine work (academic web sites, the project's own scripts, writes
to the owner's sibling repos). The owner, verbatim: *"cứ approve approve liên tục lúc cài outrigger cũng như không…
outrigger phục vụ tui ghi lại quy trình có quy cũ những cái tui hay xài, có này kia và cho by pass, khi nào có lệnh
nguy hiểm hoặc đọc tài liệu lúc làm phát hiện nguy hiểm, muốn execute mới hỏi"* — constant approvals make the guard
pointless; Outrigger is installed to record the user's workflows; let the agent run, and ask only for dangerous
commands or danger found in a script about to be executed. And: *"tui cài để mốt ghi lại quy trình từ sử dụng app,
nghiên cứu hay này kia"* — recording workflows is the reason to install it.

A guard that asks for routine work gets approved without reading. That is worse than asking less.

## Options
| Option | Gain | Lose |
| :-- | :-- | :-- |
| Keep strict, fix false positives only | No change in what is blocked | Routine medium risk still stops work |
| **Light mode + capture** | Stops only for real danger; the log becomes workflows | Some medium-risk actions run unasked (logged) |
| Ask in-app (`permissionDecision: "ask"`) for medium | No terminal | Needs a live test under bypass mode first (ROADMAP #12) |

## Decision
1. `[approvals] mode = "light" | "strict"`. **New installs: light.** No section (0.2.0 installs) or any unknown
   value: strict — nothing loosens silently.
2. Light mode still blocks every **high** risk, and these medium codes (`decide.LIGHT_STILL_ASK`): dangerous code in
   a script about to run that is not trusted, commands the guard cannot parse, deleting project files, bulk moves,
   discarding git changes, `git push`, installs, memory notes that weaken the guard, global agent config. Other
   medium risk runs, is written to the audit log as `allowed-light`, and appears in the daily summary.
3. Every tool call is written to `state/logs/trace-YYYY-MM.jsonl` (redacted, local, git-ignored).
   `cli.py capture --title … --since …` turns a stretch of it into a draft workflow. After a task no workflow
   matched, the agent asks once whether to record it. Only the human promotes a draft.
4. False positives fixed: FP-4 (memory note mentioning the command), FP-5 (harmless `__import__`), FP-6 (Outrigger
   paths of another repository, and read-only commands). R-20 added: a Python script that loads another file's code
   (`runpy`, `importlib`, `exec(open(…))`) is itself dangerous code, so a clean wrapper cannot hide a dangerous script.

## Consequences
- Light mode trades a little prevention for attention: the daily summary must be readable, or the trade is lost.
- `selftest` runs every strict case **and** every light case; a light-mode change that lets a high risk through fails it.
- The trace log grows with every call; it never leaves the machine. Retention is the user's (`state/` is theirs).
- Not done: FP-1/FP-2 (shell splitter on heredocs and `|`/`>` inside quotes) — in light mode FP-2 no longer stops
  work, FP-1 still does (unparsed stays fail-closed). In-app approval (option 3) still needs the live test.

## Revisit when
- A loss or leak happens through an `allowed-light` action → move that code into `LIGHT_STILL_ASK`.
- Captured drafts are mostly noise after two weeks of real use → change how calls are grouped before selling.
