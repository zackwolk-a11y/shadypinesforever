# Founder Packet — Autonomous Director Stress Test
**Run date:** 2026-09-04 00:13–00:20 UTC · **Wall-clock used:** ~7 minutes of a 60-minute ceiling
**Authorization:** single-run, `AUTONOMOUS_EXECUTION_ENABLED` monkeypatched `True` in one background process only — the shipped value in `scripts/director_autonomous_loop.py` never changed (confirmed `False` on disk, pre- and post-run).

---

## 1. Overall Village readiness assessment

The Village is **not dysfunctional, but its formal conversation mechanism has a real, evidence-converged structural constraint**, and the underlying cause is still genuinely unresolved after four independent review rounds (two historical, two produced tonight). Passive-action rate (94.6%) and zero-turn morning gatherings are real and repeatable, but three independent CRITIQUE passes (tonight's two plus the historical one) have each pushed back hard on reading that as "agents don't want to talk" — the accumulated evidence increasingly points at **opportunity/closure mechanics**, not agent motivation, as the more likely bottleneck. No production change is justified yet. The Village is safe to leave paused indefinitely; it is **not yet ready for a longer unattended live run** without first closing the specific instrumentation gap identified below (§12).

## 2. Systems confirmed working

- **Live-DB fail-closed resolution** (`app.core.db_safety`) — read-only health checks passed every time; nothing this run ever wrote to `internal_village.db`/`-wal`/`-shm` (byte-identical MD5 before and after, see §15).
- **ConversationMessage persistence** — confirmed correct for real SPEAK/START_CONVERSATION actions (prior diagnostic `diag_9ceb05dd4760426f`, re-cited and unchallenged tonight).
- **Level 2A diagnostic state machine** — `CANDIDATE_FOR_DIAGNOSTIC → APPROVED → DIAGNOSTIC_COMPLETE`, autonomous-approved (`approved_by="autonomous_director_loop"`), ran twice tonight against the real (paused) live DB, both `SUCCESS`.
- **Level 2B experiment state machine** — ran genuinely end-to-end through the real (non-fixture) autonomous path for the first time tonight (previously only fixture-tested): `speaker_selection_fair_opportunity_ab` → `exp_029ddb1758e04edf`, `EXPERIMENT_COMPLETE`/`SUCCESS`, `approved_by="autonomous_director_loop"`.
- **Deterministic reconciliation + SYNTHESIS chain** — 3 fresh PRIMARY→CRITIQUE→SYNTHESIS rounds completed, all schema-valid, all correctly capped at `recommendation_status=CANDIDATE_FOR_TESTING` (never `APPROVED_TO_TEST` — that value is structurally unreachable from an automated reviewer).
- **Model-call budget guard, concurrency lock, stopping rules** — all fired correctly (see §8, §14).
- **Peer engagement outside the formal conversation entity** (SEND_MESSAGE, ASK_QUESTION) is real, reciprocal, and content-bearing — not fabricated, not manufactured by this test.

## 3. Ranked confirmed defects/problems

1. **(Highest confidence, 0.62–0.72 across 3 independent chains) Conversation opportunity/closure mechanism constraint.** In every scripted scenario, closure fires (after `SILENCES_TO_WIND_DOWN` consecutive silences) before most participants — including an explicitly "willing" one — are ever offered the floor. Raising the threshold from 2→3 alone does not change who gets offered. This is confirmed mechanical behavior, not inference.
2. **Malformed agent-initiated conversation actions (3 of 141, 2.1%).** `START_CONVERSATION` missing `target_agent_id`/`content`, `JOIN_CONVERSATION` with no open conversation. Tonight's fresh review correctly reframes these as *evidence of attempted engagement hitting a schema/context mismatch*, not evidence of disengagement — a reframing that survived all three chains' scrutiny.
3. **Formal-conversation vs. peer-messaging channel conflation risk.** The Founder Report / passive-rate metric currently has no way to distinguish "agent chose true passivity" from "agent engaged via SEND_MESSAGE instead of formal conversation" — a measurement gap, not necessarily a behavior problem.
4. **(Lower confidence, ~0.42–0.58, unresolved) Prompt/decision calibration toward excessive restraint.** Plausible but not isolated from the opportunity constraint above; no prompt-variant comparison has been run.

## 4. Unresolved hypotheses and uncertainties

- Whether the true root cause is the closure/opportunity mechanism, a prompt/schema calibration issue, or **legitimate agent autonomy given only 3 simulated days with no baseline** — explicitly preserved as `unresolved` by SYNTHESIS in all 3 fresh rounds, not resolved by this test.
- Whether the model-facing action contract (SPEAK vs. `public_dialogue` vs. SEND_MESSAGE) is rendered ambiguously to the agent at decision time — no direct prompt/schema trace has been done; this is the single most-recommended next step across all 3 fresh rounds (see §9, action #1).
- Whether the 3 `INVALID_AGENT_DECISION` events reflect stale context, a genuine schema gap, or isolated errors — unresolved, only 3 data points.

## 5. Important hypotheses falsified

- **"A fairer speaker-selection rule (Candidate B) would fix zero-turn gatherings."** Falsified twice now — the original Founder-reviewed A/B experiment (round_73da274827304dbe) and tonight's fresh autonomous re-run of the identical experiment both show Candidate B is mechanically **inert** once real closure semantics are respected: closure fires before the fairness rule can ever diverge from production behavior. **Do not revisit this without genuinely new evidence** (per your explicit instruction — and none emerged tonight).
- **"Conversation initiation itself is broadly broken."** Falsified — all 3 scheduled MORNING_GATHERINGs started successfully; the failure is downstream of initiation.
- **"94.6% passive rate = unambiguous total disengagement."** Falsified as an unambiguous reading — 10 SEND_MESSAGE actions, 1 ASK_QUESTION, and reciprocal peer dialogue coexist with it.

## 6. Diagnostics and experiments performed tonight

| # | Action | ID | Result |
|---|---|---|---|
| 1 | `RUN_DIAGNOSTIC:conversation_lifecycle_trace` | `diag_3e056705021f4750` | SUCCESS → round `round_2fe37c5527ff4d50` |
| 2 | `RUN_DIAGNOSTIC:conversation_message_persistence_and_threshold_probe` | `diag_bb63185a5776461e` | SUCCESS → round `round_35b91c92f46a4f8e` |
| 3 | `RUN_LEVEL2B_EXPERIMENT:speaker_selection_fair_opportunity_ab` (Issue 2, self-test) | `exp_029ddb1758e04edf` | SUCCESS → round `round_7f9dffb521b94b16` |

Each was reviewed by the real chain: **director-primary (Gemini 2.5 Flash, PRIMARY) → hermes (CRITIQUE) → deterministic reconciliation → openai-synthesis (GPT-5.6 Sol, SYNTHESIS)**. 9 real paid model calls total across both issues (6 + 3), well under both issues' budgets (18 and 5) and the hard ceiling (30/issue).

## 7. Evidence and provenance

All three fresh rounds are persisted at `.director/packets/{round_id}_final.json` with embedded deterministic reconciliation packets, full reviewer identities/models/confidences, and (for the diagnostics) `.director/diagnostics/{diagnostic_id}/evidence.json`; for the experiment, `.director/experiments/exp_029ddb1758e04edf/evidence.json`. Issue-level bookkeeping: `.director/autonomous/issue_04111b54f0a148b8/state.json` (Issue 1) and `.director/autonomous/issue_be9c4d39c0e14b39/state.json` (Issue 2). All originate from `round_b433606f27d04e8a` (the Founder-accepted broad conversation-health round from earlier today) — deliberately *not* re-scanning the live DB, since it is unchanged (max event id still 315) and "accumulated history" was explicitly sanctioned as sufficient evidence.

## 8. Gemini / Hermes / GPT agreement and disagreement

**Agree (all 3 fresh rounds + historical):** the zero-turn pattern is real; Candidate B is inert; `INVALID_AGENT_DECISION` events are real; no production change is justified yet; `CANDIDATE_FOR_TESTING` is the correct ceiling.

**Disagree, consistently:** Gemini (PRIMARY) leans toward an agent-motivation/prompt-calibration framing at confidence 0.9 every time; Hermes (CRITIQUE) consistently pushes back that this confidence is too high for a 3-day, no-baseline sample, and consistently redirects toward the mechanism/opportunity explanation. GPT-5.6 Sol (SYNTHESIS) sided with Hermes in **every one of the ~14 tracked disagreements tonight** — a one-sided pattern worth the Founder's attention: either Gemini's PRIMARY framing is systematically too aggressive, or SYNTHESIS has a structural bias toward the more conservative CRITIQUE position. Not distinguishable from this run alone.

## 9. Recommended production changes, ranked

1. **(Highest leverage, lowest risk, medium confidence) Read-only prompt/schema/validation trace.** Reconstruct the exact rendered decision context and action schema for the traced conversation turns and the 3 invalid decisions; compare against validators. **No code or prompt change** — pure instrumentation/audit. This is the single next step every one of tonight's 3 chains converged on independently.
   - *Test:* none needed — it's read-only.
   - *Rollback:* N/A, nothing is changed.
2. **(Medium leverage, low risk, low confidence) Distinguish "formal conversation passivity" from "peer-channel engagement" in the passive-action metric / Founder Report**, so SEND_MESSAGE/ASK_QUESTION activity isn't invisible to the headline passive-rate number.
   - *Test:* unit test asserting the metric correctly buckets a synthetic day with high SEND_MESSAGE + zero formal-conversation turns as "channel-shifted engagement," not "94% passive."
   - *Rollback:* metric-only change, trivially revertible.
3. **(Low leverage on its own, do only after #1) Targeted, disposable A/B on the specific ambiguity #1 surfaces**, if any is found — e.g., clarifying SPEAK vs. `public_dialogue` vs. SEND_MESSAGE in the rendered prompt. Requires separate Founder authorization; do not pre-approve.

## 10. Changes specifically NOT recommended

- Do **not** implement Candidate B (fair-opportunity speaker selection) — falsified twice.
- Do **not** raise `SILENCES_TO_WIND_DOWN` — already tested at 2 vs. 3, no change in who gets offered the floor.
- Do **not** add prompt encouragement/examples pushing agents to speak more, reweight passive vs. active actions, or otherwise optimize raw turn count — every chain tonight explicitly warned this risks manufacturing activity rather than fixing a mechanism, which would violate the Village's autonomy principles.
- Do **not** treat the 3 invalid-decision events as justification for loosening validation — they're too few to generalize from, and validation appears to be working as designed.

## 11. Director self-assessment and limitations discovered

- **Structural catalog narrowness.** `AUTONOMOUS_DIAGNOSTIC_CATALOG` (5 entries) is *entirely* conversation/scheduler-mechanics-focused, and `AUTONOMOUS_LEVEL2B_CATALOG` has exactly 1 entry (also conversation-related). Regardless of which round seeds an issue, the autonomous Director **cannot currently investigate** memory formation, belief revision, research quality/propagation, Research Wall/Rabbit Hole continuity, curiosity/`AgentQuestion` dynamics, or observability — because it is structurally forbidden from inventing new diagnostic/experiment types (correctly, per your hard boundary). Tonight's "broad Village assessment" is broad only in the sense that the underlying snapshot data covers those areas (§2–5 draw on it); the *autonomous mechanical follow-up capability* does not yet exist for them. **This is the single biggest gap between the mission's ambition and the current build.**
- **Max-cycles vs. catalog-size collision.** `AUTONOMOUS_DIAGNOSTIC_CATALOG` has exactly 5 entries and `max_cycles` is hardcoded to a ceiling of 5 — meaning Level 2B is **structurally unreachable within a single issue** unless an early stop (CODE_CHANGE/NO_ACTION/no-new-evidence, or — as happened tonight — a safety escalation) frees a cycle before all 5 diagnostics are tried. Issue 1 only reached 2 of 5 diagnostics before escalating; Level 2B was only exercised because I (under this authorization) deliberately configured a second, narrower issue (`diagnostic_catalog=frozenset()`) as a self-test. **Recommend:** either raise the diagnostic catalog's effective reach per issue, or explicitly document that Level 2B requires a dedicated issue in practice.
- **Permission-expansion false positive — the most important finding of this test.** Cycle 2 of Issue 1 escalated because the regex `\brun the village\b` matched inside the SYNTHESIS reviewer's own explicit *prohibition*: *"Stop at diagnosis—do not alter prompts or code and **do not run the Village**."* The detector has no negation awareness and fires identically on a reviewer forbidding an action as on one recommending it. This is safe (fails closed, correctly not the primary control) but wastes cycles and forces a manual Founder read to distinguish real risk from a well-behaved reviewer being appropriately cautious. **This is exactly the kind of thing that should eventually be automatable safely** — e.g., requiring the matched phrase not be preceded within ~4 words by `not|don't|do not|never|avoid|without`.
- **No wasted/redundant cycles otherwise.** Both diagnostic cycles and the experiment cycle each produced materially new, non-duplicate evidence (fingerprints all distinct); no retry loops, no provider failures, no budget pressure (9/23 combined calls used).
- **Context/token problems:** none observed. **Provider failures/retries:** zero — Hermes (bounded to 90s this run, down from its 240s default, specifically to protect the 60-minute ceiling) never hit its timeout.
- **One-sided SYNTHESIS behavior** (§8) is itself a Director-quality question worth tracking across future rounds, not just a Village question.

## 12. Remaining blockers to long-duration autonomous operation

1. The catalog-narrowness gap above (§11) — before a long unattended run, either accept that autonomous investigation stays conversation/scheduler-scoped, or deliberately author (with Founder review, per your "no new diagnostic/experiment types" boundary — meaning this is *out of scope* for an autonomous run to do itself) new Level 2A/2B types for the other 9 mission areas.
2. The permission-expansion negation blind spot (§11) will keep causing premature escalations on well-behaved, appropriately cautious reviewer output — worth fixing before relying on long unattended stretches, since each false escalation currently requires manual Founder review to clear.
3. The still-unresolved root cause of the conversation-closure pattern (§4) — a longer run would just keep reproducing the same signature without new information until the read-only trace in §9-1 is done.

## 13. Ready for a longer unattended live run?

**Not yet.** The mechanics that exist are safe (verified: zero live-DB writes, zero simulation advancement, budget/lock/stopping rules all functioned). But autonomously iterating longer right now would mostly re-derive tonight's same conclusion under the same false-positive escalation risk, on a Village that hasn't been given the one targeted instrumentation pass (§9-1) that all three independent reviewer chains agree is the actual next piece of information needed.

## 14. Director self-test summary

- Where it worked: catalog-driven diagnostic selection, review-chain execution, deterministic reconciliation, budget/lock/stopping-rule enforcement, Level 2B genuinely exercised for the first time via the real (non-fixture) path.
- Where the catalog prevented useful investigation: entirely, for 9 of the 11 mission topic areas (§11).
- Premature escalation: 1 (§11, negation blind spot).
- Wasted/redundant cycles: 0.
- Provider failures/retries: 0.
- Context/token problems: 0.
- Model-call budget usage: 9 of 23 combined available (39%).
- Disagreements between reviewers: ~14 tracked, SYNTHESIS sided with CRITIQUE in all of them.
- Safety gates triggered: 1 (permission-expansion tripwire, false positive).
- Requiring manual Founder intervention that should eventually be automatable: the negation-aware permission-expansion fix (§11).

## 15. Migration/checkpoint readiness

No migration, restore, or seed operation was touched or needed. Live DB fingerprint identical before/after this run:
`internal_village.db = 15c10dc51...`, `-wal = 30bfc090...`, `-shm = e91c7b0c...` (unchanged). `AUTONOMOUS_EXECUTION_ENABLED` confirmed `False` on disk both before and after. No checkpoint action is pending from this run.

---

## IF THE FOUNDER APPROVES ONLY THREE THINGS NEXT, THEY SHOULD BE:

1. **Authorize the read-only prompt/schema/validation trace** (§9-1) — the one next step all three independent reviewer chains converged on tonight, zero risk, directly targets the still-unresolved root cause.
2. **Authorize a narrow negation-aware fix to the permission-expansion detector** (§11) — a defense-in-depth tripwire currently can't tell a reviewer's prohibition from a request, and will keep causing false escalations that waste Founder attention.
3. **Decide, deliberately, whether the autonomous Director should stay conversation/scheduler-scoped or be extended** — via new, separately Founder-reviewed Level 2A/2B catalog entries — to the other 9 mission areas (memory, beliefs, research, wall/rabbit holes, curiosity, observability) it currently cannot touch at all.

---

**Control returned to Founder.** No production recommendation implemented. Village not resumed or advanced. No further autonomous investigation begun. `AUTONOMOUS_EXECUTION_ENABLED` is `False` on disk.
