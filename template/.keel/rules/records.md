# Records — what to write, where

| Record | When | Where | Template |
| :-- | :-- | :-- | :-- |
| GATE | before any gated action | in chat (copy it into the report) | `GATE.md` |
| REPORT | end of every work turn | `reports/YYYY-MM-DD/HHMM-<slug>.md` | `REPORT.md` |
| ADR | the user chooses between alternatives, or you pick between real alternatives mid-task | `docs/decisions/ADR-NNNN-<slug>.md` | `ADR.md` |
| SPIKE | safe probe of an unknown task | `sandbox/spikes/SPIKE-NNN-<slug>/README.md` | `SPIKE.md` |
| WORKFLOW | a repeatable procedure | drafts: `.keel/local/workflows/drafts/`; approved: `.keel/local/workflows/` | `WORKFLOW.md` |
| BUG | a defect outside the current task | `reports/bugs/BUG-NNN-<slug>.md` | `BUG.md` |

- Numbers (`NNNN`, `NNN`) continue from the highest existing file of that type; never reuse one.
- Search for an existing record on the same topic before creating a new one.
- The guard writes machine logs: `.keel/state/logs/audit-YYYY-MM.jsonl`, `apps.jsonl`, and a daily
  summary in `reports/keel/YYYY-MM-DD.md`. Do not edit them.
- Every report says what was **not** done or **not** verified. "Done" without evidence is not done.
