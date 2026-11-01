/**
 * LEVEL 1 (vertical slice) — inside the Simps store.
 * Orchestrates: environment build, fixed-step physics, flavour powers, interactions,
 * Bubble Trouble and the freeze-frame ending.
 */
import Phaser from 'phaser';
import { C } from '../art/palette';
import { PhysicsWorld, overlap } from '../systems/physics';
import { Controls } from '../systems/input';
import { settings, saveSettings } from '../systems/settings';
import { Goose } from '../entities/Goose';
import { Person } from '../entities/Person';
import { BubbleManager, Bubble } from '../entities/Bubbles';
import { ShelfBottle, BoxWall } from '../entities/Props';
import { Foam, CherryShot, TridentLift } from '../entities/Abilities';
import { emote } from '../entities/Emote';
import { FxSystem } from '../gameplay/FxSystem';
import { Sampling } from '../gameplay/Sampling';
import { Fountain } from '../gameplay/Fountain';
import { FLAVORS, FlavorId, POWER_DURATION } from '../gameplay/flavors';
import { WORLD_W, WORLD_H, FLOOR, CEIL, L, BG_PARALLAX, BG_W, bgX, solids } from '../gameplay/layout';
import { TRIDENT_STAND } from '../art/motifs';
import { SFX } from '../audio/sfx';
import { MUSIC } from '../audio/music';

type Phase = 'intro' | 'play' | 'picker' | 'cutscene' | 'frozen';
interface Pickup { img: Phaser.GameObjects.Image; x: number; y: number; kind: 'drop' | 'leaf' | 'badge'; got: boolean; t: number; shade?: Phaser.GameObjects.Image }
interface Prompt { img: Phaser.GameObjects.Image; cond: () => boolean; done: () => boolean; at: () => { x: number; y: number }; a: number }

const STEP = 1 / 120;
const DROP_COLORS = [C.cola0, C.crm1, C.chr0, C.blu1, C.lim1, C.mng1, C.pur0];

export class StoreScene extends Phaser.Scene {
  world!: PhysicsWorld; goose!: Goose; fx!: FxSystem; bubbles!: BubbleManager;
  people: Person[] = []; bottles: ShelfBottle[] = []; boxWall!: BoxWall; lift!: TridentLift;
  foams: Foam[] = []; shots: CherryShot[] = [];
  sam!: Person;
  sampling!: Sampling; fountain!: Fountain;
  power: FlavorId | null = null; powerT = 0; abilityCd = 0;
  pickups: Pickup[] = []; dropCount = 0; dropTotal = 0; leafCount = 0; badgeGot = false;
  phase: Phase = 'intro';
  acc = 0; elapsed = 0;
  prompts: Prompt[] = [];
  honkCount = 0;
  wallShelfHonks = 0;
  bumpedWall = 0;
  lampGlows: Phaser.GameObjects.Image[] = [];
  touch = false;
  usedJump = false; usedHonk = false; usedPower = false;

  constructor() { super('Store'); }

