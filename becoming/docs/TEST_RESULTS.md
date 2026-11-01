# Test Results

## 2026-10-31 — Foundation (Phases 1–2)
Command: `cd becoming/backend && .venv/bin/python -m pytest -q` → **33 passed** (Python 3.13).

| Suite | Tests | What it proves |
|---|---|---|
| test_canon.py | 16 | Exactly the nine residents; Paisley and legacy-roster IDs rejected; canon cannot claim verified sources or carry memories, development, or relationship histories; identity separated from revisable beliefs; residents are non-interchangeable; inspirations disclaimed; curriculum has 10 multi-thread questions; style paragraph pinned |
| test_world_layout.py | 10 | Canonical layout valid; 9 homes, one per resident; buildings and water block, doors walkable; negative cases detected (removed path, walled-off house, off-wall door, overlapping buildings, tree on path); square has open room |
| test_sim_calendar.py | 7 | 96 ticks × 450 sim-min = one 30-day month; season and month rollover; 12-month completion; time advances only by ticks (no wall-clock catch-up) |

`python -m becoming.world_layout --check` → `layout OK`.

Old project regression (untouched): `pytest tests` at repo root → 27 passed.

## 2026-10-31 — Cost model + Pepper sources
`pytest -q` → **36 passed** (adds `test_cost_model.py`: arithmetic, caching reduces cost, invalid cache shares rejected). Pepper canon with 13 sources validates.

## 2026-10-31 — Canon reconciliation with the Founder profiles
`pytest -q` → **42 passed**. New checks: registry unique and unable to claim verification; every citation resolves and is assigned to its resident; unknown code rejected; foundations cite only listed codes; editorial sources stay labeled; Pepper's anchors are lyric texts only; ensemble scenes load.

## 2026-11-01 — First playable village (Phase 3)
- `backend pytest -q` → **42 passed**; `python -m becoming.world_layout --check` → `layout OK` (layout aligned to the official map v2).
- `frontend npm run build` → TypeScript check and production build succeed.
- `frontend npm run test:e2e` (Playwright, Chromium, against `vite preview`) → **12/12 buildings OK**: from the town square the avatar pathfinds to every door, enters, sees the interior, and leaves; no page errors.
- Manual check by screenshot: map renders, avatar spawns at the fountain, clicking a resident shows the canon profile with portrait (docs/world/play_*.png).
