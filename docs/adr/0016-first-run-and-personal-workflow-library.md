# ADR-0016 — First run in a project, and a personal workflow library that follows the user

- Status: Accepted · 2026-11-28 · amends [ADR-0009](0009-light-mode-and-workflow-capture.md) (two more codes that ask in light mode)
- Decided by: the owner. The question, verbatim: *"logic vừa nếu cài đặt tinh khôi, chưa có gì phải luôn hỏi người
  dùng, làm sao biết đó là máy mới hoặc làm sao để import quy trình vô á, ở đâu"*; the choice *"B nha"*, then
  *"Làm đi"*.

## Context
Up to 0.6.0 an install ran straight away and asked nothing. The workflows a user had built in one project (their own
`.outrigger/local/workflows/`) could only reach another project by hand-copying files, and nothing told the agent
that this was the first session in a project or on a machine. The only interview for building workflows is the Pro
builder. Copying workflows is also a supply-chain path: a workflow is text the agent follows, so a poisoned one is an
instruction injected into every project that takes it.

## Options
| Option | Gain | Lose |
| :-- | :-- | :-- |
| A · Project level only: first-run question + `cli.py import <path>` | Small, nothing written outside the project | Cannot tell a new machine; every import names a folder by hand |
| **B · A + a personal library (`~/.outrigger/library/`) and `cli.py export`** | Workflows follow the user; "new machine" = no library; one folder to sync | A store outside the project that every project reads, so writes to it must be guarded |
| C · Leave it to the Pro builder; core only prints the question | Core unchanged | Every core user hand-copies workflows |

## Decision
**B.**
1. **New project** = no `.outrigger/state/onboarded.json` (protected, git-ignored, so a fresh clone asks again). The
   session-start hook prints `OUTRIGGER FIRST RUN`; the rules make the agent ask the user **one** question before any
   other work, then record the answer with `cli.py onboard --done "<answer>"`.
2. **New machine** = no `<home>/library/` (home is `$OUTRIGGER_HOME`, default `~/.outrigger/`). Workflows live in
   `<home>/library/workflows/*.md`; moving machines is copying or syncing that folder.
3. `cli.py import <library | project folder | folder>` copies top-level `*.md` workflows into this project's
   `drafts/`, rewrites `status: draft`, clears `approved_by`, adds `imported_from`, never overwrites, refuses odd file
   names, symlinks and files over 256 KB, and **skips** any file with text aimed at an agent (the recon content check,
   ADR-0012). A repository is imported by `cli.py recon <url>` first, then `import` from the quarantine folder. Import
   writes only inside `drafts/`, so it needs no approval.
4. `cli.py export <name…> [--replace]` copies a **promoted** workflow (not a draft, no text aimed at an agent) into the
   library; a different version already there needs `--replace` and goes to `library/.history/`.
5. The guard treats the library as its own outside zone `[zones] library`. `export` → `library-export` (matched on
   the whole command, so `cd .outrigger/engine && python cli.py export` asks too); any other write into it
   (`Write`/`Edit`, redirect, `cp`/`mv`/`tee`/`Copy-Item`) → `library-write`, and so does **any** command that is not
   read-only and names the library anywhere in its text (a path token, `OUTRIGGER_HOME`, `.outrigger…library` in
   `python -c` or a heredoc, a link made with `ln`/`mklink`). Both are medium and **ask in light mode too**: one
   approval reaches every project.
6. Only the user promotes a workflow: writing or moving a file into `.outrigger/local/workflows/` outside `drafts/`
   → `workflow-promote` (medium, asks in light mode too), so "export takes promoted workflows only" means the user
   promoted them. `import` refuses to write through a `drafts/` that is a link or junction.

## Consequences
- Building 0.7.0 found that `cp`/`mv`/`tee` into a folder outside the project was not judged at all (only redirects
  and edit tools were); copy-like commands now give `write-outside` / `agent-config` / `library-write` like the other
  write paths (R-34).
- Review round 1 (NOT PASS) found: `export` by bare `cli.py` name ran unasked (P0); a junction at `drafts/` made
  `import` write into the library; `--target-directory=`, `$env:VAR`, `~/.outrigger./` (Windows drops the dot),
  `tar -C`, `unzip -d`, `curl -o`, `git clone`, `python -c` reached the library unjudged; the agent could promote its
  own drafts; the source folder name went unscanned into `imported_from:`; `cp x /dev/null` and `/tmp` were flagged.
  All fixed with regression tests (`ReviewRound1`).
