# Test Report — Vertical Slice v0.1

**Result: 40/40 automated checks pass, 0 page errors** (headless Chromium, Playwright).
Run against the dev server and again against the production build (`vite preview`), with the same results.

## Method
- `tests/e2e.mjs` drives the real game in Chromium. **All gameplay actions use real keyboard or touch input** (key down/up, CDP multi-touch).
  A `teleport` test hook moves the goose between sections so each feature is tested independently.
  The hooks are listed in the log and are not reachable by players.
- `tests/perf.mjs` measures frame rate during Bubble Trouble (the heaviest moment).
- `tests/export-assets.mjs` renders every sound through an OfflineAudioContext. Every file has non-zero signal (RMS and peak checked).

## Automated checks
| Check | Result | Detail |
|---|---|---|
| title screen loads | PASS |  |
| START DEMO → intro cinematic | PASS |  |
| cinematic plays through to the store | PASS |  |
| no missing textures (title/intro/store) | PASS |  |
| cinematic is skippable | PASS |  |
| goose walks right | PASS | 79 → 157 |
| goose turns and walks left | PASS | 157 → 147 |
| jump leaves ground and lands | PASS | apex-ish y=285, landed y=330 |
| jump onto display crate | PASS | y=304 on crate1 |
| honk makes customers react | PASS | 1 reacting (was browse,browse,browse,browse,idle,browse,idle,browse) |
| honk jiggles bottles on shelves | PASS | 28 wobbling |
| trident stand: pedestal | PASS | "tridentPedestal" |
| trident stand: crossbar ledge | PASS | "trident0" |
| sampling station opens picker | PASS |  |
| sip COLA → Fizzy Dash | PASS | cola |
| Fizzy Dash smashes the delivery box wall | PASS |  |
| sip CREAM SODA → Foam Float | PASS | cream |
| Foam Float lifts the goose on a foam cloud | PASS | y=283 on foam |
| foam cloud lets goose clear the box wall | PASS | x=1663 |
| sip BLACK CHERRY → Cherry Blast | PASS | cherry |
| Cherry Blast topples the box wall | PASS |  |
| only one power active at a time (HUD shows cherry) | PASS |  |
| power expires (burp) after its timer | PASS |  |
| first honk wakes the fountain (stage 1) | PASS |  |
| second honk → eruption (stage 2) | PASS |  |
| bubbles spawn continuously | PASS | 8 active |
| floating bubble supports the goose | PASS | {"x":2085,"y":219,"ground":true,"gtag":"bubble","mode":"play","phase":"play","power":null,"drops":1,"fountain":2,"wall":true,"bubbles":8,"anim":"g_land"} |
| goose rides the bubble (still on it after 0.5s) | PASS |  |
| bubble pops after repeated landings | PASS |  |
| trident lift is moving | PASS | 317.6 → 322.5 |
| bubble → elevated mezzanine (real jump) | PASS | {"x":2188,"y":168,"ground":true,"gtag":"mezz","mode":"play","phase":"play","power":null,"drops":1,"fountain":2,"wall":true,"bubbles":15,"anim":"g_idle"} |
| pause and resume | PASS |  |
| valve triggers finale | PASS |  |
| goose rides the giant bubble upward | PASS | {"x":2326,"y":140,"ground":true,"gtag":"mezz","mode":"ride","phase":"cutscene","power":null,"drops":1,"fountain":2,"wall":true,"bubbles":16,"anim":"g_ride"} |
| freeze frame + demo end | PASS |  |
| no missing textures (gameplay) | PASS |  |
| REPLAY DEMO restarts at the cinematic | PASS |  |
| mobile: touch RIGHT moves goose | PASS | 79 → 152 |
| mobile: multi-touch RIGHT+JUMP jumps | PASS | {"x":180,"y":301,"ground":false,"gtag":null,"mode":"play","phase":"play","power":null,"drops":2,"fountain":0,"wall":false,"bubbles":0,"anim":"g_jump"} |
| mobile: HONK button honks | PASS |  |

