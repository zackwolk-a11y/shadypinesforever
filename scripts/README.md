# scripts/

- `inspect_schema.py` — prints every table, column, foreign key and index, so the
  schema can be eyeballed against §17. Run it after `alembic upgrade head`.
- `seed_agents.py` — **not built yet.** The Founding Eight of §3 and the §5
  location list belong here, not in an Alembic migration: migrations describe
  schema, and seeding agents from a migration would make the roster
  un-editable without a new revision. Add it when §3 is implemented.
