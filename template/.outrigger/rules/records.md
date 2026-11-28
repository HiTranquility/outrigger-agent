# Records — what to write, where

| Record | When | Where | Template |
| :-- | :-- | :-- | :-- |
| GATE | before any gated action | in chat (copy it into the report) | `GATE.md` |
| REPORT | end of every work turn | `reports/YYYY-MM-DD/HHMM-<slug>.md` | `REPORT.md` |
| ADR | the user chooses between alternatives, or you pick between real alternatives mid-task | `docs/decisions/MM-YYYY/ADR-NNNN-<slug>.md` | `ADR.md` |
| SPIKE | safe probe of an unknown task | `sandbox/spikes/SPIKE-NNN-<slug>/README.md` | `SPIKE.md` |
| WORKFLOW | a repeatable procedure | drafts: `.outrigger/local/workflows/drafts/`; approved: `.outrigger/local/workflows/` | `WORKFLOW.md` |
| BUG | a defect outside the current task | `reports/bugs/MM-YYYY/BUG-NNN-<slug>.md` | `BUG.md` |
| REQ | a new request that is more than a quick fix — **before** building | `docs/requirements/MM-YYYY/REQ-NNN-<slug>.md` | `REQ.md` |
| ISSUE | an agreed REQ is broken into work that spans more than one turn | `docs/issues/MM-YYYY/ISSUE-NNN-<slug>/issue.md` (a **folder**) | `ISSUE.md` |
| PHASE | one risk-sized step of an ISSUE | `docs/issues/MM-YYYY/ISSUE-NNN-<slug>/phase/phase-N.md` | `PHASE.md` |
| HANDOFF | a session ends with work unfinished, or the task passes to someone else | `reports/YYYY-MM-DD/handoff-<slug>.md` | `HANDOFF.md` |
| STATUS | the user asks for a weekly / periodic summary | `reports/status/YYYY-MM-DD.md` | `STATUS.md` |
| POSTMORTEM | something was lost, leaked or broken — or nearly was | `docs/postmortems/MM-YYYY/PM-NNN-<slug>.md` | `POSTMORTEM.md` |
| RISK | once per project; reviewed at each phase change | `docs/RISK.md` | `RISK.md` |
| MEETING | the user gives meeting notes or a transcript | `docs/meetings/YYYY-MM-DD-<slug>.md` | `MEETING.md` |

Which one? idea or request → REQ · agreed work over several turns → ISSUE (+ PHASE) · choice made → ADR · unknown territory → SPIKE · work done → REPORT · work
unfinished → HANDOFF · something went wrong → POSTMORTEM (and a BUG if code is at fault) · could go wrong → RISK.
Do not invent a new document format: if none fits, ask the user, then draft a template in `.outrigger/local/`.

## Turning work into a workflow (0.3.0)

Recording how the user works is the main reason Outrigger is installed. When a piece of work is finished and **no
workflow matched it at the start** (first time doing this kind of task — using an app, a research pass, fixing a
kind of problem), ask the user **one** question: *"Record this as a workflow?"* Do not ask again in the same task.

If they say yes, run `python .outrigger/engine/cli.py capture --title "<short imperative>" --since <time the work
started>` (or `--last <N calls>`). It writes a draft from the guard's trace log — the commands that actually ran,
files changed, sources fetched, where the guard stopped — into `.outrigger/local/workflows/drafts/`. Then fill in
**only** what the log cannot know and mark it as yours: when to use it, what "done" looks like, what went wrong.
Remove detours the user confirms were detours. Never promote a draft yourself.

When the task **did** follow a workflow and something changed (a step added, a gate that turned out routine), add a
row to that workflow's *Changelog* instead of capturing a new one.

## First run and the personal library (0.7.0, ADR-0016)

`OUTRIGGER FIRST RUN` at session start = this project was never set up. Ask **one** question: import workflows (from
the personal library, another project folder, or a repository read with `cli.py recon`), or start empty? Then:
`cli.py import library` / `cli.py import <folder>` (everything lands in `drafts/` as `status: draft`; files with text
aimed at an agent are skipped — show the user the SKIP lines), and `cli.py onboard --done "<their answer>"`.
The library (`~/.outrigger/library/workflows/`, or `$OUTRIGGER_HOME`) reaches every project: put a workflow there only
with `cli.py export <name>` when the user asks, after they promoted it. The guard asks every time. Never write the
library folder any other way.

- **Folders (0.6.0, ADR-0015).** Numbered records go into a month folder `MM-YYYY/` of the month they were created;
  an ISSUE is a folder: only `issue.md` at its top, then `phase/`, `review/` (`review-N.md`), `handoff/`, `evidence/`.
  Records written before 0.6.0 stay where they are (flat); do not move them.
- Numbers (`NNNN`, `NNN`): take them from `python .outrigger/engine/cli.py next-id <ADR|REQ|ISSUE|BUG|SPIKE|PM>` —
  it counts every month folder **and** every branch (a record on an unmerged branch is invisible otherwise).
  Never reuse a number; a `WARN … used twice` line means two records share one — tell the user.
- Search for an existing record on the same topic before creating a new one.
- The guard writes machine logs: `.outrigger/state/logs/audit-YYYY-MM.jsonl`, `trace-YYYY-MM.jsonl` (every call,
  redacted, local only — the source for `capture`), `apps.jsonl`, and a daily
  summary in `reports/outrigger/YYYY-MM-DD.md`. Do not edit them.
- Every report says what was **not** done or **not** verified. "Done" without evidence is not done.
