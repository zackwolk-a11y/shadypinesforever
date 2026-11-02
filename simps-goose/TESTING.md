# Test Report — SIMPS: GOOSE ON THE LOOSE! v1.0

All results below were produced by the automated suites against the **production build** (`vite preview`) in headless Chromium (Playwright), and generated from their JSON output by `scripts/testing-report.py`.

| Suite | Result |
|---|---|
| Original vertical-slice checks (`tests/e2e.mjs`, demo mode) | **40/40** |
| Full game (`tests/fullgame.mjs`, Levels 1–3, bosses, endings, saves, menus, touch) | **84/84** |
| Every coffee defeats Ogopogo (`tests/ogopogo.mjs`) | **6/6** |
| Page errors | 0 |

## Method and honesty notes
- Gameplay actions use **real keyboard input** (key down/up), including mixer pumps, coffee extraction/pour holds, honks, stomps, dashes, burps and menus. Mobile uses **CDP multi-touch** on the on-screen buttons.
- `window.__SIMPS.teleport` moves the goose between sections so each feature is checked independently. In boss tests it puts the goose where a player would stand (e.g. next to a bubble, on a buoy). It does not skip any rule: damage, phases and win conditions all run normally.
- Not verified: real phones/tablets, Firefox/Safari, physical gamepads, audio by ear (audio files are checked for signal), and a single uninterrupted human playthrough timed end-to-end (the suite covers every stage separately).

## Ogopogo — every coffee
| Coffee (Simps café syrup) | Result | Fight time with good positioning |
|---|---|---|
| vanilla | defeated → true ending | 32 s |
| saltedcaramel | defeated → true ending | 29 s |
| hazelnut | defeated → true ending | 33 s |
| peppermint | defeated → true ending | 38 s |
| lavender | defeated → true ending | 34 s |
| marshmallow | defeated → true ending | 34 s |

## Performance
```
bubble trouble: {"fps":31,"bubbles":14,"objects":376,"renderer":"WebGL"}
```
Measured in headless Chromium, where WebGL is rendered **in software on the CPU**. The same build measured **57–60 fps** in Bubble Trouble before a container restart, and **34–46 fps** across all scenes on the replacement VM. The unchanged store scene dropped by the same proportion, so the drop is the environment, not the game. Real GPUs should hold 60 fps. Since the delta fix below, a slower device keeps real-time speed instead of running in slow motion.

