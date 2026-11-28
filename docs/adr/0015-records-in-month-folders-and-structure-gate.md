# ADR-0015 — Records in month folders, ISSUE as a folder, numbering across branches, and an opt-in structure gate

- Status: Accepted · 2026-11-28 · amends [ADR-0009](0009-light-mode-and-workflow-capture.md) (one more code that asks in light mode)
- Decided by: the owner. Verbatim: *"quy trình còn thiếu nhiều bộ chia folder ra sao … nhưng coi điều chỉnh phạm vi
  hay chuẩn hóa lại á"*, then the choice *"B: A + cổng cấu trúc"*.

## Context
Core 0.5.0 stored records flat (`docs/decisions/ADR-NNNN-*.md`, `reports/bugs/BUG-NNN-*.md`) and had no record for
work that spans several turns. The owner's own repositories (five of them) had already moved to month folders and to
an ISSUE that is a folder (`issue.md` + `phase/`, `review/`, `handoff/`, `evidence/`), because flat folders grow
without limit and a single ISSUE file has nowhere to put its phases. Numbering by "highest file + 1" also failed in
practice: a record created on an unmerged branch is invisible in the working tree, and two sessions took the same
number. Separately, the rules said nothing about how big a source file may get; in the owner's repositories files of
2,000–9,000 lines passed every gate because the gates checked import direction, not responsibility.

Scope boundary (ADR-0001): this is generic method, so it belongs in the open core. Workflows tied to one application
or domain — for example the screenshot-driven UI design workflow verified on the Aicomi project — stay in Pro packs.

## Options
| Option | Gain | Lose |
| :-- | :-- | :-- |
| A · Records only: month folders, ISSUE/PHASE, `cli.py next-id` | Small, no new guard rule | Source files may still grow without limit |
| **B · A + an opt-in structure gate on `git commit`** | Growth is stopped where it happens; reuses the light-mode "always ask" path | New engine code (≈ 240 lines) and a new protected file |
| C · Keep core flat; put the layout in a paid team pack | Core unchanged | Every user meets the duplicate-number and flat-folder problems; the fix is generic |

## Decision
**B.**
1. Numbered records go into `MM-YYYY/` of the month they were created. An ISSUE is a folder: only `issue.md` at its
   top; `phase/phase-N.md`, `review/review-N.md`, `handoff/`, `evidence/` below. Templates `ISSUE.md`, `PHASE.md`.
   Records written before 0.6.0 stay where they are.
2. `cli.py next-id <ADR|REQ|ISSUE|BUG|SPIKE|PM>` counts every file or folder named `<TYPE>-<NNN>-…` under `docs/`,
   `reports/`, `sandbox/spikes/` **and** every local or remote branch carrying `<TYPE>-<NNN>`; it warns when one
   number has two slugs.
3. Structure gate, off until the human switches it on (`[structure] enabled = true`). Limits per file: 400 lines,
   10 `useState` calls in a `.tsx`/`.jsx`, 6 constructor parameters (TS; C# classes, not records). Files already over
   a limit are recorded once by `cli.py structure --seed` (human only) in `.outrigger/local/structure-baseline.json`,
   a protected file. On `git commit` the guard judges the **staged** content of files in scope, and also the files on
   disk (the larger value wins) when the commit names paths, uses `-a`/`-i`/`-o`/`--pathspec-from-file`, or follows
   `git add`/`stage`/`mv`/`rm` in the same command; git's global options (`-C`, `-c`, `--git-dir`…) are skipped
   before reading the subcommand. A new file over a limit or a baseline file that grew → `structure-grow` (medium, asked in light mode too); a broken baseline →
   `structure-check-failed` (fail closed). `cli.py structure --update` (agent allowed) only lowers or removes entries.

## Consequences
- The guard runs `git diff --cached`, one `git ls-files -s` and one `git cat-file --batch` on each `git commit` when
  the gate is on; off, it costs nothing.
- Review of 0.6.0 also found that `git -C <dir> <sub>` hid the subcommand from **every** git rule (force push,
  `reset --hard`, the secret scan) and that `git add x && git commit` let a secret through because the hook runs
  before `git add`. Both are fixed in the same release (R-32).
- Tests, generated code, migrations, locales and build folders are excluded by default; projects can change
  `include`/`exclude` in `outrigger.toml` (human-edited).
- Not covered: C# partial classes split across files (the owner's sister repositories measure them; core does not
  yet), files committed with `--no-verify` style bypasses outside the agent, and edits by a human.
- Known gaps after review round 3 (P3, stricter or rare): a file over 2 MB is judged by its line count only, so a
  minified one-line file passes; `git add <one file> && git commit` counts every untracked file in scope (asks more
  than needed); `--git-dir=…` without `--work-tree`, and `GIT_DIR=`/`GIT_WORK_TREE=` set in front of the command, are
  measured in the wrong folder.
- `docs/RISK_REGISTER.md` R-30 traces the gate to loss L-5 (a wrong result is trusted: code nobody can review).
