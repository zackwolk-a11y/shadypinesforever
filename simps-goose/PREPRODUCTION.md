# SIMPS: GOOSE ON THE LOOSE! — Pre-Production Notes

*HONK. SIP. BURP. REPEAT.*

Status: **preparation only, no game code written yet.** This file collects the research, the
decisions, and the build plan, so the build can start as soon as it's approved.

---

## 1. Brand research status

`simpsmb.com` is **blocked by this session's network policy**, so I couldn't open the site.
Everything below comes from search-engine snapshots of simpsmb.com product pages and third-party
listings. Before the build, the site should be allowed so I can check logo, colours, typography,
bottle labels, and the storefront directly.

**Facts I could confirm (from search snapshots):**
- Kelowna, BC company. Founding year is given as 2015 on Simps' own pages and 2014 on one
  third-party profile.
- Makes flavoured syrups, a "Café Series", local soda concentrates (1 oz concentrate to 5 oz
  soda water), Zero Sugar lines, caesar mixes, adaptogen drinks, and non-alcoholic spirits.
- Has a facility and a retail shop in Kelowna.
- Sells a "Dirty Soda Pack" (Cola, Root Beer, Dr. Feelgood, Black Cherry, Cream Soda, C.R.E.A.M.).

**Still unverified (needs the site):** the trident mark, exact brand red/black/white values,
typefaces, label layout, and what the store interior looks like.

### Verified flavour names

| Flavour | Line | Status |
|---|---|---|
| Cola (incl. Zero Sugar Cola) | Soda concentrate | ✅ |
| Cream Soda | Soda concentrate | ✅ |
| Black Cherry | Soda concentrate | ✅ |
| Root Beer | Soda concentrate | ✅ |
| Lemon Lime | Soda concentrate | ✅ |
| Dr. Feelgood | Soda concentrate (Dirty Soda Pack) | ✅ |
| Blue Raspberry | Syrup / concentrate | ✅ |
| Mango | Syrup | ✅ |
| Blackberry, Coconut, Strawberry | Syrup | ✅ |
| Vanilla | Syrup / Café | ✅ |
| Caramel, Salted Caramel | Café Series | ✅ |
| Hazelnut (best seller in the Café Series) | Café Series | ✅ |
| Peppermint | Café | ✅ |
| Lavender | Café / fruit | ✅ |
| Toasted Marshmallow | Café | ✅ |
| Blue Cotton Candy | Unclear | ⚠️ exists, but I couldn't confirm which line |
| **Orange** | — | ❌ **not found, replace** |

---

## 2. Flavour → power mapping (revised to use verified flavours)

All powers are fictional gameplay abilities, not claims about the products.

### Level 1: sampling station (soda concentrates)
| Flavour | Power | Effect | Colour identity |
|---|---|---|---|
| Cola | Fizzy Dash | Fast horizontal burst | Deep brown / caramel foam |
| Cream Soda | Foam Float | Spawns a floating cloud platform | Cream / pale gold |
| Black Cherry | Cherry Blast | Bouncing cherry-bubble projectiles | Dark crimson |
| **Lemon Lime** *(replaces Orange)* | Citrus Burst | Fizzy projectile that triggers distant switches | Lime green / yellow |
| Vanilla | Soft Landing | Slow, safe descent | Ivory |
| Blue Raspberry | Bubble Bounce | Bouncy bubble platforms | Electric blue |
| Root Beer *(bonus, hidden)* | Root Rumble | Ground-pound shockwave that shakes shelves | Dark amber |

### Level 2: lab recipes (fictional combinations)
| Recipe | Name | Effect |
|---|---|---|
| Cola + Black Cherry | Cherry Rocket | Enhanced dash that breaks crates |
| Cream Soda + Vanilla | Cloud Nine | Large, long-lasting platform |
| **Mango + Lemon Lime** *(Orange removed)* | Tropical Launch | Vertical rocket jump |
| Black Cherry + Cream Soda | Dark Foam Shield | Temporary invulnerability |
| Blue Raspberry + Lemon Lime | Electric Fizz | Ricocheting bubbles |
| Root Beer + Cream Soda *(secret)* | Float Mode | Super-buoyant bubble ride |
| Any combination not listed | "Foam Fiasco" | Comic explosion plus a small random buff, so failed mixes still pay off |

### Level 3: café bubble-burp (all six requested café flavours were verified)
| Café syrup | Bubble Burp | Ogopogo strategy |
|---|---|---|
| Vanilla | Large floating bubbles | Easy hits, slow |
| Caramel | Heavy impact bubbles | High damage, short arc |
| Hazelnut | Ricocheting bubbles | Banks off rocks and docks |
| Peppermint | Rapid-fire bubbles | Low damage, high rate |
| Lavender | Slow suspension bubbles | Freezes splash hazards in place |
| Toasted Marshmallow | Protective foam bubbles | Absorbs hits, medium damage |

Balance rule: every flavour does the same damage per second (within ±10%) against each boss
phase, and an automated test plays the boss once with each flavour.

---

## 3. Technical decisions

