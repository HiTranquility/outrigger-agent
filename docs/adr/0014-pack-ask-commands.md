# ADR-0014 — A pack can list commands that must always be asked about

- Status: Accepted · 2026-11-21 · builds on [ADR-0013](0013-pack-gui-always-ask.md), amends [ADR-0009](0009-light-mode-and-workflow-capture.md)
- Decided by: the owner, designing the Pro Capstone pack (verbatim choice: *"Guard chặn thật"*: the guard really
  blocks migrations so the schema gate is enforced, not only written in a workflow)

## Context
The Capstone pack's schema gate (CAP-04) says: no migration reaches a database before the human confirmed the ERD,
columns and indexes. Written as a workflow step only, an agent in light mode can run `dotnet ef database update` or
`prisma migrate deploy` without asking: neither is risky to the core rules. The same holds for commands that destroy
data (`docker compose down -v`, `prisma migrate reset`, `dropdb`). Which commands matter depends on the domain, so the
core cannot list them; the pack knows.

## Options
| Option | Gain | Lose |
| :-- | :-- | :-- |
| **A · `[[ask]]` tables in `pack.toml`: command word sequences + reason + risk** | Domain knowledge stays in the pack; one generic mechanism; works in light mode | A word-sequence match is a heuristic |
| B · Only a workflow step | No code | Not enforced: the owner's explicit choice was enforcement |
| C · Hard-code migration tools in core rules | Simple | Core grows a list per framework; every user pays for packs they do not use |

## Decision
**A.**
1. `pack.toml` may hold any number of `[[ask]]` tables: `commands` (strings), `reason`, `risk` (`medium` default,
   `high` allowed; never lower).
2. Match: the first word is the program; up to three **runner** words may come before it (`npx`, `pnpm exec`,
   `uv run`, `python -m`, `yarn`, `sudo`…), anything else first (e.g. `echo`) means no match; the remaining words must
   appear in order, with flags or other words between (`docker compose -f x.yml down -v` matches `docker compose down -v`).
3. Finding `pack-ask` at the entry's risk. It is asked in **strict and light** mode (`LIGHT_STILL_ASK`), also when the
   command is hidden in a script or an npm script (`script:pack-ask`), and it is **never learnable** (ADR-0011): an
   approval is the one-time, SHA-bound approval of that exact command.
4. `selftest` adds a light-mode case for the first command of every `[[ask]]`.
5. Older cores ignore `[[ask]]` (unknown table); the pack's workflows still apply as text.

## Consequences
- The Capstone pack lists 32 schema-applying and 24 data-destroying commands across EF Core, Prisma, Alembic, Flyway,
  Liquibase, Knex, Sequelize, TypeORM, Drizzle, Laravel, Django, Rails, Supabase, golang-migrate and Docker.
- Not covered: SQL run by hand or from a GUI, migrations the application applies at start-up, tools not listed.

## Revisit when
- A real project shows a false block (a command that only reads) → narrow that entry.
- A migration tool in common use is missing → add it to the pack, not the core.
