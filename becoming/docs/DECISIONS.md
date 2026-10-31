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
