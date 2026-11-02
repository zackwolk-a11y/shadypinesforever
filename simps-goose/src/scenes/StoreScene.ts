/**
 * LEVEL 1 — BUBBLE TROUBLE (the Simps store).
 * Story mode: 3 pressure valves → giant bubble ride out through the skylight → Level 2.
 * Demo mode (the original vertical slice): single valve → freeze-frame "TO BE CONTINUED".
 */
import Phaser from 'phaser';
import { C } from '../art/palette';
import { settings, saveSettings } from '../systems/settings';
import { Person } from '../entities/Person';
import { ShelfBottle, BoxWall } from '../entities/Props';
import { TridentLift } from '../entities/Abilities';
import { emote } from '../entities/Emote';
import { Sampling } from '../gameplay/Sampling';
import { Fountain } from '../gameplay/Fountain';
import { WORLD_W, WORLD_H, FLOOR, CEIL, L, BG_PARALLAX, BG_W, bgX, solids } from '../gameplay/layout';
import { TRIDENT_STAND } from '../art/motifs';
import { LevelScene, Rect, SwitchLike } from '../levels/LevelScene';
import { GS } from '../systems/gamestate';
import { complete, unlock, StageId, save, update } from '../systems/save';
import { txt } from '../art/font';
import type { Platform } from '../systems/physics';
import { achieve } from '../data/achievements';
import { shake, flash } from '../systems/camfx';
import { SFX } from '../audio/sfx';
import { MUSIC } from '../audio/music';
import { Controls } from '../systems/input';
import type { Line } from '../ui/Dialogue';

/** Dave's Bubble Workshop syrup valve (story mode). Honk it (or bump it from a bubble) in the right colour order. */
const WS = { x: 2176, y: 236 };
const VALVE_COL = [C.red1, C.gold1, C.blu1];
const VALVE_NAME = ['RED', 'GOLD', 'BLUE'];
class SyrupValve implements SwitchLike {
  on = false; by = ['honk', 'interact', 'shot', 'electric'];
  wheel: Phaser.GameObjects.Image;
  constructor(public s: StoreScene, public x: number, public y: number, public n: number) {
    s.add.rectangle(x, y - 16, 4, 16, C.st2).setOrigin(0.5, 0).setDepth(30);
    this.wheel = s.add.image(x, y - 18, 'valveWheel').setDepth(31).setTint(VALVE_COL[n]);
    s.tweens.add({ targets: this.wheel, angle: { from: -6, to: 6 }, yoyo: true, repeat: -1, duration: 300 });
  }
  rect(): Rect { return { x: this.x - 18, y: this.y - 40, w: 36, h: 44 }; }
  activate() { this.s.valveHit(this); }
  reset() { this.on = false; this.wheel.setRotation(0); this.wheel.setTint(VALVE_COL[this.n]); }
}

const STOCK_X = 1524;

export class StoreScene extends LevelScene {
  stage: StageId = 'store';
  bottles: ShelfBottle[] = []; boxWall!: BoxWall; lift!: TridentLift;
  sam!: Person;
  sampling!: Sampling; fountain!: Fountain;
  valves: SyrupValve[] = []; seq = [1, 0, 2]; seqIdx = 0; workshopOn = false; workshopDone = false; finalSwitch: { x: number; on: boolean; img: Phaser.GameObjects.Image } | null = null;
  wsBubbles: { b: import('../entities/Bubbles').Bubble; x0: number; x1: number; ph: number; sp: number }[] = []; overfill: { img: Phaser.GameObjects.Image; x: number; y: number; t: number; dead: number }[] = [];
  gaugeImg: Phaser.GameObjects.Image | null = null;
  sampledAny = false; ropeLeft = true; checklistSeen = false; objT!: Phaser.GameObjects.BitmapText; objBg!: Phaser.GameObjects.Rectangle; checklist: Phaser.GameObjects.Container | null = null; pushBack = 0;
  rope: Platform | null = null; ropeImg: Phaser.GameObjects.Image | null = null; returning = false; welcomeDone = false;
  wallShelfHonks = 0;
  bumpedWall = 0;
  lampGlows: Phaser.GameObjects.Image[] = [];
  demo = false;
  fridgeT = 0;
  dave!: Person; gerry!: Person; greetedDave = false; gerryLine = 0;

  constructor() { super('Store'); }
  get dropCount() { return this.counts.drop; }
  get dropTotal() { return this.totals.drop; }
  get leafCount() { return this.counts.leaf; }
  get badgeGot() { return this.counts.badge > 0; }

  create() {
    this.demo = GS.mode === 'demo';
    this.returning = this.registry.get('fromStockroom') === true; this.registry.set('fromStockroom', false);
    this.welcomeDone = this.returning || this.demo; this.workshopOn = false; this.workshopDone = false; this.seqIdx = 0; this.wsBubbles = []; this.overfill = []; this.finalSwitch = null; this.rope = null; this.ropeImg = null; this.sampledAny = this.returning; this.checklist = null; this.pushBack = 0; this.ropeLeft = true;
    this.levelName = this.demo ? 'BUBBLE TROUBLE (DEMO)' : 'LEVEL 1: BUBBLE TROUBLE';
    this.initLevel({ w: WORLD_W, h: WORLD_H, floor: FLOOR, bg: C.blk2, spawn: { x: 40, y: FLOOR } });
    this.bottles = []; this.valves = []; this.lampGlows = []; this.wallShelfHonks = 0; this.bumpedWall = 0;
    for (const sd of solids()) this.world.add(sd);
    this.buildEnvironment();
    this.buildPeople();
    this.buildBottles();
    this.buildPickups();
    if (!this.demo) this.buildStorage();
    this.finishInit({ music: 'store', spawnX: this.returning ? 1524 : undefined, spawnY: this.returning ? FLOOR : undefined });
    this.boxWall = new BoxWall(this, this.world, L.boxWall.x, L.boxWall.cols, L.boxWall.rows, L.boxWall.bw, L.boxWall.bh);
    const bw = this.boxWall;
    this.breakables.push({ get broken() { return bw.toppled; }, rect: () => bw.rect(), by: ['dash', 'shot'], smash: (dir: number) => bw.topple(dir, this.world, (x, y) => this.fx.dust(x, y, 6)) });
    this.add.image(L.boxWall.x + 24, FLOOR - 92, 'signDelivery').setOrigin(0.5, 1).setDepth(37);
    this.lift = new TridentLift(this, this.world, L.lift.x, L.lift.low, L.lift.high);
    this.sampling = new Sampling(this);
    this.fountain = new Fountain(this);
    if (!this.demo) {
      this.buildWorkshop();
      this.buildStockDoor();
    }
    this.buildPrompts();
    if (!this.demo) {
      this.objBg = this.add.rectangle(240, 259, 300, 13, C.ink, 0.78).setScrollFactor(0).setDepth(140);
      this.objT = txt(this, 240, 256, '', { align: 'center', outline: false, color: C.gold0 }).setScrollFactor(0).setDepth(141);
      this.add.existing(this.objT);
    }
    if (this.returning) { this.restoreSnap(); this.phase = 'play'; }
    else if (!this.demo && GS.mode === 'story') { this.phase = 'intro'; this.goose.body.vx = 70; this.time.delayedCall(650, () => this.welcome()); }
    else {
      // intro: goose waddles in through the door
      this.phase = 'intro';
      this.goose.body.vx = 70;
      this.time.delayedCall(650, () => { if (this.phase === 'intro') this.phase = 'play'; });
    }
    const api = (window as unknown as { __SIMPS: Record<string, unknown> }).__SIMPS;
    api.store = this;
    api.restartStore = () => this.scene.restart();
  }
  valvesReady() { return this.demo || this.workshopDone; }

