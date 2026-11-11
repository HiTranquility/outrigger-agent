# ⚓ Keel

**Let your AI agent sail at full speed — without capsizing.**
*Cho AI agent chạy hết tốc lực mà không lật thuyền.* · [Tiếng Việt](docs/vi/bat-dau.md)

A keel is what lets a sailboat carry full sail in strong wind and stay upright.
Keel does the same for coding agents (Claude Code today; Codex, Antigravity, Cursor next) that people run with
**bypass all permissions**:

| You get | How |
| :-- | :-- |
| 🛑 Dangerous actions are **blocked, not just discouraged** | a fail-closed guard hook checks every tool call: recursive deletes, `git push --force`, registry/firewall, download-into-shell, uploads, secret files, schedules, edits to Keel itself |
| 📱 You are told | high-risk blocks send a Windows notification or a phone push (ntfy) — only risk, project and an id, never your data |
| ✋ You decide at every turning point | the agent must offer 2–4 options with a **cost level** (L0 read → L1 headless → L2 open app → L3 network/install) and wait; blocked actions need *your* approval from *your* terminal |
| 🗑️ Nothing is lost | "delete" = restorable trash with SHA-256 manifest; edits outside the sandbox are backed up first; ADRs are never deleted |
| 📝 Every turn leaves a trail | report template, ADR for every decision, machine log of every block and every app opened |
| 🧭 Your own workflows | packs (MATLAB first) and an interview that builds workflows for *your* work; updates never overwrite them |

## Install (2 minutes)

Requires Python 3.11+ (Keel never installs anything for you).

```bash
python install.py --target "C:/path/to/your/project" --dry
```

```bash
python install.py --target "C:/path/to/your/project"
```

Then do the **live check** printed at the end (ask the agent to `rm -rf sandbox/keel-live-check` in bypass mode — you must see `KEEL BLOCKED`).

## When the guard blocks something

```text
KEEL BLOCKED [HIGH] K-3f9a1c2e
- git-force: force/delete push rewrites shared history
```

Read the agent's GATE question. If you agree, run in **your own** terminal:

```bash
python .keel/engine/cli.py approve K-3f9a1c2e
```

The approval is bound to that exact action (SHA-256), used once, expires in 30 minutes. The agent cannot approve itself.

## Layout after install

```
your-project/
├── AGENTS.md  CLAUDE.md  GEMINI.md     ← rules (one source: AGENTS.md)
├── sandbox/  reports/  docs/decisions/  ← green zone: experiments, reports, ADRs
├── STOP                                  ← (only when you pull the brake)
└── .keel/
    ├── rules/  templates/                ← details the agent reads on demand
    ├── engine/                           ← the guard (Python, stdlib only)
    ├── keel.toml                         ← zones, limits, trusted hosts — you edit, the agent cannot
    ├── packs/<software>/                 ← Keel Pro packs (MATLAB, …)
    ├── local/                            ← YOUR workflows and settings — updates never touch it
    └── state/                            ← logs, approvals, backups, trash (git-ignored)
```

## Honest limits

- Keel is a **seatbelt, not a sandbox**. It reads commands heuristically; a script that deletes files when run is
  only caught if Keel can read that language (core: shell, PowerShell, batch, `package.json` scripts, Python, Node.js;
  Pro: MATLAB `.m`). Imported modules are not followed. Run untrusted code in a VM.
- What is covered, how, which test proves it, and what is not covered: [docs/RISK_REGISTER.md](docs/RISK_REGISTER.md)
  (mapped to the OWASP Top 10 for Agentic Applications 2026).
- Claude Code docs say hooks run before every tool call; that a deny holds in `bypassPermissions` is implied, not
  stated — hence the live check.

## Keel Pro

Software packs (MATLAB: 7 workflows from intake to report, code scanner, demo project), the workflow-builder
interview and updates. Research (NCKH) pack and Codex/Antigravity/Cursor adapters in release 2.

## Licence

Apache-2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE). Design decisions: [docs/adr](docs/adr/README.md).
