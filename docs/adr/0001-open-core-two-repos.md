# ADR-0001 — Open core: public rules + guard, paid packs

- Status: Accepted · 2026-11-11 · decided by: owner (chat)
## Context
Outrigger is sold. Buyers must grant an agent full permissions, so they need to *read* the safety rules before paying.
## Options
A. Open core (public core Apache-2.0, private paid packs) · B. Fully closed EULA · C. Source-available (PolyForm Noncommercial) · D. Docs CC BY-NC-SA + code commercial.
## Decision
**A.** Trust comes from inspectable safety rules; value is charged on packs, the builder interview and updates.
## Consequences
Core can be copied freely (accepted). `local/` must never be overwritten by updates, so updates stay worth paying for.
