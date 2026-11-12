# Working on the Outrigger repository itself

- `template/` is the payload copied into a user's project. `template/AGENTS.md` is the product's rule file — keep it
  under 8 KB (Codex reads at most 32 KiB in total, and the user's own rules share that budget).
- The guard engine is stdlib-only Python ≥ 3.11 and **fails closed**. Every new rule needs a test in
  `tests/test_outrigger.py` and, if user-visible, a case in `cli.py` selftest `CASES`.
- Run before calling anything done:
  `python -X utf8 -m unittest discover -s tests` and `python -X utf8 template/.outrigger/engine/cli.py selftest` (from `template/`).
- Decisions with alternatives → new ADR in `docs/adr/`; never edit an accepted ADR's decision, supersede it.
- Answer the maintainer in their language (Vietnamese or English).
