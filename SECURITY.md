# Security policy

Outrigger is a guard for AI coding agents that run with every permission granted. A way to get past the guard is a
security bug, even when the agent "could have done it anyway". Please report it privately.

## Report a vulnerability

Use GitHub's private reporting: **Security → Report a vulnerability** on this repository
(`https://github.com/HiTranquility/outrigger-agent/security/advisories/new`). Do **not** open a public issue, pull
request or discussion for a bypass until a fix is released.

Include, if you can:

- the exact tool call or shell command the agent sent (the JSON input of the hook is best),
- the Outrigger version (`python .outrigger/engine/cli.py status`), the approvals mode (`light` / `strict`), the OS
  and shell,
- what you expected the guard to do and what it did.

Never send real secrets, keys or personal data as proof — a fake value with the right shape is enough
(`"AKIA" + "Q" * 16`).

## What counts

| In scope | Examples |
| :-- | :-- |
| Guard bypass | an action the rules call high risk runs without asking; a medium-risk action that must ask in light mode does not (`LIGHT_STILL_ASK`) |
| Self-approval | the agent reaches `approve`, `trust`, `rule accept`, `structure --seed` or edits a protected file |
| Fail-open | the guard crashes or times out and the action runs |
| Secret leak | a secret value is printed in a reason, a log, a notification or a report |
| Quarantine escape | code under `sandbox/quarantine/` runs, builds or installs |

Out of scope: limits already written down in [README → Honest limits](README.md#honest-limits) and in
[ADR-0015 → Consequences](docs/adr/0015-records-in-month-folders-and-structure-gate.md#consequences) (for example,
code in languages Outrigger cannot read, or agents other than Claude Code that are not enforced yet). Telling us such
a limit hurts in practice is still welcome as a normal issue.

## What happens next

The maintainer works on this alone, so there is no fixed response time. Every confirmed bypass gets a regression test
in `tests/` and a row (or an extra test name) in [`docs/RISK_REGISTER.md`](docs/RISK_REGISTER.md) before the fix is
released, and is credited in [`CHANGELOG.md`](CHANGELOG.md) unless you ask not to be named.

## Supported versions

Only the latest minor version gets fixes. Update an installed project with
`python install.py --target <project> --update`.
