# Roadmap — what to add next (from comparing Outrigger 0.1 with IPLMS, Quy trình học tập/IELTS and the research vault)

Ranked by value for buyers ÷ effort. Nothing here is decided — each item needs the owner's choice (then an ADR).

## Already taken into 0.1
SHA-bound approvals (IPLMS `audit_gate.py`) · shell-splitting lessons (IPLMS bug-052/053) · supply-chain report (IPLMS
rule) · fixed report order and "not done / not verified" (IPLMS REQ-007) · decision → ADR in the same turn (IPLMS
"chốt sau phản biện") · answers must *graduate* (Quy trình học tập §6) · check every number, even official examples
(IELTS rule 5) · source rules S1–S5 and the 🆕 marker (research vault §10.4) · goal → knowledge → practice loop
(Quy trình học tập §1) in the builder.

## Candidates

| # | Idea | From | Why buyers care | Effort |
| :-: | :-- | :-- | :-- | :-: |
| ✅ | *Done 2026-11-11:* #1 → [`RISK_REGISTER.md`](RISK_REGISTER.md) (checked by `RegisterIntegrity` tests) · #7 → core Python pack `template/.outrigger/packs/python/` | | | |
| ✅ | *Done 2026-11-12 (Outrigger 0.2.0, group 1):* script scanning for `.sh .ps1 .bat` + `package.json` scripts + Node.js pack · secret check on `git commit` · agent memory / global config protection · `cli.py trust` | | | |
| 1 | **Risk register / coverage matrix**: OWASP ASI01–ASI10 → Outrigger control → test name; every new guard rule traces to a loss (STPA chain: loss → unsafe action → constraint → gate → test) | vault `SO_RUI_RO.md`, `00-070` | Sales proof: "this is what we cover and what we don't" | S |
| 2 | **Output filter**: long build/test/MATLAB logs go to a file, the agent gets a summary | IPLMS `filter_verbose_output.py` | Token cost — the most visible saving | M |
| 3 | **`cli.py next-id ADR|SPIKE|BUG`** — numbering from the files, never reused | IPLMS `next_record_id.py`, vault `MA_SO.md` | No duplicate ADR numbers across sessions | S |
| 4 | **`cli.py doctor`** — lint workflows/records: frontmatter, status vocabulary, broken links, orphan drafts, workflow without a real run | vault `lint.py`, IPLMS `workflow-health` | Buyers' own workflows stay valid after edits | M |
| 5 | **Guard statistics**: which rule fires most, which approvals are routine → suggest moving a host to the allow-list or a step to a lower level | IELTS error codes + `NHAT_KY_LOI` | Fewer interruptions over time, without weakening safety | S |
| 6 | **Dashboard generated from frontmatter** (reports, ADRs, workflows, pending approvals) — never edited by hand | IPLMS BOARD from Meta, IELTS rule 7 | One page to see the project | M |
| 7 | **Python pack** (scan the `.py` file being run for `rmtree`, `subprocess`, `requests.post`) | gap found in 0.1 | Closes the biggest hole: "write a script, then run it" | S |
| 8 | **Hint tiers** for teaching/research packs (hint 1 → hint 2 → solution) | IELTS rule 3 | Students learn instead of copying | S |
| 9 | **Human-review date on workflows** (`human_read: YYYY-MM-DD`), like the vault's `tác-giả-đọc` | vault origin tag | Separates "AI wrote it" from "a person checked it" | S |
| 10 | **Definition of Done per workflow** + "ask at start, ask at end" (branch? who does it? merge?) | IPLMS ADR-0053 | Clear finish line, fewer half-done turns | S |
| 11 | **Git policy pack**: one record one branch, never commit to main, delete merged branches only on approval | IPLMS ADR-0043/0053 | Teams | M |
| 12 | **Native approval prompt** — try Claude Code `permissionDecision: "ask"` for medium risk if it still prompts under bypass (live test needed) | own analysis | Less typing for the user | S (test first) |

## Packs proposed 2026-11-12 — owner said "later" (not started)

| Pack | Workflows sketched |
| :-- | :-- |
| `packs/business` | BIZ-01 business problem one-pager · BIZ-02 option / competitor comparison · BIZ-03 proposal · BIZ-04 SOP · BIZ-05 customer interview |
| `packs/legal` | LEG-01 contract reading + questions for a lawyer · LEG-02 software licence inventory · LEG-03 personal-data inventory · LEG-04 compliance register · LEG-05 content provenance log |
| `packs/finance` | FIN-01 cost estimate (three points) · FIN-02 break-even · FIN-03 cloud cost forecast · FIN-04 project cost ledger · FIN-05 pricing model comparison |
| `packs/strategy` (owner's idea) | strategic-management workflows built on named consulting frameworks (the owner mentioned McKinsey-style models); each framework must be checked against its original source before it is written in (rule S2) |

Rules fixed for the legal and finance packs: every number has a source and a formula; outputs are "draft — needs a
professional"; laws are cited with number and effective date from the official text; the agent never concludes
"legal", "sign it" or "invest".

## Release 2 (decided, ADR-0005)
Research (NCKH) pack `RES-01…08` · Codex / Antigravity / Cursor adapters · output filter (#2).
