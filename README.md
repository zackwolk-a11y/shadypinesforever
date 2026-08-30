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
  main.py            FastAPI app
  core/config.py     environment-driven settings (model + research routing, budgets)
  domain/
    enums.py         every enumerated value, shared by db and services
    ids.py           business-key generation
  schemas/
    actions.py       the agent decision envelope (what a model may return)
    research.py      search results, source documents, research synthesis
  db/
    base.py          declarative base, timestamp mixins, naming convention
    session.py       engine + session factory (SQLite WAL, FK pragma)
    models/
      agents.py      agents, agent_interests, agent_beliefs, relationships
      belief.py      belief_basis (directional evidence trail behind a belief)
      memory.py      memories (typed, scored, agent-private — Packet 7)
      research.py    research_sessions, _queries, _sources, _findings
      research_provenance.py  research_source_passages, claims, claim_evidence
      wall.py        research_wall
      rabbit_holes.py rabbit_holes, _members, _research
      conversations.py conversations, conversation_messages, messages
      world.py       world_state, simulation_clock, locations
      reports.py     founder_messages, daily_reports
      events.py      events (append-only)
      exposure.py    agent_exposures (partial-knowledge enforcement)
      telemetry.py   llm_runs
  providers/
    llm/             base.py (Protocol), fixture.py, anthropic.py
    research/        base.py (Protocol), fixture.py, brave.py, tavily.py
  services/
    scheduler.py, context_builder.py, conversations.py, clock.py,
    research.py, wall.py, rabbit_holes.py, beliefs.py,
    memory.py, interests.py,
    orchestrator.py, exposure.py, telemetry.py, founder.py, events.py
alembic/             migration environment
scripts/             inspect_schema.py, inspect_research.py, inspect_wall.py,
                     inspect_memories.py, inspect_interests.py,
                     seed_agents.py, run_event.py, run_day.py,
                     smoke_test_research.py, smoke_test_cross_pollination.py,
                     smoke_test_character_development.py
```

The tree follows the build bible's layout. Files it does not name were still
needed: `world.py` (world_state, simulation_clock, locations fit none of its
seven model files), `wall.py` (the research wall is its own social surface),
`exposure.py` and `telemetry.py` (§17's own tables, `agent_exposures` and
`llm_runs`, doubling as their service modules), `belief.py` (`belief_basis`,
new in Packet 6 — see below).

28 tables in total.

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

### Days and periods

A day runs MORNING → RESEARCH → AFTERNOON → EVENING → NIGHT and rolls over.
Periods do not schedule model calls — nothing fires every virtual hour. A period
changes what the activation scheduler finds likely, and it ends when the agents
in it have run out of reasons to act.

```bash
.venv/bin/python scripts/run_day.py            # one simulated day
.venv/bin/python scripts/run_day.py --days 3   # three
.venv/bin/python scripts/run_event.py --advance -n 40   # step, advancing as needed
```

```bash
curl http://127.0.0.1:8000/simulation/clock
curl -X POST http://127.0.0.1:8000/simulation/advance-period
```

`run_day.py` has a `--max-events` ceiling (400) so a runaway can never spend
without limit.

### Conversations

The day opens with everyone in the room and no agenda — deliberately *not*
"generate one research topic each", which produces exactly the eight-silo
behaviour the experiment is trying to avoid. Turn-taking is mechanical
(whoever has spoken least, never the same agent twice in a row); what anyone
says is theirs. Silence is a legal move, and two consecutive silences wind a
conversation down. A conversation also ends at the turn cap
(`MAX_CONVERSATION_TURNS`) or when everyone has left.

### Research

An agent's own `START_RESEARCH` action names a question — its own, grounded in
its interests, memories, recent conversation, wall activity, and its own past
findings (all shown in context; nothing is assigned). What happens next is a
pipeline, not a single state change:

```
validate today's research budget
  -> research_provider.search()        real, independent retrieval
  -> persist the query + every source's metadata
  -> research_provider.fetch_source()  bounded, exact text, for a few sources
  -> persist each passage, with its sha256
  -> llm_provider.complete(ResearchSynthesis)   interprets ONLY the persisted passages
  -> persist findings, atomic claims, and claim -> passage evidence links
