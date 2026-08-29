# scripts/

- `inspect_schema.py` — prints every table, column, foreign key and index, so the
  schema can be eyeballed against §17. Run it after `alembic upgrade head`.
- `seed_agents.py` — seeds the Founding Eight (§3), the eleven clubhouse
  locations (§5) and the simulation clock. Idempotent; safe to re-run.
  **Every agent still needs a `voice` line** — the roster gives roles and
  interests but not how each one talks, and `agents.voice` is NOT NULL, so the
  script exits 1 naming the agents still missing one.

Seed data lives here rather than in an Alembic migration: migrations describe
schema, and a roster seeded from a migration could not be corrected without
authoring a new revision.