  create() {
    this.resetState();
    const cam = this.cameras.main;
    cam.setBounds(0, 0, WORLD_W, WORLD_H).setBackgroundColor(C.blk2).setRoundPixels(true);
    this.world = new PhysicsWorld();
    for (const sd of solids()) this.world.add(sd);
    this.fx = new FxSystem(this);
    this.touch = this.registry.get('touch') === true;
    this.buildEnvironment();
    this.buildPeople();
    this.buildBottles();
    this.buildPickups();

    this.goose = new Goose(this, 40, FLOOR);
    this.goose.events.on('honk', (p: { x: number; y: number }) => this.onHonk(p.x, p.y));
    this.goose.events.on('land', (x: number, y: number) => this.fx.dust(x, y, 5));
    this.goose.events.on('jump', () => { this.usedJump = true; this.fx.dust(this.goose.x, this.goose.y, 3); });
    this.goose.events.on('hurt', () => { this.fx.stars(this.goose.sprite); emote(this, this.goose.x, this.goose.y - 40, 'HONK?!', { life: 900 }); });

    this.bubbles = new BubbleManager(this, this.world, 28);
    this.bubbles.onPop = (b: Bubble) => this.onBubblePop(b);
    this.boxWall = new BoxWall(this, this.world, L.boxWall.x, L.boxWall.cols, L.boxWall.rows, L.boxWall.bw, L.boxWall.bh);
    this.add.image(L.boxWall.x + 24, FLOOR - 92, 'signDelivery').setOrigin(0.5, 1).setDepth(37);
    this.lift = new TridentLift(this, this.world, L.lift.x, L.lift.low, L.lift.high);
    this.sampling = new Sampling(this);
    this.fountain = new Fountain(this);
    this.buildPrompts();

    cam.startFollow(this.goose.sprite, true, 0.12, 0.1, 0, 30);
    cam.setDeadzone(40, 50);
    cam.fadeIn(500, 20, 12, 24);

    this.registry.set('dropTotal', this.dropTotal);
    if (!this.scene.isActive('UI')) this.scene.launch('UI');
    else this.scene.get('UI').events.emit('reset');
    this.scene.bringToTop('UI');
    MUSIC.play('store'); MUSIC.setIntensity(0);
    this.game.events.emit('hud:reset', { dropTotal: this.dropTotal });

    // intro: goose waddles in through the door
    this.phase = 'intro';
    this.goose.body.vx = 70;
    this.time.delayedCall(650, () => { if (this.phase === 'intro') this.phase = 'play'; });
    this.events.once('shutdown', () => { this.goose.events.removeAllListeners(); });
    const api = (window as unknown as { __SIMPS: Record<string, unknown> }).__SIMPS;
    api.store = this;
    // test hooks (used by tests/e2e.mjs to reach sections quickly; gameplay itself uses real input)
    api.teleport = (x: number, y: number) => { const b = this.goose.body; b.x = x - b.w / 2; b.y = y - b.h; b.vx = 0; b.vy = 0; b.ground = null; this.cameras.main.centerOn(x, y); };
    api.restartStore = () => this.scene.restart();
  }

  resetState() {
    this.people = []; this.bottles = []; this.foams = []; this.shots = []; this.pickups = []; this.prompts = []; this.lampGlows = [];
    this.power = null; this.powerT = 0; this.abilityCd = 0; this.dropCount = 0; this.dropTotal = 0; this.leafCount = 0; this.badgeGot = false;
    this.acc = 0; this.elapsed = 0; this.honkCount = 0; this.wallShelfHonks = 0; this.bumpedWall = 0;
    this.usedJump = false; this.usedHonk = false; this.usedPower = false;
  }