```

If search fails, returns nothing, or every fetch fails, the pipeline stops
before the LLM is ever called — the session is marked `RESEARCH_UNAVAILABLE`
and no interpretation is produced. **A model is never asked to pretend it
searched.** Whatever sources' metadata was already retrieved (even if every
fetch then failed) stays on the record; only the interpretation step is
skipped.

```bash
.venv/bin/python scripts/inspect_research.py               # every session's full chain
.venv/bin/python scripts/inspect_research.py --agent agent_dex
.venv/bin/python scripts/inspect_research.py --failed-only  # RESEARCH_UNAVAILABLE only
```

Two provider hierarchies, entirely independent of each other:

- `LLM_PROVIDER` (`fixture` | `anthropic`) picks who interprets evidence.
- `RESEARCH_PROVIDER` (`fixture` | `brave` | `tavily`) picks who retrieves it.

Running Claude as the agent brain against Tavily's index, or swapping either
side out later (OpenAI, Gemini, Perplexity, a different search vendor), is a
one-file adapter behind the existing `LLMProvider` / `ResearchProvider`
Protocols — nothing in `app/services` imports a vendor name. `brave.py` and
`tavily.py` are written against each API's publicly documented shape but are
**unverified**: no key or live network access was available while building
them. Treat the first live call as a smoke test, same as the Anthropic LLM
adapter.

Research budgets default to the build bible's numbers
(`MAX_RESEARCH_SESSIONS_PER_AGENT_PER_DAY=2`, `MAX_SOURCES_PER_QUERY=5`,
`MAX_EVIDENCE_TOKENS_PER_RESEARCH_SESSION=6000`). `MAX_SEARCH_QUERIES_PER_SESSION`
and `MAX_FOLLOW_UP_DEPTH` are declared but not yet enforced — Packet 5 runs one
query per session and stores follow-up questions without auto-chaining into a
new session; an agent choosing one of its own follow-ups next time it acts is
that agent's decision, not mechanical chaining.

### The Research Wall, Rabbit Holes, and belief revision

The wall is the clubhouse's one shared, public surface. Posting is always an
agent's own choice — `POST_TO_WALL` with a `wall_post_type` (`FINDING`,
`SOURCE`, `QUESTION`, `HYPOTHESIS`, `DISAGREEMENT`, `CONNECTION`, `MYSTERY`,
`RABBIT_HOLE_SUGGESTION`). Everyone sees every recent post's *headline*
(shared infrastructure — the wall is physically visible to all eight); reading
one in full is a separate action, `READ_WALL_POST`, and is what actually
grants exposure — including exposure to whatever research that post cites.
Nothing here posts, reads, or connects on an agent's behalf.

```bash
.venv/bin/python scripts/inspect_wall.py               # every post, hole, and belief
.venv/bin/python scripts/inspect_wall.py --agent agent_dex
```

**Cross-pollination is mechanical, not model-decided.** Each turn, an agent's
context includes at most one "you may find this relevant" nudge — the
single most interest-relevant *unread* post by someone else, scored by plain
keyword overlap with the agent's own interests (no model call, no
embeddings). What the agent does with the nudge — investigate, challenge,
discuss, or ignore it — is entirely its own call; the mechanism only decides
what surfaces, never what it means.

**Rabbit Holes emerge from `CREATE_RABBIT_HOLE`, never a schedule.** An agent
proposes a title and description, grounded in its own research or a wall post
it read. What is *not* agent-decided is the hole's heat and status
(`NEW → ACTIVE → HOT → COOLING → DORMANT`, or `RESOLVED`/`ABANDONED`) —
`app/services/rabbit_holes.py:recompute()` derives those from arithmetic over
real rows every time the hole changes: research sessions linked to it,
distinct contributors (weighted higher than raw activity, so one agent
talking to itself never reads as thriving), challenges to its claims, and
wall interactions. `JOIN_RABBIT_HOLE`, `CONTRIBUTE_TO_RABBIT_HOLE` (optionally
linking a member's own different research in — this is what actually pulls a
second agent's independent work into a shared investigation),
`LEAVE_RABBIT_HOLE`, and `RESOLVE_RABBIT_HOLE` round out the lifecycle.
`RabbitHoleMember.left_at` is stamped, never deleted — the same
audit-trail-over-mutable-flag pattern conversations use for
`departed_agent_ids`.

**Beliefs stay provisional and evidence-linked for their whole life.**
`FORM_BELIEF` grounds a new belief in the agent's own completed research,
starting `PROVISIONAL` with a confidence copied from that research's own
assessed confidence — never invented fresh. `REVISE_BELIEF` requires the
agent's qualitative judgment on direction (`STRENGTHENS` / `WEAKENS` /
`REJECTS`) and exactly one real piece of new evidence (a research session, a
wall post it has actually read, or a claim it has real exposure to) — but the
resulting confidence delta and status transition are computed mechanically in
`app/services/beliefs.py`, the same “agent supplies judgment, code supplies
arithmetic” split the build bible draws for rabbit-hole heat. Even a
`SUPPORTED` belief can be weakened again by the next piece of evidence;
nothing marks a belief permanently settled.

**Disagreement is ordinary, not staged.** `CHALLENGE_CLAIM` targets one
specific atomic claim — never a whole finding, never another agent generally
— and an agent can never challenge its own claim (that is what
`REVISE_BELIEF` is for). Nothing scores agents against each other or declares
a winner; a challenge is a fact on the record the original researcher can see
next time it is activated, and revising a belief in response is its own
choice, never automatic.

**Anti-repetition is enforced where it is cheap and honest to check.** A
`CONNECTION` post repeating an already-made connection is rejected
(`wall.already_connected`); a `CREATE_RABBIT_HOLE` with the same title as an
already-open one is rejected (`rabbit_holes.has_similar_active_title`, exact
match after case/whitespace normalisation — deliberately not fuzzy, so it
never blocks two genuinely different questions that happen to share a few
words); an exact-duplicate research question is visible in context
(`QUESTIONS YOU HAVE ALREADY RESEARCHED`) so an agent can see it is repeating
itself, though nothing hard-blocks a live model from asking it anyway. Beyond
that, the rabbit-hole heat formula's own preference for distinct contributors
over raw activity is what discourages a single dyad from monopolising one
investigation — not a separate penalty bolted on top.

**Every action targets a real id shown in context, never an invented one.**
The convention Packet 5 established for research passages (`[N]` inline)
extends to every new surface: wall posts, rabbit holes, claims, and beliefs
all render with their real database id, and semantic validation checks every
one against the database before anything executes — an unknown id, a claim
the agent has no real exposure to, or a belief it doesn't own are all
rejected the same way an unknown `target_agent_id` already was.

```bash
.venv/bin/python scripts/smoke_test_cross_pollination.py
```

Drives the real loop — scheduler, `FixtureLLMProvider.complete()`,
orchestrator validation and execution — with a fixed seed until a full organic
chain has happened: research completes, gets posted, another agent reads and
connects, a rabbit hole forms, a second agent's different research joins it,
a claim gets challenged, and the original belief is revised in response.
Nothing is scripted or inserted directly; the seed only makes which choices
happen to occur reproducible. Takes a few thousand events (still just
computation, no network) since several independent things have to align, unlike
`smoke_test_research.py`'s single-digit event count for triggering research
alone.

### Memory, interests, and character development

Packet 7's premise: eight agents that are the same on day 7 as day 1 have not
actually lived through anything. Nothing here stores every event — that would
be a transcript, not a memory — and nothing lets a model self-report how
important or how strong something is; both are computed from real database
state, the same "mechanism, not content" split the wall, rabbit holes, and
beliefs already draw.

**Five memory types, never collapsed.** EPISODIC (a specific moment —
reading a post, being challenged), SEMANTIC (a conclusion that outlives the
moment — a research interpretation, a belief's latest twist), SOCIAL (a read
on how another agent thinks or collaborates), INTEREST (a note the agent
itself wrote about its own curiosity, via `WRITE_NOTE`), and PROJECT (a
running, regenerated summary of one rabbit hole's state — see below).

**Memory selection is a deterministic filter over the event log, not a
second copy of it.** `app/services/memory.py` hooks in at exactly one point
— `orchestrator.run_next_event`, right after `execute_decision` — and
re-queries every event that activation's `correlation_id` produced. A
handler exists only for event types judged likely to matter later: a
research session completing with real evidence (or genuine, "major
uncertainty" conflicting/insufficient evidence — thin, empty results are
skipped outright), a claim being challenged (both sides get an EPISODIC
memory; the pattern repeating twice or more additionally reinforces a SOCIAL
memory — "X tends to challenge my claims"), a belief being revised, a rabbit
hole being created, joined, contributed to, left, or resolved, a wall post
being read, and a founder message being delivered (always memory-worthy,
handled separately since it reaches its recipients before anyone is
activated). Routine actions — `OBSERVE`, `REST`, ordinary conversation turns
— never become memories at all.

**Reinforcement strengthens a memory instead of duplicating it.** A second
challenge from the same agent, a belief's second revision, another touch of
the same rabbit hole — each is matched against a small recent window of the
agent's own memories by real typed relation (a shared `rabbit_hole_id`,
`belief_id`, or other-agent id, never by comparing prose) and bumps
`reinforcement_count`/`importance` on the existing row rather than creating a
near-duplicate. A rabbit hole's PROJECT memory in particular is *replaced*,
not appended to, on every touch — regenerated fresh from the hole's current
title, description, status, evidence strength, and member count
(`memory._rabbit_hole_summary`). That is what lets returning to a dormant
hole recall "why it started, what evidence exists, ... their own previous
stance" (§13) without replaying its history: the summary already reflects
everything that happened to it, because it is computed from current state,
not narrated as a log. Reinforcement never touches `AgentBelief.confidence`
or any other truth-bearing field — memory strength and evidence stay
strictly separate (§5, §14).

**Retrieval is a small, scored slice, never the whole table.**
`memory.retrieve_relevant` combines importance, simulated-day recency,
reinforcement, and decay into one score, plus a flat bonus for actually
matching the current topic, the agents present, or the rabbit holes in play.
A high-importance floor (70+) keeps old-but-important memories eligible
regardless of age — decay only ever lowers retrieval *priority*
(`decay_score`, floored, never below a minimum), never deletes a row and
never happens to a memory at or above that floor. `MEMORY_RECALLED` is
logged only when a surfaced memory is genuinely stale (not accessed in 2+
simulated days) — routine re-display of what is already fresh in mind never
spams the event log.

**Interests move in small, mechanical steps — never one conversation to an
obsession.** `app/services/interests.py` mirrors `beliefs.py`'s split: the
qualitative trigger (a rabbit hole joined, a research question answered, a
wall post read that cites someone else's work) is a fact about what
happened; `interests.bump` computes the resulting number. Deltas are all a
few hundredths on a 0.0-1.0 scale (founding interests start at 0.5); a
brand-new interest starts at essentially nothing and only becomes real
strength through repeated, independent reinforcement. `INTEREST_CREATED`
fires once; `INTEREST_INCREASED`/`INTEREST_DECREASED` on every later move;
`INTEREST_DORMANT`/`INTEREST_REVIVED` are swept once per simulated day
(`sweep_dormancy`, called from `clock.advance()` on every day rollover) — a
weak, long-neglected interest goes quiet, and the next real engagement with
it revives it, exactly the way rabbit holes cool and get pulled back into
(see below). Cross-agent influence is a first-class origin: joining a rabbit
hole someone *else* started, or reading a wall post that cites someone
else's research, both bump the reader's own interest in that topic — this is
the mechanism behind "an agent's curiosity rubbing off on another," never
scripted to any one pair.

**A genuine rabbit-hole dormancy bug from Packet 6 is fixed here.**
`rabbit_holes.recompute()` was overwriting `last_activity_day` to the
current simulated day *before* computing how stale the hole had been,
which made `days_stale` always evaluate to zero — `DORMANT`/`COOLING` were
unreachable through that function. The fix splits the concern in two:
`recompute()` (only ever called *because* of a real interaction) now judges
status purely from heat and contributors — never staleness, since being
called at all means the hole was just touched — while a new
`rabbit_holes.sweep_dormancy`, run once per simulated day alongside the
interest sweep, is the only thing that marks a hole `COOLING`/`DORMANT` from
elapsed time with nobody touching it. A member returning to a hole
`sweep_dormancy` marked dormant naturally revives it the moment `recompute()`
runs again — no special-casing needed, it falls straight out of status being
recomputed fresh from current engagement. The activation scheduler also
gives members of a currently-dormant hole a small, deterministic pull back
toward it (`scheduler.DORMANT_RABBIT_HOLE_PULL`), so "an agent returning to a
dormant rabbit hole" (§13) is more than pure chance without ever forcing the
choice.

**Social continuity moves slowly, and disagreement never counts against
it.** `relationships.trust_score` starts at 60/100 — friendship is the
Village's baseline, not something earned from zero — and only ever moves in
small, capped steps: an ordinary conversation exchange nudges it up
slightly, and bringing new research into a shared rabbit hole (useful
collaboration) nudges the other current members up a little more.
Challenging a claim never touches trust in either direction — disagreement
is normal between friends, not a hostility signal (§10). This is a
documented, deliberate scope limit: nothing here currently models a
*negative* trust signal (an ignored request, poor collaboration) — trust
only ever holds steady or rises in this packet.

**A short structured reflection, never chain-of-thought.** `AgentDecision`
gained an optional `reflection` field (`WHAT_CHANGED`/`WHAT_MATTERS_NOW`/
`WHAT_I_WANT_TO_REVISIT`, §15) that a model may fill in after something
significant — the fixture does, about 40% of the time, after `FORM_BELIEF`,
`REVISE_BELIEF`, `RESOLVE_RABBIT_HOLE`, or `CHALLENGE_CLAIM`. When present,
it becomes one EPISODIC memory, verbatim — nothing here asks for or stores
reasoning, only the concise conclusion a model chooses to report.

**Belief and memory stay two concepts, never one table.** `AgentBelief`
(structured, evidence-linked, §2/§9) is unchanged in shape by Packet 7. A
memory may *reference* a belief (`Memory.related_belief_ids`, used only to
find the right memory to reinforce on a belief's next revision) but never
replaces or duplicates what a belief already tracks — an agent can remember
"I once believed X" in a SEMANTIC memory while `AgentBelief.statement` now
reads Y (§14).

**Context stays bounded.** `context_builder.py` renders `IMPORTANT
MEMORIES`, `RELEVANT SOCIAL MEMORIES` (only about agents actually present),
`RECENT RABBIT-HOLE EXPERIENCE` (only for holes the agent is currently a
member of), `EMERGING INTERESTS` (non-founding-origin only), a revision
count inline on `YOUR BELIEFS` when a belief has been revised more than
once, and the existing `RECENTLY EXPLORED QUESTIONS` — each capped at a
handful of rows, never the full memory table.

```bash
.venv/bin/python scripts/smoke_test_character_development.py
```

Drives the real loop with a fixed seed until an organic character-development
chain has happened: a meaningful event creates a memory; a previously-absent
topic becomes a new emerging interest somewhere in the Village; that interest
strengthens through independent, repeated engagement (not one event); an
earlier memory gets recalled again after a genuine multi-day gap; and later
behavior actually cites the now-stronger interest as its topic — provable
because the fixture's own topic selection can only ever choose from what
context actually renders. Nothing is scripted, hand-written, or set
directly; a fixed seed only makes which choices happen to occur reproducible
(same discipline as `smoke_test_cross_pollination.py`). Two independent
checks, not one: the memory half (create, then genuinely recall) and the
interest half (create, strengthen, then get cited) are allowed to involve
different agents, since the spec's own example chain treats them as
separate roles, and requiring one agent to satisfy both would test a
coincidence rather than the mechanism.

```bash
.venv/bin/python scripts/inspect_memories.py --agent agent_alien
.venv/bin/python scripts/inspect_interests.py --emerging-only
```

## Design notes

**Foreign keys reference stable business keys.** `agent_id` columns point at
`agents.agent_id` (`agent_optimisto`), and `research_session_id` /
`related_research_id` point at `research_sessions.research_id` — not at the
surrogate integer primary keys. §17 also stores these ids inside JSON columns
(`conversations.participant_ids`, `research_sessions.related_research`,
`agent_beliefs.basis`, `memories.related_research_ids`/`related_agent_ids`/
`related_rabbit_hole_ids`/`related_belief_ids`), and JSON cannot carry a
foreign key — a memory may legitimately point at something that has since
changed shape, and should still be recallable. Pointing the real foreign keys at the same value space means an `agent_id`
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

**Knowledge is partial, and `agent_exposures` is what enforces it.** Nothing is
shown to an agent it has no exposure row for. Conversation turns reach the
people who were in the room; a direct message reaches its sender and recipient;
a targeted founder message reaches one person. The research wall contributes
*headlines* only — enough to make something discoverable, never enough to make
it known. A context builder that ever does `get_all_wall_entries()` makes all
eight omniscient and ends the experiment.

**`participant_ids` is who is in the room now; `departed_agent_ids` remembers
who left.** Both are needed: turn-taking wants the first, and auditing who may
legitimately know what wants the second — someone who walked out still heard
what was said before they went.

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

**Provenance is a chain, not a URL-plus-summary.** A claim points at a
passage (the exact bounded text a model was shown, with a sha256 of it); the
passage points at a source and the query that produced it. That is what makes
it possible to tell "the source says this" apart from "the agent thinks the
source implies this" after the fact — the distinction the build bible calls
the single most important provenance improvement over the bare §17 schema.

**Every finding decomposes into independently-classified atomic claims.** A
finding can be `RESEARCH_FINDING` while bundling a `SOURCE_CLAIM` alongside
the `AGENT_INFERENCE` drawn from it; collapsing that to one classification per
finding would erase exactly the distinction §2 exists to preserve. Claims
reuse the same nine-value classification as findings — it is one reality
classification, applied at two granularities, never two vocabularies.

**`research_sources.excerpt` and `research_source_passages.excerpt_text` answer
different questions.** The first is the short relevance snippet the search
call itself returned — what the Village saw *before* deciding whether a
source was worth reading. The second is the exact bounded text actually shown
to the interpreting model, with its own sha256. Neither is derived from the
other.

**The LLM provider interface is generic over the output schema, not one
method per purpose.** `complete(..., output_type=AgentDecision)` and
`complete(..., output_type=ResearchSynthesis)` are the same call through the
same adapter; a later packet's report generator needs a new Pydantic model,
not a new provider method every adapter must grow.

**Research is private until an agent chooses to share it.** A completed
session's findings and claims are exposed only to the agent who ran it
(`CREATED` exposure) until that agent posts about it, or another agent reads
that post or joins a rabbit hole the research got linked into — at which
point the reader/joiner gains real (`SHARED_FINDING`) exposure to the session,
its findings, *and* its claims (needed so `CHALLENGE_CLAIM` and a
claim-grounded `REVISE_BELIEF` have something real to target). Nothing here
shares anything automatically; every exposure traces back to a specific
`POST_TO_WALL`, `READ_WALL_POST`, `JOIN_RABBIT_HOLE`, or
`CONTRIBUTE_TO_RABBIT_HOLE` action.

**The `belief_basis`/`BeliefStatus` schema tension is resolved by giving each
side its own place, not by picking one.** §17's `agent_beliefs.status`
(`PROVISIONAL/SUPPORTED/CONTESTED/REJECTED/RETIRED`) stays exactly as
migrated in Packet 1 — renaming it now would be pure churn. The build bible's
real point was that a belief needs a typed, queryable evidence trail, which
`belief_basis` now provides: `basis_type`/`basis_id` name what moved the
belief, and `relation` (`STRENGTHENS`/`WEAKENS`/`REJECTS` — a deliberately
different vocabulary from claims' `EvidenceRelation`, since a claim is
supported *by a passage* but a belief is strengthened *by an agent's
judgment*) records which direction. `agent_beliefs.basis` (JSON) keeps being
written as a flat, denormalised quick list; `belief_basis` is the
authoritative, directional record behind it — both populated together, never
in disagreement.

**Extension points left open, not built.** `locations` is semantic rather than
spatial but nothing forbids adding coordinates or a building reference later;
`world_state` is a generic key/value store so new global state needs no
migration; `simulation_clock.current_period` is a string so §5's day structure
can grow periods as a data change.
