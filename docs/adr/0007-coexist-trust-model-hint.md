# ADR-0007 — Install beside existing rules; trust scripts by SHA; model hint is a suggestion

- Status: Accepted · 2026-11-11 · decided by: owner (chat: "B: Keel làm nền chung")
## Context
The owner has 14 code folders. Most already have their own AGENTS.md / CLAUDE.md; several carry the IPLMS tool-chain
(guard_command, audit_gate). Keel must become the shared base without replacing what is there. Repositories with many
helper scripts would hit the Python pack on every run. The owner also asked whether the agent should ask which model to use.
## Decision
1. **Coexist.** The installer never rewrites an existing rule file: Keel rules go to `.keel/KEEL.md` and a marked pointer
   block (`<!-- keel:start -->`) is appended once. Existing hooks stay; Keel hooks are added. Stricter rule wins.
2. **Trust by content.** `cli.py trust <file>` (human-only) records the file SHA-256; pack scanners skip a file only
   while it is byte-identical. Editing it removes the trust. `.keel/KEEL.md`, `.keel/rules`, `.keel/packs` are protected.
3. **Model hint, not a model gate.** One `Model hint:` line with the options, tiers from `keel.toml [models]`
   (strongest / balanced / fast / cheap — no product names). The agent never switches models itself.
## Options rejected
Replacing each repo's rules with Keel's (loses 62 ADRs of project rules) · path-based trust lists (an agent could edit a
trusted path) · a mandatory model question every turn (interrupts, and costs tokens itself).
## Consequences
Two guards run in repos that keep the IPLMS tool-chain (git conventions there, dangerous actions in Keel).
