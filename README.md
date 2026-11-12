# ⚓ Keel

**Let your AI agent sail at full speed — without capsizing.**
*Cho AI agent chạy hết tốc lực mà không lật thuyền.* · [Tiếng Việt](docs/vi/bat-dau.md)

A keel is what lets a sailboat carry full sail in strong wind and stay upright.
Keel does the same for AI coding agents that people run with **bypass all permissions**: the agent keeps its
speed, and the human keeps the helm.

> **Status: 0.2.0, early.** Enforcement works on Claude Code today. Codex, Antigravity/Gemini and Cursor read the
> rules but are not yet enforced by a hook (adapters planned). Read [Honest limits](#honest-limits) before relying on it.

## What it does

| | What you get | How |
| :-: | :-- | :-- |
| 🛑 | Dangerous actions are **blocked, not just discouraged** | A fail-closed hook judges every tool call: recursive deletes, `git push --force`, `git reset --hard`, registry and firewall changes, download-into-shell, uploads, secret files, schedules, edits to the guard itself |
| 📜 | Scripts are judged like typed commands | `.sh` `.ps1` `.bat` files, `package.json` scripts, Python and Node.js files are read **before** they run |
| 🔑 | Secrets stay out of git | `git commit` is checked against the staged diff (AWS, GitHub, private keys, passwords in URLs, `.env`); the value is never printed |
| ✋ | You decide at every turning point | The agent offers 2–4 options with a **cost level** and waits. A blocked action gets an id; only *you* can approve it, from *your* terminal, once, for that exact input (SHA-256) |
| 💸 | No surprise costs | Cost = permission levels: **L0** read → **L1** headless run → **L2** open an app → **L3** network / install / schedule. Cheapest level first |
| 🗑️ | Nothing is lost | "Delete" is a restorable trash with a SHA-256 manifest; files outside the sandbox are backed up before every edit; ADRs and postmortems are never deleted |
| 📝 | Every turn leaves a trail | 12 record templates (request, gate, report, ADR, hand-off, postmortem, risk…), a machine log of every block, approval and app launch |
| 🧠 | Agent memory is watched | Memory writes are logged and backed up; a note like "approve automatically next time" needs your approval, and so do global agent config files |
| 📱 | You are told | High-risk blocks send a desktop notification or a phone push (ntfy) carrying only risk, project and id — never your data |
| 🧭 | It grows with you | Packs describe a piece of software to the guard (Python and Node.js ship in the core); your own workflows live in `.keel/local/` and are never overwritten by updates |

## Install (2 minutes)

Requires **Python 3.11+** and git. Keel uses the standard library only and never installs anything for you.

```bash
git clone https://github.com/<you>/<repo>.git
```

```bash
python <repo>/install.py --target "C:/path/to/your/project" --dry
```

```bash
python <repo>/install.py --target "C:/path/to/your/project"
```

The installer shows its plan and asks before writing. It **keeps your existing** `AGENTS.md` / `CLAUDE.md` /
`GEMINI.md` (it appends one marked pointer block) and your existing hooks.

**Then do the live check** — the one thing only you can verify: start your agent in bypass mode in that project and ask it to run

```text
rm -rf sandbox/keel-live-check
```

You must see `KEEL BLOCKED`. If the command runs, Keel is not protecting you — stop and open an issue.

## When the guard blocks something

```text
KEEL BLOCKED [HIGH] K-3f9a1c2e
- git-force: force/delete push rewrites shared history
```

The agent must stop and show you a GATE (what · why · risk · cost · options · rollback). If you agree, in **your own** terminal:

```bash
python .keel/engine/cli.py approve K-3f9a1c2e
```

| Command | Who | What |
| :-- | :-: | :-- |
| `status` · `pending` · `scan` | anyone | state, waiting approvals, dangerous calls in pack files |
| `approve K-…` · `deny K-…` | **you only** | one use, exact input, 30 minutes |
| `trash <path> --reason "…"` · `restore <id>` · `archive <path>` | anyone | soft delete, undo, long-term archive |
| `trust <file>` · `untrust <file>` | **you only** | stop asking about a script you reviewed — until one byte of it changes |
| `stop "reason"` / `resume` | anyone / **you only** | emergency brake: block every write |
| `empty-trash` | **you only** | hard delete, typed confirmation |
| `selftest` · `notify-test` | anyone | check the rules and your notification channel |

## What gets installed

```
your-project/
├── AGENTS.md  CLAUDE.md  GEMINI.md     ← your rules, plus one pointer block
├── sandbox/  reports/  docs/decisions/  ← green zone: experiments, reports, ADRs
└── .keel/
    ├── KEEL.md  rules/  templates/      ← the rules the agent reads (protected from the agent)
    ├── engine/                          ← the guard: Python, stdlib only, fail-closed
    ├── keel.toml                        ← zones, limits, trusted hosts, model tiers — you edit, the agent cannot
    ├── packs/<software>/                ← what the guard knows about a tool (python, node, …)
    ├── local/                           ← YOUR workflows and settings — updates never touch it
    └── state/                           ← logs, approvals, backups, trash (git-ignored)
```

## Honest limits

- **A seatbelt, not a sandbox.** Commands are read heuristically. Code is checked only in languages Keel can read
  (shell, PowerShell, batch, `package.json` scripts, Python, Node.js; MATLAB in Keel Pro); imported modules are
  not followed. Run untrusted code in a VM.
- **One platform enforced so far.** Claude Code. The others get the rules as text only.
- **The bypass guarantee is yours to confirm.** Claude Code's docs say hooks run before every tool call; that a deny
  holds under `bypassPermissions` is implied, not stated — hence the live check.
- **False alarms cost one approval; that is the trade.** The guard fails closed: when it cannot parse something, it asks.

What is covered, how, which test proves it, and what is not: **[docs/RISK_REGISTER.md](docs/RISK_REGISTER.md)**
— 19 risks traced loss → unsafe action → rule → gate → test, mapped to the OWASP Top 10 for Agentic Applications (2026).

## Documentation

| | |
| :-- | :-- |
| [Getting started](docs/en/getting-started.md) · [Bắt đầu (Tiếng Việt)](docs/vi/bat-dau.md) | install, notifications, approvals |
| [Risk register](docs/RISK_REGISTER.md) | coverage, evidence, known gaps |
| [Design spec](docs/specs/2026-11-11-keel-design.md) · [Decisions (ADR)](docs/adr/README.md) | why it is built this way |
| [Roadmap](docs/ROADMAP.md) | what is next |

## Development

```bash
python -X utf8 -m unittest discover -s tests
```

72 tests. Every guard rule needs a test, and a row in the risk register that names it — a test fails if the register
names a test that does not exist.

## Keel Pro

Paid add-ons in a private repository: software packs (MATLAB first: seven workflows from intake to report, a `.m`
code scanner, a demo project) and an interview that turns your own way of working into workflows.

## Licence

Apache-2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
