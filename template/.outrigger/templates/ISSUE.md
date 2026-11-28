---
id: ISSUE-NNN
date: YYYY-MM-DD
req: REQ-NNN
branch: <one record, one branch — never main>
status: draft | in-progress (phase N) | done | dropped
---

# ISSUE-NNN — <the piece of work, in one line>

> Folder `docs/issues/MM-YYYY/ISSUE-NNN-<slug>/`: only this `issue.md` at the top; the rest goes in
> `phase/phase-N.md`, `review/review-N.md`, `handoff/handoff-N.md`, `evidence/` (logs, screenshots).
> Number from `python .outrigger/engine/cli.py next-id ISSUE` — it counts month folders and branches.

## Goal
<the outcome, linked to the REQ's "done means">

## Current state / problem
<what is wrong or missing today, with evidence (`file:line`, a measured number)>

## Tasks (S/M/L)
- [ ] **1.1 (S):** …
- [ ] **1.2 (M):** …

Split into phases by **risk**, not by size: a breaking change or a schema change is its own phase.

## Rollback
<is reverting the commit enough, or did something change that does not roll back (data, schema, cache)?>

## Out of scope
<related work deliberately not done here, and where it will be done>

## Security
- Money or actions that must not repeat? · Personal data shown or logged? · New input or endpoint? · Who gains
  which permission? — answer each, or "not touched".

## Done means
- [ ] <checkable by a command or an action — "cleaner code" is not checkable>
