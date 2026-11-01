/**
 * LEVEL 2b — THE EXPERIMENTAL SODA DIMENSION.
 * Floating fruit islands, citrus wheels, collapsing foam, geysers, a syrup river current,
 * bubble elevators, a hidden recipe chamber, 5 enemy types, 3 checkpoints with flavour taps.
 */
import Phaser from 'phaser';
import { C } from '../art/palette';
import { LevelScene } from '../levels/LevelScene';
import { Platform } from '../systems/physics';
import { FizzSprite, SyrupSlug, BottleBot, FoamMonster, FruitFlyer } from '../entities/Enemies';
import { emote } from '../entities/Emote';
import { complete, unlock, StageId } from '../systems/save';
import { flash } from '../systems/camfx';
import { SFX } from '../audio/sfx';
import { PowerId } from '../data/recipes';

const W = 3600, H = 480;
interface Wheel { cx: number; cy: number; r: number; a: number; pads: { p: Platform; img: Phaser.GameObjects.Image }[]; img: Phaser.GameObjects.Image }
interface Collapse { p: Platform; img: Phaser.GameObjects.Image; x: number; y: number; t: number; state: 'idle' | 'shake' | 'gone' }
interface Geyser { x: number; base: number; h: number; on: boolean; phase: number; col: Phaser.GameObjects.TileSprite }
interface Mover { p: Platform; img: Phaser.GameObjects.Image; x: number; y0: number; y1: number; t: number }

export class DimensionScene extends LevelScene {
  stage: StageId = 'dimension';
  wheels: Wheel[] = []; collapses: Collapse[] = []; geysers: Geyser[] = []; movers: Mover[] = [];
  taps: { x: number; y: number; i: number }[] = [];
  elevT = 0; t = 0; exiting = false;
  layers: Phaser.GameObjects.TileSprite[] = [];
  constructor() { super('Dimension'); }

  create() {
    this.levelName = 'THE SODA DIMENSION';
    this.initLevel({ w: W, h: H, floor: H + 100, bg: 0x2a1450, spawn: { x: 80, y: 400 } });
    this.wheels = []; this.collapses = []; this.geysers = []; this.movers = []; this.taps = []; this.exiting = false; this.layers = [];
    this.add.image(0, 0, 'dimSky').setOrigin(0).setScrollFactor(0).setDepth(0);
    this.layers.push(this.add.tileSprite(0, 0, 480, 270, 'dimFar').setOrigin(0).setScrollFactor(0).setDepth(1));
    this.layers.push(this.add.tileSprite(0, 0, 480, 270, 'dimMid').setOrigin(0).setScrollFactor(0).setDepth(2));
    this.add.particles(0, 0, 'bubble16', { x: { min: 0, max: 480 }, y: 290, lifespan: 6000, speedY: { min: -40, max: -15 }, scale: { min: 0.2, max: 0.8 }, frequency: 200, alpha: { start: 0.8, end: 0.1 } }).setScrollFactor(0).setDepth(3);
    this.addPlatform(-40, 0, 40, H, 'solid', 'wallL'); this.addPlatform(W, 0, 40, H, 'solid', 'wallR');
    this.build();
    this.finishInit({ music: 'dimension' });
    this.buildPrompts();
    unlock('dimension');
    this.arrival();
    (window as unknown as { __SIMPS: Record<string, unknown> }).__SIMPS.dim = this;
  }

