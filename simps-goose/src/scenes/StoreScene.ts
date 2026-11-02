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
import { complete, unlock, StageId } from '../systems/save';
import { achieve } from '../data/achievements';
import { shake, flash } from '../systems/camfx';
import { SFX } from '../audio/sfx';
import { MUSIC } from '../audio/music';

/** Trident pressure valve (story mode). Honk it, use it, or hit it with a shot. */
class PressureValve implements SwitchLike {
  on = false; by = ['honk', 'interact', 'shot', 'electric'];
  wheel: Phaser.GameObjects.Image;
  constructor(public s: StoreScene, public x: number, public y: number, public n: number) {
    s.add.rectangle(x, y, 6, 30, C.st2).setOrigin(0.5, 1).setDepth(30);
    s.add.rectangle(x - 14, y - 30, 28, 6, C.st3).setOrigin(0, 0.5).setDepth(30);
    this.wheel = s.add.image(x, y - 34, 'valveWheel').setDepth(31);
    s.tweens.add({ targets: this.wheel, angle: { from: -6, to: 6 }, yoyo: true, repeat: -1, duration: 300 });
  }
  rect(): Rect { return { x: this.x - 16, y: this.y - 50, w: 32, h: 50 }; }
  activate() {
    if (this.on || this.s.fountain.stage < 2) { if (this.s.fountain.stage < 2) emote(this.s, this.x, this.y - 54, 'NO PRESSURE YET', { life: 900 }); return; }
    this.on = true;
    const s = this.s;
    s.tweens.killTweensOf(this.wheel);
    s.tweens.add({ targets: this.wheel, rotation: Math.PI * 4, duration: 900, ease: 'Cubic.InOut' });
    SFX.valve(); SFX.hiss(1.2); shake(s, 400, 0.004);
    for (let i = 0; i < 3; i++) s.time.delayedCall(i * 150, () => s.fx.steam(this.x, this.y - 40, 2));
    s.bubbles.spawn(this.x + 40, this.y - 70, 30, 'drift', { vx: 30, vy: -18, maxStomps: 99, life: 12, tint: 0xf8f0ff });
    const done = s.valves.filter((v) => v.on).length;
    s.game.events.emit('hud:toast', `PRESSURE VALVE ${done}/${s.valves.length + 1}`, C.red0, done === s.valves.length ? 'MAIN VALVE ON THE MEZZANINE UNLOCKED!' : 'GIANT BUBBLE RELEASED!');
    s.fountain.pressure = Math.max(0.3, s.fountain.pressure - 0.2);
  }
}

