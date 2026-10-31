# Canonical Visual Style Guide

**The canonical paragraph lives in [`canon/style/canonical_style.txt`](../canon/style/canonical_style.txt) and must be included verbatim in every visual asset-generation prompt or art brief.** `becoming.canon.load_style_paragraph()` loads it, and a test pins its text.

## Technical art specification (locked once a direction is chosen)

| Property | Value |
|---|---|
| Projection | Top-down three-quarter ("SNES RPG"). Ground plane seen from above; building fronts and characters seen at about 3/4. Doors face south (toward the camera) |
| Tile size | 16 × 16 px native. World is 80 × 60 tiles (1280 × 960 px native) |
| Display scale | Integer only (2×, 3×, 4×), nearest-neighbour, `pixelArt: true` |
| Character sprites | 16 × 24 px body on a 16 × 32 frame. 4 directions × (idle 2 frames, walk 4 frames). Seated and talking poses in Phase 4 |
| Buildings | Footprints match `village_layout.json` exactly (homes 6 × 5 tiles; Pepper's house 5 × 5; public buildings 10–12 × 7–8). Roof overhang may extend 1 tile north, never south over the door |
| Light | Sun from upper left; shadows fall down-right, 1–2 px for small props and about 1/2 tile for buildings |
| Outline | 1 px dark outline, hue-shifted (deep brown-green, not pure black) |
| Palette | 48 colours maximum per seasonal palette, shared ramps across the world. Seasonal variants are palette swaps plus a few overlays (snow caps, blossoms, falling leaves) |
| Text | None embedded in art (UI renders all labels) |
| Interiors | Same scale and camera. One room per interior at Phase 3, rooms added later |

## Core palette ramps (baseline "Golden Spring Commons")

| Ramp | Hex (dark → light) |
|---|---|
| Forest green | `#1f3b2a` `#2f5d34` `#3f7a3e` `#5c9a48` |
| Moss / grass | `#5f8f3a` `#7fae4c` `#9cc85e` `#c3e08a` |
| Honey timber | `#5a3a1e` `#8a5a2b` `#b98545` `#e0b36e` |
| Terracotta roof | `#6e2f1e` `#9c4a2c` `#c2683d` `#e08b5a` |
| Cream stone | `#8a7d68` `#b9ab8e` `#ddd0b2` `#f3ead6` |
| Water | `#2d5f7a` `#3f86a3` `#5fa8c8` `#a7d8e6` |
| Muted florals | `#b56576` `#e3a6a1` `#c9b458` `#8c7fb5` `#e8e3d3` |
| Outline / ink | `#1d1a14` `#2b2a20` |

## Do / Don't
- **Do** hand-craft irregularity (crooked fence posts, varied shingles), make gardens dense and lived-in, and give each home visible personal objects from its canon `home.contents`.
- **Don't** use photorealism, blur or soft gradients, mixed perspectives, lettering in art, office furniture, chrome or glass towers, or generic castles.

## Asset rules
Every asset is recorded in [ASSETS.md](ASSETS.md) with its origin (hand-authored, procedural, CC0 pack + licence, or generated + prompt + cost), the style-guide version, and the date.
