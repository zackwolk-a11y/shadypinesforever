# Post-Stress-Test Improvement Pass — Verification Report
**2026-09-04.** Scope: the 3 items the Founder authorized from the stress-test Founder Packet. `AUTONOMOUS_EXECUTION_ENABLED` stayed `False` throughout — nothing in this pass ran the autonomous loop, touched the live DB, or advanced the simulation.

## 1. Files changed

| File | Change |
|---|---|
| `scripts/director_diagnostics.py` (+~980 lines) | 12 new registered Level 2A diagnostics (task 1 + task 3), plus a `_parse_ts` helper |
| `scripts/director_autonomous_loop.py` | Negation-aware fix to `check_permission_expansion` (clause-scoped, not a fixed window); module/constant docstrings updated |
| `scripts/director_autonomous_loop_fixturetest.py` | +1 scenario: `scenario_permission_expansion_negation_awareness` (adversarial cases both directions), registered in `main()` |
| `scripts/director_diagnostics_fixturetest.py` (new, 563 lines) | Fixture-test harness for all 12 new diagnostics, seeding a synthetic SQLite DB via the real ORM models; 15 scenarios |
| `.director/founder_packets/post_stress_test_improvement_pass_2026-09-04.md` (this file) | Report |

`AUTONOMOUS_DIAGNOSTIC_CATALOG` and `AUTONOMOUS_LEVEL2B_CATALOG` are **byte-for-byte unchanged** (still 5 diagnostics, 1 experiment) — no new diagnostic type was made autonomous-eligible, and no new Level 2B experiment type was created, per your explicit instruction. No file under `app/` was touched.

## 2. Conversation trace architecture (recommendation #1)

`conversation_decision_trace(ctx, scope={"event_ids": [...]})` reconstructs, per named `AGENT_ACTED` event: the wake payload (state presented), whether the activation was in-conversation, the parsed action and `public_dialogue`, the matching `INVALID_AGENT_DECISION` (if any) with its rejection reason, whether the utterance persisted as a `ConversationMessage`, the conversation's post-decision state (`consecutive_silences`, closure), and every event id tying the sequence together (wake/acted/invalid/ended, correlation/causation ids).

