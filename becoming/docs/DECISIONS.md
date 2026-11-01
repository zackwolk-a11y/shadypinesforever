# Project Decision Log

Format: ID · date · decision · rationale · reversibility. Founder decisions are marked **[F]**; builder decisions made under "sensible, reversible defaults" are marked **[B]**.

| ID | Date | Decision | Rationale | Reversible? |
|---|---|---|---|---|
| D-001 [B] | 2026-10-31 | New project lives in `becoming/` inside this repo, on branch `claude/village-of-becoming-foundation` | Only repository reachable this session; keeps the old project untouched | Yes, can be moved to its own repo with history via `git subtree split` |
| D-002 [B] | 2026-10-31 | Port proven modules from the Internal Village (providers, db_safety, provenance, event pattern) rather than import them | Separate DBs, migrations, and runtimes; no coupling to the Founding Eight schema | Yes |
| D-003 [B] | 2026-10-31 | Frontend: TypeScript + React + Phaser 3 (Vite) | Phaser provides tilemaps, collision, cameras, scenes, input, and sound; PixiJS would require rebuilding these | Moderate; the world is data-driven so a renderer swap is contained |
| D-004 [B] | 2026-10-31 | World geometry is authoritative JSON (`canon/world/village_layout.json`) validated by tests; art conforms to it | Part V: collision/interaction independent of the art layer | Yes |
| D-005 [B] | 2026-10-31 | Doors face south (toward the camera) for every building | Standard 3/4-view readability; consistent sprite production | Yes |
| D-006 [B] | 2026-10-31 | Simulated time is tick-driven, measured in sim-minutes; 30-day months; default 15 real min/tick = 450 sim min; no backfill while offline or paused | Part VII honesty: offline time is a recorded gap. Consequence: a sim month can take longer than one real day if the system is down | Yes, all values are config |
| D-007 [B] | 2026-10-31 | Canon may never mark a source `retrieved_verified`, and may not contain memories or relationship histories (enforced by schema) | Part XI memory integrity; Part X provenance | Yes, but should not be |
| D-008 [B] | 2026-10-31 | Great Questions curriculum reconstructed from the master prompt, labeled `reconstructed_from_master_prompt` | The original was not found (HV-001) | Yes, to be reconciled on import |
| D-009 [B] | 2026-10-31 | Single-writer Steward process with file lock; API only enqueues commands | Part XIX protection against simultaneous jobs | Yes |
| D-010 [B] | 2026-10-31 | Semantic retrieval starts with SQLite FTS5 (free, local); embeddings optional later | Cost and local-first | Yes |
| D-011 [B] | 2026-10-31 | Pronouns for residents follow the Founder's character descriptions (he: Tony, Mark, Ralph, Bernie, Mao; she: Haize, Ashley, Pepper, Anna) | Stated in the master prompt | Founder may change |
| D-012 [B] | 2026-10-31 | Recommended visual base: Golden Spring Commons + Riverstone touches; other directions become seasonal palettes | Seasonal variation is required anyway | **Awaiting [F]** |
| D-013 [B] | 2026-10-31 | Pepper's song themes are recorded from the Founder's Oct 20 guide, with status `known_reference_pending_retrieval`, never as lyrics | Bandcamp unreachable here; copyright | Yes |
| D-014 [B] | 2026-10-31 | Recommended provider configuration: Sonnet 5.5 dialogue + Sonnet 5.5 Batch reports, $10/day hard cap, pending a Haiku A/B | Estimated $36–$103 per 12-month experiment | **Awaiting [F]** |
| D-015 [B] | 2026-10-31 | Founder profiles supersede the builder's prompt-derived drafts for character content; master-prompt philosophical interests kept alongside | Founder-authored, source-grounded | Yes |
| D-016 [B] | 2026-10-31 | One shared source registry with the Founder's codes; editorial scholarship is a distinct role | Single provenance store | Yes |
| D-017 [B] | 2026-10-31 | "Scenes worth testing" stored as evaluation probes, never scripts | Part XXII | Yes |
| D-018 [B] | 2026-11-01 | Mood and direction art via the Founder's ChatGPT subscription (manual copy, paste and upload); builder redraws game tiles and sprites to the 16 px grid | No extra cost; Founder controls each image; AI images are not grid-accurate pixel art | Yes |
| D-019 [F] | 2026-11-01 | Resident portraits for Tony, Ashley and Pepper accepted; Founder confirms they are original fictional characters | Founder statement | Yes |
| D-020 [B] | 2026-11-01 | Portraits are profile and dialogue art; small walking map sprites are drawn separately in matching colors | Portraits are too detailed for 16 px map sprites | Yes |
| D-021 [F] | 2026-11-01 | Keep Mao v1 and Bernie v1 art as provisional; edits to come later | Founder decision after the builder flagged concerns (HV-020, HV-021) | Yes |
| D-022 [F] | 2026-11-01 | Concept map v2 is the official village map; the layout data is aligned to it | Founder decision | Yes |
| D-023 [F] | 2026-11-01 | Keep the crystals in the Quiet Grove (decorative only; no spiritual claims attached) | Founder decision | Yes |
| D-024 [F] | 2026-11-01 | Tony has two outfits (portrait: blue tee and striped strap; sprite: cream shirt and rust trousers) as a wardrobe | Founder decision | Yes |
| D-025 [B] | 2026-11-01 | First playable client uses Phaser 3.90 + Vite + TypeScript with a plain HTML side panel; React shell deferred to the dashboard phase; Phaser 4 (now released) noted as a later upgrade | Smallest working client; Phaser 3 API is the one the plan assumed | Yes |
| D-026 [B] | 2026-11-01 | The game reads geometry only from tools/export_world.py output (validated layout); the client never re-implements geometry | Single source of truth (Part V) | Yes |
| D-027 [B] | 2026-11-01 | Residents are shown standing at home, labelled "not simulated yet", until the simulation records events | Part XXII honesty: no animation unrelated to agent decisions | Yes |
| D-028 [F] | 2026-11-01 | The player avatar is Zachary, Chief Human Officer (Founder), defined in canon/founder.yaml and kept separate from the nine residents | Founder request; Part XV (Founder is a participant, residents need not agree) | Yes |