## Full-game checks
| Check | Result | Detail |
|---|---|---|
| L1 owners welcome the goose (Dave + Gerry dialogue) | PASS |  |
| L1 both owners at the entrance | PASS |  |
| L1 skipping the welcome keeps the instructions (toast) and saves it | PASS |  |
| L1 rope blocks Bubble Trouble until the Stock-Up is done | PASS |  |
| L1 storage route golden bottle collectable | PASS |  |
| L1 two honks erupt the fountain (story) | PASS |  |
| L1 main valve locked until the workshop is done | PASS |  |
| L1 Dave's Bubble Workshop dialogue | PASS |  |
| L1 workshop: syrup valves in the colour order (from the moving bubbles) | PASS | [true,true,true] |
| L1 pressure switch → DOUBLE BUBBLE unlocked | PASS |  |
| L1 final trident valve starts the finale | PASS |  |
| L1 transitions into Level 2 (Lab) | PASS |  |
| Lab arrival cutscene → play | PASS |  |
| no missing textures (store/lab) | PASS |  |
| Mixer: Cola + Black Cherry = Cherry Rocket | PASS | {"recipe":"cherry_rocket","q":"good","power":"rocket","isSuper":false} |
| Mixer: green-zone pumps rated GOOD or PERFECT | PASS | observed good |
| Cherry Rocket power granted | PASS |  |
| Lab: rocket dash smashes the fragile glass wall | PASS |  |
| Lab: dash ends on impact (goose not flung into the syrup vat) | PASS | {"key":"Lab","phase":"play","x":661,"y":390,"power":"rocket","burp":null,"gtag":"floor"} |
| Mixer: Blue Raspberry + Lemon Lime = Electric Fizz | PASS | {"recipe":"electric_fizz","q":"good","power":"electric","isSuper":false} |
| Lab: Electric Fizz zaps the target and opens the gate | PASS |  |
| Lab: pressure lever starts the trident lift | PASS |  |
| Mixer: unknown combo still gives a power (Mystery Fizz) | PASS | {"recipe":null,"q":"good","power":"cream","isSuper":false} |
| Lab: Super Soda gated behind Gerry's experiment | PASS |  |
| Lab: Gerry's Experimental Flavor Lab dialogue | PASS |  |
| Lab: three samples matched to their tanks | PASS |  |
| Lab: timed honk → rainbow soda → SUPER BURP unlocked | PASS |  |
| Lab: SUPER BURP fires a charged shot (hold C) | PASS |  |
| Lab: SUPER BURP bursts into smaller bubbles | PASS |  |
| Super Soda (Cola + Cream Soda + Black Cherry + MAX) | PASS | {"recipe":null,"q":"over","power":"cola","isSuper":true} |
| Portal accident → Soda Dimension | PASS |  |
| Recipes saved to the journal | PASS | cherry_rocket,electric_fizz |
| Dimension: stomping a Syrup Slug defeats it | PASS |  |
| Dimension: all 5 enemy types present | PASS | BottleBot,FizzSprite,FoamMonster,FruitFlyer,SyrupSlug |
| Dimension: collapsing foam pad gives way | PASS |  |
| Dimension: checkpoint reached | PASS |  |
| Dimension frame rate playable (>=30 fps, headless software WebGL) | PASS | 30 fps |
| Dimension exit portal → Carbonation boss | PASS |  |
| Boss: one clear instruction on screen | PASS |  |
| Boss phase 1: honked bubbles fly back into the machine | PASS |  |
| Boss phase 2: same trick, faster | PASS |  |
| Boss phase 3: Carbonator defeated | PASS |  |
| Boss → fake ending | PASS |  |
| Fake ending: credits interrupted → Level 3 café | PASS |  |
| Level 3 revealed + unlocked (progress kept) | PASS |  |
| Café: barista dialogue → coffee mini-game | PASS |  |
| Café: first burp → Bubble Burp unlocked (Peppermint) | PASS |  |
| Café: burp fires a bubble | PASS |  |
| Café → waterfront | PASS |  |
| Coffee power persisted in the save | PASS | {"c":"peppermint","r":"peppermint"} |
| Waterfront: burp targets popped | PASS |  |
| Waterfront: burp lifts the beach ball | PASS |  |
| Waterfront: E makes a bubble platform | PASS |  |
| Waterfront: bubble bell opens the dock | PASS |  |
| Waterfront: sit on the dock → ripples → Ogopogo | PASS |  |
| Stock-Up: Dave + Gerry opening dialogue | PASS |  |
| Stock-Up: big boxes pushed into the floor bays | PASS |  |
| Stock-Up: STOCK-O-METER 100% (all 8 stocked) | PASS |  |
| Stock-Up: delivery 1 (flavour compartments + jammed-conveyor honk) | PASS |  |
| Stock-Up: delivery 2 (push the cart onto the trident lift) | PASS |  |
| Stock-Up: delivery 3 (bottle rush + last box launched) | PASS |  |
| Stock-Up: MAPLE LEAF POWER HONK unlocked | PASS |  |
| Stock-Up: achievements (work here, master stocker, special delivery) | PASS | first_honk,double_bubble,bubble_trouble,rainbow_soda,master_of_fizz,coffee_break,master_st |
| Stock-Up: perfect run unlocks the golden outfit | PASS |  |
| Power Honk: shockwave pushes the heavy crate + breaks the cracked wall | PASS |  |
| Stock-Up: exit returns to the store at the stockroom door | PASS |  |
| Store: rope gone once the Stock-Up is done | PASS |  |
| Ogopogo: owner abilities carried in (Power Honk / Double Bubble / Super Burp) | PASS |  |
| Ogopogo: Power Honk briefly stuns Ogopogo | PASS |  |
| Ogopogo: SUPER BURP hits hard (3 HP)  | PASS | 40 -> 33 |
| Ogopogo: DOUBLE BUBBLE burps two platform bubbles | PASS |  |
| Celebration: Dave + Gerry arrive and talk | PASS |  |
| Celebration: owners + crowd + Ogopogo soda cup on screen | PASS |  |
| True ending → final stats screen | PASS |  |
| Final screen offers replay / levels / achievement journal | PASS |  |
| Achievements saved (Friend of Ogopogo, Golden Goose) | PASS | first_honk,double_bubble,bubble_trouble,rainbow_soda,master_of_fizz,coffee_break,master_st |
| Golden Goose Token collected | PASS |  |
| Title shows CONTINUE after progress | PASS | CONTINUE/NEW GAME/LEVEL SELECT/JOURNAL + ACHIEVEMENTS/CUSTOMIZE GOOSE/SETTINGS/HOW TO PLAY |
| Level select lists Level 3 once revealed | PASS | LEVEL SELECT/~ L1  BUBBLE TROUBLE  */L1  THE GREAT SIMPS STOCK-UP  */L2  THE HONKIN' SODA  |
| Journal opens from the title | PASS |  |
| Pause works in Level 2 | PASS |  |
| Pause menu toggles Reduce Flashing (saved) | PASS |  |
| Resume works in Level 2 | PASS |  |
| Mobile touch: move + jump in the Soda Dimension | PASS | {"key":"Dimension","phase":"play","x":80,"y":400,"power":null,"burp":null,"gtag":"island"} |