  /** Upper storage-shelf route above the coolers (golden bottle). */
  buildStorage() {
    const ledges: [number, number, number][] = [[740, 800, 196], [832, 900, 180], [930, 1066, 166]];
    const g = this.add.graphics().setDepth(27);
    for (const [x0, x1, y] of ledges) {
      this.addPlatform(x0, y, x1 - x0, 5, 'oneway', 'storage');
      g.fillStyle(C.ink).fillRect(x0 - 1, y - 1, x1 - x0 + 2, 7).fillStyle(C.wd1).fillRect(x0, y, x1 - x0, 5).fillStyle(C.wd0).fillRect(x0, y, x1 - x0, 1);
      this.add.image(x0 + 8, y + 5, 'trident13').setOrigin(0.5, 0).setDepth(26); this.add.image(x1 - 8, y + 5, 'trident13').setOrigin(0.5, 0).setDepth(26);
    }
    for (const [x, k] of [[950, 'box1'], [974, 'box2'], [962, 'box0']] as [number, string][]) this.add.image(x, k === 'box0' ? 166 - 22 : 166, k).setOrigin(0.5, 1).setDepth(27);
    this.add.image(962, 166 - 44, 'box2').setOrigin(0.5, 1).setDepth(27);
    this.addDropLine(752, 790, 182, 3); this.addDropLine(845, 890, 166, 3);
    this.addPickup('bottle', 1045, 148);
  }

  buildEnvironment() {
    const P = BG_PARALLAX;
    this.add.image(0, 0, 'storeWall').setOrigin(0).setScrollFactor(P, 1).setDepth(0);
    // waving Canadian flag + maple-leaf bunting (parallax with the wall)
    this.add.sprite(bgX(205), 58, 'bigFlag0').setScrollFactor(P, 1).setDepth(2).play('bigflag');
    this.add.rectangle(bgX(205) - 24, 46, 2, 46, C.st2).setOrigin(0.5, 0).setScrollFactor(P, 1).setDepth(1);
    this.add.tileSprite(0, 28, BG_W, 22, 'bunting').setOrigin(0).setScrollFactor(P, 1).setDepth(3);
    this.add.tileSprite(48, 124, BG_W, 22, 'bunting').setOrigin(0).setScrollFactor(P, 1).setDepth(3).setAlpha(0.9);
    // entrance door + light shafts
    this.add.image(bgX(L.door.x + 24), FLOOR - 8, 'doorInterior').setOrigin(0.5, 1).setScrollFactor(P, 1).setDepth(4);
    const shaftA = this.add.image(20, CEIL, 'shaft').setOrigin(0, 0).setBlendMode(Phaser.BlendModes.ADD).setAlpha(0.22).setDepth(60).setTint(0xfff0c8);
    this.tweens.add({ targets: shaftA, alpha: 0.32, duration: 2400, yoyo: true, repeat: -1, ease: 'Sine.InOut' });
    // fridge cool glow
    for (let k = 0; k < 2; k++) this.add.image(bgX(L.fridges.x) + 48 + k * 100, 250, 'glow128').setScale(1.1, 1.4).setTint(0x9fe8ff).setAlpha(0.22).setBlendMode(Phaser.BlendModes.ADD).setScrollFactor(P, 1).setDepth(5);
    // floor
    this.add.tileSprite(0, FLOOR, WORLD_W, WORLD_H - FLOOR, 'floor').setOrigin(0).setDepth(15);
    this.add.image(L.door.x + 26, FLOOR + 6, 'floorTrident').setTint(C.red1).setAlpha(0.55).setDepth(16);
    this.add.image(L.sample.x + 50, FLOOR + 7, 'floorLeaf').setTint(C.red1).setAlpha(0.5).setDepth(16);
    this.add.image(L.tridentStand.x + 38, FLOOR + 7, 'floorLeaf').setTint(C.wht).setAlpha(0.35).setDepth(16);
    // vents
    for (const vx of L.vents) { const gfx = this.add.graphics().setDepth(17); gfx.fillStyle(C.blk1).fillRect(vx - 12, FLOOR, 24, 4); gfx.fillStyle(C.st3); for (let i = 0; i < 5; i++) gfx.fillRect(vx - 10 + i * 5, FLOOR + 1, 2, 2); }
    // pendant lamps + warm light cones
    const cords = this.add.graphics().setDepth(58);
    for (let x = 120; x < WORLD_W - 60; x += 170) {
      if (Math.abs(x - L.skylight.x) < 60) continue;
      cords.fillStyle(C.ink).fillRect(x, CEIL, 1, 22);
      this.add.image(x, CEIL + 22, 'pendant').setOrigin(0.5, 0).setDepth(59);
      const gl = this.add.image(x, CEIL + 34, 'glow128').setOrigin(0.5, 0.15).setScale(1.3, 2.4).setTint(0xffd79a).setAlpha(0.2).setBlendMode(Phaser.BlendModes.ADD).setDepth(57);
      this.lampGlows.push(gl);
    }
    // skylight beam
    this.add.image(L.skylight.x, CEIL, 'shaft').setOrigin(0.3, 0).setScale(0.8, 1).setBlendMode(Phaser.BlendModes.ADD).setAlpha(0.25).setTint(0xcff4ff).setDepth(60);
    // furniture & props
    this.add.image(L.baskets.x, FLOOR, 'baskets').setOrigin(0.5, 1).setDepth(28);
    this.add.image(L.plantA.x, FLOOR, 'plant').setOrigin(0.5, 1).setDepth(27);
    this.add.image(L.crate1.x, FLOOR, 'crate').setOrigin(0, 1).setDepth(28);
    this.add.image(L.crate2.x, FLOOR, 'crateTall').setOrigin(0, 1).setDepth(28);
    this.add.image(L.gondola1.x, FLOOR, 'gondola').setOrigin(0, 1).setDepth(28);
    this.add.image(L.tridentStand.x, FLOOR, 'tridentStand').setOrigin(0, 1).setDepth(27);
    this.add.image(L.tridentStand.x + 38, FLOOR - TRIDENT_STAND.h + 30, 'glow128').setTint(C.red0).setAlpha(0.12).setBlendMode(Phaser.BlendModes.ADD).setDepth(26);
    // wall ledge (one-way) with trident brackets
    const ws = L.wallShelf; const g = this.add.graphics().setDepth(27);
    g.fillStyle(C.wd1).fillRect(ws.x, ws.y, ws.w, 5).fillStyle(C.wd0).fillRect(ws.x, ws.y, ws.w, 1).fillStyle(C.wd3).fillRect(ws.x, ws.y + 4, ws.w, 1).fillStyle(C.ink).fillRect(ws.x - 1, ws.y + 5, ws.w + 2, 1);
    this.add.image(ws.x + 10, ws.y + 5, 'trident13').setOrigin(0.5, 0).setDepth(26); this.add.image(ws.x + ws.w - 10, ws.y + 5, 'trident13').setOrigin(0.5, 0).setDepth(26);
    this.add.image(L.gondola2.x, FLOOR, 'gondola').setOrigin(0, 1).setDepth(28);
    this.add.image(L.checkout.x, FLOOR, 'checkout').setOrigin(0, 1).setDepth(29);
    this.add.image(L.checkout.x + 86, FLOOR - L.checkout.h + 1, 'register').setOrigin(0.5, 1).setDepth(29);
    this.add.image(L.checkout.x + 30, FLOOR - L.checkout.h + 1, 'badge').setOrigin(0.5, 1).setDepth(29).setScale(0.8);
    this.add.image(L.sample.x - 94, FLOOR, 'chalkboard').setOrigin(0, 1).setDepth(27);
    this.add.image(L.sample.x, FLOOR, 'sampleCounter').setOrigin(0, 1).setDepth(29);
    this.add.sprite(L.sample.x + 98, FLOOR - L.sample.h - 2, 'flag0').setOrigin(0, 1).setDepth(28).play('flag');
    this.add.rectangle(L.sample.x + 98, FLOOR - L.sample.h, 1, 22, C.st2).setOrigin(0, 1).setDepth(28);
    // no-honk sign on a post
    this.add.rectangle(L.noHonkSign.x, FLOOR, 3, 44, C.st3).setOrigin(0.5, 1).setDepth(27);
    this.add.image(L.noHonkSign.x, FLOOR - 40, 'signNoHonk').setOrigin(0.5, 1).setDepth(28);
    // mezzanine
    this.add.image(L.mezz.x + 8, FLOOR, 'beam').setOrigin(0, 1).setDepth(23);
    this.add.image(L.mezz.x + L.mezz.w - 18, FLOOR, 'beam').setOrigin(0, 1).setDepth(23);
    this.add.image(L.mezz.x, L.mezz.y - 20, 'mezz').setOrigin(0).setDepth(30);
    this.add.sprite(L.mezz.x + 40, L.mezz.y - 22, 'flag0').setOrigin(0, 1).setDepth(29).play('flag');
    this.add.image(L.plantB.x, FLOOR, 'plant').setOrigin(0.5, 1).setDepth(27);
    // foreground silhouettes (parallax 1.2) for depth
    // dust motes in the light
    this.add.particles(0, 0, 'px1', { x: { min: 0, max: WORLD_W }, y: { min: 60, max: FLOOR - 10 }, lifespan: 5000, speedX: { min: -4, max: 4 }, speedY: { min: -6, max: 2 }, alpha: { start: 0.6, end: 0 }, frequency: 120, tint: 0xfff1c8, blendMode: Phaser.BlendModes.ADD }).setDepth(61);
  }

