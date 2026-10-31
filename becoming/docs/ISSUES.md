# Issue Tracker

| ID | Status | Severity | Title | Detail / next step |
|---|---|---|---|---|
| HV-001 | **Partly resolved** | High | Original Healthy Village project not reachable | The Oct 20 guide PDF was received (summaries, sources, trial status). The raw foundations, the earlier codebase (which the guide says passed 183 tests), and its database are still not reachable. Resident profiles, Great Questions curriculum, research library, and conversation archives were not found in this repo (see `00_AUDIT.md` §2). Provide via upload, by attaching the repo, or by sharing the Mac folder through Remote Control |
| HV-002 | **Open, blocked on Founder** | High | Source materials pending for 6 residents | Tony (Tony Moss / I.AM.LIFE / Bird Tribe, with collaborator credits), Haize (Haize Hawke), Ashley (Ashley Bonn), Mao (Mao Tatanka), Anna (Anna Brown), ~~Pepper (song list)~~ resolved 2026-10-31 from the guide. Until supplied, these residents draw only on the Founder's prompt descriptions |
| HV-003 | Open | Medium | Visual direction not chosen | See `03_WORLD_AND_VISUAL_DIRECTIONS.md` |
| HV-004 | Open | Medium | LLM provider route and budget not chosen | See `COSTS.md`. Includes the question of whether unattended use of a consumer subscription via `claude -p` fits that plan's terms and limits |
| HV-005 | Open | Low | Interiors not yet laid out | Phase 3: one room per building, defined as data like the exterior |
| HV-006 | Fixed | Low | YAML colon parsing turned two of Tony's list items into mappings | Caught by the canon schema test; reworded (2026-10-31) |
| HV-007 | Fixed | Low | SVG blockout broke on an unescaped `&` in "Kitchen & Dining Hall" | Labels are now HTML-escaped (2026-10-31) |
| HV-008 | Open | High | Reconcile canon with the Oct 20 guide | The guide's foundations are richer and differ in emphasis (e.g. Tony on consent and credit; Mark on consultation vs consent vs control; Bernie on Workplace Democracy and the 2014 VA compromise). Produce a per-resident diff for Founder approval before changing canon |
| HV-009 | **Needs Founder decision** | Medium | Resident name: "Haize" or "Hayes"? | The Oct 20 guide names the resident **Hayes** (inspired by Haize Hawke); the Oct 31 master prompt says **Haize**. Canon currently follows the newer prompt |
| HV-010 | **Needs Founder decision** | High | Anna Brown's recorded criticism of substituting AI | The guide's source N8 ("AI No Thank You") records Anna Brown criticizing AI as a substitute for human intuitive and emotional intelligence, and notes there is no evidence she endorses this character. Options: keep Anna with this tension explicit (the guide's approach), rename or decouple her from a named living person, or seek permission |
| HV-011 | Open | Low | Bandcamp blocked by session network policy | `pepperproud.bandcamp.com` and `yaimamusic.bandcamp.com` do not resolve here, so song pages could not be re-read. Song themes come from the guide, not fresh retrieval |
