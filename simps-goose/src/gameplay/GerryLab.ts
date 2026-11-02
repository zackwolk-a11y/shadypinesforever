/**
 * SCENE 3 — GERRY'S EXPERIMENTAL FLAVOR LAB (Level 2, deep in the lab).
 * Collect three syrup samples around the lab → pour each into its matching tank →
 * timed honk to carbonate (dodge foam + bouncing bottles) → rainbow soda → SUPER BURP.
 */
import Phaser from 'phaser';
import { C } from '../art/palette';
import type { LevelScene } from '../levels/LevelScene';
import type { Person } from '../entities/Person';
import { emote } from '../entities/Emote';
import { save, update } from '../systems/save';
import { achieve } from '../data/achievements';
import { GS } from '../systems/gamestate';
import { shake } from '../systems/camfx';
import { SFX } from '../audio/sfx';

type Vial = 'lime' | 'blue' | 'mango';
const VNAME: Record<Vial, string> = { lime: 'LEMON LIME', blue: 'BLUE RASPBERRY', mango: 'MANGO' };
const VCOL: Record<Vial, number> = { lime: C.lim1, blue: C.blu1, mango: C.mng1 };
const TANK_ORDER: Vial[] = ['lime', 'blue', 'mango'];

export class GerryLab {
  mx: number; floor: number;
  state: 'idle' | 'collect' | 'carb' | 'brew' | 'done' = 'idle';
  vials: { kind: Vial; img: Phaser.GameObjects.Image; x: number; y: number; got: boolean }[] = [];
  carried: { kind: Vial; img: Phaser.GameObjects.Image } | null = null;
  filled: Record<Vial, boolean> = { lime: false, blue: false, mango: false };
  levels: Phaser.GameObjects.Rectangle[] = [];
  machine: Phaser.GameObjects.Image;
  gauge: Phaser.GameObjects.Graphics | null = null; needle = 0; needleT = 0;
  foams: { img: Phaser.GameObjects.Image; x: number; vx: number; life: number; rect: { x: number; y: number; w: number; h: number } }[] = [];
  bottles: { img: Phaser.GameObjects.Image; x: number; y: number; vx: number; vy: number; life: number }[] = [];
  hazT = 2; t = 0;

  constructor(public s: LevelScene, public gerry: Person, mx: number, floor: number, spots: [number, number][]) {
    this.mx = mx; this.floor = floor;
    this.machine = s.add.image(mx, floor, 'gerryMachine').setOrigin(0.5, 1).setDepth(26);
    s.add.image(mx, floor - 60, 'glow128').setTint(C.red0).setBlendMode(Phaser.BlendModes.ADD).setAlpha(0.15).setDepth(25);
    TANK_ORDER.forEach((k, i) => { const r = s.add.rectangle(this.tankX(i), floor - 30, 20, 44, VCOL[k]).setOrigin(0.5, 1).setDepth(27).setAlpha(0.75).setScale(1, 0); this.levels.push(r); });
    const done = save().owners.gerryLab;
    if (done) { this.state = 'done'; TANK_ORDER.forEach((k) => (this.filled[k] = true)); this.levels.forEach((l) => l.setScale(1, 1)); return; }
    TANK_ORDER.forEach((k, i) => { const [x, y] = spots[i]; const img = s.add.image(x, y - 10, 'vial_' + k).setDepth(38).setVisible(false); this.vials.push({ kind: k, img, x, y: y - 10, got: false }); });
  }
  tankX(i: number) { return this.mx - 34 + i * 34; }
  near() { const g = this.s.goose; return Math.abs(g.x - this.mx) < 80 && g.y > this.floor - 8; }
  talkAll(lines: Parameters<LevelScene['talk']>[0], then?: () => void, note?: [string, string]) { this.s.talk(lines, { gerry: this.gerry }, then, note); }

