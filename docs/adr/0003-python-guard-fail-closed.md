# ADR-0003 — Guard in Python, fail-closed, human-only approvals

- Status: Accepted · 2026-11-11 · **amended by [ADR-0009](0009-light-mode-and-workflow-capture.md)**: in light mode (new installs) only high risk and a short list of medium risk need the terminal approval
## Context
Rules in Markdown are advice; under bypass mode only hooks enforce. IPLMS's `guard_command.py` fails **open** on odd input.
## Options
Language: Python (readable, MATLAB can call it) vs Node.js (already bundled with some agents). Failure mode: open vs closed.
## Decision
Python ≥ 3.11, stdlib only. **Fail-closed**: an engine error denies. Approvals are SHA-256 bound to the exact tool input and can only be granted from the human's own terminal; the agent running `approve` is itself a high-risk block.
## Consequences
More false positives than IPLMS (accepted: a false deny costs one approval, a false allow can cost data). Python must be installed — the installer checks and asks, never installs.
