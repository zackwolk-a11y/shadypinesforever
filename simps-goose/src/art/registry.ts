/**
 * Generates every texture once at boot and caches it in the Phaser texture manager.
 * Sheets register named frames so animations can reference them.
 */
import Phaser from 'phaser';
import { C, R } from './palette';
import { Px } from './px';
import { buildGooseSheet, GOOSE_ANIMS, GF } from './goose';
import { buildPeopleSheet, PEOPLE, PERSON_ANIMS, PF_W, PF_H } from './people';
import * as FX from './fx';
import * as PR from './props';
import * as BG from './backgrounds';
import { buildFonts } from './font';
import { registerSheet } from './registry-sheets';

export const FLAVOR_RAMPS = { cola: R.cola, cream: R.cream, cherry: R.cherry };
export const SHELF_RAMPS = [R.cola, R.cream, R.cherry, R.blue, R.lime, R.mango, R.purple, R.rootbeer];

function add(scene: Phaser.Scene, key: string, px: Px) {
  if (scene.textures.exists(key)) scene.textures.remove(key);
  scene.textures.addCanvas(key, px.toCanvas());
}
function addSheet(scene: Phaser.Scene, key: string, sheet: Px, frames: { name: string; x: number; y: number }[], fw: number, fh: number) {
  if (scene.textures.exists(key)) scene.textures.remove(key);
  const tex = scene.textures.addCanvas(key, sheet.toCanvas())!;
  for (const f of frames) tex.add(f.name, 0, f.x, f.y, fw, fh);
}

/** Small registry of single-image generators (also used by the asset exporter). */
export const SINGLE: Record<string, () => Px> = {
  bubble16: () => FX.bubble(16), bubble24: () => FX.bubble(24), bubble32: () => FX.bubble(32), bubble40: () => FX.bubble(40),
  bubble64: () => FX.bubble(64), bubble96: () => FX.bubble(96), bubbleStrained: () => FX.bubble(32, { strained: true }),
  glow64: () => FX.glow(64), glow128: () => FX.glow(128, 6), shaft: () => FX.shaft(120, 300),
  dot2: () => FX.square(2), dot3: () => FX.dot(3), dot4: () => FX.dot(4), px1: () => FX.square(1),
  droplet: FX.droplet, dropletShade: FX.dropletShade, star: FX.star, sparkle: FX.sparkle, heart: FX.heart,
  puff8: () => FX.puff(8), puff12: () => FX.puff(12), honkArc: FX.honkArc,
  balloonS: () => FX.balloon(18, 14), balloonM: () => FX.balloon(30, 14), balloonL: () => FX.balloon(70, 14), balloonXL: () => FX.balloon(130, 24),
  foam: FX.foamCloud, cherryShot: FX.cherryBubble,
  icon_cola: () => FX.flavorIcon('cola'), icon_cream: () => FX.flavorIcon('cream'), icon_cherry: () => FX.flavorIcon('cherry'), icon_none: () => FX.flavorIcon('none'),
  goldenBottle: FX.goldenBottle, splat: FX.splat, shadow16: () => FX.shadowBlob(16), shadow32: () => FX.shadowBlob(32), shadow64: () => FX.shadowBlob(64),
  key_X: () => FX.keycap('X'), key_C: () => FX.keycap('C'), key_E: () => FX.keycap('E'), key_SPACE: () => FX.keycap('SPACE'),
  crate: () => PR.crate(), crateTall: () => PR.crate(34, 52), crateTower: () => PR.crate(34, 78),
  box0: () => PR.cardboard(1), box1: () => PR.cardboard(2), box2: () => PR.cardboard(3),
  gondola: () => PR.gondola(), checkout: () => PR.checkout(), register: PR.register,
  sampleCounter: () => PR.sampleCounter(), chalkboard: PR.chalkboard,
  pump_cola: () => PR.pumpBottle(R.cola), pump_cream: () => PR.pumpBottle(R.cream), pump_cherry: () => PR.pumpBottle(R.cherry),
  cup_cola: () => PR.sampleCup(C.cola1), cup_cream: () => PR.sampleCup(C.crm1), cup_cherry: () => PR.sampleCup(C.chr1), cup_empty: () => PR.sampleCup(C.gl1),
  fountain: PR.fountain, gauge: PR.gauge, needle: PR.needle, beacon: PR.beacon, valveWheel: PR.valveWheel, valvePost: PR.valvePost,
  signNoHonk: () => PR.sign(['PLEASE', 'DO NOT HONK', 'AT THE FOUNTAIN'], 82),
  signDelivery: () => PR.sign(['DELIVERY', 'DO NOT CLIMB'], 66, { bg: C.gold1, fg: C.blk1, border: C.blk1 }),
  mezz: () => PR.mezzanine(), beam: () => PR.beam(170), baskets: PR.baskets, plant: PR.plant, pendant: PR.pendant,
  doorInterior: PR.doorInterior,
  door0: () => PR.streetDoor(0), door1: () => PR.streetDoor(1), door2: () => PR.streetDoor(2), door3: () => PR.streetDoor(3),
  storeWall: BG.storeBackWall, floor: BG.floorTile,
  streetSky: BG.streetSky, streetMountains: BG.streetMountains, streetTrees: BG.streetTrees, streetFront: BG.streetFront,
  lamp: BG.lampPost, sandwich: BG.sandwichBoard, planter: BG.planterTree, bird0: () => BG.bird(0), bird1: () => BG.bird(1),
  bigBottle: () => FX.bottle(R.blue, 12, 30),
};
SHELF_RAMPS.forEach((r, i) => { SINGLE['bottle' + i] = () => FX.bottle(r, 6, 16); });

// expose to debug viewer
for (const k of Object.keys(SINGLE)) registerSheet(k, () => SINGLE[k]().toCanvas());

export function generateAll(scene: Phaser.Scene, onProgress?: (t: number) => void) {
  buildFonts(scene);
  const g = buildGooseSheet();
  addSheet(scene, 'goose', g.sheet, g.frames, GF, GF);
  for (const k of Object.keys(PEOPLE)) { const s = buildPeopleSheet(k); addSheet(scene, 'p_' + k, s.sheet, s.frames, PF_W, PF_H); }
  const keys = Object.keys(SINGLE);
  keys.forEach((k, i) => { add(scene, k, SINGLE[k]()); onProgress?.((i + 1) / keys.length); });
  // animations
  for (const [name, def] of Object.entries(GOOSE_ANIMS)) {
    if (scene.anims.exists('g_' + name)) continue;
    scene.anims.create({ key: 'g_' + name, frames: def.frames.map((_, i) => ({ key: 'goose', frame: `${name}_${i}` })), frameRate: def.fps, repeat: def.loop ? -1 : 0 });
  }
  for (const k of Object.keys(PEOPLE)) for (const [name, def] of Object.entries(PERSON_ANIMS)) {
    const key = `p_${k}_${name}`;
    if (scene.anims.exists(key)) continue;
    scene.anims.create({ key, frames: def.frames.map((_, i) => ({ key: 'p_' + k, frame: `${name}_${i}` })), frameRate: def.fps, repeat: def.loop ? -1 : 0 });
  }
  if (!scene.anims.exists('door_open')) scene.anims.create({ key: 'door_open', frames: [0, 1, 2, 3].map((i) => ({ key: 'door' + i })), frameRate: 10, repeat: 0 });
  if (!scene.anims.exists('bird_fly')) scene.anims.create({ key: 'bird_fly', frames: [{ key: 'bird1' }, { key: 'bird0' }], frameRate: 10, repeat: -1 });
}