  buildPeople() {
    const add = (key: string, x: number, o: ConstructorParameters<typeof Person>[4] = {}) => { const p = new Person(this, key, x, FLOOR, o); this.people.push(p); return p; };
    add('cust_a', 240, { range: [180, 290] });
    add('cust_c', 470, { range: [440, 520], depth: 32 });
    add('cust_b', 770, { range: [720, 840], depth: 32 });
    add('cust_e', 960, { range: [880, 1060] });
    add('emp_jo', L.checkout.x + 62, { staff: true, depth: 26, facing: -1 });
    add('cust_d', 1270, { range: [1255, 1290], facing: -1 });
    this.sam = add('emp_sam', L.sample.x + 30, { staff: true, depth: 26, facing: 1 });
    add('cust_c', 1695, { range: [1660, 1735], facing: 1 });
    const welcome = !this.demo && GS.mode === 'story' && !this.returning;
    this.dave = add('dave', welcome ? 196 : this.returning ? WS.x + 10 : this.demo ? 214 : STOCK_X + 30, { staff: true, depth: 31, facing: -1 });
    this.gerry = add('gerry', welcome ? 268 : 1918, { staff: true, depth: 31, facing: -1 });
    this.greetedDave = false; this.gerryLine = 0;
  }

  buildBottles() {
    const tex = (i: number) => 'bottle' + (i % 8);
    const add = (x: number, y: number, i: number, knock: boolean, depth = 31) => this.bottles.push(new ShelfBottle(this, x, y, tex(i), knock, depth));
    [306, 316, 326].forEach((x, i) => add(x, FLOOR - 26, i + 1, true));
    for (const gx of [L.gondola1.x, L.gondola2.x]) {
      [6, 14, 96, 104].forEach((dx, i) => add(gx + dx, FLOOR - 74, i * 3 + gx, true));
      for (const sy of [25, 49]) for (let k = 0; k < 12; k++) add(gx + 8 + k * 8.4, FLOOR - 74 + sy, k + sy + gx, false, 29);
    }
    [L.wallShelf.x + 6, L.wallShelf.x + 14, L.wallShelf.x + 54].forEach((x, i) => add(x, L.wallShelf.y, i + 4, true));
  }

  buildPickups() {
    this.addDropLine(120, 250, FLOOR - 14, 4);
    this.addDropLine(312, 324, FLOOR - 44, 2);
    this.addDropLine(366, 380, FLOOR - 72, 2);
    this.addDropLine(440, 512, FLOOR - 92, 4);
    const tx = L.tridentStand.x, ty = FLOOR - TRIDENT_STAND.h;
    this.addPickup('drop', tx + 38, ty + 46); this.addPickup('drop', tx + 15, ty + 8); this.addPickup('drop', tx + 61, ty + 8);
    this.addDropLine(735, 810, FLOOR - 92, 4);
    this.addDropLine(880, 1060, FLOOR - 14, 5);
    this.addDropLine(1125, 1200, FLOOR - 62, 3);
    this.addDropLine(1330, 1370, FLOOR - 14, 2);
    this.addDropLine(1640, 1700, FLOOR - 14, 3);
    this.addDropLine(1800, 1880, FLOOR - 14, 3);
    this.addDropLine(1960, 2000, FLOOR - 100, 2);
    this.addDropLine(2070, 2110, FLOOR - 150, 2);
    this.addDropLine(2200, 2300, L.mezz.y - 14, 4);
    this.addPickup('leaf', L.wallShelf.x + 34, L.wallShelf.y - 14);
    this.addPickup('leaf', L.checkout.x + 56, FLOOR - L.checkout.h - 48);
    this.addPickup('leaf', L.mezz.x + L.mezz.w - 20, L.mezz.y - 14);
    this.addPickup('badge', tx + 38, ty - 6);
  }

