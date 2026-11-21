# ADR-0013 — A pack can make opening its app ask in light mode too

- Status: Accepted · 2026-11-21 · amends [ADR-0009](0009-light-mode-and-workflow-capture.md) (light mode)
- Decided by: the owner, choosing between two options at a GATE (verbatim: *"Pack tự đòi hỏi"*: the pack itself demands it)

## Context
Light mode (ADR-0009, the default since 0.3.0) lets medium risk through and logs it. Opening an interactive app is
medium (`app`, L2), so `matlab` without `-batch` opened the desktop **without asking**. That broke two promises:
the Vietnamese guide ("Mở MATLAB lung tung, tốn licence → mở app L2 phải hỏi") and the Pro MATLAB pack README
("L2, approval, logged"). Found while checking the Pro pack against core 0.4.0 (2026-11-21).

An app is not one kind of cost: a browser tab costs nothing, a MATLAB or Simulink desktop holds a licence seat (L-4).
Only the pack knows which.

## Options
| Option | Gain | Lose |
| :-- | :-- | :-- |
| **A · Pack key `gui_always_ask = true`** | The cost is declared where the knowledge is; other apps keep light mode's speed | One more pack key |
| B · Keep "logged only", fix the docs, tell licence-minded users to use strict | No code | Strict asks for every medium risk, which is the friction light mode removed |
| C · All `app` findings always ask | Simple | Undoes light mode for every browser/preview launch |

## Decision
**A.**
1. A `[[tools]]` entry in `pack.toml` may set `gui_always_ask = true`. Opening that tool without a headless flag gives
   `app-ask` (medium, or high when `gui_level = "high"`) instead of `app`.
2. `app-ask` is in `LIGHT_STILL_ASK`: asked in strict **and** light mode. It is **not** in `learn.LEARNABLE`, so it is
   never offered as a standing rule: "always ask" means always. A user who disagrees removes the key in their copy of the pack.
3. When a pack lists a command, the core's generic app list stays silent for it (the pack judges its own app, so
   `simulink` is no longer reported twice).
4. Headless runs are unchanged (`-batch` → L1, code scanned first).
5. `selftest` adds a light-mode case for every installed pack tool with the key.
6. The Pro MATLAB pack (0.2.0) sets the key for `matlab` and `simulink`.

## Consequences
- Light mode again keeps the promise in the docs for MATLAB; browsers and previews stay unasked.
- Older cores ignore the unknown key: with core < 0.4.1 the Pro pack behaves as before (logged, not asked).

## Revisit when
- A user approves the same app launch many times a day → consider a time-boxed approval for `app-ask` (still not a standing rule).
