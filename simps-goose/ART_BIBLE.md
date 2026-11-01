# SIMPS: GOOSE ON THE LOOSE! — Art Bible (v0.1, vertical slice)

This is the visual rulebook for the whole game. Every texture in the slice is **authored in code**
(`src/art/*`) and rasterised into Phaser textures at boot, so these rules are enforced by
shared helpers rather than by discipline alone.

## 1. Resolution and sprite scale
| Item | Value |
|---|---|
| Internal resolution | **480 × 270** (16:9), scaled with nearest-neighbour filtering (`pixelArt: true`, `roundPixels: true`) |
| Base tile / grid | 16 px. Floor strip 30 px tall |
| Goose | 48 × 48 frame. Body ≈ 20 px wide, ≈ 30 px tall standing, up to 40 px with neck stretched. Physics box 14 × 22 |
| People | 32 × 64 frame, ≈ 58 px tall (≈ 2× the goose) |
| Text | Original 5×7 pixel font. `px` (plain, 6×9 cell) and `pxo` (ink outline + drop shadow, 8×11 cell). Always drawn at exactly 1:1 or 2:1 scale, never fractional |
| Camera zoom | 1.0 for gameplay. The freeze-frame wide shot uses 0.75 (the only non-integer zoom, and only on a still frame) |

## 2. Palette (`src/art/palette.ts`)
A single master palette of ramps, each ordered `[highlight, base, shade, deep]`:
- **Brand anchors:** Simps red `#e02a3c` (ramp `#ff6b6b → #5e0c22`), black `#2a2430`, white `#faf6ee`.
- **Ink / outline:** `#1b1222`, a warm purple-black. Pure black is never used.
- **Goose:** white with cool lavender shadows (`#ffffff → #6f7299`), so the goose pops against the warm store. Beak and feet use the orange ramp.
- **Flavours:** Cola (brown), Cream Soda (cream gold), Black Cherry (deep crimson), plus blue raspberry, lime, mango, purple and root beer for shelf variety.
- **Environment:** wood, cardboard, wall cream, steel, glass and soda, plus outdoor sky, Okanagan mountains, hills and leaves.

## 3. Lighting rules
- **One key light, from the top left.** `Px.shadedEllipse` computes every volume's shading from the same light vector, with a rim darkening term. Highlights face up-left, shade falls bottom-right.
- **Outlines:** a 1 px ink outline on the outside of every character and prop silhouette. Interior separation uses the shade ramp, not ink. Faces (eyes, brows, blush) are drawn after the outline so they stay crisp.
- **Dithering:** 4×4 Bayer, used only at ramp boundaries and in gradients. No noise dithering.
- **Glass and liquids:** glass = `gl` ramp at partial alpha plus a 1 px white vertical highlight stripe, with diagonal reflection lines on fridge doors and windows. Liquid is the flavour ramp with a highlight band at the surface.
- **Dynamic light:** additive (ADD-blend) stepped radial glows for pendant lamps (warm), fridges (cool cyan), the fountain's trident crest (pulses red with pressure) and window/skylight shafts. Glows are stepped in 5–6 bands so they stay pixel-art rather than smooth gradients.
- **Shadows:** soft ink ellipses under the goose, bubbles and props, scaled and faded by height above the surface below.

## 4. Animation timing
| Animation | Frames | FPS | Notes |
|---|---|---|---|
| idle (breathing + blink) | 6 | 5 | body ±3.5 % squash, head bob 1 px |
| look around | 8 | 5 | looks up, then back over the shoulder with a mischievous brow; plays after 5 s idle |
| walk (waddle) | 6 | 11 | body rocks ±0.07 rad. Playback speed scales with velocity |
| run | 6 | 15 | neck forward and low, wings out, mischievous brow |
| jump / fall / flutter | 2 / 2 / 4 | 12 / 10 / 16 | holding jump while falling flaps the wings (slower fall) |
| land | 3 | 16 | plus engine squash 1.3 × 0.72 easing back |
| honk | 6 | 12 | anticipation (pull back, eyes shut) → stretch → beak wide → recover |
| drink → swallow | 6 → 6 | 8 / 9 | the swallow shows a lump travelling down the neck |
| reactions | 4–6 | 6–18 | Cola: shocked, feathers puffed, vibrating. Cream Soda: heart eyes, blush, swaying. Black Cherry: sour pucker, then a wide-eyed "!!" |
| blow / ride / hurt / celebrate / dash | 4 / 2 / 2 / 6 / 2 | 8 / 4 / 10 / 12 / 20 | |
| people (each of 7) | 26 frames over 9 states | 2–12 | idle, walk, shock, laugh, flee, gesture, wave, cheer, browse |