  buildPrompts() {
    const g = this.goose;
    this.addPrompt(this.key('move'), () => this.elapsed > 0.8 && this.elapsed < 6 && g.x < 120, () => g.x > 140, () => ({ x: g.x, y: g.y - 46 }));
    this.addPrompt(this.key('jump'), () => g.x > 230 && g.x < 300, () => this.usedJump, () => ({ x: L.crate1.x + 17, y: FLOOR - 52 }));
    this.addPrompt(this.key('honk'), () => this.elapsed > 4 && this.nearestPerson(g.x, 90) !== null && this.honkCount === 0, () => this.honkCount > 0, () => ({ x: g.x, y: g.y - 46 }));
    this.addPrompt(this.key('sip'), () => this.sampling.inZone() && this.phase === 'play', () => false, () => ({ x: L.sample.x + 72, y: FLOOR - L.sample.h - 24 }));
    this.addPrompt(this.key('power'), () => this.power !== null && !this.boxWall.toppled && g.x > L.boxWall.x - 120 && g.x < L.boxWall.x, () => this.boxWall.toppled || g.x > L.boxWall.x + 60, () => ({ x: g.x, y: g.y - 46 }));
    this.addPrompt(this.key('honk'), () => this.fountain.stage < 2 && Math.abs(g.x - this.fountain.cx) < 90 && this.phase === 'play', () => this.fountain.stage >= 2, () => ({ x: this.fountain.cx, y: FLOOR - L.fountain.h - 30 }));
    for (const v of this.valves) this.addPrompt(this.key('honk'), () => this.workshopOn && v.n === this.seq[this.seqIdx] && Math.abs(g.x - v.x) < 50 && Math.abs(g.y - v.y) < 70, () => v.on || this.workshopDone, () => ({ x: v.x, y: v.y - 46 }));
    if (!this.demo) {
      this.addPrompt(this.key('use'), () => this.atStockDoor() && this.phase === 'play', () => false, () => ({ x: STOCK_X, y: FLOOR - 96 }));
      this.addPrompt(this.key('honk'), () => !!this.finalSwitch && this.seqIdx >= 3 && Math.abs(g.x - this.finalSwitch.x) < 60, () => this.workshopDone, () => ({ x: this.finalSwitch!.x, y: FLOOR - 50 }));
    }
    this.addPrompt(this.key('use'), () => this.fountain.stage >= 2 && this.fountain.nearValve() && !this.fountain.finaleStarted && this.valvesReady(), () => this.fountain.finaleStarted, () => ({ x: L.valve.x, y: L.mezz.y - 80 }));
  }

  onHonkLevel(x: number, y: number) {
    if (this.finalSwitch && !this.workshopDone && this.seqIdx >= 3 && Math.abs(x - this.finalSwitch.x) < 70) this.workshopFinale();
    for (const b of this.bottles) if (Math.hypot(b.x - x, b.y - y) < 120) b.jiggle(1);
    if (Math.abs(x - (L.wallShelf.x + 30)) < 90 && y > L.wallShelf.y) {
      this.wallShelfHonks++;
      if (this.wallShelfHonks >= 2) { const b = this.bottles.find((bb) => bb.knockable && bb.state === 'rest' && bb.baseY === L.wallShelf.y); b?.knock(x > b.x ? 1 : -1, 0.4, true); this.wallShelfHonks = 0; }
    }
    if (!this.boxWall.toppled && Math.abs(x - L.boxWall.x - 24) < 60) {
      if (!this.demo && this.goose.x > L.boxWall.x + 48) this.boxWall.topple(-1, this.world, (bx, by) => this.fx.dust(bx, by, 6)); // honked over from behind
      else this.boxWall.wobble();
    }
    this.fountain.onHonk(x);
    if (this.fountain.nearValve()) this.time.delayedCall(200, () => this.tryFinale());
  }
  onInteract() {
    if (this.sampling.inZone()) { this.sampling.open(); return true; }
    if (!this.demo && this.atStockDoor()) { this.enterStockroom(); return true; }
    if (this.fountain.nearValve()) { this.tryFinale(); return true; }
    const g = this.goose;
    if (g.x > L.fridges.x - 10 && g.x < L.fridges.x + L.fridges.w + 10 && g.y > FLOOR - 4 && this.fridgeT <= 0) {
      this.fridgeT = 1.5;
      SFX.door(); emote(this, g.x, g.y - 44, 'BRRR!', { life: 900 });
      for (let i = 0; i < 6; i++) this.time.delayedCall(i * 60, () => this.fx.steam(g.x + (Math.random() - 0.5) * 20, g.y - 20, 1));
      g.playOnce('hurt'); this.time.delayedCall(500, () => { if (g.mode === 'play') g.playLoop('idle'); });
      const p = this.nearestPerson(g.x, 140, false); p?.say('CLOSE THE DOOR!', 1200);
      return true;
    }
    return false;
  }
  tryFinale() {
    if (this.fountain.finaleStarted) return;
    if (this.fountain.stage < 2 && this.demo) return;
    if (!this.valvesReady()) { emote(this, L.valve.x, L.mezz.y - 60, 'LOCKED! SEE THE LIST', { life: 1300 }); SFX.ui('back'); return; }
    this.fountain.finale();
  }
  sampled(id: string) { void id; this.sampledAny = true; }

  stepLevel(dt: number) { this.lift.step(dt); for (const b of this.bottles) b.step(dt, this.world); for (const w of this.wsBubbles) { if (!w.b.active) continue; w.ph += dt * w.sp; w.b.anchorX = w.x0 + (w.x1 - w.x0) * (Math.sin(w.ph) * 0.5 + 0.5); } }
  frameLevel(dt: number) {
    const g = this.goose, b = g.body;
    this.fridgeT -= dt;
    if (this.demo && !this.greetedDave && this.phase === 'play' && Math.abs(g.x - this.dave.x) < 80) { this.greetedDave = true; this.dave.say("WELCOME TO SIMPS! I'M DAVE.", 2200); this.dave.setState('gesture', 2); SFX.hey(0.9); }
    this.frameWorkshop(dt);
    if (this.gerryLine < this.fountain.stage && !this.demo && Math.abs(this.gerry.x - 1918) < 40) { this.gerryLine = this.fountain.stage; const st = this.fountain.stage; this.time.delayedCall(900, () => { this.gerry.lastLine = 0; this.gerry.say(st === 1 ? "GERRY HERE. PLEASE DON'T HONK AT THAT." : '...OKAY, KEEP GOING!', 2400); this.gerry.setState(st === 1 ? 'react' : 'cheer', 2); }); }
    this.sampling.update();
    for (const bt of this.bottles) {
      if (bt.state === 'fall' && bt.canHurt && bt.vy > 80 && g.mode === 'play' && Math.abs(bt.x - g.x) < 10 && bt.y > g.y - 34 && bt.y < g.y - 4) { g.hurt(bt.x); bt.vy = -120; bt.vx = -bt.vx; }
      if (bt.state !== 'rest' || !bt.knockable) continue;
      if (Math.abs(bt.x - g.x) < 9 && bt.y <= g.y + 2 && bt.y > g.y - 22 && (Math.abs(b.vx) > 30 || g.dashing)) bt.knock(Math.sign(b.vx) || g.facing, g.dashing ? 1.8 : 1);
    }
    for (const s of this.shots) if (s.active) for (const bt of this.bottles) if (bt.state === 'rest' && Math.abs(bt.x - s.x) < 6 && Math.abs(bt.y - 8 - s.y) < 10) bt.knock(Math.sign(s.vx), 1);
    if (!this.boxWall.toppled && b.hitWall === 1 && Math.abs(b.x + b.w - L.boxWall.x) < 2 && this.phase === 'play') {
      this.bumpedWall += dt;
      if (this.bumpedWall > 0.5) { this.bumpedWall = -3; g.playOnce('shrug'); emote(this, g.x, g.y - 44, '?', { life: 900 }); if (!this.power) this.sam.say('A SAMPLE MIGHT HELP!', 1800); }
    }
    this.fountain.update(dt);
    this.lift.render();
    for (const l of this.lampGlows) l.setAlpha(0.18 + Math.sin(this.elapsed * 2 + l.x) * 0.015);
  }

