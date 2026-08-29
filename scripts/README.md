# scripts/

- `inspect_schema.py` — prints every table, column, foreign key and index, so the
  schema can be eyeballed against §17. Run it after `alembic upgrade head`.
- `seed_agents.py` — seeds the Founding Eight (§3), the eleven clubhouse
  locations (§5) and the simulation clock: 52 rows in all. Idempotent; safe to
  re-run. Identities, voices and interests are the canonical Phase 1 roster,
  stored verbatim.
- `run_event.py` / `run_day.py` — RUN NEXT EVENT / RUN ONE DAY. Runs against the
  fixture LLM and fixture research provider by default; no key, no network, no
  spend.
- `inspect_research.py` — prints every research session's full provenance
  chain: sources, fetched passages with their sha256, findings, and each
  atomic claim's classification and cited evidence.

Seed data lives here rather than in an Alembic migration: migrations describe
schema, and a roster seeded from a migration could not be corrected without
authoring a new revision.