  // ------------------------------------------------------------------ build
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
    const drops: [number, number][] = [];
    const line = (x0: number, x1: number, y: number, n: number) => { for (let i = 0; i < n; i++) drops.push([x0 + (x1 - x0) * (n === 1 ? 0 : i / (n - 1)), y]); };
    line(120, 250, FLOOR - 14, 4);
    line(312, 324, FLOOR - 44, 2);
    line(366, 380, FLOOR - 72, 2);
    line(440, 512, FLOOR - 92, 4);
    drops.push([L.tridentStand.x + 38, FLOOR - TRIDENT_STAND.h + 46], [L.tridentStand.x + 15, FLOOR - TRIDENT_STAND.h + 8], [L.tridentStand.x + 61, FLOOR - TRIDENT_STAND.h + 8]);
    line(735, 810, FLOOR - 92, 4);
    line(880, 1060, FLOOR - 14, 5);
    line(1125, 1200, FLOOR - 62, 3);
    line(1330, 1370, FLOOR - 14, 2);
    line(1640, 1700, FLOOR - 14, 3);
    line(1800, 1880, FLOOR - 14, 3);
    line(1960, 2000, FLOOR - 100, 2);
    line(2070, 2110, FLOOR - 150, 2);
    line(2200, 2300, L.mezz.y - 14, 4);
    drops.forEach(([x, y], i) => {
      const img = this.add.image(x, y, 'droplet').setTint(DROP_COLORS[i % DROP_COLORS.length]).setDepth(38);
      const shade = this.add.image(x, y, 'dropletShade').setDepth(39);
      this.pickups.push({ img, shade, x, y, kind: 'drop', got: false, t: i * 0.4 });
    });
    this.dropTotal = drops.length;
    for (const [x, y] of [[L.wallShelf.x + 34, L.wallShelf.y - 14], [L.checkout.x + 56, FLOOR - L.checkout.h - 48], [L.mezz.x + L.mezz.w - 20, L.mezz.y - 14]] as [number, number][]) {
      this.pickups.push({ img: this.add.image(x, y, 'goldenLeaf').setDepth(38), x, y, kind: 'leaf', got: false, t: 0 });
    }
    const bx = L.tridentStand.x + 38, by = FLOOR - TRIDENT_STAND.h - 6;
    this.pickups.push({ img: this.add.image(bx, by, 'badge28').setDepth(38), x: bx, y: by, kind: 'badge', got: false, t: 0 });
  }

  key(k: 'jump' | 'honk' | 'sip' | 'power' | 'use' | 'move') {
    if (this.touch) return { jump: 'key_JUMP', honk: 'key_HONK', sip: 'key_SIP', power: 'key_POWER', use: 'key_USE', move: 'key_ARROWS' }[k];
    return { jump: 'key_SPACE', honk: 'key_X', sip: 'key_E', power: 'key_C', use: 'key_E', move: 'key_ARROWS' }[k];
  }
  buildPrompts() {
    const mk = (tex: string, cond: () => boolean, done: () => boolean, at: () => { x: number; y: number }) => {
      const img = this.add.image(0, 0, tex).setDepth(85).setAlpha(0);
      this.prompts.push({ img, cond, done, at, a: 0 });
    };
    const g = this.goose;
    mk(this.key('move'), () => this.elapsed > 0.8 && this.elapsed < 6 && g.x < 120, () => g.x > 140, () => ({ x: g.x, y: g.y - 46 }));
    mk(this.key('jump'), () => g.x > 230 && g.x < 300, () => this.usedJump, () => ({ x: L.crate1.x + 17, y: FLOOR - 52 }));
    mk(this.key('honk'), () => this.elapsed > 4 && this.nearestPerson(g.x, 90) !== null && this.honkCount === 0, () => this.honkCount > 0, () => ({ x: g.x, y: g.y - 46 }));
    mk(this.key('sip'), () => this.sampling.inZone() && this.phase === 'play', () => false, () => ({ x: L.sample.x + 72, y: FLOOR - L.sample.h - 24 }));
    mk(this.key('power'), () => this.power !== null && !this.boxWall.toppled && g.x > L.boxWall.x - 120 && g.x < L.boxWall.x, () => this.boxWall.toppled || g.x > L.boxWall.x + 60, () => ({ x: g.x, y: g.y - 46 }));
    mk(this.key('honk'), () => this.fountain.stage < 2 && Math.abs(g.x - this.fountain.cx) < 90 && this.phase === 'play', () => this.fountain.stage >= 2, () => ({ x: this.fountain.cx, y: FLOOR - L.fountain.h - 30 }));
    mk(this.key('use'), () => this.fountain.stage >= 2 && this.fountain.nearValve() && !this.fountain.finaleStarted, () => this.fountain.finaleStarted, () => ({ x: L.valve.x, y: L.mezz.y - 80 }));
  }

  // ---------------------------------------------------------------- helpers
  nearestPerson(x: number, r: number, staff = true): Person | null {
    let best: Person | null = null, bd = r;
    for (const p of this.people) { if (!staff && p.staff) continue; const d = Math.abs(p.x - x); if (d < bd) { bd = d; best = p; } }
    return best;
  }
  setPower(id: FlavorId | null) {
    this.power = id;
    this.powerT = id ? POWER_DURATION : 0;
    if (id) { SFX.powerup(); this.game.events.emit('hud:toast', `${FLAVORS[id].name}: ${FLAVORS[id].power}!`, FLAVORS[id].light, FLAVORS[id].hint); this.fx.sparkle(this.goose.x, this.goose.y - 20, 10, FLAVORS[id].light); }
    this.game.events.emit('hud:power', id, this.powerT, POWER_DURATION);
  }

  onHonk(x: number, y: number) {
    this.honkCount++; this.usedHonk = true;
    const d = this.goose.facing;
    this.fx.honk(x, y, d);
    for (const p of this.people) if (Math.abs(p.x - x) < 130 && Math.abs(p.y - this.goose.y) < 120) p.onHonk(x);
    for (const b of this.bottles) if (Math.hypot(b.x - x, b.y - y) < 120) b.jiggle(1);
    // honking under the high wall ledge rattles a bottle loose (it may bonk the goose!)
    if (Math.abs(x - (L.wallShelf.x + 30)) < 90 && y > L.wallShelf.y) {
      this.wallShelfHonks++;
      if (this.wallShelfHonks >= 2) { const b = this.bottles.find((bb) => bb.knockable && bb.state === 'rest' && bb.baseY === L.wallShelf.y); b?.knock(x > b.x ? 1 : -1, 0.4, true); this.wallShelfHonks = 0; }
    }
    if (!this.boxWall.toppled && Math.abs(x - L.boxWall.x - 24) < 60) this.boxWall.wobble();
    this.fountain.onHonk(x);
  }

  useAbility() {
    const g = this.goose;
    if (this.abilityCd > 0 || g.mode !== 'play') return;
    if (!this.power) {
      // no flavor yet: a tiny sad bubble + shrug teaches that C does *something*
      this.abilityCd = 0.8;
      g.playOnce('blow', true); SFX.bubble();
      this.time.delayedCall(300, () => { const b = this.add.image(g.x + g.facing * 14, g.y - 26, 'bubble16').setScale(0.4).setDepth(46); this.tweens.add({ targets: b, y: b.y - 16, scale: 0.6, duration: 600, onComplete: () => { b.destroy(); SFX.pop(0.6); } }); });
      this.time.delayedCall(800, () => { if (g.mode === 'play') g.playOnce('shrug'); });
      if (this.sampling.nearGreet()) this.sam.say('TRY A SAMPLE!', 1400);
      return;
    }
    this.usedPower = true;
    if (this.power === 'cola') {
      if (g.dash(g.facing)) { this.abilityCd = 0.55; SFX.dash(); this.cameras.main.shake(120, 0.002); }
    } else if (this.power === 'cream') {
      if (this.foams.filter((f) => f.active).length >= 2) this.foams.find((f) => f.active)?.kill();
      const onGround = g.body.onGround;
      const f = new Foam(this, this.world, g.x, g.y, onGround ? 48 : 0);
      this.foams.push(f);
      if (onGround) { g.body.ground = f.plat; } else { g.body.vy = 0; }
      g.playOnce('blow');
      this.fx.bubbles(g.x, g.y, 5);
      this.abilityCd = 0.7;
    } else if (this.power === 'cherry') {
      if (this.shots.filter((s) => s.active).length >= 3) return;
      g.playOnce('blow');
      this.time.delayedCall(180, () => this.shots.push(new CherryShot(this, g.x + g.facing * 16, g.y - 26, g.facing)));
      this.abilityCd = 0.35;
    }
  }

  onBubblePop(b: Bubble) {
    this.fx.drops(b.x, b.y, b.tint === 0xffffff ? C.bub2 : b.tint, Math.round(b.r / 2));
    this.fx.sparkle(b.x, b.y, 3);
    if (b.y > FLOOR - 120) this.fx.splat(b.x, FLOOR + 2, [C.bub2, C.crm1, C.chr0][Math.floor(Math.random() * 3)]);
    if (this.goose.body.ground === b.plat) this.goose.body.ground = null;
  }

  wideShot() {
    const cam = this.cameras.main;
    cam.stopFollow();
    cam.pan(2150, 172, 900, 'Sine.easeInOut');
    cam.zoomTo(0.75, 900, 'Sine.easeInOut');
    for (let i = 0; i < 6; i++) this.bubbles.spawn(1900 + Math.random() * 450, 200 + Math.random() * 120, 10 + Math.random() * 10, 'rise', { vy: -20 - Math.random() * 20, tint: [0xffffff, 0xffe0ea, 0xfff6dc][i % 3] });
    this.time.delayedCall(1150, () => this.freeze());
  }
  freeze() {
    this.phase = 'frozen';
    this.tweens.pauseAll();
    this.anims.pauseAll();
    this.children.list.forEach((o) => { if (o instanceof Phaser.GameObjects.Particles.ParticleEmitter) o.pause(); });
    this.cameras.main.flash(120, 255, 255, 255);
    const pfx = (this.cameras.main as unknown as { postFX?: { addColorMatrix: () => { sepia: () => void } } }).postFX;
    try { pfx?.addColorMatrix().sepia(); } catch { /* canvas renderer */ }
    MUSIC.stinger();
    const s = settings();
    saveSettings({ bestDrops: Math.max(s.bestDrops, this.dropCount), plays: s.plays + 1 });
    this.game.events.emit('demo:end', { drops: this.dropCount, total: this.dropTotal, leaves: this.leafCount, badge: this.badgeGot, time: this.elapsed, honks: this.honkCount });
  }

  // ---------------------------------------------------------------- loop
  update(_t: number, deltaMs: number) {
    if (this.phase === 'frozen') return;
    const dt = Math.min(deltaMs / 1000, 1 / 20);
    this.elapsed += dt;
    if (Controls.pressed('pause') && this.phase !== 'picker') { this.game.events.emit('ui:pause'); return; }

    // per-frame input that isn't movement
    if (this.phase === 'play') {
      if (Controls.pressed('ability')) this.useAbility();
      if (Controls.pressed('interact')) {
        if (this.sampling.inZone()) this.sampling.open();
        else if (this.fountain.stage >= 2 && this.fountain.nearValve()) this.fountain.finale();
      }
      // honking at the valve also works (it's a goose)
      if (Controls.pressed('honk') && this.fountain.stage >= 2 && this.fountain.nearValve()) this.time.delayedCall(200, () => this.fountain.finale());
    }
    this.sampling.update();

    // fixed-step simulation
    this.acc += dt;
    let first = true, n = 0;
    while (this.acc >= STEP && n < 8) {
      this.stepSim(STEP, first);
      this.acc -= STEP; first = false; n++;
    }
    this.frame(dt);
  }

  stepSim(dt: number, first: boolean) {
    const g = this.goose;
    this.bubbles.step(dt);
    this.lift.step(dt);
    for (const f of this.foams) f.step(dt);
    const gr = g.body.ground;
    this.bubbles.standing = gr && gr.tag === 'bubble' ? (gr.owner as Bubble) : null;
    if (this.phase === 'intro') { g.body.vx = 70; g.update(dt, this.world, false, false); g.body.vx = 70; }
    else g.update(dt, this.world, this.phase === 'play', first);
    // projectiles
    for (const s of this.shots) {
      if (!s.active) continue;
      if (s.step(dt, this.world) === 'pop') { this.fx.drops(s.x, s.y, C.chr0, 6); continue; }
      const r = s.rect();
      if (!this.boxWall.toppled && overlap(r, this.boxWall.rect())) { this.boxWall.topple(Math.sign(s.vx) || 1, this.world, (x, y) => this.fx.dust(x, y, 6)); this.fx.drops(s.x, s.y, C.chr0, 12); this.fx.splat(s.x, FLOOR + 2, C.chr1); s.kill(); continue; }
      for (const p of this.people) if (Math.abs(p.x - s.x) < 8 && s.y > p.y - 60 && s.y < p.y) { p.onHonk(s.x); this.fx.drops(s.x, s.y, C.chr0, 8); s.kill(); break; }
      for (const b of this.bottles) if (b.state === 'rest' && Math.abs(b.x - s.x) < 6 && Math.abs(b.y - 8 - s.y) < 10) { b.knock(Math.sign(s.vx), 1); }
    }
    for (const b of this.bottles) {
      b.step(dt, this.world);
      if (b.state === 'fall' && b.canHurt && b.vy > 80 && g.mode === 'play' && Math.abs(b.x - g.x) < 10 && b.y > g.y - 34 && b.y < g.y - 4) { g.hurt(b.x); b.vy = -120; b.vx = -b.vx; }
    }
  }

  frame(dt: number) {
    const g = this.goose, b = g.body;
    this.abilityCd -= dt;
    // dash effects & collisions
    if (g.dashing) {
      this.fx.fizz(g.x - g.facing * 8, g.y - 12, 2);
      if (Math.random() < 0.5) this.fx.drops(g.x - g.facing * 10, g.y - 8, C.cola0, 1);
      const gr = { x: b.x - 4, y: b.y, w: b.w + 8, h: b.h };
      if (!this.boxWall.toppled && overlap(gr, this.boxWall.rect())) { this.boxWall.topple(g.facing, this.world, (x, y) => this.fx.dust(x, y, 6)); this.cameras.main.shake(250, 0.006); emote(this, g.x, g.y - 44, 'HONK!', { life: 800 }); }
    }
    // walking into the box wall without a way through
    if (!this.boxWall.toppled && b.hitWall === 1 && Math.abs(b.x + b.w - L.boxWall.x) < 2 && this.phase === 'play') {
      this.bumpedWall += dt;
      if (this.bumpedWall > 0.5) { this.bumpedWall = -3; g.playOnce('shrug'); emote(this, g.x, g.y - 44, '?', { life: 900 }); if (!this.power) this.sam.say('A SAMPLE MIGHT HELP!', 1800); }
    }
    // knock bottles off display tops by walking/dashing through them
    for (const bt of this.bottles) {
      if (bt.state !== 'rest' || !bt.knockable) continue;
      if (Math.abs(bt.x - g.x) < 9 && bt.y <= g.y + 2 && bt.y > g.y - 22 && (Math.abs(b.vx) > 30 || g.dashing)) bt.knock(Math.sign(b.vx) || g.facing, g.dashing ? 1.8 : 1);
    }
    // bump into people
    for (const p of this.people) if (Math.abs(p.x - g.x) < 10 && Math.abs(p.y - g.y) < 30 && (Math.abs(b.vx) > 110 || g.dashing)) p.onBump(g.x);
    for (const p of this.people) p.update(dt);
    // pickups
    for (const pk of this.pickups) {
      if (pk.got) continue;
      pk.t += dt;
      const bob = Math.round(Math.sin(pk.t * 3) * 2);
      pk.img.y = pk.y + bob; if (pk.shade) pk.shade.y = pk.y + bob;
      if (pk.kind !== 'drop') pk.img.setScale(Math.abs(Math.cos(pk.t * 2)) * 0.3 + 0.7, 1);
      if (Math.abs(pk.x - g.x) < 12 && pk.y > g.y - 34 && pk.y < g.y + 6) this.collect(pk);
    }
    // power timer
    if (this.power && this.phase === 'play') {
      this.powerT -= dt;
      this.game.events.emit('hud:power', this.power, this.powerT, POWER_DURATION);
      if (this.powerT <= 0) {
        SFX.burp(); SFX.powerdown();
        emote(this, g.x, g.y - 44, 'BURP!', { life: 1000 });
        this.fx.bubbles(g.x + g.facing * 12, g.y - 26, 6);
        this.setPower(null);
      }
    }
    this.fountain.update(dt);
    this.bubbles.render(dt);
    this.lift.render();
    g.updateShadow(this.world, this.bubbles.standing ?? undefined);
    for (const l of this.lampGlows) l.setAlpha(0.18 + Math.sin(this.elapsed * 2 + l.x) * 0.015);
    // world prompts
    for (const pr of this.prompts) {
      const show = !pr.done() && pr.cond();
      pr.a += ((show ? 1 : 0) - pr.a) * Math.min(1, dt * 8);
      const p = pr.at();
      pr.img.setPosition(Math.round(p.x), Math.round(p.y + Math.sin(this.elapsed * 5) * 1.5)).setAlpha(pr.a);
    }
  }

  collect(pk: Pickup) {
    pk.got = true;
    if (pk.kind === 'drop') {
      this.dropCount++; SFX.collect(this.dropCount);
      this.fx.sparkle(pk.x, pk.y, 4, pk.img.tintTopLeft);
      this.game.events.emit('hud:drops', this.dropCount, this.dropTotal);
    } else if (pk.kind === 'leaf') {
      this.leafCount++; SFX.golden(); this.fx.confetti(pk.x, pk.y, 14);
      this.game.events.emit('hud:leaf', this.leafCount);
      this.game.events.emit('hud:toast', `GOLDEN MAPLE LEAF ${this.leafCount}/3`, C.gold1);
    } else {
      this.badgeGot = true; SFX.golden(); this.fx.sparkle(pk.x, pk.y, 14, C.red0); this.fx.confetti(pk.x, pk.y, 20);
      this.game.events.emit('hud:badge', true);
      this.game.events.emit('hud:toast', 'SIMPS CERTIFIED GOOSE!', C.red0);
      this.goose.playOnce('celebrate'); this.time.delayedCall(900, () => { if (this.goose.mode === 'play') this.goose.playLoop('idle'); });
    }
    this.tweens.add({ targets: [pk.img, pk.shade].filter(Boolean), y: pk.y - 18, alpha: 0, scale: 1.6, duration: 300, onComplete: () => { pk.img.destroy(); pk.shade?.destroy(); } });
  }
}