  start() {
    if (this.state !== 'idle') return;
    this.state = 'collect';
    shake(this.s, 600, 0.004); SFX.rumble(0.6);
    this.s.tweens.add({ targets: this.machine, x: this.mx + 2, duration: 60, yoyo: true, repeat: 8 });
    this.talkAll([
      ['gerry', "GOOSE! PERFECT TIMING. I'VE BEEN TESTING SOMETHING THAT MIGHT BE COMPLETELY BRILLIANT.", 'point'],
      ['gerry', 'OR COMPLETELY DISASTROUS. FIFTY-FIFTY.', 'shock'],
      ['goose', 'HONK?'],
      ['gerry', 'WANT TO HELP ME MAKE THE ULTIMATE SODA?', 'gesture'],
      ['gerry', 'I NEED THREE SYRUP SAMPLES: ONE UP ON THE CATWALK, ONE ABOVE THE STEAM JET, ONE PAST THE SUPER SODA 9000. POUR EACH INTO ITS MATCHING TANK.', 'point'],
    ], () => {
      for (const v of this.vials) { v.img.setVisible(true); this.s.add.image(v.x, v.y, 'glow64').setTint(VCOL[v.kind]).setBlendMode(Phaser.BlendModes.ADD).setAlpha(0.35).setDepth(37); }
      this.s.game.events.emit('hud:toast', "GERRY'S EXPERIMENT", C.red0, 'FIND 3 SYRUP SAMPLES');
    }, ["GERRY'S EXPERIMENT", 'FIND 3 SAMPLES, POUR INTO MATCHING TANKS']);
  }