- Review round 2 (NOT PASS): a light-mode "still ask" code found inside a script (`script:library-write`, and the
  older `script:agent-config`) was let through; `cd ~/.outrigger && …` and `D=~/.outrigger; … $D/library` hid the
  library; `git mv`/`git restore`, `tar -C`, `cp -r … .outrigger/local/` and trashing `.outrigger/local` promoted
  workflows; the whole-command text match asked on `git commit -m "…library"`, test runs and copies *from* the
  library. Fixed: the light-mode check strips the `script:` prefix for every code; `cd` and earlier shell
  assignments are followed; the text match is applied only to code given to an interpreter (`-c`, `-e`, heredoc) and
  to writers that are not destination-aware (`tar`, `mkdir`, `ln`, `mklink`, `New-Item`, `[IO.File]`); Git Bash
  `/tmp` maps to `%TEMP%`.
- Review round 3 (NOT PASS, one P1): `cd` was read as "first argument = folder", so a bare `cd` (home), `cd -P`,
  `cd --` and `Set-Location -Path` were followed wrongly — for every rule that follows `cd`, not only the library.
  Fixed in one place (`common.cd_target`) and used by all of them. Left as known gaps (P2/P3), all still behind
  "import lands as a draft": `… | xargs touch <library path>`, `env -C <library> …`, `git -C <workflows> mv …`,
  `mklink` into `.outrigger/local`, `git apply` of a patch that adds a promoted workflow, `python -c` writing a
  promoted workflow; and asks that are not needed: `pytest -k outrigger_home`, code that only reads
  `OUTRIGGER_HOME`, archives made *from* the library, `cd ~/.outrigger && git status`.
- Closed before release (`Followups`, `StructureFollowups`): `| xargs`, `env -C`, `git -C … mv`, `git apply`
  of a patch that adds a promoted workflow, `mklink`/`New-Item -ItemType Junction` into `.outrigger/local`, and
  `python -c` writing a promoted workflow now ask; `pytest -k outrigger_home`, code that only reads the variable,
  archives made *from* the library, read-only git in the library and `git commit -m "~/.outrigger/…"` no longer ask.
  The three P3 gaps ADR-0015 left open are closed too: a new file over 2 MB that is one minified line asks;
  `git add a.py && git commit` counts only the files it adds (`.`, globs, folders and `-A` still count everything);
  `GIT_DIR=`/`GIT_WORK_TREE=`/`GIT_INDEX_FILE=` or `--git-dir` without `--work-tree` on a commit fails closed when
  the gate is on. Engine files are back under the 400-line limit (`selftest.py`, `gitrules.py` split out).
- Review round 5 (NOT PASS) on those follow-ups: narrowing reopened writes — `git config --file`, `git … --output=`
  and `git -C <library> config|add|fetch|tag` were exempt as "read-only git"; `tar cf`, `zip --out`/`-O` and
  `7z -o` hid their output. Rule kept since: **an exemption falls back to the general rule whenever it cannot be
  sure** (archive output not found → judge every argument; read-only git exempts only the folder it runs in, never
  its arguments). Also fixed: `--remove-files`/`zip -m`/`-sdel` (they delete what they pack), `printenv … | xargs`,
  `env:OUTRIGGER_HOME`, `'wt'`/`touch` as write words, `.outrigger/./local`, `cd .outrigger/local && python -c …`,
  and `git add` with braces, variables or `-f` (`ReviewRound5`, `StructureFollowups`).
- Review round 6 (NOT PASS): a command hidden in an option value — `tar --checkpoint-action=exec=…`,
  `--to-command`, `-I "tee …"`, zip `-TT "…"`, `git -c core.pager|alias|sshCommand|diff.external="…"` — reached the
  library. Option values that hold a command line (whitespace or `!`) and every `-c`/`--config-env` value are now
  text-checked; `--remove…` abbreviations, bundled zip `-rm`, and repeated tar `-f` are handled (`ReviewRound6`).
