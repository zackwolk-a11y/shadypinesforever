# Phase 1 Audit — What Exists, What Is Reusable, What Is Missing

Audit date: 2026-10-31 · Auditor: Claude (builder) · Scope: repository `zackwolk-a11y/shadypinesforever` (the only repository this session can reach).
No files outside `becoming/` were modified.

## 1. What this repository actually contains

| Item | What it is | Status |
|---|---|---|
| `app/`, `alembic/`, `scripts/`, `tests/` | **"The Internal Village — Research Clubhouse"**, a Python/FastAPI/SQLAlchemy/SQLite multi-agent simulation (packets 1–12 plus a "Director" oversight system) | Working. Its 27 tests pass (`pytest tests` → 27 passed, run 2026-10-31) |
| Roster in `scripts/seed_agents.py` | **The Founding Eight**: Optimisto, Vince, QuestAuthor, The Alien, Sol, Roxy, Dex, Lucid | This is the *older technical prototype roster* the master prompt says must **not** be substituted |
| `app/web/static/world/` | 2.5D "World View" with semantic event replay that renders only real events | Canvas/ES modules, with two raster assets |
| `.director/` | Director governance: constitution, snapshots, reviewer packets, diagnostics, experiments | Advisory oversight records |
| `index 2.html` | "Shady Pines Forever", a single-file canvas game (festival stages, radio, NPCs) | Unrelated prototype, about 40 KB |
| `DB_SAFETY_AUDIT_REPORT.md` | Post-incident report on a real live-DB data-loss event | Important lessons learned |

## 2. What was searched for and NOT found

Searched the full tree (code, docs, `.director` packets, git history across all branches):

- **None of the nine residents** (Tony, Mark, Haize, Ashley, Ralph, Bernie, Mao, Pepper, Anna) appear anywhere.
- **No Great Questions curriculum.**
- **No Healthy Village conversation archives, stories, or research library.** The live database (`data/live/internal_village.db`) is git-ignored and is not in the clone.
- No Healthy Village–branded project. The phrases "Healthy Village" and "Village of Becoming" do not appear in the repo.
- No folders on the Founder's computers are shared with this cloud session (`list_computer_folders` returned none).

**Conclusion:** the "existing Healthy Village project" described in the master prompt is most likely on the Founder's Mac mini, or in another repository not attached to this session. Everything in `becoming/canon/` is therefore **authored from the master prompt** and labeled that way. When the original material is supplied, it will be imported and reconciled as described in [MIGRATION.md](MIGRATION.md). → Issue **HV-001**.

## 3. Reuse assessment of the Internal Village codebase

The existing code is careful, honesty-oriented engineering. Many of its guarantees are exactly what Healthy Village requires. Strategy: **port, don't import.** Proven modules are copied into `becoming/backend` with an attribution header and adapted, so the two projects never share a database, migrations, or runtime. → [DECISIONS.md](DECISIONS.md) D-002.

| Component (old path) | Verdict | Why |
|---|---|---|
| `app/providers/llm/*` (fixture, anthropic, claude_cli, base with `LLMRateLimited`/`LLMProviderUnavailable`) | **Port** | A provider-agnostic structured-output boundary with a rate-limit pause. Directly satisfies Part XX |
| `app/providers/research/*` (base, tavily, brave, fixture) | **Port and extend** | Add free primary-source adapters (Gutenberg, Wikipedia, OpenAlex, arXiv, Crossref) |
| `app/core/db_safety.py` | **Port** | Fail-closed live-DB resolution, integrity checks, categorized backups. Born from a real incident |
| `app/db/models/events.py` (append-only events, causation) | **Port the pattern** | The basis of the inspectable event history |
| `research_provenance` (sources → passages → claims → claim_evidence) | **Port** | Matches Part X's provenance requirement |
| `agent_exposures` (partial-knowledge enforcement) | **Port** | Prevents residents from "knowing" research they never encountered, so attribution is enforceable |
| `beliefs` + `belief_basis` | **Port and extend** | Add before/after/cause revision records for Part XIII |
| `memory.py`, `reflection.py`, `agent_questions.py` (curiosity) | **Adapt** | Good concepts; must be re-keyed to event IDs and the nine residents |
| `orchestrator.py`, `scheduler.py`, `conversations.py`, `dialogue.py` | **Reference only** | Built around a clubhouse "periods" model and an activation budget; Healthy Village needs an opportunity/consent-based social scheduler |
| `domain/characters.py` (voice bias dimensions) | **Adapt the idea** | Structured voice knobs fit the new canon schema |
| `telemetry.py` / `llm_runs` | **Port** | Model-call accounting for the cost log |
| Fishbowl web (Jinja pages) and World View (canvas) | **Replace** | Part V requires a real game layer (collision, interiors, camera, avatar). New stack: React + Phaser |
| `.director/` Director system | **Leave in place** | Its observation-only principles inform Part XXVI's evaluator, but it is coupled to the old DB |
| Founding Eight roster and clubhouse locations | **Do not reuse** | Wrong roster and world |

