# SIMPS: GOOSE ON THE LOOSE! — Vertical Slice ("The First 60 Seconds")

*HONK. SIP. BURP. REPEAT.*

A playable browser vertical slice: the Kelowna street cinematic → the Simps store → flavour
sampling (Cola, Cream Soda, Black Cherry) → three flavour powers → **Bubble Trouble** → the giant
bubble ride → **TO BE CONTINUED…**. TypeScript + Phaser 3.90 + Vite. All art and audio are original and generated in code.

> Unofficial concept demo. Simps flavour names, the red trident and the brand colours are used to
> pitch the concept; get brand approval before public release. Flavour powers are fictional.

## Run it
```bash
npm install
npm run dev          # http://localhost:5173  (add ?touch=1 to force touch controls)
npm run build        # production build → dist/
npm run preview      # serve dist/ at http://localhost:4173
```
Debug URLs: `?scene=store` (skip to gameplay), `?scene=intro`, `/debug.html?sheet=goose&scale=4` (sheet viewer).

## Host it
`dist/` is a fully static site with relative paths (`base: './'`) and no external services.
Upload it to any static host (Netlify drop, GitHub Pages, S3 + CloudFront, itch.io as an HTML5
game: zip the *contents* of `dist/`). It works from a sub-folder.

## Controls
| Action | Keyboard | Touch | Gamepad |
|---|---|---|---|
| Move | ← → / A D | ◀ ▶ | D-pad / left stick |
| Jump (hold while falling to flutter) | Space / Z | JUMP | A |
| Honk | X | HONK | X |
| Flavour power | C | POWER | B / RB |
| Sip / use | E | SIP | Y |
| Pause | Esc / P | II button | Start |
| Mute | M | SND button | — |

## What's in the minute
1. **0–10 s, cinematic:** camera reveals the storefront (trident sign, Canadian flag, maple bunting). The goose waddles in, spots a glowing bottle, stretches its neck, tilts its head, eyes go wide → ENORMOUS HONK (birds scatter, pedestrians jump) → the door swings open. Skippable.
2. **10–25 s, store:** run, jump, flutter and honk. Customers react (shock, laugh, flee, "A GOOSE?!"), bottles jiggle and topple, and a honk-loosened bottle can bonk the goose. Climb crates, a gondola and the **Trident Display Stand**. Collect syrup drops, 3 hidden **Golden Maple Leaves** and the **Simps Certified** badge.
3. **25–40 s, sampling:** Sam at the TASTE TEST counter waves you over. Pick a flavour: the goose hops up, sips, swallows (a lump travels down the neck) and reacts. One power at a time, shown in the HUD slot with a 45 s timer (it ends in a BURP).
   - **Cola, Fizzy Dash:** fast fizzy dash that smashes the delivery box wall.
   - **Cream Soda, Foam Float:** a cream foam cloud that lifts you over the wall.
   - **Black Cherry, Cherry Blast:** a bouncing cherry bubble that topples the wall.
4. **40–60 s, Bubble Trouble:** a "PLEASE DO NOT HONK AT THE FOUNTAIN" sign. Honk → the FIZZ-O-MATIC rumbles. Honk again → the gauge goes wild → an enormous bubble erupts. Bubbles drift from the three trident spouts, rise from floor vents and hover as stepping stones; the Trident Lift pumps. Bubbles pop after repeated landings. Ride them up to the mezzanine and pull the trident valve → the goose rides a giant bubble to the skylight → wide shot → sepia freeze-frame → **TO BE CONTINUED…** → Replay Demo / Main Menu.

## Project layout
```
src/
  main.ts                 Phaser config (480×270, pixelArt, FIT scaling)
  scenes/                 Boot (texture generation) + Input (persistent controls), Title, Intro, Store, UI
  entities/               Goose (controller + animation state machine), Person (AI), Bubbles (pooled moving platforms),
                          Props (bottles, box wall), Abilities (foam, cherry shot, trident lift), Emote
  gameplay/               layout.ts (data-driven level), flavors.ts, Sampling.ts, Fountain.ts, FxSystem.ts
  systems/                physics.ts (fixed 120 Hz AABB + one-way + moving platforms), input.ts, settings.ts
  art/                    palette, Px rasteriser, font, goose, people, props, fx, motifs, backgrounds, registry
  audio/                  engine (buses, persisted volumes), sfx (synthesised), music (layered chiptune sequencer)
  debug/                  sprite-sheet viewer + offline audio exporter
assets/                   exported PNG sheets + WAV audio (generated from the code above)
screenshots/              e2e screenshots + results.json
tests/                    e2e.mjs (40 checks), perf.mjs, export-assets.mjs, smoke.mjs, play.mjs
```

## Tests
```bash
npm run dev &                 # or: npm run build && npm run preview &  then BASE=http://localhost:4173
npm run test:e2e              # 40 browser checks, writes screenshots/ and screenshots/results.json
node tests/perf.mjs           # FPS during Bubble Trouble + small-phone screenshots
npm run export:assets         # regenerate assets/ (PNG + WAV)
```
See `TESTING.md` for the report and `ART_BIBLE.md` for the art rules.
