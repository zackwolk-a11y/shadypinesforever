# THE 333 DIMENSIONS OF MADNESS

An original side-scrolling action platformer starring **Moshmouth**, the screaming green monster head.
The whole game is in one self-contained offline file: **`333-dimensions-of-madness.html`**.
To play, open it in any modern browser. It needs no server, makes no network requests and has no dependencies.

## Controls

| Action | Keyboard | Gamepad | Touch |
|---|---|---|---|
| Move | Arrows / WASD | D-pad / stick | left stick |
| Jump / confirm | Space, Z, K | A | JUMP |
| Tongue Whip (UP = upward) | X, J | X | WHIP |
| Slime Spit | C, L | B | SPIT |
| Bone Bash (reflects shots) | V, I | Y | BASH |
| Mosh Dash (hold = sprint) | Shift, ; | RB/RT | DASH |
| Metal Scream (hold to charge) | B, O | LT | SCRM |
| Tongue Grapple / yank | E, U (or UP+WHIP) | LB | HOOK |
| Headbang (on the beat) | H, N | L3 | BANG |
| Transform menu / switch pig | Q, T | R3 | FORM |
| Summon ally (DOWN+ = cycle) | R, G | Select | SUMN |
| Pause / skip cutscene | Esc, P | Start | II |

## What is in the game

- **30 levels in 6 worlds.** The third level is shown as **LEVEL 333: THE THREE LITTLE PIGS**. It has seven chapters: the straw house, Hamwise's glide, the stick house, the motorcycle chase, the brick house, the three-phase werewolf boss, and a concert.
- **Six character groups**, all animated from the supplied artwork:
  - Moshmouth
  - the three pigs: Hamwise (glide and kazoo stun), Porkington (builds bridges and ladders, throws sticks) and Trufflina (punches, carries bricks, ground pound)
  - Razz Vroomberg on a motorcycle with spinning wheels, suspension bob, flowing hair, wheelies, turbo and crashes
  - Big Bad Barnaby, a werewolf with a swinging claw arm, huff and puff, leap and howl
  - Captain Udderly, a cow with a fluttering cape who flies, charges and stomps
  - the Golden Gloop, which morphs, splits into three, stretches and reforms
- **Eight multi-phase bosses**: Barnaby (3 versions), Udderly (hypnotised), the Puppet King, the Bovine Overlord, the Dimension Devourer, the Carnival Colossus, King of the Garbage Heap and The Eternal Feedback. In the last phase of the final boss, all six groups help out.
- **Abilities**: whip, grapple, spit, bash, dash/sprint, charged scream and headbang. Hitting attacks or headbangs on the beat fills the METAL meter. A full meter powers the METAL SCREAM that destroys MAX amps.
- **Transformations**: Pig, Wolf, Cow, Bear, Clown and Mega Monster. **Summons**: the three pigs, Razz and Udderly.
- **Original procedural soundtrack.** 38 songs are composed at runtime in punk, thrash, metal, industrial, psych, circus and comedy styles. The music gets heavier in combat and changes again for each boss phase. Beat blocks and beat platforms move to the music.
- **Meta features**: world map, persistent save, checkpoints, 25 achievements, 3 Dimensional Shards per level, the Monster Encyclopedia (44 entries), a jukebox, options (volumes, difficulty, shake, touch), and replayable levels.

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
- `mechanics.js`: 31 checks:
  - every ability and transformation
  - the pig abilities
  - the straw, stick and brick quests and the assembly-line mech
  - summons, checkpoints and saves
  - measured audio output
- `smoke.js`: loads every level and chapter, simulates input and fails on any runtime error.
- `platform.js`: frame rate at 1080p, no network requests, phone touch controls (the jump button really jumps), tablet layout.
- `autoplay.js`: a god-mode bot that tries to play each level through. It is diagnostic only; some levels need puzzle solving it cannot do.
- `ui_screens.js`, `rig_preview.js`, `sprite_preview.js`: render screens and sprites to PNG for visual review.

## Known limitations

- Playtime has not been measured with real players. LEVEL 333 is probably shorter than the 25–35 minutes targeted in the brief.
- Enemies, bosses that are not in the supplied art (Puppet King, MOO-9000 and others), tiles and backgrounds are generated in code in a matching outlined pixel style. Their encyclopedia portraits are simpler than the cast portraits.
- Level layouts mix hand-placed set pieces with seeded procedural segments. Layouts are the same every run.