  // ---------------------------------------------------------------- SCENE 1: the owners welcome the goose
  welcome() {
    const g = this.goose;
    const seen = save().owners.welcome;
    this.phase = 'cutscene'; g.body.vx = 0;
    g.playOnce('honk'); SFX.honk(1.3); this.fx.honk(g.x + 12, g.y - 30, 1);
    // the goose nearly knocks over the syrup display; Gerry catches a bottle, Dave laughs
    for (const b of this.bottles) if (b.x < 340) b.jiggle(1.5);
    const fly = this.add.image(316, FLOOR - 34, 'bottle2').setDepth(40);
    this.tweens.add({ targets: fly, x: this.gerry.x - 4, y: FLOOR - 50, angle: -360, duration: 650, delay: 250, ease: 'Sine.Out', onComplete: () => { this.gerry.act('catch', 1.6); SFX.clink(); fly.destroy(); this.gerry.say('GOT IT!', 900); } });
    this.time.delayedCall(450, () => { this.dave.act('laugh', 1.4); SFX.laugh(0.9); });
    const lines1: Line[] = [
      ['dave', "WELL, WOULD YOU LOOK AT THAT! GERRY, WE'VE GOT OURSELVES A GOOSE!", 'laugh'],
      ['gerry', "OF ALL THE CUSTOMERS WE'VE HAD, THIS ONE'S DEFINITELY THE MOST FEATHERED.", 'hold'],
      ['dave', "WELCOME TO SIMPS MODERN BEVERAGE! WE'RE ALL ABOUT MAKING DELICIOUS DRINKS WITH OUR CANADIAN-MADE SYRUPS.", 'wave'],
      ['gerry', "WE'VE GOT CLASSICS, CREATIVE FLAVORS, AND ENOUGH COMBINATIONS TO KEEP A GOOSE BUSY ALL AFTERNOON.", 'gesture'],
    ];
    const lines2: Line[] = [
      ['dave', 'GO AHEAD! SAMPLE THE FLAVORS. FIND YOUR FAVORITES!', 'point'],
      ['gerry', 'JUST TRY NOT TO DESTROY THE STORE.', 'talk'],
      ['goose', 'HONK!!'],
      ['dave', 'I THINK THAT MEANS YES!', 'laugh'],
    ];
    const note: [string, string] = ['SAMPLE FLAVORS AT THE COUNTER', this.touch ? 'SIP AT THE SAMPLE COUNTER' : 'E AT THE SAMPLE COUNTER'];
    const end = () => {
      this.welcomeDone = true; update((sv) => { sv.owners.welcome = true; });
      this.dave.setState('laugh', 1.2); this.gerry.setState('laugh', 1.2); SFX.laugh(1);
      this.phase = 'play';
      // Dave opens the sampling area, Gerry fires up the fountain
      this.time.delayedCall(900, () => {
        this.dave.walkTo(STOCK_X + 30, 120, () => { this.dave.facing = -1; });
        this.gerry.walkTo(1918, 130, () => { this.gerry.facing = -1; this.fx.sparkle(this.fountain.cx, FLOOR - 120, 10, C.blu0); SFX.fizz(0.4, 1); });
      });
      this.game.events.emit('hud:toast', 'THE ADVENTURE BEGINS!', C.red0, note[1]);
    };
    this.time.delayedCall(1300, () => {
      if (seen) { this.talk([['dave', 'WELCOME BACK, GOOSE! THE SAMPLES ARE ON US.', 'wave'], ['gerry', 'THE STORE IS... MOSTLY INTACT. KEEP IT THAT WAY.', 'talk']], { dave: this.dave, gerry: this.gerry }, end, note); return; }
      this.talk(lines1, { dave: this.dave, gerry: this.gerry }, (sk) => { if (sk) return end(); this.brandPanels(() => this.talk(lines2, { dave: this.dave, gerry: this.gerry }, end, note)); }, note);
    });
  }
  /** Interactive brand intro: three flavor cards + how concentrate becomes a soda. */
  brandPanels(then: () => void) {
    this.phase = 'cutscene';
    const c = this.add.container(0, 0).setScrollFactor(0).setDepth(190);
    const g = this.add.graphics(); g.fillStyle(C.ink, 0.88).fillRoundedRect(14, 20, 452, 166, 8).lineStyle(2, C.red1).strokeRoundedRect(15, 21, 450, 164, 8);
    c.add(g);
    c.add(txt(this, 240, 28, 'MEET THE FLAVORS', { align: 'center', color: C.gold0 }));
    const cards: [string, string, string, number][] = [['COLA', 'CLASSIC SODA FLAVOR', 'UNLOCKS: FIZZY DASH', 0x8a4a22], ['CREAM SODA', 'SWEET AND CREAMY', 'UNLOCKS: FOAM CLOUD', 0xf2dca0], ['BLACK CHERRY', 'FRUITY AND BOLD', 'UNLOCKS: CHERRY BUBBLES', 0xa01838]];
    cards.forEach(([n, d, p, col], i) => {
      const x = 32 + i * 146;
      const cg = this.add.graphics(); cg.fillStyle(C.blk2).fillRoundedRect(x, 42, 136, 96, 5).lineStyle(1, col).strokeRoundedRect(x, 42, 136, 96, 5);
      c.add(cg);
      const bt = this.add.image(x + 22, 108, 'bottle' + [0, 1, 2][i]).setScale(2); c.add(bt);
      this.tweens.add({ targets: bt, y: 104, duration: 600 + i * 90, yoyo: true, repeat: -1, ease: 'Sine.InOut' });
      c.add(txt(this, x + 44, 52, n, { color: col === 0xf2dca0 ? C.gold0 : C.wht }));
      c.add(txt(this, x + 44, 66, d, { color: C.st1 }).setMaxWidth(90));
      c.add(txt(this, x + 44, 96, p, { color: C.gold1 }).setMaxWidth(90));
      for (let k = 0; k < 4; k++) { const bub = this.add.image(x + 22 + (k - 1.5) * 4, 88, 'bubble16').setScale(0.2); c.add(bub); this.tweens.add({ targets: bub, y: 50, alpha: 0, duration: 1100, delay: k * 260 + i * 120, repeat: -1 }); }
    });
    c.add(txt(this, 240, 146, 'HOW SYRUP BECOMES SODA: 1 PART CONCENTRATE + 5 PARTS SODA WATER = 1 DRINK', { align: 'center', color: C.wht }).setMaxWidth(420));
    c.add(txt(this, 240, 170, 'JUMP / TAP TO CONTINUE', { align: 'center', color: C.st2 }));
    c.setAlpha(0); this.tweens.add({ targets: c, alpha: 1, duration: 250 });
    SFX.sparkle(); SFX.fizz(0.4, 1);
    const zone = this.add.zone(0, 0, 480, 270).setOrigin(0).setScrollFactor(0).setDepth(191).setInteractive();
    let done = false, t = 0;
    const finish = () => { if (done) return; done = true; zone.destroy(); this.events.off('update', tick); this.tweens.add({ targets: c, alpha: 0, duration: 200, onComplete: () => c.destroy(true) }); then(); };
    const tick = (_t: number, d: number) => { t += d; if (t > 300 && (Controls.pressed('jump') || Controls.pressed('interact') || Controls.pressed('confirm') || Controls.pressed('back') || Controls.pressed('pause'))) finish(); };
    zone.on('pointerdown', () => { if (t > 300) finish(); });
    this.events.on('update', tick);
  }

