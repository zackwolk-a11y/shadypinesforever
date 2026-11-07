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
| Fullscreen | F | - | ⛶ (top right) |

ATTACK picks the right move for the situation:
- a tongue whip next to enemies
- a bone bash at a cracked wall
- a spin in the air (with a bounce if it hits)
- a roll when you're running
- a swing whenever a hook is in reach (any attack, including power-up attacks, in the air or from the ground)
- flipping switches, smashing MAX amps and building houses when you're next to them

Transformations are now temporary **power-up bubbles**:
- PIG: charge
- WOLF: howl plus a double jump
- COW: horn charge, or a stomp in the air
- SLIME: triple spit

## What's in the game

- **30 levels in 6 worlds.** Each level has one main gimmick and a set-piece spectacle. Examples: a giant amp falls from the sky, Shitman crashes through a wall, Electric Harley jumps his motorcycle over you, a milk tsunami, a giant cow stomps past in the background, a ferris wheel rolls away, a garbage monster eats a building, the moon screams.
- **A 90-second wordless tutorial** opens Level 1: move, jump, attack, collect, then an escape sequence, ending with "GO MAKE A MESS!".
- **LEVEL 333** is the third level:
  - You collect straw, sticks and bricks along the road and press ATTACK at the end to build each house.
  - The wolf destroys the straw and stick houses, with a motorcycle chase after each.
  - The brick house survives, then comes the boss fight.
  - Trufflina finishes the wolf off in an action-hero slapstick finale, followed by a two-button concert.
- **All six character groups**, animated from the supplied art and helping automatically:
  - **Moshmouth** is the hero.
  - **The Three Little Pigs** (Hamwise, Porkington, Trufflina) follow you, honk, throw sticks and punch.
  - **Cowgod** drops COW POWER from the sky (and is a hypnotised boss in Level 8).
  - **Electric Harley House (of Love)** ("Electric Harley" on the health bar) is the Level 2 boss and drives the chase sequences.
  - **Big Bad Wolf** is the boss in levels 333, 11 and 28.
  - **Shitman** splits into smaller Shitkins, chases you and is the core of the Garbage Heap boss.
- **8 bosses** (the Big Bad Wolf fought three times), each with at most three big, obvious attack patterns.
- **Saves, checkpoints and extras**: persistent saves, frequent automatic checkpoints, achievements, secret shards, the Monster Encyclopedia, a jukebox and options.
- **Original procedural soundtrack** with melodic lead lines that gets heavier in combat and boss phases.

A backup of the previous version is at `backups/333-dimensions-of-madness-v1.html`.

## Project layout

```
assets/source/          the supplied artwork (definitive reference)
assets/gen/             generated sprite parts + sprites.json (anchors/pivots)
assets/atlas/           the six character collections as atlases: <id>.png + <id>.json
                        (moshmouth, pig_hamwise, pig_porkington, pig_trufflina, harley, wolf,
                        cowgod, shitman): frame rects, fps, loop, pivot, collision + attack boxes
screenshots/            gameplay screenshots of every character (tests/screenshots.js)
tools/extract_sprites.py  asset pipeline: keys backgrounds, cuts parts (wolf arm, cow cape,
                          bike/rider, pig heads...), downsamples to crisp pixel sprites
tools/close_mouth.py    completes Moshmouth's mouth (idle head without the tongue)
tools/extract_tongue_frames.py  the supplied 8-frame tongue attack strip -> sprite sheet
tools/export_atlases.js writes assets/atlas/ from the game's baked animations (--previews adds checkerboards)
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
- `arenas.js`: every combat arena in all 30 levels spawns its enemies on screen and opens once they are beaten.
- `sprites.js`: all six character groups and every required animation (438 frames): none blank, clipped or out of bounds; transparent backgrounds; hard alpha; no see-through holes in bodies; tyres solid; feet on the baseline; safe frame fallback; no blinking while invulnerable; the inspector draws every frame.
- `overlays.js`: plays nine real scenes (tutorial, all cast boss fights, Level 333 with the pigs, Cowgod as an ally, dialogue) and checks every drawn frame: no impact word, toast, banner, boss card or dialogue box covers a character's face, and overlays keep at least 6px between each other.
- `screenshots.js`: captures the gameplay screenshots in `screenshots/`.
- `ui_screens.js`, `rig_preview.js`, `sprite_preview.js`: render screens and sprites to PNG for visual review.

## Developer sprite inspector

Press **F9** (or open the file with `#inspector` at the end of the URL). It is not reachable from the normal menus.
UP/DOWN picks the character, LEFT/RIGHT the animation. SPACE plays or pauses, `,` and `.` step frames, `-` and `+` change speed,
B cycles light/dark checkerboard, black and white backgrounds, O toggles the overlays (frame bounds, opaque bounds, pivot,
collision box, attack hitbox), G zooms and V validates every character. F9 or Esc leaves.