  onInteract(): boolean {
    if (this.state === 'idle' && this.near()) { this.start(); return true; }
    if (this.state !== 'collect' || !this.carried || !this.near()) return false;
    const g = this.s.goose;
    const i = [0, 1, 2].sort((a, b) => Math.abs(this.tankX(a) - g.x) - Math.abs(this.tankX(b) - g.x))[0];
    const want = TANK_ORDER[i];
    if (this.filled[want]) { emote(this.s, g.x, g.y - 44, 'THAT TANK IS FULL', { life: 800 }); return true; }
    if (want !== this.carried.kind) {
      emote(this.s, g.x, g.y - 44, 'WRONG TANK!', { life: 900 }); SFX.foam(); this.spillFoam(this.tankX(i));
      this.gerry.lastLine = 0; this.gerry.say(`THAT'S ${VNAME[this.carried.kind]}! MATCH THE COLOUR.`, 1800); return true;
    }
    this.filled[want] = true; this.carried.img.destroy(); this.carried = null;
    SFX.pour(); SFX.fizz(0.3, 1.2); this.s.fx.drops(this.tankX(i), this.floor - 70, VCOL[want], 10);
    this.s.tweens.add({ targets: this.levels[i], scaleY: 1, duration: 900 });
    GS.addScore(300);
    const n = TANK_ORDER.filter((k) => this.filled[k]).length;
    this.s.game.events.emit('hud:toast', `TANK ${n}/3: ${VNAME[want]}`, VCOL[want], n === 3 ? 'TIMED HONK TO CARBONATE!' : undefined);
    if (n === 3) this.startCarb();
    return true;
  }
  startCarb() {
    this.state = 'carb'; this.needleT = 0;
    this.gerry.lastLine = 0; this.gerry.say('NOW HONK WHEN THE NEEDLE HITS GREEN. CAREFUL, SHE FOAMS!', 2600); this.gerry.act('point', 1.2);
    this.gauge = this.s.add.graphics().setDepth(40);
  }
  onHonk(x: number) {
    if (this.state !== 'carb' || Math.abs(x - this.mx) > 140) return;
    if (this.needle > 0.3 && this.needle < 0.7) this.brew();
    else { SFX.foam(); emote(this.s, this.mx, this.floor - 120, this.needle < 0.5 ? 'TOO FLAT!' : 'TOO FOAMY!', { life: 900 }); this.spillFoam(this.mx); this.spillFoam(this.mx + 20); }
  }
  spillFoam(x: number) {
    const dir = this.s.goose.x < x ? -1 : 1;
    const f = { img: this.s.add.image(x, this.floor - 4, 'foamBlob').setDepth(36).setScale(0.8).setTint(0xfff6e0), x, vx: dir * 50, life: 4, rect: { x: x - 16, y: this.floor - 14, w: 32, h: 14 } };
    this.foams.push(f); this.s.hazards.push({ kind: 'slow', rect: f.rect, active: () => f.life > 0 });
  }
  brew() {
    this.state = 'brew';
    this.gauge?.destroy(); this.gauge = null;
    for (const f of this.foams) { f.img.destroy(); f.life = 0; } this.foams = [];
    for (const b of this.bottles) b.img.destroy(); this.bottles = [];
    const s = this.s, g = s.goose, ge = this.gerry;
    s.phase = 'cutscene'; g.mode = 'script'; g.body.vx = 0;
    SFX.honk(1.4); SFX.mixer(2); SFX.rumble(1.5); shake(s, 1500, 0.008);
    s.tweens.add({ targets: this.machine, x: this.mx + 3, angle: 1.5, duration: 50, yoyo: true, repeat: 24 });
    for (let i = 0; i < 12; i++) s.time.delayedCall(i * 110, () => s.fx.drops(this.mx + (Math.random() - 0.5) * 100, this.floor - 100, [C.red0, C.gold0, C.lim0, C.blu0, C.pur0][i % 5], 5));
    const glass = s.add.image(this.mx, this.floor - 110, 'rainbowGlass').setDepth(45).setScale(0.2);
    s.time.delayedCall(1500, () => {
      SFX.bigPop(); s.fx.confetti(this.mx, this.floor - 110, 28); SFX.chime();
      s.tweens.add({ targets: glass, scale: 1, x: ge.x - 2, y: ge.y - 44, angle: 360, duration: 700, ease: 'Sine.Out', onComplete: () => { ge.act('catch', 3); SFX.clink(); } });
    });
    s.time.delayedCall(2600, () => this.talkAll([
      ['gerry', "THAT'S EITHER THE BEST THING WE'VE EVER MADE OR A SCIENTIFIC EMERGENCY.", 'hold'],
      ['gerry', 'GO ON. YOU FIRST.', 'pour'],
    ], () => {
      s.phase = 'cutscene'; g.mode = 'script';
      s.tweens.add({ targets: glass, x: g.x + g.facing * 8, y: g.y - 26, duration: 400 });
      s.time.delayedCall(500, () => { g.playOnce('drink'); SFX.slurp(); glass.destroy(); });
      s.time.delayedCall(1200, () => { g.playOnce('swallow'); SFX.gulp(); });
      s.time.delayedCall(2100, () => { g.playOnce('growl'); SFX.growl(); s.say('*RUMBLE*', g.x, g.y - 44, 900); });
      s.time.delayedCall(3100, () => {
        // the enormous multicoloured burp
        g.playOnce('burp'); SFX.burp(); SFX.burp(); SFX.whoosh(); shake(s, 500, 0.01);
        for (let i = 0; i < 6; i++) { const b = s.add.image(g.x + g.facing * 16, g.y - 30, 'bubble32').setDepth(47).setScale(0.2).setTint([C.red0, C.mng0, C.gold0, C.lim0, C.blu0, C.pur0][i]); s.tweens.add({ targets: b, x: b.x + g.facing * (60 + i * 20), y: b.y - 30 - i * 14, scale: 0.6 + i * 0.12, alpha: 0, duration: 1400, delay: i * 80, onComplete: () => b.destroy() }); }
        ge.act('shock', 1);
      });
      s.time.delayedCall(4700, () => {
        update((sv) => { sv.superBurp = true; sv.owners.gerryLab = true; });
        achieve('rainbow_soda');
        s.game.events.emit('hud:abilities', { ph: save().powerHonk, db: save().doubleBubble, sb: true });
        SFX.powerup(); s.fx.sparkle(g.x, g.y - 20, 16, C.pur0);
        s.game.events.emit('hud:toast', 'SUPER BURP!', 0xffb0e0, s.touch ? 'HOLD POWER, THEN RELEASE' : 'HOLD C TO CHARGE, RELEASE TO FIRE');
        this.talkAll([['gerry', 'THAT OUGHT TO COME IN HANDY. JUST DON\'T POINT IT AT ME!', 'point']], () => this.foreheadGag());
      });
    }));
  }
  foreheadGag() {
    const s = this.s, g = s.goose, ge = this.gerry;
    s.phase = 'cutscene'; g.mode = 'script';
    g.face(ge.x > g.x ? 1 : -1);
    s.time.delayedCall(300, () => { g.playOnce('burp'); SFX.burp(); });
    const b = s.add.image(g.x + g.facing * 12, g.y - 28, 'bubble16').setDepth(47).setScale(0.4).setTint(0xffd0f0);
    s.tweens.add({ targets: b, x: ge.x, y: ge.y - 56, duration: 900, delay: 400, ease: 'Sine.InOut', onComplete: () => { b.destroy(); SFX.pop(0.6); s.fx.sparkle(ge.x, ge.y - 56, 6, 0xffd0f0); ge.act('laugh', 1.8); SFX.laugh(1.05); } });
    s.time.delayedCall(1700, () => this.talkAll([['gerry', 'YEP. DEFINITELY WORKS.', 'laugh']], () => {
      this.state = 'done'; g.mode = 'play'; g.playLoop('idle'); s.phase = 'play';
      ge.lastLine = 0; ge.say('NOW THE SUPER SODA 9000, RIGHT THERE! COLA + CREAM SODA + BLACK CHERRY, MAX FIZZ.', 5000); s.game.events.emit('hud:toast', 'NEXT: SUPER SODA 9000', C.red0, s.touch ? 'SIP AT THE BIG MACHINE ON THE RIGHT' : 'PRESS E AT THE BIG MACHINE ON THE RIGHT');
    }));
  }

