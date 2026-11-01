# Level 4 — The Pinecone

A new fourth level for Fried Pig: Hot Wax. It sits between Psychedelic
Pig-Out (Level 3) and Shady Pines Festival, which is now **Level 5**.

* **Branch:** `claude/level4-pinecone`, built on `claude/fried-pig-hot-wax`.
  That branch still holds the previous working build, unchanged.
* **Screenshots:** `screenshots/level4-the-pinecone/` (35 shots covering
  every section, plus a phone layout).

## Progression changes
* `LEVELS` now has five stages. The festival keeps its design, layout,
  Easter eggs and finale. Only its number changed, to 5.
* Clearing Level 3 leads into The Pinecone. Finishing The Pinecone fades
  into "LEVEL 5 — SHADY PINES FESTIVAL". The game's final ending screen
  still plays only after the Level 5 finale.
* Stage Select lists all five stages, plus the Crank Kings bonus.
* **Save migration:** a save that had reached the festival (old level 4) is
  moved to level 5 once, so returning players don't lose their unlock.
  Finishing the festival now records level 6.
* The two festival songs now unlock at stage 5 in the jukebox. Seven new
  songs unlock at stage 4.

## The seven sections
| Section | What happens |
|---|---|
| **4A The Snowy Forest** | Peaceful trail through snowy firs: falling snow, distant mountains, sun rays, fallen logs with icicles, shallow creeks, a deer and a rabbit. The glowing pinecone pulses as the pig nears it. Picking it up changes the music, makes the trees sway, and sends rainbow particles up from the ground. A pinecone icon in the HUD shows it's carried, and it rides on the pig's back. |
| **4B The Pinecone Portal** | A giant hollow pinecone pulls the pig in. Inside is a rainbow tunnel with pinecone scales, floating eyes, faces in the walls and drifting needles. Hazards: pine-needle spikes, burning sap drips that leave sticky puddles (they slow the pig), warning-then-burst flame vents, moving platforms and collapsing scale platforms. Ends in a bright flash out into a moonlit clearing. |
| **4C The Alien's Warning** | A long-armed alien in a straw hat, holding a pitchfork, greets the pig in a Southern drawl. Then he spots the pinecone: "Return the pinecone!" Demon birds wake (glowing eyes, a "!" warning, then a dive), branches fall with a shake warning first, and the alien chases the pig to the carnival lights, then gives up. |
| **4D The Haunted Carousel** | A dark carousel lights up when the pig arrives. The gates close and it runs for 32 seconds, speeding up the whole time. It has six painted animals (horse, unicorn, sea serpent, griffin, flying pig, owl), a colour-cycling canopy and flashing bulbs. Clowns arrive juggling, throwing pies, bouncing on rubber balls and dancing. The background swirls more as it speeds up, and the music speeds up too. At the end it stops dead and launches the pig into the mushroom woods. |
| **4E The Wormhole** | After the launch the pig walks a stretch of glowing-mushroom woods (about 40 tiles, with records and a ledge) before he spots the magic mushroom ("OOH... SHINY"). Touching it plays an eating scene: he sniffs it, plucks it, takes three chomps (it shrinks with each bite and crumbs fly), gulps, hiccups rainbow bubbles, then "...uh oh". His eyes bulge, his flame turns rainbow, the screen wobbles and a wormhole opens. Then a 60-second **Piggies vs. Worms** mini-game (below). Afterwards the pig drops back where he ate the mushroom and lands face-first in the snow. A tiny worm pops up and waves, and he shakes it off. |
| **4F The Jacuzzi Elephant** | Boss fight; see below. |
| **4G Return the Pinecone** | At a campfire the alien waits, now friendly. The pig sets the pinecone down; it glows, burns with a gentle rainbow flame and turns to sparkling ash. "Embrace love, little pig. Just don't hold on too tight." The pig nods, the alien fades away, the snow stops and the sun rises. The pig walks to a Shady Pines Festival banner, and the screen fades into Level 5. |

**Checkpoints:** mid-forest, tunnel start, the Alien's Warning, the chase,
before the carousel, after the mushroom, before the arena, and at the
campfire trail.

## Piggies vs. Worms
* **Separate mode:** it runs as its own game mode (`G.mode='worms'`). It
  doesn't touch the main level's state, the pig's health, lives, records or
  checkpoints, and it returns the pig to exactly where he ate the mushroom.
  The mushroom only works once per playthrough.
* **Battlefield:** hills, trees, logs and rocks you can blow holes in, a
  water hazard in the middle, a colour-cycling sky and drifting clouds.
  Three floating islands (one over each team, one over the water) are
  destructible and work as rope anchors. Lil Sizzle starts on the pig-side
  island and Sgt. Slime on the worm-side island. Explosions blow craters
  and knock characters back.
* **Pigs:** Bacon Bit (headband), Hamlet (top hat) and Lil Sizzle (shades),
  100 HP each. You control them one at a time. Each pig has two weapons,
  and the POOP button switches between them (the current one is shown in
  the bottom-left box):
  * **Poop bomb:** hold Fire to charge, release to throw. It flies in an
    arc, blows a crater and splatters brown everywhere. Throwing it ends
    the turn.
  * **Ninja rope:** Fire shoots the rope along your aim. It hooks onto any
    terrain, tree or island and gives a short tug that lifts you into a
    swing. Left/right pump the swing, up/down climb, and Jump lets go with
    your momentum. You can fire it again in mid-air to chain swings and
    cross to the other side. Using the rope never ends the turn.