  // ---------------------------------------------------------------- the stockroom door (THE GREAT SIMPS STOCK-UP)
  buildStockDoor() {
    this.add.image(STOCK_X, FLOOR, 'stockDoor').setOrigin(0.5, 1).setDepth(20);
    if (!save().stockDone) {
      this.ropeImg = this.add.image(1556, FLOOR, 'rope').setOrigin(0.5, 1).setDepth(33);
      this.rope = this.addPlatform(1546, FLOOR - 40, 18, 40, 'solid', 'rope');
    }
  }
  atStockDoor() { const d = this.goose.x - STOCK_X; return d > -26 && d < 8; }
  enterStockroom() {
    const got = this.pickups.filter((p) => p.got).map((p) => p.id);
    this.registry.set('storeSnap', { got, counts: { ...this.counts }, sampled: (this.sampling as unknown as { done?: string[] }).done ?? [] });
    SFX.door(); this.phase = 'cutscene';
    GS.persistRun();
    this.goTo('Stockroom');
  }
  restoreSnap() {
    const snap = this.registry.get('storeSnap') as { got: string[]; counts: Record<string, number> } | undefined;
    if (snap) for (const pk of this.pickups) if (snap.got.includes(pk.id)) { pk.got = true; pk.img.destroy(); pk.shade?.destroy(); this.counts[pk.kind]++; }
    this.game.events.emit('hud:drops', this.counts.drop + this.counts.bean, this.totals.drop + this.totals.bean);
    this.game.events.emit('hud:leaf', this.counts.leaf, this.totals.leaf);
    if (this.counts.badge) this.game.events.emit('hud:badge', true);
    this.time.delayedCall(500, () => this.game.events.emit('hud:toast', 'POWER HONK READY!', C.gold0, this.touch ? 'HOLD HONK TO CHARGE' : 'HOLD X TO CHARGE'));
  }

  // ---------------------------------------------------------------- objectives + valve checklist
  steps() {
    return [
      { label: 'HELP DAVE + GERRY IN THE STOCKROOM', done: save().stockDone, hint: 'STOCK DOOR, JUST AFTER THE SAMPLE COUNTER' },
      { label: 'ERUPT THE FOUNTAIN', done: this.fountain.stage >= 2, hint: 'HONK AT THE BIG FOUNTAIN TWICE' },
      { label: "FIX DAVE'S BUBBLE WORKSHOP", done: this.workshopDone, hint: 'ON THE FLOOR UNDER THIS MEZZANINE' },
    ];
  }
  objective(): string {
    const use = this.touch ? 'SIP' : 'E';
    if (!this.sampledAny && !save().stockDone) return `NEXT: SIP A FREE SAMPLE AT THE COUNTER (${use})`;
    if (!save().stockDone) return `NEXT: GO THROUGH THE STOCK DOOR (${use}) AFTER THE SAMPLES`;
    if (!this.boxWall.toppled && this.goose.x < L.boxWall.x) return this.power === 'cola' ? `NEXT: DASH INTO THE BOX WALL (${this.touch ? 'POWER' : 'C'})` : 'NEXT: GET A COLA SAMPLE, THEN DASH THROUGH THE BOXES';
    if (this.fountain.stage < 2) return `NEXT: HONK AT THE FOUNTAIN TWICE (${this.touch ? 'HONK' : 'X'})`;
    if (!this.workshopDone) {
      if (!this.workshopOn) return "NEXT: DAVE'S BUBBLE WORKSHOP, UNDER THE MEZZANINE";
      if (this.seqIdx < 3) return `WORKSHOP: FROM A BUBBLE, HONK THE ${VALVE_NAME[this.seq[this.seqIdx]]} VALVE (${this.seqIdx + 1}/3)`;
      return 'WORKSHOP: HONK THE PRESSURE SWITCH (FAR RIGHT, ON THE FLOOR)';
    }
    if (this.fountain.finaleStarted) return '';
    if (this.fountain.nearValve()) return `PULL THE VALVE: PRESS ${use} (OR HONK)`;
    return `NEXT: LIFT + BUBBLES UP TO THE MEZZANINE, THEN PULL THE VALVE (${use})`;
  }
  hintText() { if (this.demo) return null; const o = this.objective(); return o ? o.replace(/^NEXT: /, '') : null; }
  updateObjective() {
    if (!this.objT) return;
    const o = this.phase === 'play' ? this.objective() : '';
    if (this.objT.text !== o) { this.objT.setText(o); this.objBg.setSize(Math.max(40, this.objT.width + 14), 13); }
    this.objT.setVisible(!!o); this.objBg.setVisible(!!o);
    // standing up by the main valve while something is still missing → clear checklist
    const g = this.goose;
    const atValve = this.phase === 'play' && !this.valvesReady() && g.x > L.mezz.x && Math.abs(g.y - L.mezz.y) < 14;
    if (atValve && !this.checklistSeen) { this.checklistSeen = true; this.showChecklist(); }
    if (!atValve) { this.checklistSeen = false; if (this.checklist) { this.checklist.destroy(true); this.checklist = null; } }
  }
  /** Small banner at the top (out of the way of the action), shown for 3 seconds. */
  showChecklist() {
    const st = this.steps().filter((x) => !x.done);
    const c = this.add.container(0, 0).setScrollFactor(0).setDepth(150);
    const h = 16 + st.length * 10;
    c.add(this.add.graphics().fillStyle(C.ink, 0.85).fillRoundedRect(140, 38, 200, h, 4).lineStyle(1, C.red1).strokeRoundedRect(140.5, 38.5, 199, h - 1, 4));
    c.add(txt(this, 240, 41, 'VALVE LOCKED. STILL TO DO:', { align: 'center', outline: false, color: C.gold0 }));
    st.forEach((x, i) => c.add(txt(this, 240, 51 + i * 10, '~ ' + x.label, { align: 'center', outline: false, color: C.wht })));
    this.checklist = c;
    this.time.delayedCall(3000, () => { if (this.checklist === c) { this.tweens.add({ targets: c, alpha: 0, duration: 300, onComplete: () => c.destroy(true) }); this.checklist = null; } });
  }


