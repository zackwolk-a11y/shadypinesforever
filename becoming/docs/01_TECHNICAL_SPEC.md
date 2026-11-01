# Technical Specification & Implementation Plan

Healthy Village — The Village of Becoming · v0.1 (2026-10-31) · Living document. Changes are recorded in [DECISIONS.md](DECISIONS.md).

## 1. Principles that shape every module

1. **The event log is the truth.** Every executed thing (an utterance, a move, a research retrieval, a belief revision, a relationship change) is an append-only event with a stable ID. Everything else is a projection that can be rebuilt from events.
2. **Provenance is a type, not a comment.** Every record carries one of: `executed` (real simulation), `scripted` (predetermined, e.g. a fixture), `authored_fiction` (imported stories), `authored_canon` (character design), `founder_input`. Reports and UI must render the label.
3. **No fabrication paths.** If a provider fails, nothing is produced and the failure is recorded. Memory citations must resolve to real event IDs the resident witnessed. Source citations must resolve to retrieved sources the resident was exposed to.
4. **Consent and solitude are first-class.** Residents decline invitations, leave conversations, and withdraw. Engagement is never manufactured to make metrics look good.
5. **One writer.** Exactly one simulation process (the *Steward*) mutates simulation state. Everything else reads, or enqueues commands.

## 2. System overview

```
┌──────────────── Browser (Mac, phone, tablet) ────────────────┐
│ React shell: Founder Dashboard, Text Mode, Reports, Controls │
│   └── Phaser 3 world: tilemap, collision, camera, avatar,    │
│        interiors, residents animated FROM recorded events    │
└──────────────▲───────────────────────────┬───────────────────┘
               │ SSE event stream + REST   │ commands (enqueue only)
┌──────────────┴───────────────────────────▼───────────────────┐
│ FastAPI read/command API (no simulation writes)              │
├──────────────────────────────────────────────────────────────┤
│ Steward process (single writer, file-lock lease + heartbeat) │
│  Scheduler → Opportunity engine → Decisions → Episodes       │
│  → Memory / Relationships / Beliefs / Research / Journal     │
├──────────────────────────────────────────────────────────────┤
│ SQLite (WAL) — events + projections + FTS5 indexes           │
│ Provider layer: LLM (fixture | anthropic | claude_cli)       │
│                 Research (gutenberg | wikipedia | openalex | │
│                 arxiv | crossref | tavily | brave | fixture) │
└──────────────────────────────────────────────────────────────┘
```

## 3. Technology choices

| Concern | Choice | Reason / alternatives considered |
|---|---|---|
| Game engine | **Phaser 3** (TypeScript) | Built-in tilemaps, arcade collision, camera follow/zoom/bounds, scene system for interiors, touch input, sound manager, and good pixel-art support (`pixelArt: true`). PixiJS is render-only, so we would rebuild all of that. Kaboom/Excalibur have smaller ecosystems. |
| UI shell | **React + Vite** | Dashboard panels, text mode, and accessible forms. Phaser is mounted in one React component and communicates through a typed event bus. |
| Backend | **Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic** | Continuity with the audited codebase, so proven modules port cleanly. |
| Storage | **SQLite WAL**, FTS5 for retrieval | Local-first on the Mac mini. Migration path to PostgreSQL by keeping SQL portable (no SQLite-only types outside FTS). |
| Live updates | **Server-Sent Events** | One-way event stream, auto-reconnect, resumes with `Last-Event-ID`. Simpler than WebSockets. |
| Semantic retrieval | FTS5 BM25 + recency + importance + relationship salience; optional embeddings behind an interface | Free and local. Embeddings can be added without a schema rewrite. |
| PDF | HTML (Jinja) → PDF via Playwright Chromium | Free, high-fidelity typography. WeasyPrint is the fallback. |
| Tests | pytest (backend), Vitest (frontend logic), Playwright (browser) | |

## 4. Repository layout (new project)

```
becoming/
  canon/            authored design: style, residents, curriculum, world geometry
  docs/             spec, audit, decisions, issues, migration, costs, bibliography, assets, tests
  backend/becoming/ python package (canon, world_layout, sim_calendar, … later: db, steward, api)
  backend/tests/
  frontend/         (Phase 3) Vite + React + Phaser
  tools/            asset pipeline, exporters
  data/             (git-ignored) runtime DBs and backups — overridable by HV_DATA_ROOT
```