Engine-side secondary motion is layered on top of the frames: squash and stretch on jump and land, bubble wobble on landing, strain wobble before a pop, needle physics, and machine shake.

## 5. Recurring motif language: Simps trident and Canadian identity
`src/art/motifs.ts` is the single source for both motifs:
- **Red trident** (`tridentInto`): centre prong, two flared side prongs on a U crossbar, and a shaft ending in a downward arrowhead. It is an original pixel interpretation of the trident mark.
  - **Architecture and geometry:** the **Trident Display Stand** is gameplay geometry. Its pedestal, U-bottom, both prong tips and the centre tip are all standable platforms. Trident shelf brackets, header-board finials, a mezzanine railing of trident balusters, and a giant trident mural behind Bubble Trouble.
  - **Machinery:** the FIZZ-O-MATIC's three **trident-fork spouts** (where the bubbles come from), its trident crest (glows with pressure), the trident hub on the pressure valve, and the **Trident Lift** piston platform.
  - **Collectibles, effects and UI:** the *Simps Certified* trident badge (rare collectible), trident glints inside bubbles of 32 px and up, trident stamps on crates and bottle labels, a trident on staff aprons, the HUD flavour-slot crest, menu and toast headers, and the title logo.
- **Maple leaf and Canadian flag** (`leafInto`, `canadaFlag`, `bunting`): a waving flag (storefront, store wall, sampling counter, mezzanine), maple-leaf bunting, **Golden Maple Leaf** collectibles (3 hidden), maple stamps on delivery boxes, a maple floor graphic in front of the counter, maple-leaf confetti in celebrations, the fountain base and counter decals, and "PROUDLY CANADIAN" / "THANKS, EH!" signage.
- **Taste rules:** at most one dominant trident per screen. Maple leaves are accents (bunting, stamps, confetti), never wallpaper. Both use only the brand red / white / ink colours (gold for collectibles).

## 6. Rendering pipeline
1. `Px` (`src/art/px.ts`): a software rasteriser into an RGBA `Uint32Array` with primitives (shaded ellipse, polygon, line, ring), outline, dither, blit and flip. Deterministic RNG, so the art is identical on every boot.
2. Generators (`goose.ts`, `people.ts`, `props.ts`, `fx.ts`, `motifs.ts`, `backgrounds.ts`) return `Px` buffers. Characters are **parametric**: a pose is rasterised, and an animation is a list of poses.
3. `registry.ts` turns the buffers into canvases and registers them as Phaser textures (sheets get named frames), then builds all animations. This takes about 0.4 s on desktop.
4. Large scenery (the 2,468 × 360 store wall and the 1,000 × 270 street) is cached once as a single texture. Parallax: store wall 0.9, mountains 0.15, trees 0.45.
5. `npm run export:assets` writes every sheet to `assets/` as PNG for artists.

## 7. Production status: honest assessment
No image-generation tool was available, so **all art is code-authored pixel art**.
- **Slice-complete (consistent, animated, shippable for a demo):** goose sheet (98 frames, 24 animations), motifs, props, store and street backgrounds, effects and UI.
- **Recommended for a human artist pass before a commercial release:** people sprites (readable but simple), the goose's head and face detail, and the large backgrounds (more texture variety). Every generator can be swapped for hand-drawn PNGs without code changes elsewhere: replace the entry in `SINGLE` or the sheet builders.
- **Brand:** simpsmb.com could not be reached from this environment. The store sign and wordmark use original lettering, and the trident is an original pixel interpretation of the mark the client supplied. Brand approval is needed before public distribution.
