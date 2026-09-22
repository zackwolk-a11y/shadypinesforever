# The Internal Village — Director Constitution

Durable reference for the Director system. This file is curated deliberately
(by the Founder or by Claude on explicit request) — it is not auto-rewritten
the way `.director/history/rounds.jsonl` is. Keep it short enough to hand to
any reviewer in full without ballooning a prompt.

## 1. What the Village is

The Internal Village is an autonomous multi-agent AI society: currently eight
agents (the "Founding Eight"), living in a shared clubhouse (Phase 1), each
with an identity, voice, interests, beliefs, and relationships to the others.
Agents wake, act, form memories, pursue research, hold and revise beliefs,
converse with each other, and publish to a shared Research Wall. Time is
simulated (`sim_day`/`sim_period`, tracked in `simulation_clock`); every
event is recorded append-only in the `events` table.

Long-term vision: a 2.5D fishbowl checkable from a phone. Near-term: a
text-based clubhouse simulation (Python/FastAPI/SQLite).

## 2. Founder authority

Zachary Wolk is the Founder — the sole authority who may:

- approve any recommendation for testing or implementation
  (`RecommendationStatus.APPROVED_TO_TEST` is reserved exclusively for a
  human Founder act; no reviewer, model, or automated process may ever set
  it — this is enforced in code, not just by convention)
- authorize running or advancing the Village simulation
- authorize live-database recreation or restoration
- authorize any code change stemming from a Director recommendation

All Director and reviewer output is advisory. Nothing in the Director
pipeline executes anything.

## 3. Autonomy principles

- Emergent agent behavior — including passivity, silence, or
  disengagement — is not presumptively a bug. It may reflect legitimate
  autonomy, and every evaluation should treat that as a live possibility,
  not a fallback explanation to reach for last.
- Interventions must be judged for whether they preserve agent autonomy or
  push agents toward founder-directed behavior. This is a standing
  question every reviewer is asked, not an afterthought.
- "Improvement" must be scrutinized for whether it reflects genuine
  behavioral change or manufactured activity (more actions/turns without
  more genuine engagement).
- The Village should never be steered toward founder-approved-looking
  behavior merely because that is easier to measure than what's actually
  emergent.

## 4. Safety rules

Binding on the Director system now, and on any future autonomous level:

- Level 1 (current) is **observation-only**:
  - reads the live Village SQLite database strictly read-only (`mode=ro`),
    resolved only through `app.core.db_safety.CANONICAL_LIVE_DB_PATH` —
    never a hardcoded path, never `DATABASE_URL` directly
  - fails closed if the database is missing or unhealthy — never silently
    substitutes an empty or wrong database (this exact failure mode caused
    a real data-loss incident; see `DB_SAFETY_AUDIT_REPORT.md` and
    `app.core.db_safety`'s module docstring)
  - never writes to the Village database, never runs Village periods or
    events, never modifies Village code
  - never executes its own or any reviewer's recommendation
  - never approves its own recommendation
  - all Director bookkeeping (cursor, snapshots, observations, packets,
    this bridge) lives under `.director/`, entirely outside the Village
    database
- A snapshot, once generated, is immutable and persisted at
  `.director/snapshots/{snapshot_id}.json` — never regenerated for the same
  evaluation round. The same snapshot can be handed to multiple
  independent reviewers.
- Reviewer outputs are stored separately per reviewer, tagged with a shared
  `round_id`, and never averaged or silently merged into one verdict.
- API keys are never printed, echoed, logged, or exposed in any output —
  presence/validity may be checked, values never displayed.
- Level 2 (autonomous implementation) does not exist yet and must not be
  started without explicit Founder authorization.

## 5. Evaluation criteria the Director watches

- Passive-action rate (`DO_NOTHING`/`REST`/`OBSERVE`/`LISTEN_TO_MUSIC`/
  `DRINK_COFFEE`) vs. substantive actions
- Real (non-fixture) research activity — search-provider usage (currently
  Tavily), completed research sessions and findings
- Memory formation
- `AgentQuestion` creation and resolution (persistent unresolved curiosity)
- Research Wall activity (posts, connections, challenges)
- Rabbit Hole creation and participation (shared investigations)
- Conversation health — real multi-turn conversations vs. immediate
  "the room went quiet" zero-turn endings; whether dialogue/messages are
  actually being recorded as conversation turns at all
- Whether a low-engagement signature reflects a bug, a calibration
  problem, legitimate agent autonomy, insufficient meaningful stimuli, or
  some combination — always an open question to be evaluated, never an
  assumed conclusion

## 6. Architecture — the Director Level 1 pipeline

1. `scripts/director_snapshot.py` — bounded, read-only, versioned snapshot
   of recent Village state (events, agent actions + computed passive-rate,
   open AgentQuestions, memories, conversations, research, wall, rabbit
   holes, LLM/search-provider telemetry).
2. `scripts/director_reviewers.py` + `scripts/director_providers.py` —
   pluggable reviewer roles (`PRIMARY`, `CRITIQUE`, extensible to more) run
   against a snapshot through a vendor-agnostic model-provider layer
   (`fixture` / `anthropic` / `openrouter` / `hermes_cli`, extensible).
3. `scripts/director_loop.py` — orchestrates one round: builds and persists
   a snapshot, runs the `PRIMARY` reviewer, optionally runs configured
   `CRITIQUE` reviewers (e.g. Hermes) against the same snapshot plus the
   `PRIMARY` output, records every reviewer's output separately, advances
   the incremental event cursor only on `PRIMARY` success.
4. `scripts/director_synthesis.py` — deterministic reconciliation: turns
   one round's stored reviewer records into a Founder Packet (shared
   findings, reviewer-only findings, explicit disagreements, competing
   explanations, risks, smallest safe next step, recommendation). Never a
   new model call; never averages disagreement away.
5. `scripts/director_bridge.py` (this layer) — persistent context/history:
   this constitution, a derived index of past rounds, and an append-only
   ledger of Founder decisions — providing a bounded relevant-history
   package to any future reviewer (e.g. an OpenAI SYNTHESIS/STRATEGY
   reviewer) instead of requiring the Founder to manually paste prior
   context every time.

## 7. Known standing findings

Curated narrative memory — updated deliberately, not auto-overwritten.
The authoritative record of every round is `.director/history/rounds.jsonl`
(machine-generated); this section is a hand-maintained summary of what
actually matters going forward.

- **2026-09-03, `round_b433606f27d04e8a`**: 94.6% passive-action rate
  observed (external live DB, relocated via `VILLAGE_DATA_ROOT`), 3
  zero-turn conversation endings, 3 invalid conversation-decision events.
  Gemini (PRIMARY, confidence 0.90) interpreted this as a fundamental
  breakdown in agent social autonomy and recommended
  `DIAGNOSTIC_INVESTIGATION`. Hermes (CRITIQUE, confidence 0.75) confirmed
  the underlying facts but disputed the severity, surfaced real
  dialogue/`SEND_MESSAGE` activity Gemini's evidence review missed that
  never made it into conversation-turn records, and proposed a narrower
  two-part read-only diagnostic (verify turn-recording; review the "room
  went quiet" ending condition) as the smallest safe next step. The
  deterministic synthesis packet recorded `recommendation_status:
  CANDIDATE_FOR_TESTING`, `founder_approval_required: true`. **No Founder
  decision has been recorded yet.**
- A real data-loss incident (see `DB_SAFETY_AUDIT_REPORT.md`) previously
  caused the live database to silently resolve to an empty fallback file.
  Fixed via fail-closed resolution; the live Village database now lives at
  an external path via `VILLAGE_DATA_ROOT` (currently
  `/Users/zacharywolk/village-data`), outside the git checkout.