## Requirement coverage (assignment §11)
| # | Requirement | Covered by |
|---|---|---|
| 1 | Cinematic plays and can be skipped | "START DEMO → intro", "cinematic plays through", "cinematic is skippable" |
| 2 | Goose moves and jumps correctly | walk left/right, jump + land, crate, trident-stand ledges, bubble → mezzanine |
| 3 | Honking triggers reactions | customers react, bottles jiggle, fountain stages, mobile HONK |
| 4 | Flavour samples are interactive | picker opens, keyboard selection of each flavour; touch selection supported (tap card) |
| 5 | All three powers function | dash smashes wall, foam lifts and clears wall, cherry topples wall; expiry burp |
| 6 | Bubble platforms support the goose | stands and rides on a hover bubble; pops after repeated landings |
| 7 | Soda fountain animation triggers | stage 1 rumble, stage 2 eruption, continuous bubbles, lift moving |
| 8 | Concluding bubble ride works | valve → ride upward → freeze frame |
| 9 | Demo ends correctly | "freeze frame + demo end", TO BE CONTINUED screenshot |
| 10 | Replay restarts | "REPLAY DEMO restarts at the cinematic" |
| 11 | Desktop and mobile controls | keyboard throughout; touch RIGHT, RIGHT+JUMP multi-touch, HONK at 844×390 |
| 12 | Pause and resume | "pause and resume" (Esc / Esc) |
| 13 | No missing assets | "no missing textures" ×2 (all scenes) |
| 14 | No serious collision or physics bugs | fixed-step physics; all platform checks pass; no tunnelling seen at 120 Hz |

## Performance
- Bubble Trouble: **58–60 fps** (WebGL, headless Chromium with software GL; 13–14 live bubbles, about 330 display objects).
- Texture generation at boot: about 0.38 s on desktop. Bundle: 1.63 MB JS (392 KB gzipped). Phaser is the bulk of it.

## Screenshots (`screenshots/`)
01 title · 02 title menu · 03 intro spots the bottle · 04 ENORMOUS HONK · 05 door opens · 06 honk reaction ·
07 trident stand · 08 flavour picker · 09 drinking · 10 flavour reaction · 11 cola dash · 12 cream foam ·
13 cherry blast · 14 fountain rumble · 15 Bubble Trouble · 16 standing on a bubble · 17 pause menu ·
18 giant bubble ride · 19 TO BE CONTINUED · 20 mobile touch (844×390) · 21–22 small phone (667×375)

## Bugs found and fixed during testing
- Quick key taps (down and up inside one frame) could be lost → taps are now latched between polls.
- The E press that opened the sampling picker also confirmed it in the same frame → that press is now consumed.
- Pause → Esc didn't resume (the menu kind was reset while the menu was built) → fixed.
- Cherry shots bounced off the box wall before registering a hit → fixed.
- Camera pan and zoom used tween-style ease names that Phaser's camera rejects → fixed.
- Bitmap fonts rendered at a non-integer scale (1.5× / 1.375×), causing clipped glyphs and overflowing balloons → fixed to exact 1:1.
- A bottle knocked by walking could hurt the goose in the first seconds → only the honk-loosened ledge bottle can bonk now.
- Mezzanine route was too strict → retuned: lift → two hover bubbles in a staircase → mezzanine, plus a vent bubble beside the mezzanine.
- Effects were 10–20× quieter than the music → effects bus rebalanced.

## Not verified / known limitations
- **No real mobile hardware**: touch was tested with emulated multi-touch in Chromium at 844×390 and 667×375. iOS Safari audio unlock and safe-area insets need a device check.
- **Firefox and Safari not tested**, only Chromium.
- **Gamepad** mapping is implemented but untested (no controller available).
- **Audio was verified by signal measurement, not by listening.** The mix balance is a best estimate.
- Frame rate was measured in headless Chromium, not on low-end phones.
- simpsmb.com was unreachable from the build environment, so brand details beyond the client-supplied trident badge come from search results.
