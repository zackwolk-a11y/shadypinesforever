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