## Original 40 vertical-slice checks
| Check | Result | Detail |
|---|---|---|
| title screen loads | PASS |  |
| START DEMO → intro cinematic | PASS |  |
| cinematic plays through to the store | PASS |  |
| no missing textures (title/intro/store) | PASS |  |
| cinematic is skippable | PASS |  |
| goose walks right | PASS | 42 → 122 |
| goose turns and walks left | PASS | 122 → 111 |
| jump leaves ground and lands | PASS | apex-ish y=284, landed y=330 |
| jump onto display crate | PASS | y=304 on crate1 |
| honk makes customers react | PASS | 2 reacting (was walk,browse,walk,browse,idle,browse,idle,walk,gesture,idle) |
| honk jiggles bottles on shelves | PASS | 28 wobbling |
| trident stand: pedestal | PASS | "tridentPedestal" |
| trident stand: crossbar ledge | PASS | "trident0" |
| sampling station opens picker | PASS |  |
| sip COLA → Fizzy Dash | PASS | cola |
| Fizzy Dash smashes the delivery box wall | PASS |  |
| sip CREAM SODA → Foam Float | PASS | cream |
| Foam Float lifts the goose on a foam cloud | PASS | y=283 on foam |
| foam cloud lets goose clear the box wall | PASS | x=1675 |
| sip BLACK CHERRY → Cherry Blast | PASS | cherry |
| Cherry Blast topples the box wall | PASS |  |
| only one power active at a time (HUD shows cherry) | PASS |  |
| power expires (burp) after its timer | PASS |  |
| first honk wakes the fountain (stage 1) | PASS |  |
| second honk → eruption (stage 2) | PASS |  |
| bubbles spawn continuously | PASS | 8 active |
| floating bubble supports the goose | PASS | {"x":2089,"y":217,"ground":true,"gtag":"bubble","mode":"play","phase":"play","power":null, |
| goose rides the bubble (still on it after 0.5s) | PASS |  |
| bubble pops after repeated landings | PASS |  |
| trident lift is moving | PASS | 323.9 → 311.8 |
| bubble → elevated mezzanine (real jump) | PASS | {"x":2198,"y":168,"ground":true,"gtag":"mezz","mode":"play","phase":"play","power":null,"d |
| pause and resume | PASS |  |
| valve triggers finale | PASS |  |
| goose rides the giant bubble upward | PASS | {"x":2321,"y":134,"ground":true,"gtag":"mezz","mode":"ride","phase":"cutscene","power":nul |
| freeze frame + demo end | PASS |  |
| no missing textures (gameplay) | PASS |  |
| REPLAY DEMO restarts at the cinematic | PASS |  |
| mobile: touch RIGHT moves goose | PASS | 42 → 115 |
| mobile: multi-touch RIGHT+JUMP jumps | PASS | {"x":155,"y":298,"ground":false,"gtag":null,"mode":"play","phase":"play","power":null,"dro |
| mobile: HONK button honks | PASS |  |

## Screenshots
`screenshots/slice/` (vertical slice), `screenshots/full/` (every level, both bosses, fake + true ending, menus, journal, mobile). Gameplay clips: `captures/*.webm`.

## Bugs found and fixed during full-game development
- Bubble manager survived scene restarts and pointed at destroyed images → recreated each level start.
- The store's sampling update was dropped in the refactor → restored (caught by the original 40 checks).
- Cherry shots bounced off breakable walls before registering → breakables are ignored by projectile physics.
- Café counter was a solid block, so the goose couldn't reach the stools → one-way counter top.
- Boss health bar overlapped the machine's name plate / burp label → moved.
- Ogopogo Heavy-Burp arcs could overshoot a high head → gentle vertical steer within 55 px of head height (all 6 coffees now verified).
- Perfect pump window (±41 ms) was stricter than input latency allows → ±0.06 of the gauge.
- A test `pkill` pattern killed its own shell → the preview server is now started separately.
- **Phaser delta smoothing made the game run in slow motion below 60 fps** (reported 16.7 ms per frame while frames took 33 ms). It's off now (`smoothStep: false`), so game time follows real time on slow phones too. The level runtime still clamps frames at 50 ms.
- **Dash vs. breakables was checked once per rendered frame**, so at about 30 fps a dash could start, hit the glass and end inside one frame without smashing it → now checked every 120 Hz physics step.
- **The rocket dash flung the goose through the glass into the syrup vat** → smashing now ends the dash with a skid (new check: "dash ends on impact").
- Enemy type checks used minified class names in the production build → enemies now carry an explicit `kind`.
- Harness note: the pump-timing test presses about 55 ms early to cover its own reaction latency (as a player would). Mixes observed in the final run: GOOD/OVERMIXED. PERFECT was observed in earlier runs.
