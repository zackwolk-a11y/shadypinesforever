# Development, Testing, Backup, Rollback & Safety Procedures

## 1. Environments

| Env | Database | LLM provider | Purpose |
|---|---|---|---|
| **test** | temp file per test | `fixture` only (deterministic, labeled `scripted`) | CI and local tests; never touches real data |
| **dev** | `becoming/data/dev/village.db` | `fixture` by default | Day-to-day building |
| **staging** | a *copy* of live, made via the backup API | `fixture` or live with a low budget | Rehearsing migrations, long-run trials |
| **live** | `$HV_DATA_ROOT/live/village.db` (recommended outside the repo, e.g. `~/HealthyVillage/data`) | Founder-approved provider | The running experiment |

Live-path resolution is fail-closed, ported from the old project's `db_safety.py`. A missing or near-empty live DB is an error, never silently recreated.

## 2. Development workflow
1. Work on a feature branch (`claude/...`). Never commit directly to `main`.
2. Each phase ends with passing tests, an updated `TEST_RESULTS.md`, and a git tag `hv-phase-N`.
3. Every schema change is an Alembic migration with a tested `downgrade`.
4. Decisions go in `DECISIONS.md`, known problems in `ISSUES.md`, and spend in `COSTS.md`.

## 3. Backups
- **Online backup** via SQLite's `backup()` API (safe while running; WAL-aware). Never copy the raw file of a running DB.
- **When:** before every migration, before every Steward start, nightly at simulated month rollover, and on demand from Founder Controls.
- **Retention:** per category (pre_migration, pre_start, nightly, manual), with the 10 most recent kept in each. Backups are integrity-checked (`PRAGMA integrity_check`) right after they are written.
- **Restore drill** is part of the Phase 6 exit test: restore into staging and verify event count and hash.

## 4. Rollback procedures
| Situation | Procedure |
|---|---|
| Bad code release | `git checkout hv-phase-N` (last good tag); restart |
| Bad migration | Stop the Steward → `alembic downgrade -1` → if data is affected, restore the `pre_migration` backup |
| Corrupted live DB | Stop → move the corrupted file to `quarantine/` (never delete) → restore the latest verified backup → record an `offline_gap` |
| Bad simulation behavior | Pause → clone the world for diagnosis → fix in staging → resume. History is never rewritten; corrective events are appended |

## 5. Single-writer protection
The Steward acquires an exclusive OS file lock (`fcntl.flock`) on `$HV_DATA_ROOT/<world>/steward.lock` and writes a heartbeat row. A second Steward refuses to start. The API process opens the DB for reads and inserts only into `commands`. Ticks run inside `BEGIN IMMEDIATE` transactions, so a crash mid-tick leaves no partial tick.

## 6. Safety boundaries (summary; see spec §9)
- Residents have an allowlist of capabilities, with no shell, no external accounts, and no publishing.
- Provider keys are server-side only (`.env`, git-ignored), never sent to the browser and never logged.
- Daily model-call and token budgets are configurable. When one is hit, the clock enters `rate_limited` or `paused` and the UI says so plainly.
- No automated process may modify production code, permissions, or canon. Those are Founder-authorized changes via git.
- The old Internal Village installation is never written to.

## 7. Running the current foundation
```bash
cd becoming/backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q                       # all tests
.venv/bin/python -m becoming.world_layout --check   # validate world geometry
.venv/bin/python -m becoming.world_layout --ascii   # print the map
```
