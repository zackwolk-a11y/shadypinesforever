/**
 * LEVEL 1 BONUS — THE GREAT SIMPS STOCK-UP! (back stockroom, between sampling and Bubble Trouble)
 * Part 1: shelf stacking (conveyor → beak-carry boxes → flavour slots, push big boxes, Gerry's lift).
 * Part 2: load the truck (cola run with a jammed conveyor, push the cart, the bottle rush, last box).
 * Part 3: the gift box → MAPLE LEAF POWER HONK (+ crate, cracked wall and distant switch to try it on).
 */
import Phaser from 'phaser';
import { C } from '../art/palette';
import { WH } from '../art/stockroom';
import { LevelScene, Rect } from '../levels/LevelScene';
import { Person } from '../entities/Person';
import { emote } from '../entities/Emote';
import { Line } from '../ui/Dialogue';
import { GS } from '../systems/gamestate';
import { save, update, complete, unlock, StageId } from '../systems/save';
import { achieve } from '../data/achievements';
import { txt } from '../art/font';
import { shake } from '../systems/camfx';
import { SFX } from '../audio/sfx';
import { MUSIC } from '../audio/music';
import type { Platform } from '../systems/physics';
import { Controls } from '../systems/input';

const F = WH.FLOOR;
type Flavor = 'cola' | 'cream' | 'cherry';
const FL_NAME: Record<Flavor, string> = { cola: 'COLA', cream: 'CREAM SODA', cherry: 'BLACK CHERRY' };
const SHELVES = [280, 230, 180];
const RACK_X = 136, RACK_W = 340;
const LIFT_X = 110;
const BAY_X = 520;
const CONV_B = { x0: 600, x1: 780, y: 290 };
const DOCK = { x0: 820, x1: 930, y: 302 };
const EXIT_X = 556;

interface Slot { x: number; y: number; fl: Flavor; filled: boolean; img: Phaser.GameObjects.Image; glow: Phaser.GameObjects.Image }
interface BigBox { img: Phaser.GameObjects.Image; plat: Platform; bay: number; done: boolean; fl: Flavor }
interface Item { img: Phaser.GameObjects.Image; x: number; y: number; vx: number; vy: number; kind: 'box' | 'bottle' | 'gold'; fl: Flavor; state: 'belt' | 'wait' | 'fly' | 'gone' }
interface Faller { img: Phaser.GameObjects.Image; warn: Phaser.GameObjects.Image; x: number; y: number; vy: number; t: number }
interface Roller { img: Phaser.GameObjects.Image; x: number; vx: number }

export class StockroomScene extends LevelScene {
  stage: StageId = 'stockroom';
  dave!: Person; gerry!: Person;
  part = 0; // 0 intro, 1 shelves, 2 truck, 3 reward, 4 free
  slots: Slot[] = []; bigs: BigBox[] = []; bays: number[] = [];
  carried: { img: Phaser.GameObjects.Image; fl: Flavor; kind: 'box' | 'bottle' | 'gold' } | null = null;
  beltA: Item | null = null; beltT = 0;
  items: Item[] = []; fallers: Faller[] = []; rollers: Roller[] = [];
  fallT = 4; rollT = 6;
  dropped = 0; stocked = 0; stockTotal = 8;
  liftY = F - 6; liftTarget = F - 6; liftPlat!: Platform; liftHead!: Phaser.GameObjects.Image; liftShaft!: Phaser.GameObjects.TileSprite; liftStand = 0; liftIdle = 0; liftFirst = true; liftBusy = false;
  meter!: Phaser.GameObjects.Graphics; meterT!: Phaser.GameObjects.BitmapText; timerT!: Phaser.GameObjects.BitmapText;
  bayDoor!: Phaser.GameObjects.Image; bayWall!: Platform;
  // part 2
  delivery = 0; order: Flavor[] = []; orderIdx = 0; loaded: Phaser.GameObjects.Image[] = [];
  jam = false; jamDone = false; jamImg: Phaser.GameObjects.Image | null = null; jamNeedle: Phaser.GameObjects.Rectangle | null = null; jamT = 0;
  cart!: BigBox; cartDone = false;
  caught = 0; rushT = 0; spawnB = 0; beltSpeed = 40; rollerImgs: Phaser.GameObjects.TileSprite[] = [];
  t2 = 0; timeLimit = 150; bonusLimit = 100; overtime = false; platQueue = 0;
  stack!: Phaser.GameObjects.Container; stackWob = 0;
  // part 3
  crate!: { img: Phaser.GameObjects.Image; plat: Platform; gone: boolean };
  wallBroken = false; switchOn = false; switchImg!: Phaser.GameObjects.Image; cageImg!: Phaser.GameObjects.Graphics;
  exiting = false; elapsedStock = 0;
  conveyorA!: Phaser.GameObjects.TileSprite; conveyorB!: Phaser.GameObjects.TileSprite;
  forklift!: Phaser.GameObjects.Image;

  constructor() { super('Stockroom'); }
  create() {
    this.levelName = 'THE GREAT SIMPS STOCK-UP!';
    this.initLevel({ w: WH.W, h: WH.H, floor: F, bg: 0x2a2d38, spawn: { x: 30, y: F } });
    Object.assign(this, { part: 0, slots: [], bigs: [], bays: [], carried: null, beltA: null, beltT: 0, items: [], fallers: [], rollers: [], fallT: 4, rollT: 6, dropped: 0, stocked: 0, liftY: F - 6, liftTarget: F - 6, liftStand: 0, liftIdle: 0, liftFirst: true, liftBusy: false, delivery: 0, order: [], orderIdx: 0, loaded: [], jam: false, jamDone: false, jamImg: null, jamNeedle: null, jamT: 0, cartDone: false, caught: 0, rushT: 0, spawnB: 0, beltSpeed: 40, rollerImgs: [], t2: 0, overtime: false, platQueue: 0, stackWob: 0, wallBroken: false, switchOn: false, exiting: false, elapsedStock: 0 });
    this.add.image(0, 0, 'whWall').setOrigin(0).setScrollFactor(0.92, 1).setDepth(0);
    for (const x of [120, 400, 700, 980]) { this.add.image(x, 26, 'pendant').setOrigin(0.5, 0).setDepth(59); this.add.image(x, 40, 'glow128').setOrigin(0.5, 0.15).setScale(1.4, 2.4).setTint(0xfff0c0).setAlpha(0.18).setBlendMode(Phaser.BlendModes.ADD).setDepth(57); }
    this.add.tileSprite(0, F, WH.W, WH.H - F, 'floor').setOrigin(0).setDepth(15).setTint(0xb8b8c8);
    this.addPlatform(-40, F, WH.W + 80, 40, 'solid', 'floor'); this.addPlatform(-40, 0, 44, WH.H, 'solid', 'wallL'); this.addPlatform(WH.W - 4, 0, 44, WH.H, 'solid', 'wallR');
    this.addPlatform(-40, -40, WH.W + 80, 66, 'solid', 'ceiling');
    this.buildPart1();
    this.buildPart2();
    this.dave = new Person(this, 'dave', 56, F, { staff: true, depth: 24, facing: 1 }); this.people.push(this.dave);
    this.forklift = this.add.image(498, F, 'forklift').setOrigin(0.5, 1).setDepth(26).setFlipX(true);
    this.gerry = new Person(this, 'gerry', 500, F - 20, { staff: true, depth: 25, facing: -1 }); this.people.push(this.gerry);
    this.finishInit({ music: 'warehouse' });
    this.buildHud();
    this.addPrompt(this.key('use'), () => this.part === 1 && !this.carried && this.beltA?.state === 'wait' && Math.abs(this.goose.x - 76) < 26, () => this.stocked >= this.stockTotal, () => ({ x: 76, y: F - 50 }));
    this.addPrompt(this.key('use'), () => this.part === 1 && !!this.carried && this.nearSlot() !== null, () => this.stocked >= this.stockTotal, () => { const s = this.nearSlot(); return s ? { x: s.x, y: s.y - 40 } : { x: this.goose.x, y: this.goose.y - 46 }; });
    this.addPrompt(this.key('honk'), () => this.jam && Math.abs(this.goose.x - CONV_B.x1) < 140, () => this.jamDone, () => ({ x: CONV_B.x1 - 20, y: CONV_B.y - 70 }));
    this.addPrompt(this.key('honk'), () => this.part >= 4 && !this.crate.gone && Math.abs(this.goose.x - EXIT_X) < 160, () => this.crate.gone, () => ({ x: this.goose.x, y: this.goose.y - 46 }));
    this.phase = 'intro'; this.goose.body.vx = 60;
    this.tweens.add({ targets: [this.forklift, this.gerry.sprite], x: '-=14', duration: 700, yoyo: true, repeat: -1, ease: 'Sine.InOut' });
    this.time.delayedCall(700, () => this.opening());
    unlock('stockroom');
    (window as unknown as { __SIMPS: Record<string, unknown> }).__SIMPS.stock = this;
  }