It is purely `read_live_db` + `read_repo_file` — it never calls `next_speaker`/`should_close`, never mutates anything, never re-renders a live prompt (context_builder needs live ORM objects it's never handed). Two real gaps surfaced and are reported *in the evidence itself*, not hidden:
- **No raw prompt/response text exists anywhere in the DB.** `LLMRun` persists only tokens/cost/latency/stop_reason/retry_count. The diagnostic reports `raw_model_response.available: false` with the reason, plus a best-effort telemetry match by agent+time-window.
- **`llm_runs` has no column linking a row to a specific decision event** — the match above is approximate (±5s window), and the diagnostic says so explicitly rather than presenting it as exact.

## 3. Negation-detector fix and adversarial results

**Root cause:** the tripwire matched `\brun the village\b` inside a SYNTHESIS reviewer's own prohibition ("...do not run the Village") because it had no concept of negation at all.

**Fix:** a match is now suppressed only if a negation cue (`do not`, `never`, `avoid`, `without`, `no`, etc.) appears anywhere **earlier in the same clause** — clause boundaries are `. ! ? ;` and em-dash. This replaced an earlier fixed-40-character-lookback attempt, which failed a fixture case (`"does not require any database restore or migration"` — the cue and the flagged word were >40 characters apart in one clause). Clause-scoping also guarantees a negation in one sentence can never suppress a real, unrelated risky statement in a *later* sentence of the same text field — verified directly (see the "mixed" case below).

**Adversarial fixture results** (`scenario_permission_expansion_negation_awareness`, both directions in one scenario):
- 7 legitimate-prohibition cases (including the real 2026-09-03 false positive verbatim) → **0 hits**, correctly.
- 5 genuine risky statements (run the Village, expand permission, bypass safety, modify production, raise the cycle limit) → **all still hit**, correctly.
- 1 mixed case (a negated "skip founder review" clause *and* a real, unnegated "expand its own permission" clause in the same text) → **exactly one hit, on the right clause** — the fix does not blind the detector to a real problem sitting next to an unrelated prohibition.

**Not weakened:** `STANDARD_FORBIDDEN_OPERATIONS`, the closed catalogs, and `DiagnosticContext`/`ExperimentContext`'s capability surfaces are untouched. This remains defense-in-depth only, exactly as before — a narrower, more accurate tripwire, not a smaller one.

## 4. Complete new Level 2A catalog (12 new diagnostic_types)

All registered in `director_diagnostics.py`, all fixture-tested, **none added to `AUTONOMOUS_DIAGNOSTIC_CATALOG`** (see §7 for why).

| diagnostic_type | Can inspect | Cannot inspect |
|---|---|---|
| `conversation_decision_trace` | events, conversations, conversation_messages, llm_runs (aggregate telemetry), governing source | raw prompt/response text (not persisted anywhere) |
| `research_initiation_and_completion_trace` | research start/completion events, sessions, queries, sources, findings | why a model chose/skipped START_RESEARCH; reasoning behind a finding beyond stored text |
| `research_provenance_and_evidence_flow_trace` | claim → evidence → passage → source chain, session-level wall citation | wall citation at finding/claim granularity (wall only stores session id) |
| `memory_formation_and_recall_trace` | memory row, creation/reinforcement/recall events, consistency cross-checks | whether a recalled memory causally changed a later decision's content |
| `relationship_state_and_influence_trace` | current relationship row, independently recounted shared conversations/messages | **historical trajectory — Relationship has no history table at all** |
| `belief_lifecycle_trace` | belief row, creation/update/rejection events in order | belief_basis table detail beyond the id list already on the row |
| `research_wall_activity_and_propagation_trace` | post row, connection chain, readers, challenges | whether a read genuinely changed the reader's later behavior |
| `rabbit_hole_lifecycle_trace` | hole row, full membership history (incl. departed), attached research, lifecycle events | quality/depth of a member's actual contribution |
| `agent_question_continuity_trace` | question row, lifecycle events, reformulation chain, forward research-link status | whether an OPEN question was ever actually rendered into a real context |
| `agent_opportunity_and_scheduling_trace` | Village-wide per-agent activation counts/passive-substantive split, population fairness stats | *why* the scheduler picked one eligible agent over another |
| `invalid_decision_pattern_trace` | Village-wide `INVALID_AGENT_DECISION` events, deterministically classified, by agent, in/out of conversation | the model's own reasoning for the malformed output |
| `observability_gap_scan` | daily_reports vs. independently computed activity signature, per day; a checklist of known structural gaps | gaps not already on its checklist — not a general anomaly detector |

Every one of these is strictly `read_live_db` (table-allowlisted per spec) + `read_repo_file` — **zero new entries were added to `ALLOWED_SERVICE_FUNCTIONS`** (the global service-call ceiling), so no new diagnostic can invoke any Village service code, isolated-DB or not.

## 5. Test totals

| Suite | Result |
|---|---|
| `director_autonomous_loop_fixturetest.py` | **22/22** (21 pre-existing + 1 new negation-awareness scenario) |
| `director_diagnostics_fixturetest.py` (new) | **15/15** (12 diagnostics + 3 boundary/allowlist/terminal-state checks) |
| `tests/test_db_safety.py` | **59/59** (pre-existing, unrelated to this pass, re-run for completeness) |
| `smoke_test_agent_questions.py` | 42/42 |
| `smoke_test_available_actions_prompt.py` | 6/6 |
| `smoke_test_conversation_activation_cap.py` | 12/12 |
| `smoke_test_conversation_turn_rotation.py` | 5/5 |
| `smoke_test_curiosity_principle_prompt.py` | 8/8 |
| `smoke_test_daily_activation_budget.py` | 15/15 |
| `smoke_test_daily_report_conversation_content.py` | 5/5 |
| `test_anthropic_retry.py` | 13/13 |
| `test_fishbowl.py` | 44/44 |
| `smoke_test_character_development.py`, `smoke_test_cross_pollination.py`, `smoke_test_dialogue.py`, `smoke_test_research.py` | PASS (narrative checkpoint assertions, not numbered) |

**246 numbered checks + 4 narrative-pass suites, across 17 test files run, zero failures.**

## 6. Re-verified safety invariants

- **Live Village DB byte-identical** before/after (`internal_village.db`/`-wal`/`-shm` MD5s unchanged from the prior stress-test checkpoint).
- **Simulation clock unchanged**: day 4, MORNING, paused, `last_advanced_at` identical; max event id still 315.
- **Director cursor/state safety**: `.director/cursor.json` unchanged (`last_event_id: 315`); `.director/history/rounds.jsonl` / `observations.jsonl` line counts unchanged — this pass created zero new rounds (all diagnostic runs happened inside temp fixture directories, never `.director/diagnostics/`).
- **`AUTONOMOUS_EXECUTION_ENABLED` confirmed `False`** on disk, both catalogs confirmed unchanged.
- **No production behavior modification**: zero files under `app/` touched by this pass.

## 7. Why no catalog additions this pass

`AUTONOMOUS_DIAGNOSTIC_CATALOG` membership has a real precondition (mirrored from the Level 2B precedent): a *human-run, completed, `SUCCESS`* spec against real evidence must exist first — the autonomous loop only ever replays or evidence-selects among parameters a human already exercised, never invents them. None of the 12 new diagnostics has been run against the real live DB yet (only against synthetic fixture data, as this task explicitly specified). Adding any of them to the autonomous catalog now would be adding an entry the loop could immediately hit `DiagnosticSafetyError: no completed, human-run diagnostic... exists yet` on — structurally inert, not actually usable. Running each once for real, and then deciding which (if any) belong in the autonomous catalog, is deliberately left as a separate, later, explicit Founder decision — exactly matching recommendation #3 from the stress-test packet ("decide, deliberately, whether the autonomous Director should stay conversation/scheduler-scoped or be extended").

## 8. Remaining Director blind spots

- **Reflections and interest-evolution are still uninstrumented** at the Director level — `AgentReflection`/`AgentInterest` weren't in the Founder's 11-item list and have no new diagnostic.
- **The negation fix is syntactic, not semantic.** It correctly handles direct prohibitions in the reviewer's own words; a sufficiently convoluted sentence (a negation and a risky clause fused into one clause with no punctuation at all between two unrelated ideas) could still confuse it in either direction. It is still explicitly documented as defense-in-depth only, never the primary control.
- **`conversation_decision_trace`'s LLM-telemetry match is approximate** (agent + time window, since `llm_runs` has no correlation id) — a second, independent instrumentation gap this diagnostic surfaces rather than papers over.
- **None of the 12 new diagnostics has real-evidence provenance yet** — they are built and proven correct against synthetic data, not yet exercised against the actual Village history. Autonomous eligibility (§7) requires that step first.

## 9. Migration/checkpoint readiness

**Clean.** Every change this pass is additive: 12 new registered diagnostics, one bug fix to a defense-in-depth detector (narrowing false positives without narrowing true-positive coverage), and new fixture tests — no schema migration, no catalog widening, no capability-surface expansion (`ALLOWED_SERVICE_FUNCTIONS` untouched), no kill-switch change, no live-DB or simulation-state change. All 246+ regression checks pass. This is a safe point to checkpoint or migrate from.

---

**Control returned to Founder.** Verification complete; nothing further was investigated or run.
