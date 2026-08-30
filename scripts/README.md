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
- `inspect_research_usage.py` — prints search-provider usage telemetry
  (Packet 10): one row per research session — provider, queries executed,
  results returned, sources fetched, fetch failures, retries, duration, and
  failure reason where applicable. Takes optional `--agent`, `--provider`,
  and `--failed-only` filters.
- `inspect_wall.py` — prints the Research Wall (posts and their connections),
  every Rabbit Hole with its members and computed heat/status, and every
  belief with its full `belief_basis` trail. Takes an optional `--agent` to
  filter to one agent's beliefs.
- `smoke_test_research.py` — deterministic Packet 5 check: drives the real
  event loop under the fixture providers until an agent chooses
  `START_RESEARCH`, then asserts the whole pipeline actually ran end to end
  (session, sources, passages, finding, evidence links) rather than assuming
  it did.
- `smoke_test_cross_pollination.py` — deterministic Packet 6 check: drives
  the same real event loop until a full organic chain has occurred —
  research, a wall post citing it, another agent reading and connecting to
  it, a rabbit hole, a second agent's different research joining that hole,
  and a belief revision — and asserts every link of it.
- `inspect_memories.py` — prints every agent's memories: type, importance,
  confidence, reinforcement count, decay score, when it was created and last
  recalled, and its typed relations (agents/research/rabbit holes/beliefs).
  Takes optional `--agent`, `--type`, and `--min-importance` filters.
- `inspect_interests.py` — prints every agent's interests, founding and
  emerging, with strength, origin, and last-engaged day. Takes an optional
  `--agent` filter and `--emerging-only` to hide the founding roster.
- `smoke_test_character_development.py` — deterministic Packet 7 check:
  drives the same real event loop until an organic character-development
  chain has occurred — a meaningful memory created and later genuinely
  recalled, and a new emerging interest created, strengthened through
  repeated engagement, and then actually cited as the topic of a later
  action — and asserts every link of it.
- `inspect_conversations.py` — prints every conversation: participants,
  location, why it started and ended, the full transcript, what it
  connected to (research/wall posts/rabbit holes), and any memories it
  produced. Takes optional `--agent` and `--id` filters.
- `smoke_test_dialogue.py` — deterministic Packet 8 check: drives the same
  real event loop until an organic dialogue chain has occurred — a
  conversation begins for a real reason, runs several turns, a later turn
  directly responds to a different agent's turn, a meaningful moment
  (challenge/connection/anecdote/proposal) occurs, the conversation produces
  a persistent memory, and that memory is genuinely recalled again later —
  and asserts every link of it.
- `inspect_reflections.py` — prints every agent's reflections: topic,
  summary, importance, confidence, status, open question, and its full
  provenance chain back to the real memories/research/beliefs/conversations/
  rabbit holes/wall posts/earlier reflections it actually cites. Takes
  optional `--agent` and `--day` filters.
- `inspect_daily_report.py` — prints the Founder Daily Field Report(s)
  exactly as the Founder would read them (the ten §-numbered sections).
  `--structured` also prints the machine-queryable facts and synthesis
  backing the prose — every item's real database id and §2 classification,
  the same data that makes the report's provenance checkable. Takes
  optional `--day` and `--structured`.
- `smoke_test_reflection_report.py` — deterministic Packet 9 check: drives
  the same real event loop until both an organic reflection chain has
  occurred — several of an agent's own memories accumulate real
  significance, the mechanical pressure threshold is crossed, a reflection
  is formed citing real prior experience, and that reflection goes on to
  shape a later action's real content — and a Daily Field Report has been
  generated automatically at a day boundary, its content mapped back to real
  rows with provenance intact and ranked by actual significance rather than
  activity volume. Asserts all seven checkpoints independently.
- `smoke_test_live_research.py` — optional Level 2 check (Packet 10): one
  real research session against a live search provider. Requires
  `RESEARCH_PROVIDER` set to `tavily`/`brave` and its API key present, or it
  exits 0 with a SKIPPED message rather than failing — never runs
  automatically, never runs in a loop, hard-caps its own budget, and
  defaults the LLM side to the fixture provider so only the search itself
  spends anything real.
- `run_live_research_once.py --agent <agent_id>` — developer tool (Packet
  10): runs exactly one agent through one real, tightly-bounded research
  session (that agent's own top interest, or `--question`), using the exact
  same `research.start_research()` path a real decision takes. Refuses to
  run against `RESEARCH_PROVIDER=fixture`.

Nothing in any smoke test scripts an agent's choice or inserts a finished
record directly; a fixed seed only makes which choices happen to occur
reproducible.

Seed data lives here rather than in an Alembic migration: migrations describe
schema, and a roster seeded from a migration could not be corrected without
authoring a new revision.