  // ------------------------------------------------------------------ build
  buildPart1() {
    // conveyor A (Dave's)
    this.conveyorA = this.add.tileSprite(10, F - 12, 76, 12, 'conveyor').setOrigin(0).setDepth(27);
    this.add.rectangle(10, F - 12, 76, 2, C.st1).setOrigin(0).setDepth(28);
    this.addPlatform(10, F - 12, 76, 5, 'oneway', 'beltA');
    // the rack: three storeys
    this.add.image(RACK_X, F, 'rack').setOrigin(0, 1).setDepth(22);
    for (const y of SHELVES) this.addPlatform(RACK_X, y, RACK_W, 5, 'oneway', 'shelf');
    const defs: [number, number, Flavor][] = [[0, 70, 'cola'], [0, 260, 'cherry'], [1, 110, 'cream'], [1, 290, 'cola'], [2, 60, 'cherry'], [2, 230, 'cream']];
    for (const [s, dx, fl] of defs) {
      const x = RACK_X + dx, y = SHELVES[s];
      const glow = this.add.image(x, y - 10, 'glow64').setTint(0xfff0a0).setAlpha(0).setBlendMode(Phaser.BlendModes.ADD).setDepth(23);
      this.add.image(x, y + 6, 'tag_' + fl).setOrigin(0.5, 0).setDepth(24);
      const img = this.add.image(x, y, 'box_' + fl).setOrigin(0.5, 1).setDepth(24).setAlpha(0.22).setTint(0x000000);
      this.slots.push({ x, y, fl, filled: false, img, glow });
    }
    // floor bays for the big boxes (under the bottom shelf)
    this.bays = [RACK_X + 100, RACK_X + 250];
    for (const bx of this.bays) { const g = this.add.graphics().setDepth(16); g.lineStyle(1, C.gold1, 0.9).strokeRect(bx - 16, F - 28, 32, 28); this.add.image(bx, F + 6, 'tag_cherry').setDepth(16).setTint(0xffe0a0); }
    this.bigs.push(this.mkBig(RACK_X + 20, 'cream', 0), this.mkBig(RACK_X + 296, 'cherry', 1));
    // pallets to hop on
    for (const x of [300, 62]) { this.add.image(x, F, 'pallet').setOrigin(0.5, 1).setDepth(26); this.addPlatform(x - 22, F - 10, 44, 4, 'oneway', 'pallet'); }
    // Gerry's red-trident lift
    this.liftShaft = this.add.tileSprite(LIFT_X, F, 10, 1, 'piston').setOrigin(0.5, 1).setDepth(33);
    this.liftHead = this.add.image(LIFT_X, this.liftY, 'liftHead').setOrigin(0.5, 0).setDepth(34);
    this.liftPlat = this.world.add({ x: LIFT_X - 22, y: this.liftY, w: 44, h: 5, kind: 'oneway', tag: 'lift' });
    this.add.image(LIFT_X + 26, F, 'trident13').setOrigin(0.5, 1).setDepth(26);
    // loading bay door (closed until the shelves are stocked)
    this.bayDoor = this.add.image(BAY_X + 6, F, 'bayDoor').setOrigin(0.5, 1).setDepth(36).setScale(0.5, 1.4);
    this.bayWall = this.addPlatform(BAY_X - 10, 26, 30, F - 26, 'solid', 'bay');
  }
  mkBig(x: number, fl: Flavor, bay: number): BigBox {
    const img = this.add.image(x, F, 'box_' + fl).setOrigin(0.5, 1).setDepth(29).setScale(30 / 18, 26 / 16);
    const plat = this.addPlatform(x - 15, F - 26, 30, 26, 'solid', 'big');
    return { img, plat, bay, done: false, fl };
  }
  buildPart2() {
    this.add.image(1004, F, 'truck').setOrigin(0.5, 1).setDepth(12);
    this.conveyorB = this.add.tileSprite(CONV_B.x0, CONV_B.y, CONV_B.x1 - CONV_B.x0, 12, 'conveyor').setOrigin(0).setDepth(27);
    for (const x of [CONV_B.x0 + 10, CONV_B.x1 - 12]) this.add.rectangle(x, CONV_B.y + 12, 4, F - CONV_B.y - 12, C.st3).setOrigin(0).setDepth(26);
    this.addPlatform(CONV_B.x0, CONV_B.y, CONV_B.x1 - CONV_B.x0, 5, 'oneway', 'beltB');
    this.hazards.push({ kind: 'push', strength: 40, rect: { x: CONV_B.x0, y: CONV_B.y - 6, w: CONV_B.x1 - CONV_B.x0, h: 6 }, active: () => !this.jam && this.goose.body.ground?.tag === 'beltB' });
    // loading dock + trailer floor
    const g = this.add.graphics().setDepth(27);
    g.fillStyle(C.st3).fillRect(DOCK.x0, DOCK.y, DOCK.x1 - DOCK.x0 - 40, F - DOCK.y).fillStyle(C.gold1).fillRect(DOCK.x0, DOCK.y, DOCK.x1 - DOCK.x0 - 40, 3);
    for (let x = DOCK.x0; x < DOCK.x1 - 40; x += 10) g.fillStyle(C.blk1).fillRect(x, DOCK.y + 4, 5, 3);
    this.addPlatform(DOCK.x0, DOCK.y, DOCK.x1 - DOCK.x0 - 40, F - DOCK.y, 'solid', 'dock');
    this.addPlatform(DOCK.x1 - 40, DOCK.y, 40, 5, 'oneway', 'trailer');
    this.addPlatform(DOCK.x1, 200, 30, DOCK.y - 200, 'solid', 'trailerWall');
    // the unstable pallet stack that sheds rolling boxes
    this.stack = this.add.container(800, F).setDepth(28);
    for (let i = 0; i < 4; i++) this.stack.add(this.add.image((i % 2) * 4 - 2, -i * 16, 'box_' + (['cola', 'cream', 'cherry', 'cola'] as Flavor[])[i]).setOrigin(0.5, 1));
    this.stack.add(this.add.image(0, 0, 'pallet').setOrigin(0.5, 1).setScale(0.6, 1));
    // cart (delivery 2)
    const img = this.add.image(640, F, 'cart').setOrigin(0.5, 1).setDepth(29);
    this.cart = { img, plat: this.addPlatform(620, F - 27, 40, 27, 'solid', 'cart'), bay: 0, done: false, fl: 'cola' };
    this.add.image(806, F + 6, 'floorTrident').setTint(C.gold1).setAlpha(0.7).setDepth(16);
    // exit + power-honk practice
    this.add.image(EXIT_X - 30, F, 'stockDoor').setOrigin(0.5, 1).setDepth(20);
    const cimg = this.add.image(EXIT_X, F, 'heavyCrate').setOrigin(0.5, 1).setDepth(30);
    this.crate = { img: cimg, plat: this.addPlatform(EXIT_X - 17, F - 30, 34, 30, 'solid', 'heavy'), gone: false };
    this.add.image(690, 200, 'crackedWall').setDepth(20).setName('cracked');
    // a distant switch high on the wall: opens the ceiling hatch (bonus drops + a bubble star)
    this.switchImg = this.add.image(660, 120, 'wswitch0').setDepth(20);
    this.cageImg = this.add.graphics().setDepth(20); this.cageImg.fillStyle(C.st3).fillRect(600, 26, 120, 8).fillStyle(C.blk1).fillRect(604, 28, 112, 4);
    const sw = { on: false, by: ['powerhonk'], rect: () => ({ x: 652, y: 109, w: 16, h: 22 }), activate: (src: string) => {
      if (src !== 'powerhonk' || sw.on) return; sw.on = true; this.switchOn = true; this.switchImg.setTexture('wswitch1'); SFX.valve(); SFX.chime(); this.cageImg.clear();
      this.addDropLine(610, 710, 250, 5); this.addPickup('star', 660, 220);
      this.game.events.emit('hud:toast', 'DISTANT SWITCH!', C.gold0, 'THE CEILING HATCH OPENED');
    } };
    this.switches.push(sw);
  }
  buildHud() {
    this.meter = this.add.graphics().setScrollFactor(0).setDepth(150);
    this.meterT = txt(this, 240, 30, '', { align: 'center' }).setScrollFactor(0).setDepth(151);
    this.timerT = txt(this, 466, 30, '', { align: 'right' }).setScrollFactor(0).setDepth(151);
    this.drawMeter();
  }
  drawMeter() {
    const m = this.meter; m.clear();
    if (this.part === 1 || (this.part === 0 && this.stocked === 0)) {
      const k = this.stocked / this.stockTotal;
      m.fillStyle(C.ink, 0.85).fillRoundedRect(170, 40, 140, 12, 3).fillStyle(C.blk2).fillRect(173, 43, 134, 6).fillStyle(k >= 1 ? C.gold1 : C.red1).fillRect(173, 43, Math.round(134 * k), 6);
      this.meterT.setText(`STOCK-O-METER ${Math.round(k * 100)}%`);
    } else if (this.part === 2) {
      m.fillStyle(C.ink, 0.85).fillRoundedRect(150, 40, 180, 12, 3);
      for (let i = 0; i < 3; i++) m.fillStyle(i < this.delivery ? C.lim1 : i === this.delivery ? C.gold1 : C.st3).fillRect(156 + i * 58, 43, 52, 6);
      this.meterT.setText(['DELIVERY 1: THE COLA ORDER', 'DELIVERY 2: PUSH THE CART', 'DELIVERY 3: THE BOTTLE RUSH!'][this.delivery] ?? 'LOADED!');
    } else { this.meterT.setText(''); }
  }

