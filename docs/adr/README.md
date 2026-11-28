# Architecture Decision Records

Never delete an ADR. To change a decision, write a new ADR and mark the old one `Superseded by ADR-NNNN`.

| ADR | Decision |
| :-- | :-- |
| [0001](0001-open-core-two-repos.md) | Open core: public rules + guard, paid packs |
| [0002](0002-agents-md-single-source.md) | AGENTS.md single source; one engine, thin adapters |
| [0003](0003-python-guard-fail-closed.md) | Python guard, fail-closed, human-only approvals |
| [0004](0004-bilingual-agent-english.md) | Agent files English, human docs bilingual |
| [0005](0005-release-1-scope.md) | Release 1 scope |
| [0006](0006-soft-delete-and-schedules.md) | Soft delete; schedules are high risk |
| [0007](0007-coexist-trust-model-hint.md) | Install beside existing rules; trust by SHA; model hint |
| [0008](0008-rename-keel-to-outrigger.md) | Product renamed from Keel to Outrigger |
| [0009](0009-light-mode-and-workflow-capture.md) | Light mode by default; capture workflows from the trace log (amends 0003) |
| [0010](0010-judge-purpose-not-form.md) | Judge purpose, not form: append-only originals, diff-scoped trust, fewer form-based blocks (amends 0007) |
| [0011](0011-standing-rules-learned-from-approvals.md) | Standing rules learned from the human's approvals (accept is human-only) |
| [0012](0012-recon-quarantine-and-content-check.md) | Recon: read someone else's code in quarantine; check what tools return |
| [0013](0013-pack-gui-always-ask.md) | A pack can make opening its app ask in light mode too (licence seats) — amends 0009 |
| [0014](0014-pack-ask-commands.md) | A pack can list commands that must always be asked about (`[[ask]]`: schema migrations, data drops) |
| [0015](0015-records-in-month-folders-and-structure-gate.md) | Records in month folders, ISSUE as a folder, `next-id` across branches, opt-in structure gate on `git commit` — amends 0009 |
