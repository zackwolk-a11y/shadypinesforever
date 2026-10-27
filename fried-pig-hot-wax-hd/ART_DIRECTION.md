# Fried Pig: Hot Wax — HD Graphics Overhaul

This folder is the graphics-overhaul build. The original game is untouched in
`../fried-pig-hot-wax/` (branch `claude/fried-pig-hot-wax`). Gameplay code,
level data, collision boxes, timings and audio are the same in both builds;
only rendering changed.

## 1. Rendering architecture (audit)

* One `<canvas>` with a fixed 224 px internal height and a 400–520 px width
  (wider on phones in landscape). It is scaled up with CSS
  `image-rendering: pixelated`, and `imageSmoothingEnabled` is off on every
  context, so pixels stay crisp at any device pixel ratio.
* The world is a 16 px tile grid, 14 rows tall. Logic runs on a fixed 60 Hz
  step, and drawing happens once per animation frame.
* **There are no bitmap assets.** Every sprite, tile and background is drawn
  in code into offscreen canvases (`sprite()`, `tileImg()`, `buildZoneBG()`)
  and cached. The only images are the Fried Pig Records logo (splash screen)
  and the supplied Shady Pines Festival artwork (Rainbow Stage backdrop).
* Draw order (`drawWorld`): sky/parallax → zone backdrop → background props →
  tiles → hazards → foreground props → items → enemies → bosses → shots →
  pig → particles → crowd → HUD.

## 2. What the overhaul adds to the pipeline

| Layer | What it does |
|---|---|
| Ledge shadows | Soft dithered shadows under ledges, and edge shading on exposed tile sides, so platforms read as solid objects |
| Lighting buffer | A darkness layer per area, with light cut out around sources (pig flame, fireballs, lamps, braziers, neon, stage lights, glowing pickups, boss attacks). Light falls off in hard 4-step bands, not smooth gradients, to stay in the pixel style |
| Additive glow | The same light shapes added in colour on top. Kept low so nothing blooms out |
| Atmosphere | Particles in screen space with depth: dust, rain, leaves, fireflies, embers, spores. A dithered fog band where it suits the area |
| Foreground parallax | Dark silhouettes along the bottom edge that move faster than the camera (crates, ferns, mushrooms, fence posts). They never cover the play area |
| Colour grade + vignette | A light per-level tint and a stepped vignette |
| Transitions | An iris wipe in the shape of a vinyl record for deaths and level changes |

## 3. Style rules

* **One pixel grid.** No sprite is scaled by a non-integer factor during
  normal play. Characters are drawn at 1:1 against the 16 px tiles.
* **4-tone ramps.** Every material uses highlight / base / shadow / dark
  outline. Outlines are dark, not black, and take on the material's colour
  ("selective outlining") so silhouettes stay readable without looking stiff.
* **Light from the top left**, plus the scene's warm or cool light sources.
* **Readability first.** Hazards and enemies keep the brightest, most
  saturated colours. Backgrounds are lower in contrast and pushed towards
  the scene colour. Effects never cover platforms.
* **Palette moods**
  * Record Store Rampage — dusky magenta night, warm tungsten store lights,
    cyan/pink neon, wet street.
  * Shady Pines Radio HQ — warm wood and amber lamps upstairs, deep
    plum/teal studio basement, a night patio lit by string lights and grill
    fire.
  * Psychedelic Pig-Out — fully saturated colour cycling in the background
    only. Platforms keep a dark readable edge.
  * Shady Pines Festival — daylight greens to sunset to a navy night,
    fireflies, firelight, stage spotlights, and the supplied festival
    artwork for the Rainbow Stage.
  * Crank Kings — bright suburban afternoon, going purple when the course
    goes haywire.

## 4. Honest limits

* No image-generation or painting tool was used. All art is still pixel art
  drawn in code, rect by rect. This build adds a lot of detail, shading,
  frames and lighting, but it is not a set of hand-painted sprite sheets.
* The Rainbow Stage backdrop is the supplied festival image, shrunk to
  320×144 with 64 colours so it matches the pixel style.