| Area | Decision | Why |
|---|---|---|
| Engine | **Phaser 4.2.1** (latest) via npm | The prompt allows "Phaser 3 or equivalent maintained". v4 is the maintained line. I'll pin 3.90 instead if you prefer. |
| Language / build | TypeScript + **Vite 8** | Fast dev server, static build output |
| Physics | Phaser Arcade (AABB) plus custom one-way and bubble platforms | Enough for a platformer, and cheap on mobile |
| Levels | Data-driven: JSON/TS tilemaps and entity lists | Keeps level design separate from code |
| Saving | `localStorage` with a versioned schema | No backend needed |
| Audio | **Procedural Web Audio synthesis** (chiptune sequencer plus synthesized sound effects) | Original music with no licensing issues, and tiny downloads |
| Input | Keyboard, Gamepad API, touch overlay (landscape, safe-area aware) | Section 16 of the prompt |
| Testing | Vitest (systems) + Playwright headless Chromium (smoke tests, screenshots, automated boss runs) | Both run in this container |
| Location | New folder `simps-goose/` in this repo, **or a separate repo** (see open questions) | This repo is an unrelated Python project |

### Planned source layout
```
simps-goose/
  src/
    main.ts, config.ts
    scenes/      Boot, Preload, Title, LevelSelect, Street(intro), Store, Lab, SodaDimension,
                 FakeCredits, Cafe, Waterfront, Ogopogo, TrueEnding, Pause, Journal
    entities/    Goose, Bubble, enemies/*, bosses/CarbonationMachine, bosses/Ogopogo
    systems/     input, physics, flavor, recipes, combat, collectibles, save, audio, camera, fx
    minigames/   SodaMixer, CoffeeBar
    data/        flavors.ts, recipes.ts, levels/*.ts, achievements.ts
    ui/          HUD, menus, touch controls
    art/         pixel-art generators and palettes
    audio/       synth instruments, song data, sfx
  tests/         unit + e2e (Playwright)
  public/        built atlases
```

---

## 4. Art bible (draft)

- **Resolution:** 480×270 internal (16:9), scaled by whole numbers, nearest-neighbour filtering.
  Tiles are 16×16. The goose is about 24×24 (up to 32×32 with the neck stretched).
- **Palette:** one master palette of about 48 colours.
  - Brand anchors: Simps red, near-black, white (to confirm from the site).
  - One colour ramp per flavour, 3 to 4 shades each.
  - Separate ambient ramps: store (warm), lab (teal and steel), dimension (saturated rainbow),
    café (warm wood), waterfront (golden hour).
- **Readability:** the play layer is outlined and high-contrast. Backgrounds are lower contrast and
  shifted toward a hue. Hazards always use a red-magenta warning accent.
- **Animation:** squash-and-stretch on every goose state, played at 8 to 12 frames per second.
  Liquids use palette cycling.
- **Lighting:** additive glow sprites and palette-shifted light zones. No blur.
- **Branding:** all bottles, labels, and storefront art are drawn from scratch and Simps-*inspired*.
  The real logo and trident are **not** reproduced unless you confirm permission.

**How the art will actually be made:** this environment has no image-generation model. All sprites
will be authored as code: hand-placed pixel grids and procedural drawing, rendered into texture
atlases at boot or build time. This approach can produce consistent, detailed pixel art, but it
won't match a hand-painted Owlboy-level art pass. The final report will state that honestly, and
every asset will be swappable, so a human artist can replace the atlases later.

---

## 5. Phased build plan

| Phase | Deliverable | Check before moving on |
|---|---|---|
| 1 | Vite + Phaser + TypeScript scaffold, palette, save schema, scene skeleton | Builds, boots to title |
| 2 | Goose: movement, physics, all animations, honk | Feel test plus Playwright input test |
| 3 | Level 1: street intro, store, sampling, Bubble Trouble, 3 valves | Full-level automated run |
| 4 | Level 2: lab, portal, Soda Dimension, 5 enemies, Carbonation boss (3 phases) | Boss defeat test |
| 5 | Recipe and mixing system, Flavour Journal | Every recipe produces its power |
| 6 | Fake credits, goose interruption, hidden Level 3 unlock | Progress persists through the transition |
| 7 | Café scene and coffee mini-game | All 6 syrups selectable and saved |
| 8 | Waterfront plus bubble-burp tutorial | Interaction checklist |
| 9 | Ogopogo boss (3 phases plus Super Burp) | **6 automated wins, one per café flavour** |
| 10 | True ending, stats screen, collectibles, achievements | Save/load round-trip |
| 11 | Visual and audio polish, touch controls, gamepad | Mobile-viewport screenshots |
| 12 | Performance pass, test report, ZIP, hosting instructions | 60 FPS check, full play-through |

A working milestone gets committed after every phase.

**Scope warning:** this is a very large build (three levels, two big bosses, two mini-games, and a
full art and audio set). It will take many long working sessions. I'll make sure gameplay works
first and be clear about anything still at placeholder quality.

---

## 6. Content and legal notes

- Ogopogo appears as an original cartoon lake creature based on the popular legend. Credits will
  include a short note that it doesn't depict the syilx/Okanagan being nx̌aʔx̌ʔitkʷ.
- The credits will include a disclaimer: "Fan-made / not an official Simps product" (unless you
  are, or have, an official Simps partnership), and "Flavour powers are fictional."
- Each recipe in-game is labelled as a game recipe, not an official Simps recipe.

---

## 7. Open questions (need your answer before building)

1. **Where should the game live?** In this repo under `simps-goose/`, or in a new repository?
2. **Can you allow `simpsmb.com`** in the environment's network settings, so I can check the brand
   assets directly?
3. **Brand permission:** do you have Simps' permission to use the real logo and trident? If not,
   I'll use original stand-in branding.
4. **Engine:** Phaser 4 (current) or Phaser 3?
5. **Art:** are code-generated pixel art and synthesized chiptune audio acceptable, or will you
   supply art and audio files?
