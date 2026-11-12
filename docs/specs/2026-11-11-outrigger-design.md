# Outrigger — design spec (v0.1, approved in chat 2026-11-11)

> Status: **approved by the owner in conversation, section by section**. This file records what was decided;
> each decision with alternatives has an ADR in [`../adr/`](../adr/).

## 1. Purpose

Outrigger is a **rules + guard kit for AI coding agents** that people run with *bypass all permissions*.
The agent may go at full speed; Outrigger keeps it from capsizing:

- the human always decides at turning points (gates);
- dangerous actions are **enforced** by a guard hook, not just written in Markdown;
- every piece of work leaves a record (report, ADR, logs);
- buyers can build **their own workflows** per software (MATLAB first) through an interview, and
  updates never overwrite what they built.

Success = a buyer installs Outrigger into a project, runs an agent in bypass mode, and
(1) `rm -rf`, secret reads, schedules, unknown downloads are blocked and the phone is notified,
(2) the agent proposes options with cost levels before opening MATLAB,
(3) every turn leaves a Markdown trail.

## 2. Product shape (ADR-0001)

| Repo | Licence | Contents |
| :-- | :-- | :-- |
| `outrigger-agent` (public) | Apache-2.0 | rules (`AGENTS.md`, `.outrigger/rules`), templates, guard engine, Claude Code adapter, installer |
| `outrigger-agent-pro` (private, paid) | commercial EULA | software packs (`packs/matlab`), `builder/` interview, demo projects |

## 3. Multi-platform (ADR-0002)

`AGENTS.md` is the single source of rules (< 32 KiB because Codex truncates there).
`CLAUDE.md` = `@AGENTS.md`; `GEMINI.md` points to it. All four target platforms have a blocking
pre-tool hook (Claude Code, Codex, Antigravity CLI — which replaced Gemini CLI on 2026-06-18 —, Cursor),
so enforcement lives in **one engine** with a thin adapter per platform.
**Release 1 ships the Claude Code adapter only.**

## 4. Guard engine (ADR-0003)

- Python ≥ 3.11 (stdlib only; `tomllib` for config). No third-party dependency.
- **Fail-closed:** any internal error → deny. (IPLMS's guard fails open; Outrigger deliberately does not.)
- Approval cannot come from the agent: a blocked action gets an id `OR-xxxxxxxx`; only the human,
  in their own terminal, runs `python .outrigger/engine/cli.py approve OR-…`. The id is the SHA-256 of the
  exact tool input, so changing one character needs a new approval (idea from IPLMS `audit_gate.py`).
- The guard blocks any agent command that touches `.outrigger/engine`, `.outrigger/outrigger.toml`, `.outrigger/state`,
  hook settings or `.mcp.json`, and any attempt to run `approve`, `resume` or `empty-trash`.

### 4.1 Levels

| Cost / permission level | Meaning | Gate |
| :-: | :-- | :-- |
| L0 | read, think | none |
| L1 | headless run (`matlab -batch`, tests) | log; scan code first |
| L2 | open an interactive app (MATLAB desktop, Simulink) | approval + app log |
| L3 | network, hardware, install, schedule | approval + ADR |

| Risk | Examples | Guard |
| :-: | :-- | :-- |
| high | `rm -rf` outside project, `git push --force`, registry, firewall, `curl … \| sh`, secrets, uploads, schedules, self-approval | deny + phone notification + approval |
| medium | open GUI app, unknown host, installs, bulk edits, deleting (use trash) | deny + approval |
| low | reads, headless tests, edits in project | allow + log (+ backup in yellow zone) |

### 4.2 Zones (`.outrigger/outrigger.toml`)

green (agent writes freely) · yellow (default: backed up before every edit) · red (secrets — blocked) ·
protected (Outrigger's own files — blocked) · never_delete (ADRs, logs).

### 4.3 Deleting, archiving, scheduling

- Delete = **soft delete** to `.outrigger/state/trash/<stamp>/` with a manifest (path, SHA-256, size, reason).
  `restore` puts it back. Bulk (> 20 files or > 100 MB) needs approval. Hard delete (`empty-trash`) is
  human-only with a typed confirmation.
- Archive = move to `archive/<YYYY-MM>/` with manifest.
- Creating/changing OS or agent schedules = high risk. Kill switch: a `STOP` file at the project root
  blocks every non-read tool until the human runs `resume`.

### 4.4 Notifications

Pluggable: `toast` (Windows, default), `ntfy` (opt-in, self-hostable), `none`. A message carries only
risk level, project name and approval id — never code, paths or data.

### 4.5 Packs

A pack (`.outrigger/packs/<id>/pack.toml`) tells the engine which commands launch its software, which flag
means headless, which file extensions to scan and which patterns are dangerous. The engine has no
MATLAB knowledge of its own — a future LabVIEW or Python-sim pack is just another `pack.toml`.

## 5. Records

Agent-facing files are English (token cost, Codex limit); human docs are bilingual in `docs/en`,
`docs/vi`; the agent answers in the user's language (ADR-0004). Record types: GATE question,
REPORT (every work turn), ADR (every decision with alternatives; never deleted, only superseded),
SPIKE (safe probe of an unknown task), WORKFLOW (user-approved or AI-drafted), BUG.

## 6. Scope of release 1 (ADR-0005)

core rules + templates + guard + Claude Code adapter + installer + selftest (public);
MATLAB pack MAT-01…07 + builder interview + demo project (pro).
Release 2: research (NCKH) pack, Codex / Antigravity / Cursor adapters, output filter for token saving.

## 7. Known limits (stated to buyers)

- Outrigger is a **seatbelt, not a sandbox**: it reads commands heuristically. A script file that deletes
  things when run is only caught if its language has a pack scanner (e.g. `.m`).
- Whether a deny holds under `bypassPermissions` is implied, not stated, by Claude Code docs →
  `selftest` prints a live check the buyer must run once.
