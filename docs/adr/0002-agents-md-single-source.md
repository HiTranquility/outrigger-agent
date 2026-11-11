# ADR-0002 — AGENTS.md is the single rule source; one engine, thin adapters

- Status: Accepted · 2026-11-11
## Context
Claude Code reads `CLAUDE.md` (and `AGENTS.md` only when no CLAUDE.md exists); Codex reads `AGENTS.md` up to 32 KiB; Antigravity CLI reads `AGENTS.md`/`GEMINI.md`; Cursor has its own rules. All four have blocking pre-tool hooks (checked in official docs 2026-11-11; Codex hooks only via third-party pages).
## Options
A. One file per platform, maintained by hand · B. AGENTS.md + shims + one engine with adapters · C. Ship as a Claude Code plugin only.
## Decision
**B.** `CLAUDE.md` = `@AGENTS.md`, `GEMINI.md` points to it; enforcement logic exists once in `.keel/engine`.
## Consequences
AGENTS.md must stay short (details live in `.keel/rules/`). Release 1 ships only the Claude Code adapter.
