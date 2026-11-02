/**
 * FIZZ-O-MATIC + BUBBLE TROUBLE.
 * Stage 0 idle → honk → 1 rumbling → honk → 2 eruption: bubbles everywhere.
 * Pulling the trident valve on the mezzanine triggers the finale ride.
 */
import Phaser from 'phaser';
import type { StoreScene } from '../scenes/StoreScene';
import { SFX } from '../audio/sfx';
import { MUSIC } from '../audio/music';
import { FLOOR, L } from './layout';
import { FOUNTAIN_SPOUTS } from '../art/props';
import { C } from '../art/palette';
import { emote } from '../entities/Emote';
import { shake, flash } from '../systems/camfx';

const FX0 = L.fountain.x, TOPY = FLOOR - L.fountain.h;
export class Fountain {
  s: StoreScene;
  stage = 0;
  body: Phaser.GameObjects.Image;
  needle: Phaser.GameObjects.Image;
  crest: Phaser.GameObjects.Image;
  crestGlow: Phaser.GameObjects.Image;
  wheel: Phaser.GameObjects.Image;
  needleA = -2.2; needleTarget = -2.2;
  t = 0; spoutT = 0; ventT = 0; spoutIdx = 0; ventIdx = 0;
  pressure = 0;
  hoverTimers: number[] = [0, 0];
  hoverRefs: (ReturnType<StoreScene['bubbles']['spawn']>)[] = [null, null];
  shake = 0;
  finaleStarted = false;
  constructor(s: StoreScene) {
    this.s = s;
    this.body = s.add.image(FX0, FLOOR, 'fountain').setOrigin(0, 1).setDepth(25);
    s.add.image(FX0 + 109, FLOOR - 14, 'gauge').setDepth(26);
    this.needle = s.add.image(FX0 + 109, FLOOR - 14, 'needle').setOrigin(0.5, 0.9).setDepth(27).setRotation(this.needleA);
    this.crestGlow = s.add.image(FX0 + 64, TOPY - 6, 'glow64').setTint(C.red1).setBlendMode(Phaser.BlendModes.ADD).setAlpha(0.15).setDepth(24);
    this.crest = s.add.image(FX0 + 64, TOPY + 8, 'trident22').setOrigin(0.5, 1).setDepth(26);
    // trident valve station on the mezzanine
    s.add.image(L.valve.x, L.mezz.y, 'valvePost').setOrigin(0.5, 1).setDepth(31);
    this.wheel = s.add.image(L.valve.x, L.mezz.y - 56, 'valveWheel').setDepth(32);
  }
  get cx() { return FX0 + L.fountain.w / 2; }
  onHonk(x: number) {
    if (this.stage >= 2 || Math.abs(x - this.cx) > 120) return;
    this.stage++;
    const s = this.s;
    if (this.stage === 1) {
      SFX.fountainStart(1); SFX.fizz(1, 1);
      MUSIC.setIntensity(1);
      this.needleTarget = -0.8; this.shake = 1;
      shake(s, 300, 0.003);
      for (let i = 0; i < 6; i++) s.time.delayedCall(i * 120, () => s.fx.steam(FX0 + 20 + Math.random() * 90, TOPY + 10, 2));
      emote(s, this.cx, TOPY - 14, '?!', { life: 1100, color: C.red1 });
      s.nearestPerson(this.cx, 260)?.say('UH OH...', 1600);
    } else {
      SFX.fountainStart(2); SFX.hiss(1.4);
      this.needleTarget = 1.6; this.shake = 2.5;
      shake(s, 900, 0.006);
      s.time.delayedCall(1300, () => this.erupt());
    }
  }
  erupt() {
    const s = this.s;
    this.stage = 2;
    SFX.bigPop(); MUSIC.setIntensity(2);
    flash(s, 180, 255, 255, 255);
    shake(s, 500, 0.008);
    s.bubbles.spawn(this.cx + 10, TOPY + 40, 46, 'drift', { vx: 45, vy: -30, maxStomps: 99, life: 6 });
    for (const sx of FOUNTAIN_SPOUTS) { s.fx.bubbles(FX0 + sx, FLOOR - 40, 10); s.fx.drops(FX0 + sx, FLOOR - 40, [C.cola0, C.crm1, C.chr0][FOUNTAIN_SPOUTS.indexOf(sx)], 14); }
    for (let i = 0; i < 4; i++) s.fx.splat(FX0 + 140 + i * 40 + Math.random() * 20, FLOOR + 2, [C.cola1, C.crm2, C.chr1][i % 3]);
    s.lift.running = true;
    s.bottles.forEach((b) => b.jiggle(1.5));
    s.people.forEach((p) => { if (!p.staff && Math.abs(p.x - this.cx) < 500) { p.setState(Math.random() < 0.5 ? 'cheer' : 'laugh', 2); } });
    SFX.cheer();
    s.game.events.emit('hud:toast', 'BUBBLE TROUBLE!', C.blu0);
    this.spawnHover(0); this.spawnHover(1);
  }
  spawnHover(i: number) {
    const [x, y] = L.hovers[i];
    this.hoverRefs[i] = this.s.bubbles.spawn(x, y, 17, 'hover', { maxStomps: 3, tint: i ? 0xffe6f0 : 0xe6fbff });
  }
  update(dt: number) {
    this.t += dt;
    // needle physics-ish
    const wild = this.stage === 2 && !this.finaleStarted ? Math.sin(this.t * 9) * 0.5 + Math.sin(this.t * 23) * 0.2 : this.stage === 1 ? Math.sin(this.t * 13) * 0.15 : 0;
    this.needleA += (this.needleTarget + wild - this.needleA) * Math.min(1, dt * 6);
    this.needle.setRotation(this.needleA);
    // shake
    this.shake = Math.max(this.stage === 2 ? 0.6 : this.stage === 1 ? 0.35 : 0, this.shake - dt);
    this.body.x = FX0 + (this.shake > 0 ? Math.round(Math.sin(this.t * 60) * this.shake) : 0);
    this.crestGlow.setAlpha(this.stage === 0 ? 0.12 : 0.25 + Math.abs(Math.sin(this.t * (this.stage === 2 ? 8 : 4))) * 0.45);
    // ambient tank bubbles
    if (Math.random() < dt * (2 + this.stage * 5)) this.s.fx.fizz(FX0 + 20 + Math.floor(Math.random() * 3) * 33 + Math.random() * 20, TOPY + 60 + Math.random() * 30, 2);
    if (this.stage === 1 && Math.random() < dt * 2) this.s.fx.steam(FX0 + 30 + Math.random() * 70, TOPY + 12, 1);
    if (this.stage < 2) return;
    // ---- bubble trouble ----
    if (!this.finaleStarted) this.pressure = Math.min(0.92, this.pressure + dt * 0.03);
    this.s.game.events.emit('hud:pressure', this.finaleStarted ? 1 : this.pressure);
    this.spoutT -= dt; this.ventT -= dt;
    if (this.spoutT <= 0) {
      this.spoutT = 1.15;
      const sx = FX0 + FOUNTAIN_SPOUTS[this.spoutIdx++ % 3];
      const tint = [0xf3e4d8, 0xfff6dc, 0xffe0ea][this.spoutIdx % 3];
      this.s.bubbles.spawn(sx, FLOOR - 36, 11 + Math.random() * 5, 'drift', { vx: 50 + Math.random() * 40, vy: -40, tint, maxStomps: 2, life: 9 });
      this.s.fx.drops(sx, FLOOR - 40, C.bub2, 3);
    }
    if (this.ventT <= 0) {
      this.ventT = 1.9;
      const vx = L.vents[this.ventIdx++ % 2];
      this.s.bubbles.spawn(vx, FLOOR - 14, 16, 'rise', { vy: -24, maxStomps: 3 });
      this.s.fx.fizz(vx, FLOOR - 4, 8);
    }
    for (let i = 0; i < 2; i++) {
      const b = this.hoverRefs[i];
      if (!b || !b.active || b.kind !== 'hover' || Math.abs(b.anchorX - L.hovers[i][0]) > 1) { this.hoverTimers[i] += dt; if (this.hoverTimers[i] > 2.4) { this.hoverTimers[i] = 0; this.spawnHover(i); } }
    }
  }
  nearValve() { const g = this.s.goose; return Math.abs(g.x - L.valve.x) < 40 && Math.abs(g.y - L.mezz.y) < 12; }
  /** Pull the valve → giant bubble ride → freeze-frame. */
  finale() {
    if (this.finaleStarted) return;
    this.finaleStarted = true;
    const s = this.s, g = s.goose;
    s.phase = 'cutscene';
    g.mode = 'script'; g.ride = null; g.body.vx = 0;
    g.face(1);
    g.playOnce('honk'); s.time.delayedCall(140, () => SFX.honk(1.2));
    s.tweens.add({ targets: this.wheel, rotation: Math.PI * 6, duration: 1200, ease: 'Cubic.InOut' });
    SFX.valve();
    this.needleTarget = 2.3; this.shake = 3;
    s.time.delayedCall(500, () => { SFX.hiss(1.6); SFX.rumble(1.2); shake(s, 800, 0.007); for (const sx of FOUNTAIN_SPOUTS) s.fx.bubbles(FX0 + sx, FLOOR - 40, 14); });
    s.time.delayedCall(1300, () => {
      // giant bubble envelops the goose
      const bub = s.add.image(g.x, g.y - 22, 'bubble96').setDepth(47).setScale(0.1).setTint(0xf2fbff);
      SFX.bubble(); SFX.whoosh();
      s.tweens.add({ targets: bub, scale: 0.78, duration: 550, ease: 'Back.Out' });
      g.playLoop('ride');
      const ride = { x: g.x, y: g.y - 3 };
      g.ride = ride; g.mode = 'ride';
      const startY = bub.y, startX = bub.x;
      s.tweens.addCounter({ from: 0, to: 1, delay: 600, duration: 4200, ease: 'Sine.InOut', onUpdate: (tw: Phaser.Tweens.Tween) => {
        const k = tw.getValue() as number;
        bub.y = startY - k * 110; bub.x = startX - k * 40 + Math.sin(k * 9) * 8;
        bub.setTint(Phaser.Display.Color.HSVToRGB((s.time.now / 2500) % 1, 0.12, 1).color);
        ride.x = bub.x; ride.y = bub.y + 22;
      } });
      s.time.delayedCall(900, () => { s.people.forEach((p) => p.cheer()); SFX.cheer(); s.sam.say('GO, GOOSE, GO!', 2500); });
      for (let i = 0; i < 6; i++) s.time.delayedCall(800 + i * 450, () => s.fx.confetti(g.x + (Math.random() - 0.5) * 160, g.y + 60, 18));
      s.time.delayedCall(2600, () => { g.playLoop('celebrate'); SFX.honk(0.9); s.fx.honk(g.x + 10, g.y - 30, 1, true); });
      s.time.delayedCall(3200, () => s.wideShot());
    });
  }
}