export class StoreScene extends LevelScene {
  stage: StageId = 'store';
  bottles: ShelfBottle[] = []; boxWall!: BoxWall; lift!: TridentLift;
  sam!: Person;
  sampling!: Sampling; fountain!: Fountain;
  valves: PressureValve[] = [];
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
    this.levelName = this.demo ? 'BUBBLE TROUBLE (DEMO)' : 'LEVEL 1: BUBBLE TROUBLE';
    this.initLevel({ w: WORLD_W, h: WORLD_H, floor: FLOOR, bg: C.blk2, spawn: { x: 40, y: FLOOR } });
    this.bottles = []; this.valves = []; this.lampGlows = []; this.wallShelfHonks = 0; this.bumpedWall = 0;
    for (const sd of solids()) this.world.add(sd);
    this.buildEnvironment();
    this.buildPeople();
    this.buildBottles();
    this.buildPickups();
    if (!this.demo) this.buildStorage();
    this.finishInit({ music: 'store' });
    this.boxWall = new BoxWall(this, this.world, L.boxWall.x, L.boxWall.cols, L.boxWall.rows, L.boxWall.bw, L.boxWall.bh);
    const bw = this.boxWall;
    this.breakables.push({ get broken() { return bw.toppled; }, rect: () => bw.rect(), by: ['dash', 'shot'], smash: (dir: number) => bw.topple(dir, this.world, (x, y) => this.fx.dust(x, y, 6)) });
    this.add.image(L.boxWall.x + 24, FLOOR - 92, 'signDelivery').setOrigin(0.5, 1).setDepth(37);
    this.lift = new TridentLift(this, this.world, L.lift.x, L.lift.low, L.lift.high);
    this.sampling = new Sampling(this);
    this.fountain = new Fountain(this);
    if (!this.demo) {
      this.addPlatform(1972, 250, 36, 5, 'oneway', 'valveLedge');
      const g = this.add.graphics().setDepth(27); g.fillStyle(C.st3).fillRect(1972, 250, 36, 5).fillStyle(C.st1).fillRect(1972, 250, 36, 1);
      this.add.image(1990, 255, 'trident13').setOrigin(0.5, 0).setDepth(26);
      this.valves.push(new PressureValve(this, 1990, 250, 1), new PressureValve(this, 2245, FLOOR, 2));
      this.switches.push(...this.valves);
    }
    this.buildPrompts();
    // intro: goose waddles in through the door
    this.phase = 'intro';
    this.goose.body.vx = 70;
    this.time.delayedCall(650, () => { if (this.phase === 'intro') this.phase = 'play'; });
    const api = (window as unknown as { __SIMPS: Record<string, unknown> }).__SIMPS;
    api.store = this;
    api.restartStore = () => this.scene.restart();
  }
  valvesReady() { return this.valves.every((v) => v.on); }

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
    this.dave = add('dave', 214, { staff: true, depth: 31, facing: -1 });
    this.gerry = add('gerry', 1918, { staff: true, depth: 26, facing: -1 });
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
    for (const v of this.valves) this.addPrompt(this.key('honk'), () => this.fountain.stage >= 2 && Math.abs(g.x - v.x) < 60 && Math.abs(g.y - v.y) < 60, () => v.on, () => ({ x: v.x, y: v.y - 64 }));
    this.addPrompt(this.key('use'), () => this.fountain.stage >= 2 && this.fountain.nearValve() && !this.fountain.finaleStarted && this.valvesReady(), () => this.fountain.finaleStarted, () => ({ x: L.valve.x, y: L.mezz.y - 80 }));
  }

  onHonkLevel(x: number, y: number) {
    for (const b of this.bottles) if (Math.hypot(b.x - x, b.y - y) < 120) b.jiggle(1);
    if (Math.abs(x - (L.wallShelf.x + 30)) < 90 && y > L.wallShelf.y) {
      this.wallShelfHonks++;
      if (this.wallShelfHonks >= 2) { const b = this.bottles.find((bb) => bb.knockable && bb.state === 'rest' && bb.baseY === L.wallShelf.y); b?.knock(x > b.x ? 1 : -1, 0.4, true); this.wallShelfHonks = 0; }
    }
    if (!this.boxWall.toppled && Math.abs(x - L.boxWall.x - 24) < 60) this.boxWall.wobble();
    this.fountain.onHonk(x);
    if (this.fountain.stage >= 2 && this.fountain.nearValve()) this.time.delayedCall(200, () => this.tryFinale());
  }
  onInteract() {
    if (this.sampling.inZone()) { this.sampling.open(); return true; }
    if (this.fountain.stage >= 2 && this.fountain.nearValve()) { this.tryFinale(); return true; }
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
    if (!this.valvesReady()) { emote(this, L.valve.x, L.mezz.y - 60, `LOCKED: ${this.valves.filter((v) => !v.on).length} VALVE(S) LEFT`, { life: 1300 }); SFX.ui('back'); return; }
    this.fountain.finale();
  }
  sampled(id: string) { /* hook from Sampling */ void id; }

  stepLevel(dt: number) { this.lift.step(dt); for (const b of this.bottles) b.step(dt, this.world); }
  frameLevel(dt: number) {
    const g = this.goose, b = g.body;
    this.fridgeT -= dt;
    if (!this.greetedDave && this.phase === 'play' && Math.abs(g.x - this.dave.x) < 80) { this.greetedDave = true; this.dave.say("WELCOME TO SIMPS! I'M DAVE.", 2200); this.dave.setState('gesture', 2); SFX.hey(0.9); }
    if (this.gerryLine < this.fountain.stage && !this.demo) { this.gerryLine = this.fountain.stage; const st = this.fountain.stage; this.time.delayedCall(900, () => { this.gerry.lastLine = 0; this.gerry.say(st === 1 ? "GERRY HERE. PLEASE DON'T HONK AT THAT." : '...OKAY, KEEP GOING!', 2400); this.gerry.setState(st === 1 ? 'react' : 'cheer', 2); }); }
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
