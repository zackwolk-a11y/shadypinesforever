# Candidate behavior intervention: ACTION_DESCRIPTIONS / `_action_notes` — NOT active in production

**Status: withdrawn from the production checkpoint, preserved here as a candidate only. Not to be reintroduced without explicit Founder approval and regression/A-B testing.**

## What this is

`action_descriptions_candidate.patch` is the exact diff (`git diff 1c7cdd7~1 1c7cdd7 -- app/schemas/actions.py app/services/context_builder.py`) that added:

- `ACTION_DESCRIPTIONS` (`app/schemas/actions.py`): a short plain-language gloss for each of the 23 `ActionType` values.
- `_action_notes()` (`app/services/context_builder.py`): renders those glosses as a new `ACTION NOTES:` block, appended immediately after the existing `AVAILABLE ACTIONS:` line in every rendered agent-decision prompt.

## Why it was withdrawn

It was found, during migration-checkpoint inspection on 2026-09-04, already present — uncommitted — in the working tree from an earlier, undocumented session, then accidentally swept into commit `1c7cdd7` ("Add the Director system...") through a staging-index mistake unrelated to its own merits. That commit's message never mentions it. A follow-up commit removes it from the tracked production path; this file and the accompanying patch are its preserved record.

## Why it should not be reintroduced without review

1. **It changes information shown to every agent decision.** Every rendered `AVAILABLE ACTIONS` prompt would gain a new explanatory line per action — new information reaching the model on every single activation, not a cosmetic change.
2. **It has not been behaviorally tested.** A repo-wide search found zero tests (fixture, smoke, or otherwise) that reference `ACTION_DESCRIPTIONS`, `_action_notes`, or `"ACTION NOTES:"`. Whether adding per-action explanations shifts decision distributions (more/less research, more/less challenging, more/less passivity) is an open empirical question this patch never answered, even though its own wording is neutral by design.
3. **It should not be reintroduced without explicit Founder approval and regression/A-B testing** — e.g., a disposable, isolated comparison (in the shape of the existing Level 2B speaker-selection experiment) measuring actual decision-distribution effects before any production adoption, plus a dedicated regression test asserting its exact rendered output, the way every other prompt change in this codebase is covered.

## To reintroduce later

Apply `action_descriptions_candidate.patch` against the commit it was extracted from (`git apply` from repo root, or `git am` if turned into a mailbox-format patch) as a starting point — it applies cleanly as of `1c7cdd7~1`. Do not apply directly to a later commit without checking for conflicts first.