## 4. Gap analysis against the master specification

Legend: ✅ exists and reusable · 🟡 partial or needs adaptation · ❌ absent

| Part | Requirement | Status | Notes |
|---|---|---|---|
| II–III | Nine residents, deep character configuration | 🟡 → **now authored** | `canon/residents/*.yaml`, validated by tests. Source materials are pending (HV-002) |
| III | Foundational vs revisable beliefs, revision history | 🟡 | Schema separates them. Revision history arrives with the event store (Phase 6) |
| IV | Canonical style guide | ✅ **done** | `canon/style/canonical_style.txt` + `02_STYLE_GUIDE.md` |
| IV | Five visual alternatives | 🟡 **written** | `03_WORLD_AND_VISUAL_DIRECTIONS.md`. Awaiting Founder choice; no images generated |
| IV–V | Empty interactive world, collision, entrances, nav | 🟡 | Geometry, collision, and connectivity done as validated data. Game client not built yet |
| V | Camera, interiors, day/night, seasons, sound, a11y text nav | ❌ | Phase 3–4 |
| VI | Social simulation with consent and solitude | ❌ | Old activation model is not suitable; new design in spec §6 |
| VII | Experimental calendar, no offline backfill | 🟡 | `sim_calendar.py` done and tested. Scheduler, pause, replay, and clone come later |
| VIII–IX | Conversation engine, Great Questions | 🟡 | Curriculum reconstructed and validated. Engine in Phase 5 |
| X | Research with provenance | 🟡 | Old pipeline portable |
| XI | Multi-store memory with event-ID integrity | 🟡 | Old memory portable. The event-ID constraint is new |
| XII–XIII | Relationships and development with evidence | 🟡 | Old `relationships` table lacks evidence links |
| XIV–XV | Gatherings, visitor avatar, founder participation | ❌ | |
| XVI | Journal, reports, PDF/MD/JSON | 🟡 | Old daily synthesis exists; no PDF |
| XVII | Founder dashboard | ❌ | |
| XIX | Local-first, single-writer, recovery | 🟡 | db_safety portable; single-writer lease is new |
| XX | Cost limits and provider pause | ✅ | Port circuit breaker and budgets |
| XXI | Execution boundaries | 🟡 | Spec §9 defines the allowlist |
| XXVI | Evaluator / diagnostics | 🟡 | Director diagnostics are a design reference |

## 5. Preservation plan (before anything touches existing data)

1. The old project is **read-only** to this effort. The new project lives entirely in `becoming/`, with its own DB path, migrations, and process.
2. Old live data (`data/live/internal_village.db` on the Mac mini) is never opened for writing by new code. Any import reads a **copy** taken with SQLite's online backup API (see [04_OPERATIONS.md](04_OPERATIONS.md) §3).
3. Founding Eight data is **not** imported into Healthy Village's event history. If wanted, it can be archived as `imported_legacy` reference material, never as Healthy Village events.
4. Healthy Village stories or archives, when supplied, are imported with `provenance = authored_fiction` and can never be cited as memories (enforced by schema; see spec §5).