  // ------------------------------------------------------------------ story beats
  talkLines(lines: Line[], then?: () => void) { this.talk(lines, { dave: this.dave, gerry: this.gerry }, then); }
  opening() {
    if (this.phase === 'intro') this.phase = 'play';
    this.talkLines([
      ['dave', "HEY, GOOSE! WE'VE GOT A HUGE SHIPMENT TO PUT AWAY!", 'wave'],
      ['gerry', 'AND ANOTHER ORDER THAT NEEDS TO GET ON THAT TRUCK. THINK YOU CAN LEND US A WING?', 'point'],
      ['goose', 'HONK!'],
      ['dave', "THAT'S THE SPIRIT! LET'S GET STOCKING!", 'cheer'],
      ['dave', 'GRAB BOXES OFF MY CONVEYOR, MATCH THE FLAVOUR TAGS, AND PUSH THE BIG ONES INTO THE FLOOR BAYS.', 'gesture'],
      ['gerry', "I'LL RUN THE LIFT. WHAT COULD GO WRONG?", 'talk'],
    ], () => this.startPart1());
    this.goose.playOnce('honk'); SFX.honk(1);
  }
  startPart1() {
    this.part = 1; this.drawMeter(); this.elapsedStock = 0;
    this.game.events.emit('hud:toast', 'PART 1: SHELF STACKING MADNESS', C.gold0, this.touch ? 'SIP: PICK UP / STACK   PUSH BIG BOXES' : 'E: PICK UP / STACK   WALK INTO BIG BOXES TO PUSH');
    this.gerry.sprite.setPosition(LIFT_X + 40, F); this.gerry.facing = -1;
    this.tweens.killTweensOf([this.forklift, this.gerry.sprite]);
  }
  finishPart1() {
    this.part = 0;
    SFX.bell(); this.time.delayedCall(500, () => { this.goose.playOnce('honk'); SFX.honk(1.6); this.fx.honk(this.goose.x, this.goose.y - 30, this.goose.facing, true); });
    this.fx.confetti(this.goose.x, this.goose.y - 40, 24);
    this.game.events.emit('hud:toast', 'STOCK-O-METER 100%!', C.gold0, this.dropped === 0 ? 'NOT A SINGLE BOX DROPPED!' : `${this.dropped} BOX(ES) DROPPED`);
    if (this.dropped === 0) achieve('master_stocker');
    GS.addScore(1500);
    for (const f of this.fallers) { f.img.destroy(); f.warn.destroy(); } this.fallers = [];
    this.time.delayedCall(1600, () => {
      SFX.rumble(1.2);
      this.tweens.add({ targets: this.bayDoor, y: 120, scaleY: 0.2, duration: 1200, onComplete: () => { this.bayWall.active = false; this.bayWall.x = -999; } });
      this.cameras.main.pan(800, 200, 900, 'Sine.easeInOut');
      this.time.delayedCall(1400, () => {
        this.cameras.main.pan(this.goose.x, this.goose.y, 600, 'Sine.easeInOut');
        this.dave.walkTo(812, 90, () => this.tweens.add({ targets: this.dave.sprite, x: 862, y: DOCK.y, duration: 450, ease: 'Sine.Out', onComplete: () => { this.dave.facing = -1; } })); this.gerry.walkTo(560, 90);
        this.talkLines([
          ['dave', "GREAT WORK! NOW LET'S GET THIS DELIVERY ON THE ROAD!", 'cheer'],
          ['gerry', 'AND PREFERABLY WITH ALL THE BOTTLES STILL INSIDE THE BOXES.', 'clip'],
          ['gerry', "THREE DELIVERIES. I'LL CALL OUT WHAT GOES NEXT. BRING IT TO DAVE ON THE DOCK.", 'clip'],
        ], () => this.startPart2());
      });
    });
  }
  startPart2() {
    this.part = 2; this.delivery = 0; this.t2 = 0; this.orderIdx = 0; this.order = ['cherry', 'cola', 'cream'];
    MUSIC.setIntensity(1);
    this.drawMeter(); this.callOrder();
    this.game.events.emit('hud:toast', 'PART 2: LOAD THAT TRUCK!', C.red0, `BONUS TIMER: ${this.bonusLimit}S`);
  }
  callOrder() { const fl = this.order[this.orderIdx]; if (fl) { this.gerry.lastLine = 0; this.gerry.say(`NEXT: ${FL_NAME[fl]}!`, 2200); this.gerry.act('clip', 1); } }
  nextDelivery() {
    this.delivery++; SFX.chime(); GS.addScore(800);
    this.dave.act('cheer', 1.2);
    this.drawMeter();
    if (this.delivery === 1) { this.gerry.lastLine = 0; this.gerry.say('CHECK! NOW PUSH THAT CART ONTO THE TRIDENT.', 2400); }
    if (this.delivery === 2) {
      this.dave.lastLine = 0; this.dave.say("WE'RE ALMOST THERE!", 2000);
      MUSIC.setIntensity(2); this.beltSpeed = 110; this.rushT = 0; this.caught = 0;
      this.game.events.emit('hud:toast', 'THE BOTTLE RUSH!', C.red0, 'CATCH 5 BOTTLES FLYING OFF THE BELT');
    }
    if (this.delivery === 3) this.truckDone();
  }
  truckDone() {
    this.part = 0; this.drawMeter();
    const bonus = this.t2 <= this.bonusLimit && !this.overtime;
    for (const r of this.rollers) r.img.destroy(); this.rollers = [];
    for (const it of this.items) it.img.destroy(); this.items = [];
    // the doors slam shut, the horn plays
    const dl = this.add.rectangle(DOCK.x1 - 40, 222, 20, 80, C.wht).setOrigin(0).setDepth(13).setScale(0, 1);
    const dr = this.add.rectangle(DOCK.x1 - 20, 222, 20, 80, C.wht).setOrigin(0).setDepth(13).setScale(0, 1);
    this.tweens.add({ targets: [dl, dr], scaleX: 1, duration: 260, delay: 400, onComplete: () => { SFX.crash(); shake(this, 250, 0.006); this.time.delayedCall(400, () => SFX.horn()); } });
    MUSIC.setIntensity(0);
    if (bonus) achieve('special_delivery');
    const perfect = bonus && this.dropped === 0;
    this.game.events.emit('hud:toast', 'TRUCK LOADED!', C.gold0, bonus ? 'SPECIAL DELIVERY, EH! (BONUS TIMER BEATEN)' : 'ALL THREE DELIVERIES DONE');
    if (perfect && !save().goldenOutfit) { update((s) => { s.goldenOutfit = true; }); this.time.delayedCall(2200, () => this.game.events.emit('hud:toast', 'GOLDEN GOOSE OUTFIT UNLOCKED!', C.gold0, 'EQUIP IT: TITLE MENU > CUSTOMIZE GOOSE')); }
    this.time.delayedCall(1800, () => this.reward(perfect));
  }
  reward(perfect: boolean) {
    const g = this.goose;
    const gx = Math.max(EXIT_X + 90, Math.min(780, g.x));
    this.tweens.add({ targets: this.dave.sprite, y: F, x: 805, duration: 400, onComplete: () => this.dave.walkTo(gx + 40, 90) }); this.gerry.walkTo(gx + 70, 90);
    const gift = this.add.image(gx + 22, F, 'gift').setOrigin(0.5, 1).setDepth(40).setAlpha(0);
    this.time.delayedCall(900, () => { this.dave.facing = -1; this.gerry.facing = -1; this.tweens.add({ targets: gift, alpha: 1, duration: 300 }); });
    this.time.delayedCall(1100, () => this.talkLines([
      ['dave', 'YOU JUST SAVED US A WHOLE AFTERNOON OF WORK!', 'cheer'],
      ['gerry', 'AND SOMEHOW MANAGED NOT TO DRINK THE ENTIRE INVENTORY.', 'talk'],
      ['dave', "WE'VE GOT SOMETHING SPECIAL FOR YOU.", 'point'],
    ], () => {
      // the box opens in a burst of bubbles; the medallion rises
      gift.setTexture('giftOpen'); SFX.bigPop(); SFX.sparkle(); this.fx.confetti(gift.x, gift.y - 20, 30); this.fx.bubbles(gift.x, gift.y - 16, 14);
      const med = this.add.image(gift.x, gift.y - 20, 'medallion').setDepth(48);
      this.tweens.add({ targets: med, y: g.y - 54, x: g.x, duration: 1100, ease: 'Sine.Out', onComplete: () => { med.destroy(); this.unlockPowerHonk(); } });
      this.time.delayedCall(1300, () => this.talkLines([
        ['dave', "THAT'S THE MAPLE LEAF POWER HONK! A LITTLE THANK-YOU FROM US!", 'cheer'],
        ['gerry', 'TRY NOT TO USE IT INDOORS.', 'point'],
      ], () => this.indoorsGag(perfect)));
    }));
  }
  unlockPowerHonk() {
    update((s) => { s.powerHonk = true; s.stockDone = true; });
    this.goose.powerHonk = true;
    this.game.events.emit('hud:abilities', { ph: true, db: save().doubleBubble, sb: save().superBurp });
    SFX.powerup(); this.fx.sparkle(this.goose.x, this.goose.y - 20, 16, C.gold0);
    this.game.events.emit('hud:toast', 'MAPLE LEAF POWER HONK!', C.gold0, this.touch ? 'HOLD HONK, THEN RELEASE' : 'HOLD X TO CHARGE, RELEASE TO BLAST');
  }
  indoorsGag(perfect: boolean) {
    const g = this.goose;
    this.phase = 'cutscene'; g.mode = 'script';
    g.chargeGlow = true;
    for (let i = 0; i < 8; i++) this.time.delayedCall(i * 90, () => this.fx.sparkle(g.x + (Math.random() - 0.5) * 20, g.y - 20, 1, C.gold0));
    this.time.delayedCall(900, () => {
      g.chargeGlow = false; g.playOnce('honk'); SFX.honk(2.2); SFX.rumble(1);
      this.powerHonkFx(g.x, g.y - 20); shake(this, 700, 0.012);
      const b = this.add.image(this.gerry.x, 60, 'bottle2').setDepth(45);
      this.tweens.add({ targets: b, y: this.gerry.y - 46, angle: 540, duration: 700, delay: 300, ease: 'Quad.In', onComplete: () => { this.gerry.act('catch', 1.6); b.setPosition(this.gerry.x + 6, this.gerry.y - 40).setAngle(0); SFX.clink(); this.time.delayedCall(1200, () => b.destroy()); } });
      this.time.delayedCall(1300, () => {
        g.mode = 'play'; g.playLoop('idle');
        this.talkLines([['gerry', 'I LITERALLY JUST SAID THAT.', 'hold'], ['dave', 'HA HA HA!', 'laugh']], () => {
          this.dave.setState('laugh', 1.5); SFX.laugh(0.9);
          this.finishStock(perfect);
        });
      });
    });
  }
  /** visual-only shockwave for the scripted demo honk */
  powerHonkFx(x: number, y: number) { const ring = this.add.circle(x, y, 10, C.gold1, 0).setStrokeStyle(4, C.gold0).setDepth(80); this.tweens.add({ targets: ring, radius: 170, alpha: 0, duration: 520, onComplete: () => ring.destroy() }); this.fx.confetti(x, y, 20); }
  finishStock(perfect: boolean) {
    this.part = 4;
    achieve('honk_if_you_work_here');
    complete('stockroom');
    GS.addScore(perfect ? 3000 : 1500); GS.persistRun();
    this.dave.lastLine = 0; this.dave.say('THE EXIT DOOR IS STUCK BEHIND THAT HEAVY CRATE. YOU KNOW WHAT TO DO!', 3200);
    this.time.delayedCall(3400, () => { this.gerry.lastLine = 0; this.gerry.say('A CRACKED WALL AND A FAR-OFF SWITCH, TOO. JUST SAYING.', 3000); });
    this.time.delayedCall(6800, () => { this.dave.lastLine = 0; this.dave.say('MEET ME AT MY BUBBLE WORKSHOP PAST THE FOUNTAIN!', 3000); });
  }
  onPowerHonkLevel(x: number, y: number) {
    if (!this.crate.gone && Math.abs(x - EXIT_X) < 170 && Math.abs(y - F) < 120) {
      this.crate.gone = true; this.crate.plat.active = false; this.crate.plat.x = -999;
      const dir = x < EXIT_X ? 1 : -1;
      SFX.crash(); this.tweens.add({ targets: this.crate.img, x: this.crate.img.x + dir * 50, angle: dir * 12, alpha: 0.4, duration: 500, ease: 'Quad.Out' });
      this.game.events.emit('hud:toast', 'HEAVY CRATE PUSHED!', C.gold0, 'THE EXIT IS OPEN');
    }
    const cw = this.children.getByName('cracked') as Phaser.GameObjects.Image | null;
    if (!this.wallBroken && cw && Math.hypot(690 - x, 200 - y) < 170) {
      this.wallBroken = true; SFX.crash(); this.fx.dust(690, 210, 12); cw.destroy();
      this.addPickup('leaf', 690, 204); this.addDropLine(676, 704, 186, 2);
      this.game.events.emit('hud:toast', 'CRACKED WALL!', C.gold0, 'A HIDDEN GOLDEN MAPLE LEAF');
    }
    for (const r of this.rollers) if (Math.abs(r.x - x) < 170) r.vx = Math.sign(r.x - x) * 260;
  }

