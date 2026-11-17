# ADR-0010 — Judge what an action does to the protected thing, not how it is written

- Status: Accepted · 2026-11-17 · **amends [ADR-0007](0007-coexist-trust-model-hint.md)** (trust by SHA) for light mode, extends [ADR-0009](0009-light-mode-and-workflow-capture.md)
- Decided by: the owner (verbatim: *"Cả A, B, C"*), after a review of the research vault's audit log

## Context
The owner was studying *Schrems v Meta*. Two Vienna courts read Meta's terms and found for Meta: the terms said
personalised ads were part of the service, and the user had signed. The Austrian Supreme Court (6 Ob 189/24y, 2025)
ignored the wording and asked whom the processing served: *"The fact that such processing is mentioned in the
contract or is merely useful for its performance is irrelevant in itself."*

Applied to Outrigger: after light mode, the vault still had 22 blocks in two days (16–17 Nov 2026). Most matched
a *form*, not the *purpose* of the rule:

| Block | Count | The guard checked | What the rule protects |
| :-- | --: | :-- | :-- |
| write to the owner's read-only originals folder (reported as `outrigger-self`) | 9 | the path is in `protected` | bytes of originals that **exist**; most writes created a **new** transcript |
| `pack-danger` on the project's own tools | 7 | the script contains `os.remove`, `subprocess` … | dangerous calls the human has **not** seen; a one-line edit dropped the whole trust |
| `self-approval` | 2 | the text `cli.py trust` | one was `trust --help` |

Also found: a read-only `diff` of two engines was blocked as high risk (`diff` was not a read-only command), and
**`cp`/`mv`/`tee`/`sed -i` into a protected path were not checked at all** — only `>` redirects were.

## Options
| Option | Gain | Lose |
| :-- | :-- | :-- |
| **A · append-only `originals` zone** | 9 of 22 blocks; closes the `cp`/`mv` gap | must not let an overwrite pass as a create |
| **B · diff-scoped trust (light mode)** | no repeat questions for the project's own tools | an old call can change meaning through a variable on another line (R-25) |
| **C · fix form-based false positives** | cheap | small count |
| Keep the list-based tests | nothing to build | the guard keeps asking for things that cannot hurt, and gets approved unread |

## Decision
All three. One principle for all of them: **the engine judges necessity on facts it observes itself — whether a
file exists, what a diff adds — never on a reason the agent writes.** Letting the agent assert that it needs to act
is letting the drafter of the contract grade it.

1. **A.** `[zones] originals = [...]`. A create tool (`Write`, `write_file`, `create_file`, `apply_patch` *Add File*)
   on a path that does not exist → low, `original-added`, content hash logged. Anything else → high,
   `original-protected`. Shell commands that write (`cp`/`copy`/`robocopy`/`install`/`ln` target, `mv`/`ren` source
   and target, `tee`/`touch`/`set-content`/… , `sed -i`) into `protected` or `originals` → high, `write-protected`.
   `cd` is followed between segments so relative paths are judged where they run.
2. **B.** `cli.py trust` stores `{sha, danger}`: the full text of every dangerous line. In **light** mode an edited
   trusted script asks only for dangerous lines not in the snapshot (counted); a run with no new line is logged
   `trusted-drift`. Strict mode and 0.3.0 hash-only entries keep whole-file hashing.
3. **C.** `cli.py <human-only> --help|-h` passes when the flag is its own token in every such segment; owner-added
   `protected` paths report `protected-path` (guard files keep `outrigger-self`); `diff`, `cmp`, `comm`, `fc`,
   `compare-object`, `sha256sum`, `md5sum`, `get-filehash` are read-only.

## Consequences
- 18 tests in `PurposeNotForm`; risk rows R-25 and R-26; 114 tests pass.
- Installs must re-run `cli.py trust` once to get a snapshot; until then trust works as before.
- A command that `cp`s into a protected path now stops where it used to pass. This is intended.
- Open: version bump to 0.3.1 and the CHANGELOG are left to the release step.

## Revisit when
- An original changes without a block → drop A for that install, return to `protected`.
- A drift-trusted script causes harm → drop B; R-25 becomes the post-mortem.