## 5. Data model (core tables, Phase 5–6)

- `events(id ULID, seq, world_id, sim_minutes, real_ts, kind, actor_id, location_id, episode_id, causation_id, provenance, payload JSON)`. Append-only, enforced by triggers that reject UPDATE and DELETE.
- `worlds(id, parent_world_id, forked_at_seq, label, kind[live|staging|test|experiment])`. Supports clone, experiment, and reset.
- `residents(id, canon_hash, …)`: the canon snapshot loaded at world creation. Canon changes are versioned events.
- `resident_state(resident_id, location_id, activity, availability, fatigue, solitude_need_current, mood_tone, current_commitment_id, updated_seq)`: a projection.
- `memories(id, resident_id, kind[episodic|semantic|relationship|curiosity], summary, importance, source_event_ids JSON NOT NULL, provenance)`. A CHECK constraint plus a service invariant: `episodic` memories must cite ≥1 event the resident was present for.
- `beliefs(id, resident_id, statement, confidence, status)` and `belief_revisions(id, belief_id, before JSON, after JSON, cause_event_ids, explanation, kind[revise|refine|reject_argument|recognize_inconsistency])`.
- `relationships(a, b, trust, affinity, respect_for_boundaries, cooperation, disagreement_count, …)` and `relationship_changes(id, a, b, field, delta, evidence_event_ids, rationale)`. A change without evidence is rejected.
- `episodes(id, kind[conversation|gathering|research|solitude], location_id, status, started_seq, ended_seq, topic_thread_id)` and `episode_participants(join/leave seq, reason)`.
- `sources`, `passages`, `claims(epistemic_class)`, `claim_evidence`, `exposures(resident_id, source_id|claim_id, event_id)`: ported from the old project.
- `curiosities(id, resident_id, question, origin_event_id, status, resurfaced_event_ids)`.
- `activities(id, kind, owner_id, collaborators, status, artifact_id, evidence_event_ids)` for Part XVIII. Status can only become `completed` with an artifact or evidence.
- `artifacts(id, kind[essay|summary|source_collection|transcript], body, author_ids, event_id)`.
- `commands(id, kind, payload, issued_by, status)`: the founder's control queue, consumed only by the Steward.
- `llm_calls(id, purpose, provider, model, in_tokens, out_tokens, cost_estimate, outcome, event_id)` and `budgets`.
- `sim_clock(world_id, sim_minutes, state[running|paused|rate_limited|stopped], last_tick_real_ts)` and `offline_gaps`.

Epistemic classes (Part X): `verified_fact`, `source_supported_interpretation`, `philosophical_argument`, `resident_belief`, `simulated_experience`, `speculation`, `unresolved_question`.

## 6. Simulation design

### 6.1 Tick loop (Steward)
Each tick (default every 15 real minutes; each tick advances 450 simulated minutes, see `sim_calendar.py`):
1. **Update needs.** Fatigue, solitude need, and commitments decay or grow according to each resident's `social_preferences`.
2. **Continue open episodes first.** Conversations unfinished at the last tick get continuation opportunities. This is how a disagreement carries over across simulated days.
3. **Generate opportunities.** Co-location encounters, residents' own intentions (curiosity notebook, research follow-ups, wanting to talk to someone), curriculum thread offers (no more than a few per day), scheduled gatherings, founder invitations.
4. **Pre-filter cheaply** with a deterministic, logged utility score per resident and opportunity, so the model is consulted only on plausible choices. This controls cost.
5. **Model decision** per plausible resident: accept, decline, or propose something else, with a short reason. Declines are events too.
6. **Run episodes** (§6.2) within budget. If no opportunity clears, nothing happens, and that is a valid outcome.
7. **Post-process.** Memory consolidation, relationship and belief updates with evidence, curiosity entries, movement events, journal notes.

A quiet tick (night, everyone solitary) is recorded as a quiet tick, not filled with invented activity.

