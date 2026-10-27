# Fried Pig: Hot Wax HD

This is the graphics-overhaul build of Fried Pig: Hot Wax. Open `index.html`
in a browser to play.

* **Original game:** `../fried-pig-hot-wax/` on the `claude/fried-pig-hot-wax`
  branch. It was not changed by this work, apart from one bug fix described
  under "Verification".
* **Gameplay:** this build has the same levels, mechanics, collision boxes,
  timings, dialogue and music as the original. Only the rendering changed.
* **Art direction and pipeline notes:** see [ART_DIRECTION.md](ART_DIRECTION.md).
* **Screenshots:** `screenshots/before/` holds the original game and
  `screenshots/after/` holds this build, with the same filenames and the same
  camera positions. `screenshots/sheets/` holds the character contact sheets.

## What changed

### Rendering pipeline
* **Lighting:** a darkness layer per area with light cut out around sources.
  Lights include the pig's back-flame, fireballs, flamethrower, music notes,
  lamps, braziers, the bonfire, neon signs, TVs, the jukebox, the grill,
  stage rigs, glowing pickups, boss attacks and explosion flashes. The
  falloff is dithered (Bayer 4×4), so light keeps the pixel-art look instead
  of smooth airbrushed gradients.
* **Atmosphere:** particles chosen per area. Rain on the street, dust in
  rooms, embers on the patio and at the Fire Circle, fireflies and pollen in
  the forest, spores in the psychedelic stage, glints in the CD Tunnel,
  floating hold-music notes and haywire sparks for the Crank Kings. There is
  also a stepped fog band where it fits.
* **Light shafts and spotlights:** cones under the store lamps, house lamp
  and kitchen-window shafts, sweeping colour spotlights in the studio, the
  Barn Owl Stage and the Rainbow Stage, searchlights over the night meadow,
  and sun rays in the daytime forest and suburbs.
* **Depth cues:**
  * dithered shadows under every ledge;
  * edge shading on exposed tile sides (cached per tile);
  * a foreground parallax silhouette layer along the bottom edge, switched
    off during boss fights so the arena stays clear;
  * a light colour grade and a stepped vignette.
* **Transitions:** an iris wipe shaped like a vinyl record when a stage
  starts and on every respawn.

### Characters
* **Fried Pig** is redrawn as a lit sprite: per-pixel 4-tone shading, a
  wine-coloured selective outline, a snout with nostrils, ears that move,
  blush, and the FPR lettering. He has a layered 5-colour back-flame that
  flickers with noise, leans into the wind when he runs, burns hotter with
  the pepper, and throws off sparks. He has 20 states:
  * idle, breathing and blinking;
  * alert (wide eyes and raised brow when an enemy or projectile is close);
  * a 6-frame run with body bob, ear flop and tail;
  * jump stretch, fall (ears flapping), and a landing squash;
  * a cheek-puff before spitting fire, then the spit;
  * a poop strain;
  * hurt;
  * two celebration frames and two dance frames.

  He also kicks up dust on footfalls. Squash and stretch come from redrawn
  shapes, not from stretching the image.
* **Enemies:** the suit, cop, security guard, tavern patron, werewolf,
  chicken, drone and psych eye are rebuilt with shading. They get 4-frame
  walk cycles, alert faces, a wind-up frame and a hurt frame.
* **Mr. Markup** is redrawn at native resolution as a 30×54 executive with a
  pinstripe suit, cigar, shades and a briefcase of cash. He has walk, throw,
  crate, charge, stun and hurt frames, and dust puffs on the charge wind-up.
  The original was the normal suit sprite scaled up 2×.
* **The Evil BBQ** is a lit kettle with chrome legs and wheels, glowing eyes,
  layered grill fire, embers from the open lid, and smoke from the vent.
* **DJ Scratchzilla** gains shoulder speaker towers whose cones pump to the
  beat, a light rig over his head, LED VU meters and chrome pistons. In
  phase 3 everything runs faster and flashes pink.
* **Jason Bane** is redrawn at native resolution (the original was scaled
  1.35×).