## Faces stay visible

Every character registers where its face is on screen while it is drawn (Moshmouth, the pigs, Electric Harley, the wolf,
Cowgod, Shitman and Shitkins from their art anchors; other enemies and bosses from the top of their body). Everything
drawn on top of the world then lays itself out around those faces and around each other:
- impact words ("THWACK!", "ON BEAT!") move up, down or sideways to a free spot, and are skipped for a frame if none exists;
- toasts, banners and the boss name card try the default spot, then other bands and the sides, then a smaller size;
- the dialogue box moves to the top of the screen if a face is behind it at the bottom;
- fixed HUD panels (hearts, notes, power-up, boss bar) fade to 35% while a face is under them;
- if there is truly no free spot, the overlay is drawn see-through (40-55%) and never on top of another overlay.
Items (notes, power-up bubbles, prompts, pickups) are drawn underneath the characters, so they cannot hide a face.

## Character repair report (what was actually wrong)

- **Invisible motorcycle.** The cast lineup paints a black bike on a black background. The cut-out flood-filled the
  background through every near-black pixel, which leaked into the bike and erased its tank, seat, engine and tyres,
  leaving only the chrome outlines (17% of the sprite was enclosed see-through holes). Electric Harley and his bike are
  now cut from the supplied boss reference, whose purple backdrop can be keyed without touching the black paint.
- **Blinking.** After a hit (and after respawning) the hero was simply *not drawn* on alternate 4-frame steps for 1.5
  seconds; the kart and pig helpers did the same. Hit flashes also replaced characters with flat silhouettes. Characters
  are now always drawn, with a short tint instead, and every entity is drawn from a reset canvas state.
- **Level 4 soft-lock.** Arena flyers spawned at a fixed height (y=120). In low arenas, like Level 4's candlestick room,
  that is above the camera, so the haunted candle could never be reached and the arena never opened. Waves now spawn
  relative to the arena floor, and a watchdog pulls back or pops anything that stays out of reach.
- **Sprites already came from separated art.** Gameplay never cropped the six-panel collage at runtime; each character was
  cut once into its own transparent PNG in `assets/gen`. The atlases in `assets/atlas` are baked from those.

## Known limitations

- Playtime has not been measured with real players.
- The character animations are posed from each character's separated artwork (squash, stretch, rotation, limb and rider
  offsets, effects); only Moshmouth's tongue attack and the biker boss reference are frame-by-frame art you supplied.
- iPhone Safari has no fullscreen API, so the ⛶ button is hidden there (Add to Home Screen gives a full-screen app).
- Environments, tiles, props, enemies and the bosses that aren't in the supplied art are painted by code and baked into images when a level loads. They are not hand-drawn sprite sheets.
- Enemy encyclopedia portraits are simpler than the cast portraits.
- Level layouts mix hand-placed set pieces with seeded procedural segments. Layouts are the same every run.
- The diagnostic autoplay bot can't finish every level with one button. Completability is covered by `reachability.js`, `mechanics.js` and `bosses.js`, not by the bot.
