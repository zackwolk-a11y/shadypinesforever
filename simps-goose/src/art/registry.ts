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
import * as MO from './motifs';
import * as F2 from './fx2';
import * as LB from './lab';
import { INGREDIENTS } from '../data/recipes';
import { ENEMY_FRAMES } from './enemies';
import * as DM from './dimension';
import * as BS from './boss';
import * as CF from './cafe';
import * as WFA from './waterfront';
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
  key_JUMP: () => FX.keycap('JUMP'), key_HONK: () => FX.keycap('HONK'), key_SIP: () => FX.keycap('SIP'), key_POWER: () => FX.keycap('POWER'), key_USE: () => FX.keycap('USE'), key_ARROWS: () => FX.keycap('< >'),
  key_X: () => FX.keycap('X'), key_C: () => FX.keycap('C'), key_E: () => FX.keycap('E'), key_SPACE: () => FX.keycap('SPACE'),
  crate: () => PR.crate(), crateTall: () => PR.crate(34, 52), crateTower: () => PR.crate(34, 78),
  box0: () => PR.cardboard(1), box1: () => PR.cardboard(2), box2: () => PR.cardboard(3),
  gondola: () => PR.gondola(), checkout: () => PR.checkout(), register: PR.register,
  sampleCounter: () => PR.sampleCounter(), chalkboard: PR.chalkboard,
  pump_cola: () => PR.pumpBottle(R.cola), pump_cream: () => PR.pumpBottle(R.cream), pump_cherry: () => PR.pumpBottle(R.cherry),
  cup_cola: () => PR.sampleCup(C.cola1), cup_cream: () => PR.sampleCup(C.crm1), cup_cherry: () => PR.sampleCup(C.chr1), cup_empty: () => PR.sampleCup(C.gl1),
  fountain: PR.fountain, gauge: PR.gauge, needle: PR.needle, beacon: PR.beacon, valveWheel: PR.valveWheel, valvePost: PR.valvePost,
  signNoHonk: () => PR.sign(['PLEASE', 'DO NOT HONK', 'AT THE FOUNTAIN'], 100),
  signDelivery: () => PR.sign(['DELIVERY', 'DO NOT CLIMB'], 82, { bg: C.gold1, fg: C.blk1, border: C.blk1 }),
  mezz: () => PR.mezzanine(), beam: () => PR.beam(170), baskets: PR.baskets, plant: PR.plant, pendant: PR.pendant,
  doorInterior: PR.doorInterior,
  door0: () => PR.streetDoor(0), door1: () => PR.streetDoor(1), door2: () => PR.streetDoor(2), door3: () => PR.streetDoor(3),
  storeWall: BG.storeBackWall, floor: BG.floorTile,
  streetSky: BG.streetSky, streetMountains: BG.streetMountains, streetTrees: BG.streetTrees, streetFront: BG.streetFront,
  lamp: BG.lampPost, sandwich: BG.sandwichBoard, planter: BG.planterTree, bird0: () => BG.bird(0), bird1: () => BG.bird(1),
  bigBottle: () => FX.bottle(R.blue, 12, 30),
  trident13: () => MO.trident(13), trident22: () => MO.trident(22), trident44: () => MO.trident(44), tridentWhite13: () => MO.trident(13, C.wht),
  leaf9: () => MO.maple(9), leaf15: () => MO.maple(15), leafWhite9: () => MO.maple(9, C.wht), leafConfetti: () => MO.maple(9, 0xffffff, 1, false),
  goldenLeaf: MO.goldenLeaf, badge: () => MO.badge(20), badge28: () => MO.badge(28), bunting: MO.bunting,
  flag0: () => MO.canadaFlag(0), flag1: () => MO.canadaFlag(1), flag2: () => MO.canadaFlag(2), flag3: () => MO.canadaFlag(3),
  bigFlag0: () => MO.canadaFlag(0, 44, 22), bigFlag1: () => MO.canadaFlag(1, 44, 22), bigFlag2: () => MO.canadaFlag(2, 44, 22), bigFlag3: () => MO.canadaFlag(3, 44, 22),
  recipeCard: F2.recipeCard, bubbleStar: F2.bubbleStar, coffeeBean: F2.coffeeBean, goldenGoose: F2.goldenGoose, electricShot: F2.electricShot,
  foamBig: () => F2.foamCloudW(64), buoy: F2.buoy, checkpoint0: () => F2.checkpoint(0), checkpoint1: () => F2.checkpoint(1), checkpoint2: () => F2.checkpoint(2),
  icon_rocket: () => F2.powerIcon('rocket'), icon_cloud9: () => F2.powerIcon('cloud9'), icon_tropical: () => F2.powerIcon('tropical'), icon_shield: () => F2.powerIcon('shield'),
  icon_electric: () => F2.powerIcon('electric'), icon_float: () => F2.powerIcon('float'), icon_pinkfizz: () => F2.powerIcon('pinkfizz'), icon_burp: () => F2.powerIcon('burp'),
  labWall: LB.labBackWall, labFloor: LB.labFloor, labConsole: LB.console_, mixer: LB.mixerMachine, superMachine: LB.superMachine, glassBlock: LB.glassBlock,
  syrup_cola: () => LB.syrupSurface(R.cola), syrup_cherry: () => LB.syrupSurface(R.cherry), syrup_mango: () => LB.syrupSurface(R.mango), syrup_blue: () => LB.syrupSurface(R.blue),
  conveyor: LB.conveyor, ventSteam: () => LB.vent('steam'), ventJet: () => LB.vent('jet'), gate: LB.gate, target0: () => LB.target(false), target1: () => LB.target(true),
  lever0: () => LB.lever(false), lever1: () => LB.lever(true), arm0: () => LB.armFrame(0), arm1: () => LB.armFrame(1), arm2: () => LB.armFrame(2), arm3: () => LB.armFrame(3),
  fruit_cherry: () => LB.fruit('cherry'), fruit_lemon: () => LB.fruit('lemon'), fruit_mango: () => LB.fruit('mango'), fruit_coconut: () => LB.fruit('coconut'), fruit_strawberry: () => LB.fruit('strawberry'),
  catwalk48: () => LB.catwalk(48), catwalk80: () => LB.catwalk(80),
  dimSky: DM.dimSky, dimFar: DM.dimFar, dimMid: DM.dimMid, island64: () => DM.strawberryIsland(64), island96: () => DM.strawberryIsland(96), island140: () => DM.strawberryIsland(140),
  cherryIsland: DM.cherryIsland, citrusWheel: DM.citrusWheel, citrusPad: DM.citrusPad, foamPad: DM.foamPad, rainbow: DM.rainbowTile, geyserBase: DM.geyserBase, geyserCol: DM.geyserCol,
  syrupRiver: DM.syrupRiver, portalBottle: DM.portalBottle, dimTap: DM.dimTap,
  carbBody: BS.carbBody, eyes_normal: () => BS.bossEyes('normal'), eyes_angry: () => BS.bossEyes('angry'), eyes_hurt: () => BS.bossEyes('hurt'), eyes_panic: () => BS.bossEyes('panic'), eyes_dizzy: () => BS.bossEyes('dizzy'),
  tap_cola0: () => BS.flavorTap(C.cola1, false), tap_cola1: () => BS.flavorTap(C.cola1, true), tap_cream0: () => BS.flavorTap(C.crm1, false), tap_cream1: () => BS.flavorTap(C.crm1, true), tap_cherry0: () => BS.flavorTap(C.chr1, false), tap_cherry1: () => BS.flavorTap(C.chr1, true),
  fizzWave: BS.fizzWave, foamBlob: BS.foamBlob, foamFlood: BS.foamFlood,
  cafeWall: CF.cafeWall, cafeFloor: CF.cafeFloor, cafeCounter: () => CF.cafeCounter(300), espresso: CF.espressoMachine, pastryCase: CF.pastryCase, stool: CF.stool, cafeTable: CF.cafeTable,
  mug_a: () => CF.mug(C.cola1), mug_b: () => CF.mug(C.crm1), cafeDoor: CF.cafeDoor,
  wfSky: () => WFA.wfSky(false), wfSkySunset: () => WFA.wfSky(true), wfHills: () => WFA.wfHills(false), wfHillsSunset: () => WFA.wfHills(true), wfLake: () => WFA.wfLake(false), wfLakeSunset: () => WFA.wfLake(true),
  wfTrees: WFA.wfTrees, wfPath: WFA.path, bench: WFA.bench, picnic: WFA.picnic, flowers: WFA.flowers, dock160: () => WFA.dock(160), dock80: () => WFA.dock(80), sailboat: WFA.sailboat, flagPole: WFA.flagPole, bike: WFA.bike,
  ripple: WFA.ripple, wave: WFA.wave, splash: WFA.splash, ogNeck: WFA.ogNeck, ogHump: WFA.ogHump, ogTail: WFA.ogTail, panorama: WFA.panorama,
  tridentStand: MO.tridentStand, floorLeaf: () => MO.floorDecal('leaf'), floorTrident: () => MO.floorDecal('trident'), liftHead: MO.liftHead, piston: MO.pistonShaft,
};
SHELF_RAMPS.forEach((r, i) => { SINGLE['bottle' + i] = () => FX.bottle(r, 6, 16); });
(['normal', 'roar', 'hurt', 'dizzy', 'sad', 'happy', 'drink', 'burp', 'surprised'] as const).forEach((f) => { SINGLE['og_' + f] = () => WFA.ogHead(f); });
Object.entries(ENEMY_FRAMES).forEach(([k, f]) => { SINGLE[k] = f; });
Object.entries(CF.CAFE_SYRUP_RAMPS).forEach(([k, r]) => { SINGLE['csy_' + k] = () => F2.syrupBottleBig(r); });
INGREDIENTS.forEach((ing) => { SINGLE['ing_' + ing.id] = () => F2.syrupBottleBig(ing.ramp); });

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
  for (const [k, p] of [['flag', 'flag'], ['bigflag', 'bigFlag']]) if (!scene.anims.exists(k)) scene.anims.create({ key: k, frames: [0, 1, 2, 3].map((i) => ({ key: p + i })), frameRate: 6, repeat: -1 });
  const A = (key: string, frames: string[], fps: number, repeat = -1) => { if (!scene.anims.exists(key)) scene.anims.create({ key, frames: frames.map((k) => ({ key: k })), frameRate: fps, repeat }); };
  A('fs_idle', ['fs_idle0', 'fs_idle1'], 4); A('sl_crawl', ['sl_crawl0', 'sl_crawl1'], 3); A('bb_walk', ['bb_walk0', 'bb_walk1'], 6); A('fm_small', ['fm_small0', 'fm_small1'], 3); A('fm_big', ['fm_big0', 'fm_big1'], 5); A('ff_fly', ['ff_fly0', 'ff_fly1'], 12);
  if (!scene.anims.exists('arm')) scene.anims.create({ key: 'arm', frames: [0, 1, 2, 3].map((i) => ({ key: 'arm' + i })), frameRate: 3, repeat: -1 });
  if (!scene.anims.exists('checkpoint_on')) scene.anims.create({ key: 'checkpoint_on', frames: [{ key: 'checkpoint1' }, { key: 'checkpoint2' }], frameRate: 5, repeat: -1 });
  if (!scene.anims.exists('bird_fly')) scene.anims.create({ key: 'bird_fly', frames: [{ key: 'bird1' }, { key: 'bird0' }], frameRate: 10, repeat: -1 });
}
