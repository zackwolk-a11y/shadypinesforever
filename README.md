# The Internal Village — Phase 1: The Research Clubhouse

Persistence layer for Phase 1, per §17 of the build bible. This is **schema
only**: SQLAlchemy 2.x models, Alembic migrations, and a FastAPI skeleton with a
health check. No agent logic, no research execution, no LLM calls.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Database

The database URL comes from the `DATABASE_URL` environment variable and defaults
to `sqlite:///./village.db`. `alembic.ini` deliberately leaves `sqlalchemy.url`
blank so migrations and the app can never disagree about which database they mean.

```bash
.venv/bin/alembic upgrade head      # create every table
.venv/bin/alembic downgrade base    # drop every table (reversible)
.venv/bin/alembic check             # confirm models and migrations agree
```

Eyeball the result against §17:

```bash
.venv/bin/python scripts/inspect_schema.py               # read the live database
.venv/bin/python scripts/inspect_schema.py --from-models # read ORM metadata only
```

## Seeding

`scripts/seed_agents.py` seeds the Founding Eight (§3), the eleven clubhouse
locations (§5) and the simulation clock. It is idempotent — re-running only adds
what is missing, and never overwrites runtime state such as an agent's
`current_location` or an interest's drifted `strength`.

```bash
.venv/bin/python scripts/seed_agents.py            # seed anything missing
.venv/bin/python scripts/seed_agents.py --dry-run  # report, then roll back
.venv/bin/python scripts/seed_agents.py --update   # refresh identity/voice
.venv/bin/python scripts/seed_agents.py --reset    # wipe seeded rows first
```

The Founding Eight are transcribed: Optimisto (espresso_counter), Vince (bar),
QuestAuthor (zine_desk), The Alien (recording_desk), Sol, Roxy (phone), Dex and
Lucid — 8 agents, 32 founding interests, 11 locations and the clock, 52 rows in
all. Sol, Dex and Lucid have no dedicated §5 station and start at the
`communal_table`. Since §17's `agents` table has no display-name or emoji
column, `identity` carries the emoji and character name alongside the role so
nothing from the roster is lost.

Voice lines are the canonical Phase 1 voice definitions, seeded verbatim into
`agents.voice` (NOT NULL, unchanged from §17). The roster is validated before
anything is written, so a missing voice, a wrong agent count, a duplicate
`agent_id` or a starting location outside §5 all fail up front rather than
part-way through the insert.

## Running

```bash
.venv/bin/uvicorn app.main:app --reload
curl http://127.0.0.1:8000/health
```

## Layout

```
app/
  main.py            FastAPI app — /health only
  core/config.py     environment-driven settings (model routing, budgets)
  domain/
    enums.py         every enumerated value, shared by db and services
    ids.py           business-key generation
  db/
    base.py          declarative base, timestamp mixins, naming convention
    session.py       engine + session factory (SQLite WAL, FK pragma)
    models/
      agents.py      agents, agent_interests, agent_beliefs, relationships
      memory.py      memories
      research.py    research_sessions, _queries, _sources, _findings
      wall.py        research_wall
      rabbit_holes.py rabbit_holes, _members, _research
      conversations.py conversations, conversation_messages, messages
      world.py       world_state, simulation_clock, locations
      reports.py     founder_messages, daily_reports
      events.py      events (append-only)
alembic/             migration environment
scripts/             inspect_schema.py, seed_agents.py
```

The tree follows the build bible's layout. Two files it does not name were still
needed: `world.py` (world_state, simulation_clock, locations fit none of its
seven model files) and `wall.py` (the research wall is its own social surface).

22 tables in total.

## Running the loop

`RUN NEXT EVENT` activates one agent, has it decide, validates the decision and
executes it. It runs against the **fixture provider** by default — no API key,
no network, no spend — so the loop can be exercised end to end today:

```bash
.venv/bin/python scripts/run_event.py            # one event
.venv/bin/python scripts/run_event.py -n 20      # twenty
.venv/bin/python scripts/run_event.py --scores   # show the activation scoreboard
```