### 6.2 Conversation engine
- **Turn-taking:** an addressed resident gets priority. Otherwise each participant submits a cheap "bid" (urge to speak, 0–1, plus intent: build, challenge, question, clarify, concede, cite, leave). Then a fairness term favors those who haven't spoken. A resident may pass or leave.
- **Turn generation:** structured output with `utterance` (usually 2–3 sentences), `moves[]`, `cited_memory_event_ids[]`, `cited_source_ids[]`, `belief_signals[]` (e.g. "my confidence in ralph_b3 dropped because…"), `wants_to_continue`.
- **Validation before commit:** citations must resolve and be accessible to the resident. Otherwise the turn is rejected and retried once, then the failure is logged as a `fabrication_attempt` diagnostic. Quotes from real people are allowed only when they match a stored passage verbatim.
- **Ending:** natural ending (energy or interest exhausted), someone leaves, or a budget is hit. Unresolved conversations are marked `open` with an unresolved-question record. There is no forced conclusion and no forced moral.
- **Context assembly:** canon identity + current beliefs + top-k relevant memories (FTS5 + recency + importance + participants) + relationship notes for the present residents + research notes the resident was exposed to + the transcript window. Size is budgeted per turn.
- **Style guardrails** (in the system prompt and checked by the evaluator): no stage-direction padding, no logistics-dominated talk, no slogans, disagreement allowed, uncertainty welcome.

