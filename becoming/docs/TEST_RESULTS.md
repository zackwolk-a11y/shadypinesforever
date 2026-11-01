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

## 2026-11-01 — Standalone single-file build
`tools/build_standalone.py` → `standalone/healthy_village.html` (4.7 MB, 162 embedded images). Opened from disk in Chromium with **all network requests blocked**: 12/12 buildings entered and left, 0 network requests attempted, 0 page errors. Published as a private claude.ai artifact.

## 2026-11-01 — Talk demo and mobile controls
- `npm run test:e2e` → 12/12 buildings OK.
- `node tests/talk_and_mobile.mjs` → **13/13 checks pass**: pad visible and moves the avatar on an emulated iPhone 13; Talk button appears near a resident and names them; without Claude, Talk states it is unavailable and disables input; with a test-only stand-in for `sample`, the first message carries the character prompt and Zachary's words, honesty rules are included, follow-ups send the conversation so far, the hidden prompt never appears in the transcript, and typing W/A/S/D/E/T goes into the chat without moving the avatar.
- Standalone rebuilt (5.0 MB); offline test 12/12, no errors. Artifact republished with the `sample` capability declared. **Live replies from Claude have not been exercised by an automated test** (they require the artifact viewer and the Founder's consent).

## 2026-11-01 — Conversation patterns and Overhear demo
- `backend pytest -q` → **43 passed** (adds the conversation-patterns check: labelled fiction, 12 types, 75 topics, voices are real residents).
- Browser: buildings 12/12; talk/mobile/overhear **21/21 checks pass**: prompt carries the chosen type, a Days theme and the craft rules, and forbids invented memories; the cast comes from the type's voices; lines stream into the transcript and raise map bubbles; non-cast lines are ignored; it is labelled a demo; without Claude it says so.
- Live generation by Claude in the artifact is not covered by an automated test.

## 2026-11-01 — Research library
- `tools/fetch_sources.py`: 0 fetched, 127 blocked (network policy, HTTP 403 at the gateway), 15 skipped (lyrics, no public URL, design docs); every attempt recorded in research/retrievals.json.
- `tools/build_research_library.py`: 169 founder_note passages (all nine residents; 102 cite registry codes).
- Browser: research checks pass. Bernie's search for the McCain veterans agreement returns passages citing [B8]; Ralph's search stays within his reading; Talk offers search_library, results are labelled Founder research notes, cited sources are shown first with links (govinfo.gov), the rest folded; Overhear prompts carry each resident's reading with codes. Buildings 12/12.