- Review round 7 (NOT PASS): a variable set earlier in the same command (`D=~/.outrigger/library; cp a $D/`)
  hid the path from every rule — older than this branch. And the general hole behind round 6: `git -c
  core.pager='rm -rf ~' log`, `tar --checkpoint-action=exec='rm -rf ~'`, `zip -TT 'rm -rf ~'` ran with no finding
  at all. Both fixed in one place, `libguard.hidden_commands`: the command is judged again with its `X=value`
  assignments filled in, and every command line a tool will run from an option (tar `--checkpoint-action=exec`,
  `--to-command`, `-I`/`--use-compress-program`, `--rsh-command`, `-F`; zip `-TT`/`--unzip-command`; git `-c` /
  `--config-env` for pager, editor, sshCommand, fsmonitor, aliases with `!`, `*.command`, drivers…) is judged like a
  typed command, script files included (R-35, `ReviewRound7`).
- Review round 8 (NOT PASS, one P0): **time is a way through.** A regex with a look-ahead re-scanned the command
  from every position; `rm -rf ~ #` + 90 KB of padding took 50 s, and a hook that outlasts Claude Code's 30 s
  timeout lets the tool run. Fixed three ways: the check is linear and runs only when the gate is on; `rel()`
  resolves each distinct path once; and the pre-tool hook has its own **20 s budget** — when it runs out the call is
  denied (exit 2), so slowness fails closed like any other error (R-36). Also: an assignment value is one whole
  shell word (`D="$HOME"/.outrigger/…`); variables that git or a pager run (`GIT_PAGER`, `GIT_SSH_COMMAND`,
  `GIT_EXTERNAL_DIFF`, `EDITOR`, `PAGER`, `VISUAL`, `GIT_CONFIG_KEY_n`/`VALUE_n`, `GIT_CONFIG_PARAMETERS`) are judged
  as commands; chains of assignments resolve up to 8 steps; hidden commands follow `cd` (`ReviewRound8`).
- Review round 9 (NOT PASS, P0 still open): the thread timer cannot fire while one long regex holds the GIL —
  `rm -rf ~ #` + `curl ` × 90,000 ran 119 s (the pipe-to-shell pattern, older than 0.7.0, was quadratic). Fixed for
  real: the pre-tool hook now **judges in a child process** and the parent waits with an OS timeout (20 s), so no
  input can keep the hook past the host's limit; the parent loads no engine code, which keeps the cost of the extra
  process to about 0.1 s per call. The pipe-to-shell check is linear, and a shell command over 256,000 characters
  asks without being judged (`command-too-long`, asked in light mode too). Also: `D+=…` appends to the earlier
  value; a variable a tool writes a file to (`GIT_TRACE*`, `GIT_INDEX_FILE`, `HISTFILE`, `*_FILE`, `*_LOG`…) is
  judged as a write; `GIT_CONFIG_PARAMETERS` in both quoting forms; `GIT_SSH_COMMAND="ssh -i key"` no longer
  blocks (`ReviewRound9`).
- Review round 10 (NOT PASS, one P1): a bash array `A=(<library>)` hid the path. Arrays now give their first
  element, and **any** variable whose value lands in the library or a promoted folder asks when a command that is not
  read-only follows (`HOME=…`, `TMPDIR=…`, `XDG_CONFIG_HOME=…` point a tool's folders there) (`ReviewRound10`).
- Still open (P2/P3, all behind "import lands as a draft"): a script or config file named in an exec option or
  variable (`GIT_SSH=s.sh`, `ssh -F cfg`, `core.hooksPath=dir`) is not read; `BROWSER`, `LESSOPEN` under `less`,
  `PROMPT_COMMAND`, `BASH_ENV`, `PYTHONSTARTUP`, ANSI-C quoting `$'\x7e…'` and `${!E}` indirection; `pushd` with
  no folder; a heredoc over 256 KB asks. Asks that are not needed, kept on purpose (narrowing reopened holes
  twice): a variable pointing into the library or a promoted folder followed by any writing command, even when the
  command only reads from it (`D=<library>; cp $D/x.md sandbox/`). Review round 11: PASS.
- **Design limit, accepted:** the write side is best effort. A path assembled at run time from pieces that never spell
  the library (`'~/.outrig'+'ger'`), or written by a `.py` script the guard does not read for paths, is not seen
  (G-5). The library is therefore defended where it is **read**: every import is a draft the user must promote.
- Not covered: a workflow that misleads in plain language (G-7 applies to the library too) — every import lands as a
  draft and the user promotes it; a user who edits the library folder by hand; `OUTRIGGER_HOME` pointed into the
  project; a path built at run time from pieces that never spell `.outrigger…library` (G-5); `cd ~/.outrigger`
  followed by a relative write in the same command.
- `docs/RISK_REGISTER.md` R-33 traces the library to loss L-6 (the guard is weakened later, through text the agent follows).
