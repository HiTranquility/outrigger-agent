# Zones — where the agent may write

Configured in `.keel/keel.toml` → `[zones]`. The guard enforces them on every write tool and on shell commands.

| Zone | Default paths | Agent may |
| :-- | :-- | :-- |
| green | `sandbox/`, `reports/`, `docs/decisions/`, `.keel/local/workflows/drafts/` | write freely |
| yellow | everything else inside the project | write — the guard copies the old file to `.keel/state/backups/` first |
| red | `.env*` (except `.env.example`), keys, certificates, `credentials.json`, `SecretKeys/` | nothing — not even read |
| protected | `.keel/engine`, `.keel/keel.toml`, `.keel/state`, hook settings, `.mcp.json` | nothing — ask the user to edit |
| outside the project | anything not under the project root | blocked (medium) unless listed in `outside_allow` |

Experiments, copies and throw-away files go to `sandbox/`. To undo an edit, copy the file back from
`.keel/state/backups/<date>/` and tell the user which one.