  hintText(): string | null {
    const use = this.touch ? 'SIP' : 'E';
    if (this.part === 1) return this.carried
      ? `TAKE THE ${FL_NAME[this.carried.fl]} BOX TO A MATCHING TAG ON THE SHELVES (RIDE GERRY'S LIFT), THEN ${use}. (${this.stocked}/8)`
      : `GRAB A BOX FROM DAVE'S CONVEYOR (${use}) OR PUSH THE BIG BOXES INTO THE FLOOR BAYS. (${this.stocked}/8)`;
    if (this.part === 2) {
      if (this.delivery === 0) return this.jam ? 'HONK WHEN THE JAM GAUGE NEEDLE IS IN THE GREEN.' : `CARRY ${FL_NAME[this.order[this.orderIdx]]} FROM THE BELT TO DAVE ON THE DOCK (${use}). (${this.orderIdx}/3)`;
      if (this.delivery === 1) return 'PUSH THE CART ALL THE WAY RIGHT ONTO THE GOLD TRIDENT BY THE DOCK.';
      if (this.delivery === 2) return this.caught >= 5 ? 'HONK THE GOLDEN LAST BOX AT THE END OF THE BELT.' : `CATCH THE BOTTLES FLYING OFF THE BELT END. (${this.caught}/5)`;
    }
    if (this.part === 4) return this.crate.gone ? `WALK TO THE EXIT DOOR AND PRESS ${use}.` : `HOLD HONK TO CHARGE A POWER HONK NEXT TO THE HEAVY CRATE, THEN LET GO.`;
    return null;
  }
  // ------------------------------------------------------------------ input hooks
  nearSlot(): Slot | null {
    const g = this.goose;
    if (!this.carried) return null;
    for (const s of this.slots) if (!s.filled && Math.abs(g.x - s.x) < 22 && Math.abs(g.y - s.y) < 6) return s;
    return null;
  }
  onInteract() {
    const g = this.goose;
    if (this.part === 1) {
      if (!this.carried && this.beltA && this.beltA.state === 'wait' && Math.abs(g.x - this.beltA.x) < 26 && g.y > F - 20) { this.pickUp(this.beltA); this.beltA = null; this.beltT = 0.8; return true; }
      if (this.carried) {
        const s = this.nearSlot();
        if (s) {
          if (s.fl !== this.carried.fl) { emote(this, g.x, g.y - 44, `THAT'S ${FL_NAME[this.carried.fl]}!`, { life: 1000 }); SFX.ui('back'); return true; }
          s.filled = true; s.img.clearTint().setAlpha(1); s.glow.setAlpha(0); this.carried.img.destroy(); this.carried = null;
          this.stockOne(s.x, s.y - 10); return true;
        }
        emote(this, g.x, g.y - 44, 'FIND A MATCHING TAG!', { life: 900 }); return true;
      }
    }
    if (this.part === 2 && this.carried) return this.tryDeliver();
    if (this.part === 2 && !this.carried && this.delivery === 0) { const it = this.items.find((i) => i.state === 'wait' && Math.abs(i.x - g.x) < 24 && Math.abs(i.y - g.y) < 50); if (it) { this.pickUp(it); return true; } }
    if (this.part === 2 && this.delivery === 2) { const gold = this.items.find((i) => i.kind === 'gold' && i.state === 'wait' && Math.abs(i.x - g.x) < 30); if (gold) { this.launchGold(gold); return true; } }
    if (this.part >= 4 && this.crate.gone && Math.abs(g.x - (EXIT_X - 30)) < 30) { this.exit(); return true; }
    return false;
  }
  onHonkLevel(x: number) {
    // a honk right next to a big box nudges it away from the goose (backup for tight spots)
    if (this.part === 1) for (const bx of this.bigs) {
      if (bx.done) continue;
      const cx = bx.plat.x + 15, g = this.goose;
      if (Math.abs(cx - g.x) < 40 && g.y > F - 30) {
        const dir = cx > g.x ? 1 : -1;
        const nx = Math.max(RACK_X - 10, Math.min(BAY_X - 50, bx.plat.x + dir * 18));
        bx.plat.x = nx; this.tweens.add({ targets: bx.img, x: nx + 15, duration: 150 }); SFX.clunk(); this.fx.dust(cx, F, 4);
        for (const bay of this.bays) if (Math.abs(nx + 15 - bay) < 10) { bx.plat.x = bay - 15; this.tweens.add({ targets: bx.img, x: bay, duration: 120 }); }
      }
    }
    if (this.jam && Math.abs(x - CONV_B.x1) < 160 && this.jamNeedle) {
      const k = (this.jamNeedle.x - (CONV_B.x1 - 36)) / 32;
      if (k > 0.28 && k < 0.72) { this.clearJam(); } else { emote(this, this.goose.x, this.goose.y - 44, k < 0.5 ? 'TOO EARLY!' : 'TOO LATE!', { life: 700 }); SFX.clunk(); }
    }
    if (this.part === 2 && this.delivery === 2) { const gold = this.items.find((i) => i.kind === 'gold' && i.state === 'wait' && Math.abs(i.x - x) < 40); if (gold) this.launchGold(gold); }
    if (this.part === 1 && Math.abs(x - LIFT_X) < 30) this.liftStand = 1;
  }
  pickUp(it: Item) {
    it.state = 'gone'; it.img.destroy();
    this.carried = { img: this.add.image(this.goose.x, this.goose.y - 30, 'box_' + it.fl).setDepth(44), fl: it.fl, kind: it.kind };
    SFX.clink(); this.goose.playOnce('honk');
    for (const s of this.slots) s.glow.setAlpha(0);
  }
  stockOne(x: number, y: number) {
    this.stocked++; GS.addScore(150); SFX.collect(this.stocked); this.fx.sparkle(x, y, 8, C.gold0);
    this.drawMeter();
    if (this.stocked === 3) { this.dave.lastLine = 0; this.dave.say('CAREFUL WITH THAT CREAM SODA!', 2000); }
    if (this.stocked === 5) { this.gerry.lastLine = 0; this.gerry.say("I'VE SEEN WORSE WAREHOUSE WORKERS. NOT MANY, THOUGH.", 2800); this.gerry.act('laugh', 1); }
    if (this.stocked >= this.stockTotal) this.finishPart1();
  }
  dropCarried(why: string) {
    if (!this.carried) return;
    const c = this.carried; this.carried = null;
    if (this.part === 1) this.dropped++;
    this.tweens.add({ targets: c.img, y: F - 6, angle: 90, duration: 300, ease: 'Quad.In', onComplete: () => { SFX.crash(); this.fx.drops(c.img.x, F - 6, C.red0, 8); c.img.destroy(); } });
    emote(this, this.goose.x, this.goose.y - 44, why, { life: 900 });
    if (this.part === 1) { this.dave.lastLine = 0; this.dave.say('OOPS! ANOTHER ONE COMING!', 1600); }
  }
  tryDeliver() {
    const g = this.goose, c = this.carried!;
    if (!(g.x > DOCK.x0 - 10 && g.y <= DOCK.y + 2)) { emote(this, g.x, g.y - 44, 'TO THE DOCK!', { life: 800 }); return true; }
    if (this.platQueue >= 2) { emote(this, g.x, g.y - 44, 'OVERLOADED! WAIT!', { life: 900 }); this.dave.say('WHOA, ONE AT A TIME!', 1200); return true; }
    const want = this.order[this.orderIdx];
    if (c.fl !== want) { this.gerry.lastLine = 0; this.gerry.say(`THAT GOES IN THE ${FL_NAME[c.fl]} COMPARTMENT. I NEED ${FL_NAME[want]}!`, 2200); SFX.ui('back'); return true; }
    this.carried = null; this.platQueue++;
    const tx = DOCK.x1 - 34 + this.orderIdx * 12, ty = DOCK.y - 2 - this.loaded.length * 0;
    this.tweens.add({ targets: c.img, x: DOCK.x1 - 50, y: DOCK.y - 10, duration: 250, onComplete: () => {
      this.dave.act('catch', 0.8); SFX.clink();
      this.time.delayedCall(700, () => { this.tweens.add({ targets: c.img, x: tx, y: ty, duration: 300, onComplete: () => { c.img.setOrigin(0.5, 1).setDepth(13); this.loaded.push(c.img); this.platQueue--; } }); });
    } });
    GS.addScore(200);
    this.orderIdx++;
    if (this.orderIdx >= this.order.length) { this.time.delayedCall(1100, () => this.nextDelivery()); }
    else this.callOrder();
    return true;
  }
  spawnBeltB(kind: Item['kind'], fl: Flavor = 'cola') {
    const tex = kind === 'box' ? 'box_' + fl : kind === 'gold' ? 'gift' : 'bottle' + Math.floor(Math.random() * 8);
    const img = this.add.image(CONV_B.x0 + 6, CONV_B.y, tex).setOrigin(0.5, 1).setDepth(30);
    const it: Item = { img, x: CONV_B.x0 + 6, y: CONV_B.y, vx: 0, vy: 0, kind, fl, state: 'belt' };
    this.items.push(it); return it;
  }
  clearJam() {
    this.jam = false; this.jamDone = true; SFX.honk(1.5); SFX.valve(); this.fx.sparkle(CONV_B.x1 - 20, CONV_B.y - 40, 10, C.gold0);
    this.jamImg?.destroy(); this.jamNeedle?.destroy(); this.jamImg = null; this.jamNeedle = null;
    this.game.events.emit('hud:toast', 'CONVEYOR UNJAMMED!', C.gold0); this.dave.say('NICE HONK!', 1200);
  }
  launchGold(it: Item) {
    it.state = 'fly'; this.goose.playOnce('honk'); SFX.honk(1.3); SFX.whoosh();
    this.tweens.add({ targets: it.img, x: DOCK.x1 - 20, y: DOCK.y - 10, angle: 360, duration: 900, ease: 'Sine.InOut', onComplete: () => { it.state = 'gone'; it.img.setAngle(0).setDepth(13); this.fx.confetti(it.img.x, it.img.y - 10, 20); this.nextDelivery(); } });
  }
  exit() {
    if (this.exiting) return; this.exiting = true;
    SFX.door();
    GS.persistRun();
    this.registry.set('fromStockroom', true);
    this.levelClear('Store', { title: 'STOCK-UP COMPLETE!', delay: 2600 });
  }