  // ---------------------------------------------------------------- pieces
  island(x: number, top: number, w: 64 | 96 | 140) { this.addPlatform(x + 2, top, w - 4, 6, 'oneway', 'island'); this.add.image(x, top, 'island' + w).setOrigin(0).setDepth(25); }
  cherry(x: number, top: number) { this.addPlatform(x, top, 64, 6, 'oneway', 'island'); this.add.image(x, top, 'cherryIsland').setOrigin(0).setDepth(25); }
  bridge(x0: number, x1: number, y: number) { this.addPlatform(x0, y, x1 - x0, 6, 'oneway', 'bridge'); this.add.tileSprite(x0, y, x1 - x0, 9, 'rainbow').setOrigin(0).setDepth(25); }
  wheel(cx: number, cy: number) {
    const img = this.add.image(cx, cy, 'citrusWheel').setDepth(22);
    const pads = [0, 1, 2, 3].map(() => ({ p: this.addPlatform(0, 0, 30, 6, 'oneway', 'wheel'), img: this.add.image(0, 0, 'citrusPad').setDepth(26) }));
    this.wheels.push({ cx, cy, r: 50, a: 0, pads, img });
  }
  foam(x: number, y: number) { const p = this.addPlatform(x - 20, y, 40, 6, 'oneway', 'collapse'); const img = this.add.image(x, y + 6, 'foamPad').setDepth(25); this.collapses.push({ p, img, x, y, t: 0, state: 'idle' }); }
  geyser(x: number, base: number, h: number, phase = 0) {
    this.add.image(x, base + 6, 'geyserBase').setDepth(24);
    const col = this.add.tileSprite(x, base, 16, h, 'geyserCol').setOrigin(0.5, 1).setDepth(23).setAlpha(0);
    const gz: Geyser = { x, base, h, on: false, phase, col };
    this.geysers.push(gz);
    this.hazards.push({ rect: { x: x - 10, y: base - h, w: 20, h }, kind: 'jet', strength: 460, active: () => gz.on });
  }
  river(x0: number, x1: number, y: number) {
    this.addPlatform(x0, y, x1 - x0, 8, 'oneway', 'river');
    const ts = this.add.tileSprite(x0, y, x1 - x0, 16, 'syrupRiver').setOrigin(0).setDepth(25);
    this.tweens.add({ targets: ts, tilePositionX: -64, duration: 1600, repeat: -1 });
    this.hazards.push({ rect: { x: x0, y: y - 24, w: x1 - x0, h: 26 }, kind: 'push', strength: 34 }, { rect: { x: x0, y: y - 24, w: x1 - x0, h: 26 }, kind: 'slow' });
  }
  mover(x: number, y0: number, y1: number) { const p = this.addPlatform(x - 22, y0, 44, 5, 'oneway', 'mover'); const img = this.add.image(x, y0, 'liftHead').setOrigin(0.5, 0).setDepth(26); this.movers.push({ p, img, x, y0, y1, t: 0 }); }
  tap(x: number, y: number) { this.add.image(x, y, 'dimTap').setOrigin(0.5, 1).setDepth(26); this.taps.push({ x, y, i: 0 }); }

