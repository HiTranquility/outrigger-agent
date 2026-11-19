# ADR-0011 — Standing rules learned from the human's approvals

- Status: Accepted · 2026-11-19 · builds on [ADR-0009](0009-light-mode-and-workflow-capture.md) and [ADR-0010](0010-judge-purpose-not-form.md)
- Decided by: the owner, in the research vault (verbatim: *"thấy lệnh này nên làm thường xuyên (kiểu 3 lần trở lên) thì kêu người dùng kiểu oke chấp nhận làm đi"* — when an action is done often, three times or more, ask the user once to accept it for good)

## Context
A one-time approval is bound to the exact tool input (SHA-256), so the same kind of action — a push to the same
branch, the same package, files deleted from the same folder — is asked about again and again. Asking for
routine work trains the human to approve without reading (R-22).

## Options
| Option | Gain | Lose |
| :-- | :-- | :-- |
| **A · Learn a rule after N approvals; the human accepts it** | Repeats stop; the human still decides; no config editing | The signature must be narrow enough |
| B · Permissions declared by a workflow | Fits "record your workflows" | The guard cannot see which workflow runs — it would trust the agent's claim (ADR-0010 forbids) |
| C · Only count and print a config line | Cheapest | The human edits `outrigger.toml` each time |

## Decision
**A.**
1. On every block the engine computes a **signature** from what it sees, never from the agent's words:
   fetch → the site's domain (`cmu.edu`; shared hosting like `github.io` keeps the full host) · install → manager,
   verb and exact package list · `git push` → remote and branch · delete → the folder the files are directly in ·
   write outside → that folder · app / MCP → its name. Saved with the pending action and with the approval.
2. Only **medium** risk with **every** finding learnable gets a signature. High risk never does (the guard itself,
   secrets, originals, force-push, root deletes, schedules…); nor do scripts with dangerous calls — `trust`, bound
   to the file's bytes and its dangerous calls, is stricter than any pattern. Suggestions are computed again from
   the log and filtered by the same list, so a forged log line cannot propose a high-risk rule.
3. `suggest_after` (3) **distinct** approvals of a signature inside `window_days` (30) → a suggestion, shown at
   session start (the agent tells the user once) and after the third `approve`.
4. `cli.py rule accept L-…` — **human only**, like `approve`: it prints what the rule covers with real examples and
   asks `[y/N]`. Rules live in `.outrigger/state/rules.json` (guard-protected), expire after `ttl_days` (90), and
   every use is logged as `allowed-rule`. `rule list` and `rule drop` are open to the agent: dropping only tightens.
5. An action is let through by rules only when **every** signature is covered (`rm` + `pip install` needs both).

## Consequences
- Dry run on the research vault's real log (2026-11-19): approved fetches spread over 16 sites, at most 2 each,
  so research browsing never reached 3. In light mode those fetches already run unasked. The rules pay off on
  routine repeats — pushes, installs, deletes in one folder — and in strict mode.
- Approvals made before 0.3.2 have no signature; counting starts at the upgrade.
- Summaries are still cut at 300 characters; signatures are computed from the full input, so this does not matter.

## Revisit when
- A rule lets through something the owner would not have approved → narrow that code's signature, or drop the code
  from `LEARNABLE`.
- After a month: count accepted rules and their uses. No rule ever offered → lower `suggest_after` or widen signatures.