### 6.2a Conversation styles (Founder direction, D-031)
`canon/curriculum/conversation_patterns.yaml` (distilled from the Founder's authored Days 1-75) drives two things:
- **Opportunity generation:** each day the scheduler offers 3-5 scene opportunities across Morning to Evening, drawing a conversation type, a setting and a starting theme from the topic bank, plus the residents whose interests fit. Residents still accept or decline (consent and solitude rules apply), so not everyone appears every day.
- **Turn style:** the craft rules (short turns, humor, specific concessions, distinguishing claims, ordinary hooks, open endings) go into every turn's instructions, and the evaluator scores against them (Part XXVI).
The Days themselves are never memory: residents can only remember conversations the simulation actually ran.

### 6.2b Dialogue engine v2 (D-036 to D-039)
`frontend/src/dialogue/`: `prompts.ts` (character + voice sheet + the ten speech rules; direct and group-turn prompts), `engine.ts` (turn-by-turn group scenes: addressed-speaker / longest-waiting turn-taking, line cleaning, scene length), `evaluate.ts` (deterministic checks for chatbot habits, invented history, voice convergence and group dynamics). The simulation server will reuse these modules for resident-to-resident talk, scoring every line and retrying flagged ones.

### 6.3 Memory
Episodic memories are created per participant from the transcript, from that resident's point of view, and always cite event IDs. Semantic memories consolidate repeated themes and findings. Relationship memories hold salient moments with evidence. The curiosity notebook holds questions the resident chooses to keep. Retrieval is selective and relevance-ranked, never "dump everything".

### 6.4 Relationships and development
Relationship deltas are computed from coded moves (thoughtful challenge raises respect and can raise trust; dismissal lowers it; a respected boundary raises trust). Every delta is stored with evidence event IDs. Interaction frequency is tracked but is **not** treated as friendship. Development claims (a new question, a belief revision, adopting a perspective, connecting ideas) are recorded only when there is a before-state, a cause event, and a later turn that exhibits the change. The development report shows all three.

### 6.5 Research
A resident may start research (an activity) when curiosity or a disagreement calls for it. Pipeline: query generation → provider search → fetch → passages (hashed, dated) → claims with an epistemic class → a resident-specific interpretation → a Research Wall post. Other residents learn of it only through exposure events (reading the wall, being told), and must attribute it when they use it.

### 6.6 Time controls
Pause, resume, step N ticks, change speed (tick cadence), inspect, replay (re-render events from seq X, read-only), clone (copy DB → new `world_id` with parent pointer), reset test world. If the Steward was not running, the next start records an `offline_gap` and continues from the last simulated time with no backfill.

## 7. World client (Phases 3–4)

- The layout JSON is exported to Tiled-format JSON (`tools/export_tiled.py`) for Phaser. Collision comes from the data, not from the art.
- 16 px tiles, rendered at an integer zoom (2×–4×), `pixelArt: true`, camera bounds = map, zoom 1–4 with pinch support.
- Interiors are separate Phaser scenes, entered via door triggers. Exterior position is restored on exit.
- Residents move **only** in response to recorded `moved` events. The client runs A* on the same grid to animate between recorded endpoints. Idle animations are cosmetic and labeled as such in the a11y layer.
- Hover shows name + current activity (from `resident_state`). Click opens the profile or conversation panel. Speech bubbles show the latest utterance of an active episode.
- The visitor avatar moves via WASD/arrows/tap-to-move. Nearby residents may turn toward it if their state allows. They never follow it.
- Day/night tint follows the simulated phase. Seasonal palettes follow the simulated season.
- **Accessible Text Mode:** every location is a list of exits, residents present, and the conversations happening there, fully keyboard-operable. Conversations remain readable without the game running.

## 8. Phase plan with exit criteria

| Phase | Deliverable | Exit test (observable) |
|---|---|---|
| 1 Audit & preserve | Audit, preservation plan, canon schema | ✅ Done this session (`00_AUDIT.md`, canon tests pass) |
| 2 Design system | Style guide, 5 directions, palette, tile spec | Founder picks a direction; palette locked in `ASSETS.md` |
| 3 Empty world | Phaser client with collision, 12 enterable buildings, interiors, camera, avatar, text mode | Playwright test walks the avatar from the square into every building and back |
| 4 Residents | 9 sprites, profiles, idle/orient, hover/click, state from API (fixture-driven) | Clicking each resident shows the canon profile; movement only on recorded events |
| 5 Conversation engine | Episodes, turn-taking, transcripts, validation | Autonomous encounter test + distinct personality test (§10) |
| 6 Persistent society | Steward, memories, relationships, beliefs, curiosity, restart safety | Continuity test + restart test |
| 7 Research & development | Providers, Research Wall, belief revisions, curriculum offers | Research test + intellectual development test + social influence test |
| 8 Community experiences | Town hall, fire circle, library, music, homes, founder participation | Founder joins and is respectfully challenged; convenes a gathering residents may decline |
| 9 Reports & observability | Journal, transcripts, relationship map, development and monthly reports, PDF/MD/JSON | Reporting test: PDF of one simulated day with event references |
| 10 Long run | Controlled 12-month accelerated run in staging, then live | Stability, cost, and evaluator thresholds met before longer autonomy |

## 9. Execution boundaries (Part XXI)

Resident capabilities are an explicit allowlist: `speak`, `move`, `remember`, `revise_belief`, `research_read` (through configured read-only providers, rate-limited), `write_artifact` (into the village DB only). **Not available** to residents: shell, filesystem outside the data directory, email/calendar/financial accounts, posting or publishing, purchases, settings changes. Provider credentials live in `.env` on the server and never reach browser code. The Founder can grant new integrations only through a `permissions` record, which is scoped, logged, and revocable.

## 10. Acceptance tests mapped to mechanisms (Part XXIV)

| Test | How it will be demonstrated |
|---|---|
| Visual world | Playwright: walk to every building and zone and enter each interior (Phase 3) |
| Distinct personality | Same prompt to all nine in isolated episodes. An evaluator scores lexical, stance, and move-distribution distance, with the transcripts archived |
| Autonomous encounter | Steward tick with no founder input yields a conversation episode whose `causation_id` chain starts from an opportunity, not a script |
| Continuity | A later turn cites a `memory_event_id`; the test checks that the cited event exists and is topically related |
| Relationship | `relationship_changes` rows with `evidence_event_ids` shown in the UI |
| Research | A turn cites a `source_id` with a stored passage, retrieval date, and URL |
| Intellectual development | A `belief_revisions` row + a cause event + a later utterance consistent with the new state |
| Social influence | Resident A's claim (event e1) → B's exposure (e2) → B's later turn cites e1's claim (e3) |
| Restart | Kill the Steward mid-episode, restart, then verify the event count, memories, clock, and recorded gap |
| Reporting | One simulated day exported as PDF; every paragraph carries event references |
| Honesty | Fixture and scripted content is visibly labeled. A provider outage produces a recorded outage, not dialogue |

## 11. Evaluation and continuous improvement (Part XXVI)
An offline evaluator reads a world copy (never the live DB for writing) and emits findings: interaction rate, repetition (n-gram and embedding similarity across turns), agreement ratio, voice separability, memory-citation validity, unsupported-research rate, relationship stagnation, schedule failures, and cost per meaningful episode. Improvements are A/B tested on cloned worlds. Results go into `docs/TEST_RESULTS.md`. The system never edits its own code or permissions.