  build() {
    this.island(20, 400, 140); this.addDropLine(60, 140, 384, 4);
    this.cherry(190, 386);
    this.island(290, 372, 96); this.enemies.push(new FizzSprite(this, 338, 372, 302, 376));
    this.bridge(420, 700, 360); this.enemies.push(new SyrupSlug(this, 600, 360, 520, 690)); this.addDropLine(430, 690, 344, 8);
    this.island(500, 250, 64); this.addPickup('star', 532, 228); this.addDropLine(510, 554, 236, 3);
    this.wheel(790, 330);
    this.island(860, 320, 140); this.enemies.push(new BottleBot(this, 940, 320, 885, 990)); this.addCheckpoint(986, 320); this.tap(876, 320);
    this.river(1040, 1320, 380); this.addDropLine(1060, 1300, 362, 8);
    this.geyser(1140, 380, 210, 0); this.geyser(1250, 380, 210, 1.2);
    this.island(1170, 220, 64); this.addPickup('leaf', 1202, 200); this.addPickup('star', 1140, 150);
    this.enemies.push(new FruitFlyer(this, 1190, 290));
    for (const [x, y] of [[1350, 350], [1410, 330], [1470, 310], [1530, 330]] as [number, number][]) this.foam(x, y);
    this.island(1580, 330, 140); this.enemies.push(new FoamMonster(this, 1650, 330)); this.enemies.push(new FizzSprite(this, 1700, 330, 1600, 1712));
    this.wheel(1800, 300); this.addPickup('star', 1800, 300);
    this.island(1880, 310, 96); this.addCheckpoint(1958, 310); this.tap(1898, 310);
    // hidden recipe chamber (drop down off the right side)
    this.island(2010, 440, 140); this.addPickup('card', 2060, 420, 'pink_fizz'); this.addPickup('bottle', 2120, 420); this.geyser(2130, 440, 230, 0.6);
    this.add.image(2090, 440, 'signDelivery').setVisible(false);
    // climb
    this.island(1996, 266, 64); this.island(2076, 228, 64); this.island(2156, 190, 64);
    this.enemies.push(new FruitFlyer(this, 2070, 160), new FruitFlyer(this, 2200, 130));
    this.addDropLine(2010, 2200, 170, 6);
    this.bridge(2240, 2570, 190); this.addDropLine(2250, 2560, 174, 10);
    this.enemies.push(new BottleBot(this, 2320, 190, 2245, 2400), new BottleBot(this, 2480, 190, 2420, 2560), new FizzSprite(this, 2400, 190, 2380, 2440));
    this.addPickup('leaf', 2566, 150);
    this.mover(2620, 190, 344); this.addPickup('badge', 2620, 130);
    this.island(2680, 350, 140); this.addCheckpoint(2790, 350); this.tap(2700, 350);
    for (const [x, y] of [[2850, 340], [2910, 320]] as [number, number][]) this.foam(x, y);
    this.wheel(3010, 310); this.addPickup('leaf', 3010, 312);
    this.island(3090, 320, 96); this.enemies.push(new FoamMonster(this, 3140, 320));
    this.island(3220, 330, 140); this.enemies.push(new SyrupSlug(this, 3290, 330, 3230, 3350), new FizzSprite(this, 3320, 330, 3240, 3350));
    this.island(3380, 330, 140); this.addDropLine(3230, 3400, 312, 6);
    this.add.image(3480, 332, 'portalBottle').setOrigin(0.5, 1).setDepth(24);
    this.add.image(3480, 270, 'glow128').setTint(C.pur0).setBlendMode(Phaser.BlendModes.ADD).setAlpha(0.35).setDepth(23);
    this.add.sprite(3400, 330, 'flag0').setOrigin(0, 1).setDepth(26).play('flag');
  }
  buildPrompts() {
    for (const tp of this.taps) this.addPrompt(this.key('use'), () => Math.abs(this.goose.x - tp.x) < 26 && Math.abs(this.goose.y - tp.y) < 8, () => false, () => ({ x: tp.x, y: tp.y - 52 }));
  }
  arrival() {
    const g = this.goose;
    this.phase = 'cutscene'; g.mode = 'script';
    g.body.x = 80 - 7; g.body.y = -60;
    g.sprite.setAngle(0).setScale(1);
    this.tweens.addCounter({ from: 0, to: 1, duration: 1300, ease: 'Quad.In', onUpdate: (tw: Phaser.Tweens.Tween) => { const k = tw.getValue() as number; g.body.y = -60 + k * (400 - 22 + 60); g.sprite.setAngle(k * 720); g.syncSprite(0.016); },
      onComplete: () => { g.sprite.setAngle(0); g.squash(1.4, 0.6); SFX.land(); this.fx.dust(g.x, g.y, 10); g.playLoop('hurt'); this.say('...HONK?', g.x, g.y - 46, 1400); } });
    flash(this, 400, 255, 200, 255);
    this.time.delayedCall(2600, () => { g.mode = 'play'; g.playLoop('idle'); this.phase = 'play'; this.game.events.emit('hud:toast', 'THE SODA DIMENSION', C.pink, 'STOMP, HONK OR SHOOT THE FIZZ CREATURES'); });
  }
  onInteract() {
    const g = this.goose;
    const tp = this.taps.find((t) => Math.abs(g.x - t.x) < 26 && Math.abs(g.y - t.y) < 8);
    if (!tp) return false;
    const ids: PowerId[] = ['cola', 'cream', 'cherry'];
    const id = ids[tp.i++ % 3];
    g.playOnce('drink'); SFX.pour(); SFX.gulp();
    this.time.delayedCall(500, () => this.setPower(id));
    emote(this, tp.x, tp.y - 46, ['COLA!', 'CREAM SODA!', 'BLACK CHERRY!'][(tp.i - 1) % 3], { life: 900 });
    return true;
  }
  onRespawn() { for (const c of this.collapses) { c.state = 'idle'; c.t = 0; c.p.active = true; c.img.setAlpha(1).setScale(1).setPosition(c.x, c.y + 6); } }

