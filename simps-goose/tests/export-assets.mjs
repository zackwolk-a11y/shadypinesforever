// Exports rendered sprite sheets (PNG) and audio (WAV) to ./assets. Requires the dev server.
import { createRequire } from 'module';
import fs from 'fs';
const { chromium } = createRequire(import.meta.url)('playwright');
const base = process.env.BASE ?? 'http://localhost:5173';
const b = await chromium.launch();
const p = await b.newPage();
p.on('pageerror', (e) => console.log('pageerror', e.message));
const sheets = {
  'sprites/goose_sheet.png': 'goose', 'sprites/people_sheet.png': 'people', 'sprites/motifs_trident_maple.png': 'motifs',
  'environment/store_back_wall.png': 'storeWall', 'environment/street_front.png': 'streetFront', 'environment/street_sky.png': 'streetSky',
  'environment/street_mountains_okanagan.png': 'streetMountains', 'environment/street_trees.png': 'streetTrees', 'environment/floor_tile.png': 'floor',
  'props/fizz_o_matic_fountain.png': 'fountain', 'props/trident_display_stand.png': 'tridentStand', 'props/gondola_shelf.png': 'gondola', 'props/checkout.png': 'checkout',
  'props/sample_counter.png': 'sampleCounter', 'props/chalkboard.png': 'chalkboard', 'props/crate.png': 'crate', 'props/mezzanine.png': 'mezz', 'props/valve_wheel.png': 'valveWheel',
  'props/cardboard_box.png': 'box0', 'props/trident_lift.png': 'liftHead', 'fx/bubble_96.png': 'bubble96', 'fx/bubble_32.png': 'bubble32', 'fx/foam_cloud.png': 'foam',
  'fx/cherry_shot.png': 'cherryShot', 'ui/icon_cola.png': 'icon_cola', 'ui/icon_cream_soda.png': 'icon_cream', 'ui/icon_black_cherry.png': 'icon_cherry',
  'collectibles/golden_maple_leaf.png': 'goldenLeaf', 'collectibles/certified_badge.png': 'badge28', 'collectibles/golden_bottle.png': 'goldenBottle',
  'environment/canada_flag_frame0.png': 'bigFlag0', 'environment/bunting.png': 'bunting',
  'sprites/enemies_soda_dimension.png': 'enemies', 'sprites/ogopogo_and_lake.png': 'ogopogo',
  'level2/lab_back_wall.png': 'labWall', 'level2/mix_o_matic.png': 'mixer', 'level2/super_soda_9000.png': 'superMachine', 'level2/console.png': 'labConsole', 'level2/glass_block.png': 'glassBlock', 'level2/trident_gate.png': 'gate', 'level2/zap_target.png': 'target0', 'level2/lever.png': 'lever1',
  'level2/dimension_sky.png': 'dimSky', 'level2/dimension_far.png': 'dimFar', 'level2/dimension_mid.png': 'dimMid', 'level2/strawberry_island.png': 'island140', 'level2/citrus_wheel.png': 'citrusWheel', 'level2/portal_bottle.png': 'portalBottle',
  'level2/carbonator_3000.png': 'carbBody', 'level2/carbonator_eyes_angry.png': 'eyes_angry',
  'level3/cafe_wall.png': 'cafeWall', 'level3/espresso_machine.png': 'espresso', 'level3/cafe_counter.png': 'cafeCounter', 'level3/pastry_case.png': 'pastryCase',
  'level3/waterfront_sky.png': 'wfSky', 'level3/waterfront_hills.png': 'wfHills', 'level3/waterfront_trees.png': 'wfTrees', 'level3/sunset_panorama.png': 'panorama', 'level3/ogopogo_happy.png': 'og_happy',
  'collectibles/recipe_card.png': 'recipeCard', 'collectibles/bubble_star.png': 'bubbleStar', 'collectibles/coffee_bean.png': 'coffeeBean', 'collectibles/golden_goose_token.png': 'goldenGoose', 'ui/checkpoint.png': 'checkpoint1',
};
for (const [out, key] of Object.entries(sheets)) {
  await p.goto(`${base}/debug.html?sheet=${key}&scale=1&bg=none`);
  await p.waitForFunction(() => window.__ready);
  const data = await p.evaluate(() => window.__raw.toDataURL('image/png'));
  fs.mkdirSync('assets/' + out.split('/').slice(0, -1).join('/'), { recursive: true });
  fs.writeFileSync('assets/' + out, Buffer.from(data.split(',')[1], 'base64'));
}
console.log('exported', Object.keys(sheets).length, 'images');
await p.goto(`${base}/debug-audio.html`);
await p.waitForFunction(() => window.__ready);
const audio = await p.evaluate(() => window.exportAudio());
for (const [k, v] of Object.entries(audio)) { fs.mkdirSync('assets/audio/' + k.split('/')[0], { recursive: true }); fs.writeFileSync('assets/audio/' + k, Buffer.from(v, 'base64')); }
console.log('exported', Object.keys(audio).length, 'audio files');
await b.close();