  update(dt: number) {
    const s = this.s, g = s.goose;
    this.t += dt;
    if (this.state === 'idle' && this.near() && s.phase === 'play' && this.t > 0.5) this.start();
    // samples
    for (const v of this.vials) {
      if (v.got || !v.img.visible) continue;
      v.img.y = v.y + Math.sin(this.t * 3 + v.x) * 2;
      if (!this.carried && Math.abs(v.x - g.x) < 14 && v.y > g.y - 40 && v.y < g.y + 6) {
        v.got = true; v.img.setVisible(false); SFX.golden();
        this.carried = { kind: v.kind, img: s.add.image(g.x, g.y - 30, 'vial_' + v.kind).setDepth(44) };
        s.game.events.emit('hud:toast', `SAMPLE: ${VNAME[v.kind]}`, VCOL[v.kind], 'BRING IT TO GERRY\'S MACHINE');
      }
    }
    if (this.carried) { const tip = g.x + (g.facing > 0 ? 17 : -15); this.carried.img.setOrigin(0.5, 0).setScale(0.8).setPosition(Math.round(tip + g.facing * 3), Math.round(g.y - 31 + Math.abs(Math.sin(this.t * 8)))).setDepth(g.sprite.depth + 1); }
    // carbonation gauge
    if (this.state === 'carb' && this.gauge) {
      this.needleT += dt; this.needle = Math.sin(this.needleT * 1.8) * 0.5 + 0.5;
      const gx = this.mx - 30, gy = this.floor - 130;
      this.gauge.clear().fillStyle(C.ink).fillRoundedRect(gx - 2, gy - 2, 64, 14, 3).fillStyle(C.red1).fillRect(gx, gy, 60, 10).fillStyle(C.lim1).fillRect(gx + 18, gy, 24, 10).fillStyle(C.wht).fillRect(gx + Math.round(this.needle * 58), gy - 3, 2, 16);
    }
    // hazards while the machine is live: foam overflow + bouncing bottles
    if (this.state === 'collect' || this.state === 'carb') {
      const live = TANK_ORDER.some((k) => this.filled[k]) || this.state === 'carb';
      this.hazT -= dt;
      if (live && this.hazT <= 0) {
        this.hazT = this.state === 'carb' ? 1.6 : 3;
        if (Math.random() < 0.5) this.spillFoam(this.mx + (Math.random() - 0.5) * 60);
        else { const dir = Math.random() < 0.5 ? -1 : 1; this.bottles.push({ img: s.add.image(this.mx, this.floor - 100, 'bottle' + Math.floor(Math.random() * 8)).setDepth(44), x: this.mx, y: this.floor - 100, vx: dir * (60 + Math.random() * 50), vy: -120, life: 4 }); SFX.clink(); }
      }
    }
    for (const f of this.foams) {
      f.life -= dt; f.x += f.vx * dt; f.vx *= Math.pow(0.5, dt); f.img.setPosition(f.x, this.floor - 4).setAlpha(Math.min(1, f.life)); f.rect.x = f.x - 16;
    }
    this.foams = this.foams.filter((f) => { if (f.life <= 0) f.img.destroy(); return f.life > 0; });
    s.hazards = s.hazards.filter((h) => !h.active || h.active() || h.kind !== 'slow');
    for (const b of this.bottles) {
      b.life -= dt; b.vy += 600 * dt; b.x += b.vx * dt; b.y += b.vy * dt;
      if (b.y > this.floor - 6) { b.y = this.floor - 6; b.vy = -Math.abs(b.vy) * 0.7; SFX.clink(1.4); }
      b.img.setPosition(b.x, b.y).setAngle(b.img.angle + b.vx * dt * 6).setAlpha(Math.min(1, b.life));
      if (g.mode === 'play' && Math.abs(b.x - g.x) < 10 && b.y > g.y - 30 && b.y < g.y) { s.damage(b.x); if (this.carried) this.dropVial(); b.life = 0; }
    }
    this.bottles = this.bottles.filter((b) => { if (b.life <= 0) b.img.destroy(); return b.life > 0; });
  }
  dropVial() {
    const c = this.carried!; this.carried = null; c.img.destroy();
    const v = this.vials.find((q) => q.kind === c.kind)!; v.got = false; v.img.setVisible(true);
    emote(this.s, this.s.goose.x, this.s.goose.y - 44, 'SPILLED! IT WENT BACK.', { life: 1100 });
  }
}