  // ------------------------------------------------------------------ simulation
  stepLevel(dt: number) {
    const g = this.goose, b = g.body;
    // lift
    const prev = this.liftY;
    const sp = 70;
    if (Math.abs(this.liftTarget - this.liftY) > 0.5) this.liftY += Math.sign(this.liftTarget - this.liftY) * Math.min(sp * dt, Math.abs(this.liftTarget - this.liftY));
    this.liftPlat.y = this.liftY; this.liftPlat.dy = this.liftY - prev; this.liftPlat.dx = 0;
    // pushing big boxes / the cart
    const push = (bx: BigBox, w: number, minX: number, maxX: number) => {
      if (bx.done || !b.onGround) return;
      const p = bx.plat;
      const vert = Math.abs(b.y + b.h - (p.y + p.h)) < 4;
      const right = vert && b.x < p.x && b.x + b.w >= p.x - 3 && Controls.down('right');
      const left = vert && b.x > p.x && b.x <= p.x + p.w + 3 && Controls.down('left');
      const dir = right ? 1 : left ? -1 : 0;
      if (!dir) return;
      const nx = Math.max(minX, Math.min(maxX, p.x + dir * 60 * dt));
      p.x = nx; bx.img.x = nx + w / 2;
    };
    for (const bx of this.bigs) push(bx, 30, RACK_X - 10, BAY_X - 50);
    if (this.part === 2 && this.delivery === 1 && !this.cartDone) push(this.cart, 40, 560, 790);
  }
  frameLevel(dt: number) {
    const g = this.goose;
    this.conveyorA.tilePositionX -= this.part === 1 ? dt * 30 : 0;
    this.conveyorB.tilePositionX -= this.jam ? 0 : dt * this.beltSpeed * 0.7;
    this.liftHead.y = Math.round(this.liftY); this.liftShaft.height = Math.max(1, F - Math.round(this.liftY) - 10);
    // carried in the beak: the box hangs just in front of the beak tip (never over the head)
    if (this.carried) { const tip = g.x + (g.facing > 0 ? 17 : -15); this.carried.img.setOrigin(0.5, 0).setScale(0.75).setPosition(Math.round(tip + g.facing * 5), Math.round(g.y - 31 + Math.abs(Math.sin(this.elapsed * 8)))).setDepth(g.sprite.depth + 1); }
    if (this.timerT) this.timerT.setText(this.part === 2 ? `${Math.max(0, Math.ceil(this.timeLimit - this.t2))}S${this.t2 <= this.bonusLimit && !this.overtime ? ' *' : ''}` : '');
    if (this.part === 1) this.frameShelves(dt);
    if (this.part === 2) this.frameTruck(dt);
    this.frameLift(dt);
    // falling bottles
    for (const f of this.fallers) {
      f.t += dt;
      if (f.t < 0.8) { f.warn.setAlpha(0.3 + Math.sin(f.t * 30) * 0.3); continue; }
      f.vy += 900 * dt; f.y += f.vy * dt; f.img.setPosition(f.x, f.y).setAngle(f.t * 400);
      if (g.mode === 'play' && Math.abs(f.x - g.x) < 10 && f.y > g.y - 30 && f.y < g.y) { this.damage(f.x); this.dropCarried('BONK!'); f.y = F + 99; }
      if (f.y >= F - 4) { SFX.crash(); this.fx.drops(f.x, F - 4, C.red0, 8); f.img.destroy(); f.warn.destroy(); f.t = -99; }
    }
    this.fallers = this.fallers.filter((f) => f.t > -1);
    // rolling boxes
    for (const r of this.rollers) {
      r.x += r.vx * dt; r.img.x = r.x; r.img.angle += r.vx * dt * 4;
      if (g.mode === 'play' && this.invuln <= 0 && Math.abs(r.x - g.x) < 12 && g.y > F - 14) { this.damage(r.x); this.dropCarried('OOF!'); }
    }
    this.rollers = this.rollers.filter((r) => { const keep = r.x > BAY_X + 20 && r.x < 900; if (!keep) { this.fx.dust(r.x, F, 4); r.img.destroy(); } return keep; });
  }
  frameShelves(dt: number) {
    this.elapsedStock += dt;
    // Dave's conveyor feeds a box (flavours that are still needed)
    if (!this.beltA && !this.carried) {
      this.beltT -= dt;
      if (this.beltT <= 0) {
        const need = this.slots.filter((s) => !s.filled).map((s) => s.fl);
        if (need.length) {
          const fl = need[Math.floor(Math.random() * need.length)];
          const img = this.add.image(14, F - 12, 'box_' + fl).setOrigin(0.5, 1).setDepth(29);
          this.beltA = { img, x: 14, y: F - 12, vx: 0, vy: 0, kind: 'box', fl, state: 'belt' };
          this.dave.act('point', 0.6);
        }
      }
    }
    if (this.beltA && this.beltA.state === 'belt') { this.beltA.x += 30 * dt; this.beltA.img.x = this.beltA.x; if (this.beltA.x >= 76) { this.beltA.state = 'wait'; SFX.clunk(); } }
    // highlight the matching slots
    for (const s of this.slots) if (!s.filled) s.glow.setAlpha(this.carried && this.carried.fl === s.fl ? 0.35 + Math.sin(this.elapsed * 6) * 0.2 : 0);
    // big boxes into bays
    for (const bx of this.bigs) if (!bx.done) for (const bay of this.bays) if (Math.abs(bx.plat.x + 15 - bay) < 5) { bx.done = true; bx.plat.x = bay - 15; bx.img.x = bay; this.stockOne(bay, F - 30); this.bays = this.bays.filter((x) => x !== bay); break; }
    // falling syrup bottles
    this.fallT -= dt;
    if (this.fallT <= 0) {
      this.fallT = 3.2 + Math.random() * 2;
      const x = RACK_X + 20 + Math.random() * (RACK_W - 40);
      const warn = this.add.image(x, F + 1, 'shadow32').setDepth(18).setScale(0.6, 0.6).setAlpha(0);
      this.fallers.push({ img: this.add.image(x, 150, 'bottle' + Math.floor(Math.random() * 8)).setDepth(45), warn, x, y: 150, vy: 0, t: 0 });
    }
  }
  frameLift(dt: number) {
    const g = this.goose;
    const on = g.body.ground === this.liftPlat;
    if (this.part !== 1) { this.liftTarget = on ? this.liftTarget : F - 6; return; }
    if (on && !this.liftBusy && Math.abs(this.liftY - this.liftTarget) < 1) {
      this.liftStand += dt;
      if (this.liftStand > 0.35) {
        this.liftStand = 0;
        const stops = [F - 6, ...SHELVES];
        const cur = stops.reduce((bi, y, i) => (Math.abs(y - this.liftY) < Math.abs(stops[bi] - this.liftY) ? i : bi), 0);
        let want = Math.min(stops.length - 1, cur + 1);
        if (this.carried) { const s = this.slots.find((sl) => !sl.filled && sl.fl === this.carried!.fl); if (s) want = stops.indexOf(s.y); }
        if (want === cur) want = cur === 0 ? 1 : 0;
        if (this.liftFirst) {
          this.liftFirst = false; this.liftBusy = true; this.liftTarget = SHELVES[2] - 30;
          this.gerry.lastLine = 0; this.gerry.say('GOING UP! WAIT... WRONG BUTTON!', 2400); this.gerry.act('shock', 1.2);
          this.time.delayedCall(2600, () => { this.liftTarget = stops[want]; this.liftBusy = false; this.gerry.act('point', 0.8); });
        } else { this.liftTarget = stops[want]; this.gerry.act('point', 0.5); SFX.clunk(); }
      }
    } else if (!on) {
      this.liftStand = 0;
      this.liftIdle += dt; if (this.liftIdle > 2 && !this.liftBusy) this.liftTarget = F - 6;
    }
    if (on) this.liftIdle = 0;
  }
  frameTruck(dt: number) {
    const g = this.goose;
    this.t2 += dt;
    if (this.t2 > this.timeLimit) { this.t2 = this.timeLimit - 30; this.overtime = true; this.gerry.lastLine = 0; this.gerry.say('OVERTIME! THE DRIVER CAN WAIT 30 SECONDS. MAYBE.', 2600); }
    // the wobbly stack sheds rolling boxes
    this.stackWob += dt; this.stack.setAngle(Math.sin(this.stackWob * 7) * (this.rollT < 1 ? 5 : 1.2));
    this.rollT -= dt;
    if (this.rollT <= 0 && this.delivery !== 1) {
      this.rollT = this.delivery === 2 ? 3.2 : 5 + Math.random() * 2;
      const img = this.add.image(788, F, 'box_' + (['cola', 'cream', 'cherry'] as Flavor[])[Math.floor(Math.random() * 3)]).setOrigin(0.5, 0.9).setDepth(31);
      this.rollers.push({ img, x: 788, vx: -(70 + this.delivery * 25) });
      SFX.clunk();
    }
    // delivery 1: boxes on the belt, with one jam
    if (this.delivery === 0) {
      if (!this.items.some((i) => i.kind === 'box' && i.state !== 'gone') && !this.carried) this.spawnBeltB('box', this.order[this.orderIdx]);
      if (this.orderIdx === 1 && !this.jamDone && !this.jam && this.items.some((i) => i.state === 'belt' && i.x > CONV_B.x0 + 60)) {
        this.jam = true; SFX.clunk(); SFX.hiss(1); shake(this, 200, 0.004);
        this.jamImg = this.add.image(CONV_B.x1 - 20, CONV_B.y - 40, 'jamGauge').setDepth(46);
        this.jamNeedle = this.add.rectangle(CONV_B.x1 - 36, CONV_B.y - 34, 2, 10, C.ink).setDepth(47);
        this.dave.lastLine = 0; this.dave.say('THE BELT JAMMED! HONK WHEN THE NEEDLE HITS GREEN!', 2600);
      }
    }
    if (this.jam && this.jamNeedle) { this.jamT += dt; this.jamNeedle.x = CONV_B.x1 - 36 + (Math.sin(this.jamT * 2.2) * 0.5 + 0.5) * 32; for (let i = 0; i < 1; i++) if (Math.random() < 0.1) this.fx.sparkle(CONV_B.x1 - 10, CONV_B.y - 6, 1, C.gold0); }
    // delivery 2: push the cart onto the trident marker
    if (this.delivery === 1 && !this.cartDone && this.cart.plat.x + 20 > 790) {
      this.cartDone = true; SFX.valve(); this.dave.act('catch', 1);
      this.tweens.add({ targets: this.cart.img, y: DOCK.y, duration: 800, ease: 'Sine.Out', onComplete: () => { this.tweens.add({ targets: this.cart.img, x: DOCK.x1 - 20, duration: 700, onComplete: () => { this.cart.img.setDepth(13); this.nextDelivery(); } }); } });
      this.cart.plat.active = false; this.cart.plat.x = -999;
    }
    // delivery 3: the rush — bottles fly off the belt end; catch 5, then the golden last box
    if (this.delivery === 2) {
      this.rushT += dt; this.spawnB -= dt;
      if (this.spawnB <= 0 && this.caught < 5) { this.spawnB = 1.1; this.spawnBeltB('bottle'); }
      if (this.caught >= 5 && !this.items.some((i) => i.kind === 'gold')) { const it = this.spawnBeltB('gold'); it.img.setScale(0.8); this.gerry.lastLine = 0; this.gerry.say('LAST BOX! MAKE IT COUNT!', 2400); this.beltSpeed = 40; }
    }
    // belt items
    for (const it of this.items) {
      if (it.state === 'belt' && !this.jam) {
        it.x += this.beltSpeed * dt; it.img.x = it.x;
        if (it.x >= CONV_B.x1 - 8) {
          if (it.kind === 'bottle') { it.state = 'fly'; it.vx = 60 + Math.random() * 60; it.vy = -160 - Math.random() * 60; SFX.bounce(); }
          else { it.state = 'wait'; it.x = CONV_B.x1 - 8; }
        }
      } else if (it.state === 'fly' && it.kind === 'bottle') {
        it.vy += 600 * dt; it.x += it.vx * dt; it.y += it.vy * dt; it.img.setPosition(it.x, it.y).setAngle(it.img.angle + 600 * dt);
        if (Math.abs(it.x - g.x) < 14 && it.y > g.y - 40 && it.y < g.y + 4) {
          it.state = 'gone'; this.caught++; SFX.collect(this.caught); GS.addScore(150);
          this.fx.sparkle(it.x, it.y, 6, C.gold0); emote(this, g.x, g.y - 44, `CATCH ${this.caught}/5`, { life: 600 });
          const im = it.img; this.tweens.add({ targets: im, x: DOCK.x1 - 20, y: DOCK.y - 8, duration: 500, onComplete: () => im.setDepth(13) });
        } else if (it.y >= F - 2) { it.state = 'gone'; SFX.crash(); this.fx.drops(it.x, F - 2, C.red0, 6); it.img.destroy(); }
      }
    }
    // pick up the waiting delivery-1 box from the belt end
    this.items = this.items.filter((i) => i.state !== 'gone' || (i.img.active && i.kind !== 'box'));
    void g;
  }
  onRespawn() { if (this.carried) this.dropCarried('OOPS'); }
  rectOf(o: Phaser.GameObjects.Image): Rect { return { x: o.x - o.displayWidth / 2, y: o.y - o.displayHeight, w: o.displayWidth, h: o.displayHeight }; }
}
