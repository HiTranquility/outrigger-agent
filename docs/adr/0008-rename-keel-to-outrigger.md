# ADR-0008 — Rename the product from Keel to Outrigger

- Status: Accepted · 2026-11-12 · decided by: owner (chat: "Outrigger")
## Context
The working name was "Keel". A search before publishing (2026-11-12) found `qiweiz94/keel` on GitHub — guardrails
for AI coding agents, same category and same users, distributed as `@get-keel/cli` — plus `keel-hq/keel`
(Kubernetes, ~2.7k stars) and `rockerlabs/keel` (context layer for coding assistants). The name had been proposed
without that search.
## Options
Keep the name · Outrigger · Hoa Tiêu · Ballast · Leeboard.
## Decision
**Outrigger** — the float beside a canoe that lets a narrow, fast hull take open water without rolling over; the same
picture as before (speed without capsizing).
Checked on 2026-11-12 through the public registry APIs: no AI-agent product of that name on GitHub (74 repositories
contain the word; the largest are a 2017 bioinformatics tool, a Rails migration tagger and a Red Hat OpenShift
operator org). The bare package name is **taken** on PyPI (`outrigger`, bioinformatics, last release 2017) and npm
(`outrigger`, Juttle dev environment, 2016) — a future package must be published as `outrigger-agent`.
**Not checked:** trademarks (WIPO, Vietnam IP office), domain names. "Outrigger" is also a hotel brand.
## Consequences
Renamed everywhere: folder `.outrigger/`, `outrigger.toml`, `OUTRIGGER.md`, message `OUTRIGGER BLOCKED`, marker
`<!-- outrigger:start -->`, Python package `outrigger`. Approval ids changed from `K-…` to `OR-…`.
Earlier ADRs were rewritten by the rename and now read "Outrigger" where they originally said "Keel".
Projects installed under the old name must be reinstalled.