* **Worms:** segmented, wiggling worms with their tails on the ground and
  heads raised, big blinking eyes and a shoulder bazooka. General Dirtbag
  (helmet with a gold star and a moustache; aims well, targets the weakest
  pig), Private Wiggles (oversized helmet that slips, darting eyes and a
  sweat drop; nervous, often misses) and Sergeant Slime (red beret and
  shades; steady aim, holds his island). Each fires bazooka rockets with smoke trails, and each has
  its own one-liners.
* **Turns and wind:** turns alternate, with 14 seconds per pig turn (ended early only by throwing a bomb). Wind
  changes each turn and is shown by an indicator.
* **Timer:** exactly 60 seconds, starting when you get control. It freezes
  while paused.
* **Results:** win by wiping out the worms or by having more total health at
  the buzzer. Equal health is a draw. A win unlocks the golden poop bomb
  collectible, which appears on the title screen. Losing or drawing costs
  nothing.
* **Controls:**
  * **Keyboard:** ←→ move or swing, ↑↓ aim or climb, X to use the weapon,
    C to switch weapon, Space to jump or let go of the rope.
  * **Touch:** ◀▶ move or swing, ▼ sweeps the aim (or climbs the rope),
    FIRE to use, POOP to switch, JUMP to jump or let go.

## The Jacuzzi Elephant
* **Look:** a huge elephant in a bubbling jacuzzi, wearing sunglasses and a
  tiny shower cap. He has flapping ears, an animated trunk and changing
  expressions. In his intro he lowers his sunglasses and blows a giant
  bubble.
* **Phase 1 — Bubble Trouble:** bubbles drift and bounce at different speeds
  and heights. Some are trap bubbles (light purple): they carry the pig up,
  and mashing jump pops them. Fireballs or stomping pop bubbles. After his
  big-bubble attack he pants and takes double damage. He also dunks
  underwater (can't be hit) and splashes back up.
* **Phase 2 — Clown Chaos:** clowns pour in from both sides throwing pies
  and bouncing on balls. Bubbles can catch clowns and float them away.
* **Phase 3 — Jacuzzi Meltdown:** foam covers the floor (slippery), his trunk
  sprays bubbles in every direction like a sprinkler, the music speeds up,
  and the carousel in the background spins wildly.
* **Finisher:** the pig drops a giant poop bomb into the tub. A huge brown
  bubble rises carrying the elephant and the clowns, grows and pops. They
  all land in a snowbank: the elephant dizzy with his shower cap over his
  eyes, the clowns applauding. The pig celebrates and gets a +30 vinyl
  bonus.

## Music and sound
* **Seven new songs** in the game's existing music system, all newly
  composed:
  * Pinecone Trail — peaceful acoustic forest
  * Inside the Cone — psychedelic tunnel
  * Howdy Stranger — eerie alien
  * Midnight Midway — accelerating carnival
  * Piggies vs. Worms — fast artillery battle
  * Bubble Bath Blues — elephant boss
  * Return to the Forest — gentle resolution
* **New sound effects:** alien voice, bird screech, pinecone chime,
  wormhole, mushroom gulp, calliope, bubble, bubble pop, splash, rocket.
* **Not used:** no recording of Fried Pig Records' "Pinecone Song" was in the
  project, so the level uses new music instead of imitating it.

## Testing (headless Chromium + Playwright)
* **Progression:**
  * Level 3 clear leads to The Pinecone, which leads to Level 5.
  * Stage Select shows five stages and the jukebox 31 tracks.
  * Old saves migrate once.
* **Story beats:** pinecone pickup, portal, tunnel exit, the alien dialogue,
  the chase with active birds, the carousel start, speed-up and launch, the
  mushroom into the mini-game, and the return. The pig's health, records
  and lives are identical before and after the mini-game, and the mushroom
  can't re-trigger.
* **Mini-game:**
  * The clock starts at exactly 60.0 seconds.
  * Pausing freezes it.
  * Bombs and rockets deal damage.
  * Rope: hooks the island, swings about 85 px, climbs, lets go with momentum, re-fires in mid-air, and never ends the turn. Only the bomb throw does.
  * One pig and one worm start on the floating islands.
  * Win, lose and draw all resolve.
  * Golden poop bomb unlocks on a win.
* **Boss:** all three phases, clowns in phase 2, foam in phase 3, trap
  bubbles (caught and freed), fireball damage, the finisher, the +30 bonus,
  and the gate opening afterwards.
* **Ending:** the pinecone ending plays and fades into Level 5.
* **Regression:**
  * Levels 1–3.
  * The festival (now Level 5), including Scratchzilla's three phases and
    its finale.
  * The Crank Kings bonus stage, Jason's cameo and the blue horn.
  * The double jump pepper (106 px with it, 57 px without).
  * The Sasquatch pads (20/20 landings).
  * No page errors anywhere.
* **Performance:**
  * **Normal speed:** 60 fps in every section and in the mini-game.
  * **4× CPU throttle** (phone layout, no GPU): 51–61 fps in most sections.
    The carousel ride is the heaviest moment at about 40–47 fps.

## Remaining issues
* **Art is drawn in code.** All new art is pixel art drawn in code, like the
  rest of this build. It isn't hand-painted sprite sheets.
* **Camera:** the "camera pans upward" at sunrise is done with a sky change,
  not a vertical camera move, because the engine's camera only scrolls
  sideways.
* **Not tested by a person:** difficulty and timing were tuned with
  automated tests, not human playtesting. Audio was not listened to.
* **HD build not updated:** the HD build (`fried-pig-hot-wax-hd`) does not
  include this level yet.
