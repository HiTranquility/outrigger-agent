# ADR-0006 — Soft delete by default; schedules are high risk

- Status: Accepted · 2026-11-11
## Decision
- "Delete" means move to `.outrigger/state/trash/` with a SHA-256 manifest; `restore` undoes it. Bulk (> 20 files / > 100 MB) needs approval. `empty-trash` is human-only with typed confirmation. ADRs and logs are `never_delete`.
- Archive moves to `archive/<YYYY-MM>/` with manifest.
- Creating or changing a schedule (OS or agent) is high risk: approval + ADR + phone notification. A `STOP` file blocks every non-read tool until a human runs `resume`.
## Consequences
Disk use grows until the human empties trash — `status` shows trash size.