  // ---------------------------------------------------------------- SCENE 2: Dave's Bubble Workshop (under the mezzanine)
  buildWorkshop() {
    const g = this.add.graphics().setDepth(24);
    // bubbling syrup tanks behind the valves
    for (let i = 0; i < 3; i++) {
      const x = WS.x + 22 + i * 64;
      g.fillStyle(C.st3).fillRect(x - 14, 178, 28, 34).fillStyle(VALVE_COL[i], 0.85).fillRect(x - 11, 184, 22, 26).fillStyle(0xffffff, 0.5).fillRect(x - 9, 186, 2, 22).fillStyle(C.st2).fillRect(x - 14, 178, 28, 3);
      this.valves.push(new SyrupValve(this, x, WS.y, i));
    }
    this.switches.push(...this.valves);
    this.add.image(WS.x + 86, 222, 'trident13').setDepth(25).setScale(1.4).setTint(C.red1);
    this.gaugeImg = this.add.image(WS.x - 6, 196, 'psiGauge').setDepth(26);
    // the colour-order sign
    const sg = this.add.graphics().setDepth(26);
    sg.fillStyle(C.ink).fillRect(WS.x + 160, 180, 46, 30).fillStyle(C.wht).fillRect(WS.x + 161, 181, 44, 28);
    this.seq.forEach((n, i) => sg.fillStyle(VALVE_COL[n]).fillCircle(WS.x + 170 + i * 13, 201, 5));
    this.add.existing(txt(this, WS.x + 183, 183, 'ORDER', { align: 'center', outline: false, color: C.ink })).setDepth(27);
    // final pressure switch
    const img = this.add.image(WS.x + 214, FLOOR, 'wswitch0').setOrigin(0.5, 1).setDepth(30);
    this.finalSwitch = { x: WS.x + 214, on: false, img };
  }
  startWorkshop() {
    if (this.workshopOn || this.workshopDone) return;
    this.workshopOn = true;
    this.dave.sprite.setPosition(WS.x + 10, FLOOR); this.dave.facing = 1;
    this.talk([
      ['dave', "HEY, GOOSE! YOU'RE JUST IN TIME. I'VE BEEN WORKING ON SOMETHING SPECIAL!", 'wave'],
      ['goose', 'HONK!'],
      ['dave', 'YOU KNOW WHAT MAKES A GREAT SODA? GETTING THE MIX JUST RIGHT!', 'pour'],
      ['dave', 'HOP ON THE BUBBLES, HONK THE SYRUP VALVES IN THE ORDER ON MY SIGN, THEN HIT THE PRESSURE SWITCH. AVOID THE RED ONES, THEY ARE OVERFILLED!', 'point'],
    ], { dave: this.dave }, () => this.spawnWorkshopBubbles(), ['DAVE: STABILIZE THE VALVES', 'HONK VALVES IN ORDER: GOLD, RED, BLUE']);
  }
  spawnWorkshopBubbles() {
    const defs: [number, number, number, number][] = [[WS.x + 4, WS.x + 70, 306, 0.9], [WS.x + 60, WS.x + 140, 300, 1.2], [WS.x + 120, WS.x + 200, 306, 1]];
    for (const [x0, x1, y, sp] of defs) {
      if (!this.bubbles.pool.some((q) => !q.active)) { const old = this.bubbles.pool.find((q) => q.active && !this.wsBubbles.some((w) => w.b === q) && !this.fountain.hoverRefs.includes(q)); if (old) this.bubbles.pop(old); }
      const b = this.bubbles.spawn(x0, y, 15, 'hover', { maxStomps: 9999, life: 9999, tint: 0xe8f6ff });
      if (b) this.wsBubbles.push({ b, x0, x1, ph: Math.random() * 6, sp });
    }
    for (const [x, y] of [[WS.x + 54, 252], [WS.x + 118, 250]] as [number, number][]) this.overfill.push({ img: this.add.image(x, y, 'bubble24').setTint(0xff5a5a).setDepth(46), x, y, t: Math.random() * 6, dead: 0 });
  }
  valveHit(v: SyrupValve) {
    if (this.demo || v.on) return;
    const gx = this.goose.x;
    if (this.valves.some((o) => o !== v && Math.abs(o.x - gx) < Math.abs(v.x - gx))) return; // one honk = the nearest valve
    if (!this.workshopOn) { emote(this, v.x, v.y - 50, 'TALK TO DAVE', { life: 900 }); return; }
    if (v.n !== this.seq[this.seqIdx]) {
      SFX.ui('back'); SFX.hiss(0.8); this.dave.lastLine = 0; this.dave.say(`NOPE! ${VALVE_NAME[this.seq[this.seqIdx]]} FIRST!`, 1600); this.dave.act('shock', 0.8);
      for (const vv of this.valves) vv.reset(); this.seqIdx = 0; return;
    }
    v.on = true; this.seqIdx++;
    this.tweens.killTweensOf(v.wheel); this.tweens.add({ targets: v.wheel, rotation: Math.PI * 4, duration: 900, ease: 'Cubic.InOut' });
    SFX.valve(); SFX.hiss(1); this.fx.steam(v.x, v.y - 30, 3); this.fx.drops(v.x, v.y - 10, VALVE_COL[v.n], 8);
    this.game.events.emit('hud:toast', `SYRUP VALVE ${this.seqIdx}/3`, VALVE_COL[v.n], this.seqIdx === 3 ? 'NOW HONK THE PRESSURE SWITCH!' : `NEXT: ${VALVE_NAME[this.seq[this.seqIdx]]}`);
    if (this.seqIdx === 3) { this.dave.lastLine = 0; this.dave.say('THE PRESSURE SWITCH! HONK IT!', 1800); this.dave.act('point', 1.2); }
  }
  workshopFinale() {
    if (this.workshopDone) return;
    this.workshopDone = true;
    const sw = this.finalSwitch!; sw.on = true; sw.img.setTexture('wswitch1');
    SFX.valve(); SFX.rumble(1); shake(this, 600, 0.008);
    for (const w of this.wsBubbles) this.bubbles.pop(w.b); this.wsBubbles = [];
    for (const o of this.overfill) o.img.destroy(); this.overfill = [];
    this.gaugeImg?.setTint(0x80ff80);
    // the elaborate fountain eruption
    for (let i = 0; i < 18; i++) this.time.delayedCall(i * 70, () => { const x = WS.x + 20 + Math.random() * 180; this.bubbles.spawn(x, FLOOR - 10, 6 + Math.random() * 10, 'rise', { vy: -90 - Math.random() * 60, tint: [0xffd0d0, 0xfff0b0, 0xc0e0ff][i % 3], life: 3 }); this.fx.drops(x, FLOOR - 40, VALVE_COL[i % 3], 4); });
    this.fx.confetti(WS.x + 110, 220, 30); SFX.fizz(0.8, 1.2); SFX.cheer();
    this.time.delayedCall(1300, () => {
      update((s) => { s.doubleBubble = true; s.owners.workshop = true; });
      achieve('double_bubble');
      this.game.events.emit('hud:abilities', { ph: save().powerHonk, db: true, sb: save().superBurp });
      SFX.powerup();
      this.talk([
        ['dave', "NOW THAT'S WHAT I CALL A PROPER POUR!", 'cheer'],
        ['dave', 'HERE, A LITTLE TRICK: YOU CAN NOW BLOW TWO BUBBLES IN QUICK SUCCESSION. DOUBLE BUBBLE!', 'pour'],
        ['goose', 'HONK!'],
        ['dave', 'GO SHOW GERRY WHAT YOU CAN DO!', 'wave'],
      ], { dave: this.dave }, () => {
        this.dave.act('wave', 2);
        this.game.events.emit('hud:toast', 'DOUBLE BUBBLE!', 0xfff0b0, this.touch ? 'USE (WITH NO TARGET): BUBBLE PLATFORM, TWICE' : 'E: BUBBLE PLATFORM (TWO AT ONCE)');
        this.game.events.emit('hud:toast', 'MAIN VALVE UNLOCKED!', C.red0, 'UP ON THE MEZZANINE');
      });
    });
  }
  frameWorkshop(dt: number) {
    if (this.demo) return;
    const g = this.goose;
    if (this.rope && save().stockDone) { this.rope.active = false; this.rope.x = -999; this.ropeImg?.destroy(); this.rope = null; }
    // the rope only stops you going forward: if you somehow got past it you can always walk back
    if (this.rope) { if (g.x < 1530) this.ropeLeft = true; else if (g.x > 1572) this.ropeLeft = false; this.rope.active = this.ropeLeft; }
    // the box wall can always be shoved over from the far side, so running out of power never strands you
    const bw = this.boxWall, br = bw.rect();
    if (!bw.toppled && this.phase === 'play' && g.x > br.x + br.w && g.body.hitWall === -1 && Math.abs(g.body.x - (br.x + br.w)) < 2) {
      this.pushBack += dt;
      if (this.pushBack > 0.5) { this.pushBack = 0; bw.topple(-1, this.world, (x, y) => this.fx.dust(x, y, 6)); emote(this, g.x, g.y - 44, 'SHOVE!', { life: 900 }); SFX.crash(); }
    } else if (g.body.hitWall !== -1) this.pushBack = 0;
    this.updateObjective();
    if (this.rope && this.phase === 'play' && g.x > 1500 && g.x < 1546 && this.goose.body.hitWall === 1) { this.dave.lastLine = this.dave.lastLine || 0; if (this.time.now - this.dave.lastLine > 2500) { this.dave.say('STOCKROOM FIRST! LEND US A WING?', 1800); this.dave.act('point', 1); } }
    if (!this.workshopOn && !this.workshopDone && this.phase === 'play' && g.x > WS.x - 40 && g.y > FLOOR - 40) {
      if (this.fountain.stage >= 2) this.startWorkshop();
      else if (this.time.now - this.dave.lastLine > 2500) this.dave.say('GET THAT FOUNTAIN GOING FIRST!', 1600);
    }
    if (this.gaugeImg && !this.workshopDone) this.gaugeImg.setTint(Math.floor(this.elapsed * 4) % 2 ? 0xff8080 : 0xffffff);
    for (const o of this.overfill) {
      o.t += dt;
      if (o.dead > 0) { o.dead -= dt; if (o.dead <= 0) o.img.setVisible(true).setScale(0.2); continue; }
      o.img.setPosition(o.x + Math.sin(o.t * 0.8) * 14, o.y + Math.sin(o.t * 1.7) * 8).setScale(Math.min(1, o.img.scale + dt) * (1 + Math.sin(o.t * 12) * 0.06));
      if (Math.hypot(o.img.x - g.x, o.img.y - (g.y - 12)) < 18 && g.mode === 'play') { o.dead = 3; o.img.setVisible(false); SFX.bigPop(); this.fx.drops(o.img.x, o.img.y, C.red0, 12); this.damage(o.img.x); }
    }
  }

