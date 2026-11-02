# SIMPS: GOOSE ON THE LOOSE! — Complete Game (v1.0)

*HONK. SIP. BURP. REPEAT.*

A complete three-level comedic 2D platformer for desktop and mobile browsers, set in Kelowna, B.C.
TypeScript + Phaser 3.90 + Vite. All art (pixel art authored in code) and all audio (Web Audio synthesis) are original.

> Unofficial concept game. Simps flavour names, the red trident and the brand colours are used to pitch the concept;
> get brand approval before public release. Flavour powers, recipes and burp abilities are fictional.
> Ogopogo here is an original cartoon creature inspired by the popular lake-monster legend. It does not depict the
> syilx/Okanagan being nx̌aʔx̌ʔitkʷ.

## Run it
```bash
npm install
npm run dev          # http://localhost:5173   (?touch=1 forces touch controls)
npm run build        # production build → dist/
npm run preview      # serve dist/ at http://localhost:4173
```
Debug/jump URLs: `?scene=store|intro|lab|dimension|carb|fake|cafe|waterfront|ogopogo|trueend|journal`,
plus `&mode=demo` (original vertical slice), `&skipintro=1` (lab), `&burp=vanilla|saltedcaramel|hazelnut|peppermint|lavender|marshmallow`.

## Host it
`dist/` is a static site with relative paths and no external services. Upload its contents to any static host
(Netlify drop, GitHub Pages, S3/CloudFront, itch.io HTML5: zip the *contents* of `dist/`). It works from a sub-folder.

## The game (25–35 min first playthrough)
| Level | Stage | What happens |
|---|---|---|
| 1 Bubble Trouble | Simps store | Street cinematic; store aisles, Trident Display Stand, storage-shelf route above the coolers. Fridge doors and taste test: **Cola: Fizzy Dash**, **Cream Soda: Foam Float**, **Black Cherry: Cherry Blast**. **Dave & Gerry welcome the goose** at the door (skippable dialogue, flavour cards, how concentrate becomes soda). Two honks erupt the FIZZ-O-MATIC. **Dave's Bubble Workshop** under the mezzanine: ride 3 moving bubbles, honk the syrup valves in colour order, dodge overfilled bubbles, honk the pressure switch for **DOUBLE BUBBLE**. Main valve, then the giant bubble rides out through the skylight. |
| 1 Bonus | **The Great Simps Stock-Up!** (stockroom door after the samples; rope blocks Bubble Trouble until done) | **Part 1** conveyor boxes → flavour-tagged shelf slots, push big boxes into floor bays, Gerry's red-trident lift (wrong button gag), falling bottles, STOCK-O-METER. **Part 2** truck: flavour order on the dock + a jammed-conveyor timed honk, push the cart onto the trident, the bottle rush (catch 5), launch the last box; wobbly stack sheds rolling boxes. **Part 3** gift box → **MAPLE LEAF POWER HONK** (hold honk). Replayable from level select. |
| 2 Honkin' Soda Lab | Lab | Landing on the console wakes every machine. **Mix-O-Matic** mini-game: base, primary syrup, optional second, carbonation, then 3 timed pumps for Perfect, Good or Overmixed. 5 recipes + 2 secrets + Mystery Fizz. Puzzles: fragile glass (dash), zap target gate (Electric Fizz homes in), steam corridor (time it or Foam Shield), lever-driven trident lift and carbonation jets, Cloud Nine and Tropical Launch secrets. **Super Soda 9000**, rainbow bubble, portal. **Gerry's Experimental Flavor Lab** (gates the Super Soda): fetch 3 samples, pour each into its matching tank, timed carbonation honk while foam and bottles bounce around, rainbow soda → **SUPER BURP** (forehead gag). |
| 2 | Soda Dimension | Fruit islands, rainbow bridges, citrus wheels, collapsing foam, geysers, syrup-river current, bubble elevator, hidden recipe chamber, flavour taps at 3 checkpoints. Enemies: **Fizz Sprites, Syrup Slugs, Bottle Bots, Foam Monsters, Fruit Flyers**. |
| 2 Boss | Carbonation Catastrophe | Carbonator 3000 with face, gauges, arms and a rotating trident. **P1** honk or stomp its bubbles into the switches. **P2** hit the flavour tap matching its colour. **P3** foam flood: jets and bubbles up to 3 valves. |
| — | **Fake ending** | Store celebration, CONGRATULATIONS, credits… then the goose interrupts, stomach growls, empty cup, HONK, record scratch. |
| 3 One Last Sip | Café | Stool, barista dialogue, **specialty coffee** (base, Simps café syrup, 2nd syrup, milk, intensity; extraction, pumps, pour, stir, latte art), then the first burp and **Bubble Burp** unlocked. |
| 3 | Waterfront | Okanagan Lake park: burp targets, beach ball lift, branch reached by burp bubble platform (E), hedge target, bubble bell, joggers, cyclist, startled gulls. Sit on the dock, the lake ripples. |
| 3 Boss | Ogopogo | Rising intro, "Honk?". **P1** jump waves and burp. **P2** dives and resurfaces high: climb buoys and bubbles. **P3** whirlpool, charge the glowing cup, **Super Burp**. All 6 coffees are viable. Power Honk stuns it and flattens waves; Gerry's Super Burp hits for 3; Double Bubble burps two platforms. Playful defeat: dizzy spin, sheepish, friendly *blub blub*. |
| — | **True ending** | The last sip shared, Ogopogo's enormous burp, bubbles over the lake. **Grand Simps Celebration**: Dave & Gerry arrive at sunset, dialogue, pours and a rainbow soda, goose dance, cheering crowd, flags, sparkling tridents, maple-leaf fireworks, group toast, Ogopogo's giant soda cup. Sunset ride, panorama, **HONK IF YOU LOVE SODA! / THE END**, stats (flavours, secret recipes, maple leaves, trident badges, achievements, score) + replay / level select / achievement journal. |