Or over HTTP:

```bash
.venv/bin/uvicorn app.main:app --reload
curl -X POST http://127.0.0.1:8000/simulation/next-event
```

Fixture decisions are prefixed `[fixture]` and every `llm_runs` row they write
is flagged `is_fixture`, so a fixture day can never be read as a live one. To go
live, set `LLM_PROVIDER=anthropic` with credentials in the environment. That path
is written but has not been run here — no key was available — so treat the first
live call as a smoke test.

A run stops with "no agent is eligible" once the period is spent. That is the
correct end state for now: advancing the period or day is the day engine, a
later packet.

## Design notes

**Foreign keys reference stable business keys.** `agent_id` columns point at
`agents.agent_id` (`agent_optimisto`), and `research_session_id` /
`related_research_id` point at `research_sessions.research_id` — not at the
surrogate integer primary keys. §17 also stores these ids inside JSON columns
(`conversations.participant_ids`, `research_sessions.related_research`,
`agent_beliefs.basis`, `memories.related_ids`), and JSON cannot carry a foreign
key. Pointing the real foreign keys at the same value space means an `agent_id`
means exactly one thing everywhere in the schema. Surrogate `id` integer primary
keys still exist on every table.

**No cascading deletes.** Every foreign key uses the default `ON DELETE`
behaviour (restrict). Phase 1 would rather fail a delete loudly than lose
research silently. SQLite's foreign key pragma is enabled per connection in
`app/db.py`, so the constraints are actually enforced.

**Published vs. retrieved.** `research_sources.pub_date` and
`research_sources.retrieved_at` are separate columns and neither is derived from
the other (§6).

**The nine finding classifications are not collapsible.** `research_findings.classification`
carries all nine values of §2 — real-world fact, source claim, research finding,
agent inference, agent belief, hypothesis, speculation, simulation event,
creative content — even though Phase 1 will not populate every one.

**`events` is append-only.** Insert, never update or delete. Phase 1 enforces
this by convention (see the module docstring); no ORM-level immutability or
database triggers yet.

**Seed data is not in migrations.** The Founding Eight (§3) and the §5 location
list are seeded by `scripts/seed_agents.py`. Migrations describe schema; seeding
a roster from a migration would make it un-editable without a new revision.

**The scheduler offers opportunities, it does not decide content.** Activation
scoring is mechanism — unread mail, the period's baseline, a seeded curiosity
jitter, minus a penalty for having just acted. What an activated agent then does
is the agent's own. One event activates one agent, not all eight.

**A decision gets one correction attempt, then the agent does nothing.** Schema
validation proves the shape; semantic validation proves the decision refers to a
world that exists (a real location, a real recipient, not itself). A decision
that fails twice is logged as `INVALID_AGENT_DECISION` and changes no state —
no retry spiral, and nothing unvalidated is ever executed.

**Showing a message to an agent marks it delivered.** Otherwise an unread
message keeps boosting that agent's activation score forever and one inbox
monopolises the Village.

**Fixture runs are costed at zero**, never at what the same tokens would have
cost live. An unrecognised live model also costs zero, so check
`MODEL_PRICES_USD_PER_MTOK` before reading a cost report as complete.

**Seeding writes no events.** `events` records what happens *in* the simulation;
world setup happens before the simulation starts.

**Re-seeding never clobbers runtime state.** `Agent.current_location`,
`current_activity`, `interaction_target` and `AgentInterest.strength` all drift
as the simulation runs, so the seeder inserts what is missing and otherwise
leaves rows alone. `--update` refreshes the authored fields (identity, voice)
only. `--reset` deletes seeded rows for a throwaway database and will fail
loudly — by foreign key, not silently — if real research or memories still
reference an agent.

**Extension points left open, not built.** `locations` is semantic rather than
spatial but nothing forbids adding coordinates or a building reference later;
`world_state` is a generic key/value store so new global state needs no
migration; `simulation_clock.current_period` is a string so §5's day structure
can grow periods as a data change; `models/belief.py` is reserved for Phase 2.
None of this is implemented now.