### Environments
* **Record Store Rampage:** a new dithered dusk sky with stars and the moon,
  and a hazy far skyline with antenna beacons. The near skyline gains
  shaded facades, rooftop water towers, AC units, fire escapes, window
  frames with curtains, and neon signs that glow and occasionally flicker.
  The street has rain and puddles that reflect the neon.
* **Shady Pines Radio HQ:** warm lamp light upstairs, a kitchen window
  shaft, sweeping stage lights in the basement, and a patio lit by string
  lights and grill fire with embers.
* **Psychedelic Pig-Out:** the background mushrooms are now shaded, with
  wobbling stems. Their caps breathe, their spots cycle colour, and they
  glow.
* **Shady Pines Festival:** the sky runs from day to sunset to night, with
  firelight, fireflies, sun rays, stage spotlights and searchlights. The
  Rainbow Stage still uses your festival artwork as the backdrop.
* **Crank Kings:** sunlight shafts, dust, and haywire sparks.

### Interface
* Bevelled panels with gold corner studs replace the flat boxes everywhere.
* Display text uses a two-tone gradient with an outline and drop shadow.
* The HUD is a framed bar with a pig-head lives icon, a spinning record
  counter, and a live equalizer for the music mix that bounces to the beat.
* Boss bars have:
  * a white trail that shows damage just taken;
  * 10% ticks and markers at each phase change;
  * a colour for each phase;
  * a hit flash and a low-health blink.
* New title screen with a flame crown over the logo, spinning records and
  sweeping spotlights.
* New pause, game-over, stage-select, jukebox and how-to screens.
* **Final victory screen:** a full Shady Pines Festival celebration. The
  festival artwork sits on stage with a pulsing golden owl and spotlights,
  fireworks fill the sky, two rows of the crowd wave with lighters, and
  Fried Pig cheers on a riser with his flame at full heat. The score, vinyl
  count, rare records, and the Play Again / Main Menu options are in panels
  on either side.

## Verification
* **Screenshots:** all 55 before/after pairs were captured with no console
  errors. They cover every level at 7 positions, every boss in both phases,
  the dance, the Jason cameo, the Crank Kings intro and course, the victory
  and clear screens, all three stages of the finale, the menus, pause,
  game over and a phone layout.
* **Regression tests pass:**
  * the Crank Kings course;
  * the Supervisor, plus the gate opening after he's beaten;
  * the treehouse ending into Stage 3;
  * Jason's arrival, fight, peace-sign goodbye and drive-off;
  * picking up the blue horn and firing it;
  * every Level 4 mechanic, all three Scratchzilla phases, and the finale
    menus.
* **Performance:**
  * **Normal speed:** 60 fps in every area tested at 960×600 desktop.
  * **4× CPU throttle** (phone layout, 915×412 at 2× pixel density, headless
    software rendering with no GPU): 51–60 fps for the HD build against
    59–60 for the original.
  * **Auto-quality:** if a device can't hold its frame time for about 2.5
    seconds, the build turns off atmosphere particles, fog and light shafts,
    and halves the light count.
* **Bug found and fixed in the original:** a doubled comma in the song list
  crashed the jukebox and played the wrong music in the Crank Kings stage.
  It is fixed in both builds.

## Remaining limitations
* **All art is still drawn in code.** No painting or image-generation tool
  was available, so every sprite and background is pixel art drawn rect by
  rect in JavaScript. The pig, enemies, bosses, title, HUD and city skyline
  are genuine redesigns. Many background zones are the original drawings
  with the new lighting, shadows and atmosphere layered on top: the HQ house
  interiors, the Level 4 forest and tavern, and the suburban houses.
* **Some secondary characters are unchanged.** The band, campers, Crank
  Kings brothers, Supervisor, cats, taco devil and the HQ mascot cameos keep
  their original art. They get the new lighting but were not redrawn.
* **The Kaleidobeast** was not redrawn. It is already fully colour-cycled;
  it gets the new glow and lighting.
* **Not tested on real devices.** Performance figures come from headless
  Chromium with CPU throttling, not real phones.
