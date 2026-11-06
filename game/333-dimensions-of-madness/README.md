# THE 333 DIMENSIONS OF MADNESS

An original side-scrolling action platformer starring **Moshmouth**, the screaming green monster head.
The whole game is in one self-contained offline file: **`333-dimensions-of-madness.html`**.
To play, open it in any modern browser. It needs no server, makes no network requests and has no dependencies.

## Controls (v2: three buttons)

| Action | Keyboard | Gamepad | Touch |
|---|---|---|---|
| Move | Arrows / WASD | D-pad / stick | left stick |
| Jump | Space, Z, K | A | JUMP |
| Attack | X, J, C, Shift | X / B / Y / RB | ATTACK |
| Pause / skip cutscene | Esc, P | Start | II |

ATTACK picks the right move for the situation:
- a tongue whip next to enemies
- a bone bash at a cracked wall
- a spin in the air (with a bounce if it hits)
- a roll when you're running
- a swing when you're in the air near a hook
- flipping switches, smashing MAX amps and building houses when you're next to them

Transformations are now temporary **power-up bubbles**:
- PIG: charge
- WOLF: howl plus a double jump
- COW: horn charge, or a stomp in the air
- SLIME: triple spit

## What's in the game

- **30 levels in 6 worlds.** Each level has one main gimmick and a set-piece spectacle. Examples: a giant amp falls from the sky, the Gloop crashes through a wall, Razz jumps his motorcycle over you, a milk tsunami, a giant cow stomps past in the background, a ferris wheel rolls away, a garbage monster eats a building, the moon screams.
- **A 90-second wordless tutorial** opens Level 1: move, jump, attack, collect, then an escape sequence, ending with "YOU'RE READY. GO MAKE A MESS!".
- **LEVEL 333** is the third level:
  - You collect straw, sticks and bricks along the road and press ATTACK at the end to build each house.
  - The wolf destroys the straw and stick houses, with a motorcycle chase after each.
  - The brick house survives, then comes the boss fight.
  - Trufflina finishes the wolf off in an action-hero slapstick finale, followed by a two-button concert.
- **All six character groups**, animated from the supplied art and helping automatically:
  - Moshmouth is the hero.
  - The three pigs follow you, honk, throw sticks and punch.
  - Captain Udderly drops COW POWER from the sky.
  - Razz Vroomberg drives the chase sequences.
  - Big Bad Barnaby is the boss in levels 333, 11 and 28.
  - The Golden Gloop splits into smaller Gloopkins, chases you and is the Garbage Heap boss.
- **8 bosses** (Barnaby fought three times), each with at most three big, obvious attack patterns.
- **Saves, checkpoints and extras**: persistent saves, frequent automatic checkpoints, achievements, secret shards, the Monster Encyclopedia, a jukebox and options.
- **Original procedural soundtrack** with melodic lead lines that gets heavier in combat and boss phases.

A backup of the previous version is at `backups/333-dimensions-of-madness-v1.html`.

## Project layout

```
assets/source/          the supplied artwork (definitive reference)
assets/gen/             generated sprite parts + sprites.json (anchors/pivots)
tools/extract_sprites.py  asset pipeline: keys backgrounds, cuts parts (wolf arm, cow cape,
                          bike/rider, pig heads...), downsamples to crisp pixel sprites
tools/build.js          bundles src/*.js + assets into 333-dimensions-of-madness.html
src/                    engine, audio, music, graphics, world, player, entities, bosses,
                        allies, levels, story, game, UI, concert/ending, main loop
tests/                  Playwright test-suite (see below)
```

To rebuild, run `python3 tools/extract_sprites.py` (only needed when the art changes), then `node tools/build.js`.

## Tests

Run `bash tests/run_all.sh`. It needs Node and Playwright with Chromium.

- `reachability.js`: static check that every exit, quest item, boss gate and shard in all 36 level/chapter maps can be reached. It uses the real jump arcs and models springs, hooks, crates, portals and moving platforms.
- `mechanics.js`: 28 checks:
  - the contextual ATTACK and each power-up
  - pig helpers and one-button building
  - the scripted tutorial flow
  - quests, checkpoints and saves
  - measured audio output
- `bosses.js`: every boss can be beaten using only MOVE, JUMP and ATTACK.
- `smoke.js`: loads every level and chapter, simulates input and fails on any runtime error.
- `platform.js`: frame rate at 1080p, no network requests, exactly three touch buttons on a phone (the jump button really jumps), tablet layout.
- `autoplay.js`: a god-mode bot that tries to play each level through. It is diagnostic only; some levels need puzzle solving it cannot do.
- `ui_screens.js`, `rig_preview.js`, `sprite_preview.js`: render screens and sprites to PNG for visual review.

## Known limitations

- Playtime has not been measured with real players.
- Environments, tiles, props, enemies and the bosses that aren't in the supplied art are painted by code and baked into images when a level loads. They are not hand-drawn sprite sheets.
- Enemy encyclopedia portraits are simpler than the cast portraits.
- Level layouts mix hand-placed set pieces with seeded procedural segments. Layouts are the same every run.
- The diagnostic autoplay bot can't finish every level with one button. Completability is covered by `reachability.js`, `mechanics.js` and `bosses.js`, not by the bot.
