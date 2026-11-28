# Contributing

Thank you for helping. Outrigger protects people who let an AI agent act with every permission, so a change is
judged first by "can it let something dangerous through?" and only then by convenience.

**Found a way past the guard?** Do not open a public issue — see [SECURITY.md](SECURITY.md).

## Ground rules (same as [AGENTS.md](AGENTS.md))

1. **Standard library only**, Python ≥ 3.11. No third-party packages in `template/.outrigger/engine/`.
2. **Fail closed.** When the guard cannot parse or check something, it asks; it never allows by default.
3. **Every new guard rule** needs a test in `tests/` and, if a user can see it, a case in `cli.py` selftest `CASES`.
4. **Every rule traces to a loss**: add or extend a row in [`docs/RISK_REGISTER.md`](docs/RISK_REGISTER.md) that
   names the test (`Class.test_name`); `RegisterIntegrity` fails if the named test does not exist.
5. **A decision with alternatives** is a new ADR in [`docs/adr/`](docs/adr/README.md). Never edit an accepted ADR's
   decision — supersede it.
6. `template/AGENTS.md` is the product's rule file and must stay **under 8 KB** (agents share a small budget).
7. Generic method goes in this open core; rules for one tool or domain go in a pack (ADR-0001).

## Before you open a pull request

```bash
python -X utf8 -m unittest discover -s tests
cd template && python -X utf8 .outrigger/engine/cli.py selftest
```

Both must pass. Then, by hand, the live check from the README: in a project with Outrigger installed, start the
agent in bypass mode and ask it to run `rm -rf sandbox/outrigger-live-check` — you must see `OUTRIGGER BLOCKED`.

In the pull request, say what was **not** checked (another OS, another agent, a real app). Add a line to
[`CHANGELOG.md`](CHANGELOG.md) under the next version.

## Keeping files small

The project uses its own structure gate (ADR-0015) as a target: keep a new engine module under 400 lines and split
by concern, as `rules.py` was split in 0.6.0.