  stepLevel(dt: number) {
    this.t += dt;
    for (const w of this.wheels) {
      w.a += dt * 0.7;
      w.pads.forEach((pd, i) => {
        const a = w.a + i * Math.PI / 2;
        const nx = w.cx + Math.cos(a) * w.r - 15, ny = w.cy + Math.sin(a) * w.r;
        pd.p.dx = nx - pd.p.x; pd.p.dy = ny - pd.p.y; pd.p.x = nx; pd.p.y = ny;
      });
    }
    for (const m of this.movers) { m.t += dt; const ny = m.y0 + (m.y1 - m.y0) * (1 - Math.cos(m.t * Math.PI * 2 / 5)) / 2; m.p.dy = ny - m.p.y; m.p.y = ny; }
    for (const c of this.collapses) {
      const on = this.goose.body.ground === c.p && this.goose.body.onGround;
      if (c.state === 'idle' && on) { c.state = 'shake'; c.t = 0; SFX.foam(); }
      if (c.state === 'shake') { c.t += dt; if (c.t > 0.55) { c.state = 'gone'; c.t = 0; c.p.active = false; this.fx.bubbles(c.x, c.y, 6); SFX.pop(1.3); } }
      else if (c.state === 'gone') { c.t += dt; if (c.t > 3) { c.state = 'idle'; c.p.active = true; } }
    }
    for (const gz of this.geysers) { const cyc = (this.t + gz.phase) % 3.2; gz.on = cyc > 1.6 && cyc < 2.8; }
  }
  frameLevel(dt: number) {
    const cam = this.cameras.main;
    this.layers[0].tilePositionX = cam.scrollX * 0.15; this.layers[1].tilePositionX = cam.scrollX * 0.35;
    for (const w of this.wheels) { w.img.setRotation(w.a); w.pads.forEach((pd) => pd.img.setPosition(Math.round(pd.p.x + 15), Math.round(pd.p.y + 3))); }
    for (const m of this.movers) m.img.y = Math.round(m.p.y);
    for (const c of this.collapses) {
      if (c.state === 'shake') c.img.setPosition(c.x + Math.sin(c.t * 60) * 1.5, c.y + 6);
      else if (c.state === 'gone') c.img.setAlpha(Math.max(0, 1 - c.t * 3)).setScale(1 + c.t);
      else c.img.setAlpha(1).setScale(1).setPosition(c.x, c.y + 6);
    }
    for (const gz of this.geysers) {
      gz.col.setAlpha(gz.on ? 0.9 : Math.max(0, gz.col.alpha - dt * 3)); gz.col.tilePositionY += 200 * dt;
      gz.col.height = gz.on ? gz.h : gz.h * 0.15;
      if (gz.on && Math.random() < dt * 20) this.fx.fizz(gz.x, gz.base - Math.random() * gz.h, 3);
      if (gz.on && Math.random() < dt * 0.8 && Math.abs(gz.x - this.goose.x) < 240) SFX.fizz(0.4, 0.6);
    }
    this.elevT -= dt;
    if (this.elevT <= 0) { this.elevT = 1.8; this.bubbles.spawn(470, H - 4, 15, 'rise', { vy: -32, maxStomps: 3, tint: 0xf0e0ff }); }
    // exit portal
    const g = this.goose;
    if (!this.exiting && g.x > 3462 && g.x < 3500 && g.y > 300 && this.phase === 'play') {
      this.exiting = true; this.phase = 'cutscene'; g.mode = 'ride'; g.ride = { x: 3480, y: 330 };
      SFX.portal(); this.tweens.add({ targets: g.sprite, angle: 540, scale: 0, duration: 1100 });
      complete('dimension'); unlock('carb');
      this.time.delayedCall(1200, () => this.levelClear('BossCarb', { title: 'SODA DIMENSION CLEAR!', delay: 3200 }));
    }
  }
}
