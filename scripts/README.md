# scripts/

- `inspect_schema.py` — prints every table, column, foreign key and index, so the
  schema can be eyeballed against §17. Run it after `alembic upgrade head`.
- `seed_agents.py` — seeds the Founding Eight (§3), the clubhouse locations (§5)
  and the simulation clock. Idempotent; safe to re-run. **The roster itself is
  not filled in yet** — `FOUNDING_EIGHT` is an empty tuple awaiting the §3 text,
  and the script exits 1 with an explanatory message until it is transcribed.

Seed data lives here rather than in an Alembic migration: migrations describe
schema, and a roster seeded from a migration could not be corrected without
authoring a new revision.