  /** Called by Fountain once the giant-bubble ride is under way. */
  wideShot() {
    if (!this.demo) return this.exitThroughSkylight();
    const cam = this.cameras.main;
    cam.stopFollow();
    cam.pan(2150, 172, 900, 'Sine.easeInOut');
    cam.zoomTo(0.75, 900, 'Sine.easeInOut');
    for (let i = 0; i < 6; i++) this.bubbles.spawn(1900 + Math.random() * 450, 200 + Math.random() * 120, 10 + Math.random() * 10, 'rise', { vy: -20 - Math.random() * 20, tint: [0xffffff, 0xffe0ea, 0xfff6dc][i % 3] });
    this.time.delayedCall(1150, () => this.freeze());
  }
  exitThroughSkylight() {
    complete('store'); unlock('lab'); achieve('bubble_trouble');
    GS.addScore(2000);
    flash(this, 300);
    this.levelClear('Lab', { title: 'LEVEL 1 CLEAR!', delay: 3800 });
  }
  freeze() {
    this.phase = 'frozen';
    this.tweens.pauseAll();
    this.anims.pauseAll();
    this.children.list.forEach((o) => { if (o instanceof Phaser.GameObjects.Particles.ParticleEmitter) o.pause(); });
    flash(this, 120, 255, 255, 255);
    const pfx = (this.cameras.main as unknown as { postFX?: { addColorMatrix: () => { sepia: () => void } } }).postFX;
    try { pfx?.addColorMatrix().sepia(); } catch { /* canvas renderer */ }
    MUSIC.stinger();
    const st = settings();
    saveSettings({ bestDrops: Math.max(st.bestDrops, this.dropCount), plays: st.plays + 1 });
    this.game.events.emit('demo:end', { drops: this.dropCount, total: this.dropTotal, leaves: this.leafCount, badge: this.badgeGot, time: this.elapsed, honks: this.honkCount });
  }
}
