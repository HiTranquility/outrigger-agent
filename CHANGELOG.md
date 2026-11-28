# Changelog

All notable changes to the Outrigger core. Decisions behind each change live in [`docs/adr/`](docs/adr/README.md);
the risks each rule answers live in [`docs/RISK_REGISTER.md`](docs/RISK_REGISTER.md). Vietnamese notes for users:
[`docs/vi/bat-dau.md`](docs/vi/bat-dau.md).

## 0.7.0 — 2026-11-28

- **First run asks once** (ADR-0016): until `.outrigger/state/onboarded.json` exists, session start prints
  `OUTRIGGER FIRST RUN` and the agent asks the user one question (import workflows or start empty);
  `cli.py onboard [--done "<answer>"]`.
- **Personal workflow library** `~/.outrigger/library/workflows/` (or `$OUTRIGGER_HOME`): no library = new machine.
  `cli.py import <library|folder>` copies into `drafts/` as drafts and skips text aimed at an agent;
  `cli.py export <name> [--replace]` copies a promoted workflow into the library and **asks, in light mode too**,
  like every other write into the library (`library-export`, `library-write`).
- **Only the user promotes a workflow**: the agent writing or moving a file into `.outrigger/local/workflows/`
  outside `drafts/` asks (`workflow-promote`).
- **Fixed:** a command that must ask in light mode (`agent-config`, `library-write`, …) no longer passes when it sits
  inside a script the agent runs (`script:<code>`).
- **Fixed (R-36):** a command long enough to make the guard outlast the hook timeout ran. The hook now judges in a
  child process and denies when its 20 s budget runs out (about 0.1 s more per call); the slow check is linear; a
  shell command over 256,000 characters asks.
- **Fixed (R-35):** a command hidden in an option (`git -c core.pager=…`, `tar --checkpoint-action=exec=…`,
  `--to-command`, `-I`, `zip -TT`) or behind a variable set earlier in the same command (`D=~; rm -rf $D`) ran
  unjudged; it is now judged like a typed command.
- **Fixed:** `cd` with no folder (home), `cd -P`/`--` and `Set-Location -Path` were followed to the wrong folder by
  every rule that follows `cd`.
- **Structure gate (ADR-0015 gaps closed):** a new minified file over 2 MB asks; `git add a.py && git commit`
  counts only what it adds; `GIT_DIR=` / `--git-dir` without `--work-tree` on a commit fails closed.
- Engine: `selftest.py` and `gitrules.py` split out of `cli.py` and `rules.py` (both were over 400 lines).
- Paths: PowerShell `$env:VAR` is expanded; Git Bash `/tmp` is `%TEMP%`; on Windows a trailing dot or space in a folder name no longer hides it.
- **Fixed (R-34):** `cp`/`mv`/`tee`/`Copy-Item` into a folder outside the project was not judged.

## 0.6.0 — 2026-11-28

- **Records in month folders** (ADR-0015): numbered records go into `MM-YYYY/`; an ISSUE is a folder (`issue.md` +
  `phase/`, `review/`, `handoff/`, `evidence/`); new templates `ISSUE.md`, `PHASE.md`.
- **`cli.py next-id <TYPE>`**: counts month folders and every local or remote branch, warns when one number has two
  slugs.
- **Opt-in structure gate** (ADR-0015): `git commit` asks, in light mode too, when a new file goes over 400 lines,
  10 `useState` or 6 constructor parameters, or a file in the baseline grows. `cli.py structure --seed` (human only),
  `--update` (only lowers). Off until `[structure] enabled = true`.
- **Fixed (R-32):** git global options (`-C`, `-c`, `--git-dir`, `--work-tree`) hid the subcommand from every git rule
  (force push, `reset --hard`, the secret scan); `git add x && git commit` let a secret through because the hook runs
  before `git add`. Found by an independent review (3 rounds) of this release.
- Engine: `rules.py` split into `common`, `quarantine`, `packrules`, `scripts` (no behaviour change).

## 0.5.0 — 2026-11-21

- A pack can list commands that must always be asked about (`[[ask]]` in `pack.toml`, ADR-0014): schema migrations,
  data drops — asked in light mode too, inside scripts and npm scripts, never a standing rule.

## 0.4.1

- A pack can make opening its app ask in light mode too (`gui_always_ask`, ADR-0013) — licence seats.

## 0.4.0

- `cli.py recon`: read someone else's repository in a quarantine zone; nothing in it may run; text aimed at the agent
  in what a tool returns is flagged (ADR-0012).

## 0.3.x

- 0.3.5 · 0.3.4 · 0.3.3: fewer false blocks — substitutions found the way bash finds them, heredoc bodies are data,
  a `>` inside a quoted pattern is not a redirect.
- 0.3.2: standing rules learned from the human's approvals; accept is human-only; they expire (ADR-0011).
- 0.3.1: append-only `originals` zone; judge purpose, not form; diff-scoped trust (ADR-0010).
- 0.3.0: light mode (only high risk and a short list stop), workflow capture from the trace log (ADR-0009).

## 0.2.0

- Scripts are read before they run (`.sh`, `.ps1`, `.bat`, `package.json`, Python, Node.js); secrets are checked on
  `git commit`; agent memory and global agent config are guarded; `cli.py trust`. Renamed from Keel to Outrigger
  (ADR-0008).

## 0.1.0

- Rules, fail-closed Python guard, Claude Code adapter, soft delete, record templates.
