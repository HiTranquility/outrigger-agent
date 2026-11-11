# ADR-0004 — Agent-facing files in English, human docs bilingual

- Status: Accepted · 2026-11-11
## Options
A. Agent files English, `docs/en` + `docs/vi` for people · B. Two copies of every file · C. Both languages inside each file.
## Decision
**A** — lowest token cost, fits the Codex 32 KiB limit, models follow English rules most reliably. The agent always answers in the user's language.