Coffee burps: **Vanilla** Gentle Giant · **Salted Caramel** Heavy Burp · **Hazelnut** Ricochet · **Peppermint** Rapid Fizz ·
**Lavender** Dream Bubble (pops waves, longer stun) · **Toasted Marshmallow** Warm Foam (shield).

## Controls
| Action | Keyboard | Touch | Gamepad |
|---|---|---|---|
| Move | ← → / A D | ◀ ▶ | D-pad / stick |
| Jump (hold while falling to flutter) | Space / Z | JUMP | A |
| Honk (hold to charge the Power Honk once unlocked) | X | HONK | X |
| Power / burp (hold for Super Burp once unlocked) | C | POWER | B / RB |
| Sip / use / pick up / bubble platform (Double Bubble) | E | SIP | Y |
| Pause (journal, a11y, restart) | Esc / P | II | Start |
| Mute | M | SND | — |
| Fullscreen | F | FS (HUD / title) · ⛶ FULL (phone pad) | — |

## Systems
Hearts (5 maple leaves) and trident checkpoints (resume from checkpoint). Score, time, best score.
Persistent saves (`localStorage`: unlocked stages, completion, scores, flavours, recipes, cards, collectibles, achievements, coffee, checkpoint and run).
Collectibles: syrup drops, golden maple leaves, Simps Certified badges, golden bottles, recipe cards, bubble stars, coffee beans, Golden Goose Token.
19 achievements. Owner abilities (Power Honk, Double Bubble, Super Burp) are permanent and shown as HUD icons; Power Honk cracked walls and Double Bubble stashes hide extras in Levels 2–3. Golden Canadian goose outfit (Title → CUSTOMIZE GOOSE) for a perfect Stock-Up. Flavour and recipe journal. Level select (Level 3 hidden until revealed). Continue.
Accessibility: music/SFX volume, mute, reduce flashing, reduce screen shake, high-contrast enemies, touch toggle.

## Project layout
```
src/levels/LevelScene.ts  shared runtime: fixed 120 Hz physics, goose, powers, burps, hearts, checkpoints, pickups, enemies, switches, hazards
src/scenes/               Boot/Input, Title, Intro, Store, Lab, Mixer, Dimension, BossCarb, FakeEnd, Cafe, Coffee, Waterfront, Ogopogo, TrueEnd, Journal, UI
src/entities/             Goose, Person, Bubbles, Projectile, Enemies, Props, Abilities, Emote
src/data/                 recipes (verified ingredients), coffee (burps), achievements
src/systems/              physics, input, settings, save, gamestate, camfx
src/art/                  palette, Px rasteriser, font, goose, people, props, fx, fx2, motifs, backgrounds, lab, enemies, dimension, boss, cafe, waterfront, registry
src/audio/                engine, sfx (50+ synthesised effects), music (11 original songs, data-driven sequencer)
assets/                   exported PNG sprite sheets + WAV audio (npm run export:assets)
tests/                    e2e.mjs (vertical slice), fullgame.mjs, ogopogo.mjs (all 6 coffees), perf.mjs, export-assets.mjs
```

## Tests
```bash
npm run dev &
npm run test:e2e        # 40 original vertical-slice checks (demo mode)
npm run test:full       # full-game checks across all 3 levels, endings, saves, menus, touch
npm run test:ogopogo    # every coffee burp defeats Ogopogo
```
See `TESTING.md` for recorded results, and `ART_BIBLE.md` for art rules.
