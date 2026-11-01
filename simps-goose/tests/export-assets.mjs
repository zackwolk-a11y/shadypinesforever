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
