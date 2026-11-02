/**
 * FINAL BOSS — OGOPOGO (an original cartoon lake creature inspired by the popular legend;
 * not a depiction of the syilx/Okanagan being nx̌aʔx̌ʔitkʷ).
 * Phase 1 Bubble Burps · Phase 2 Lake Chaos (dives, reappears high: use bubbles to get up)
 * · Phase 3 The Super Burp (whirlpool; charge the glowing cup, then unleash).
 */
import Phaser from 'phaser';
import { C } from '../art/palette';
import { LevelScene } from '../levels/LevelScene';
import { Projectile } from '../entities/Projectile';
import { emote } from '../entities/Emote';
import { BURPS, BurpId } from '../data/coffee';
import { achieve } from '../data/achievements';
import { GS } from '../systems/gamestate';
import { complete, StageId } from '../systems/save';
import { overlap } from '../systems/physics';
import { shake, flash } from '../systems/camfx';
import { SFX } from '../audio/sfx';
import { MUSIC } from '../audio/music';
import { Controls } from '../systems/input';

const W = 480, H = 270, DOCK = 222, WATER = 238;
interface Wv { img: Phaser.GameObjects.Image; x: number; alive: boolean; dodged: boolean }
interface Spit { img: Phaser.GameObjects.Image; x: number; y: number; vx: number; vy: number; alive: boolean }

export class OgopogoScene extends LevelScene {
  stage: StageId = 'ogopogo';
  head!: Phaser.GameObjects.Image; neck: Phaser.GameObjects.Image[] = []; humps: Phaser.GameObjects.Image[] = []; tail!: Phaser.GameObjects.Image;
  hx = 400; hy = 300; baseX = 400; tx = 400; ty = 150; visible = false;
  hp = 40; bossPhase = 0; stun = 0; face = 'normal'; faceT = 0; t = 0; atkT = 3; diveT = 0; posIdx = 0;
  waves: Wv[] = []; spits: Spit[] = []; charge = 0; chargeG!: Phaser.GameObjects.Graphics; superReady = false; over = false;
  whirl!: Phaser.GameObjects.Graphics; buoys: { p: ReturnType<LevelScene['addPlatform']>; img: Phaser.GameObjects.Image; x: number; y: number }[] = [];
  lakeBubT = 0; lake!: Phaser.GameObjects.TileSprite;
  constructor() { super('Ogopogo'); }
  create() {
    this.levelName = 'FINAL BOSS: OGOPOGO!';
    this.initLevel({ w: W, h: H, floor: WATER + 30, bg: C.sky2, spawn: { x: 120, y: DOCK } });
    this.neck = []; this.humps = []; this.waves = []; this.spits = []; this.buoys = []; this.hp = 40; this.bossPhase = 0; this.charge = 0; this.superReady = false; this.over = false; this.visible = false; this.hy = 320; this.atkT = 3;
    this.add.image(0, 0, 'wfSky').setOrigin(0).setDepth(0);
    this.add.tileSprite(0, 0, 480, 270, 'wfHills').setOrigin(0).setDepth(1).setTilePosition(300, 0);
    this.lake = this.add.tileSprite(0, 190, 480, 80, 'wfLake').setOrigin(0).setDepth(2);
    this.add.image(20, 214, 'sailboat').setOrigin(0.5, 1).setDepth(2.5).setScale(0.8);
    // shore + dock
    this.add.tileSprite(0, DOCK + 8, 150, 40, 'wfPath').setOrigin(0).setDepth(15);
    this.addPlatform(-40, DOCK + 8, 190, 40, 'solid', 'floor');
    this.add.tileSprite(150, DOCK, 160, 30, 'dock160').setOrigin(0).setDepth(16);
    this.addPlatform(150, DOCK, 160, 6, 'oneway', 'dock');
    this.addPlatform(-40, 0, 44, H, 'solid', 'wallL'); this.addPlatform(W - 4, 0, 44, H, 'solid', 'wallR');
    this.hazards.push({ rect: { x: 150, y: WATER + 8, w: 340, h: 40 }, kind: 'pit' });
    this.add.image(60, DOCK + 8, 'bench').setOrigin(0.5, 1).setDepth(18); this.addPlatform(40, DOCK - 10, 40, 5, 'oneway', 'bench');
    this.add.image(100, DOCK + 8, 'flagPole').setOrigin(0.5, 1).setDepth(18); this.add.sprite(102, DOCK - 72, 'flag0').setOrigin(0, 0.5).setDepth(19).play('flag');
    this.addPlatform(92, DOCK - 78, 20, 5, 'oneway', 'flagTop');
    // bobbing buoys (floating one-way platforms)
    for (const [x, y] of [[290, 176], [210, 140], [330, 110]] as [number, number][]) { const p = this.addPlatform(x - 14, y, 28, 5, 'oneway', 'buoy'); const img = this.add.image(x, y + 4, 'buoy').setDepth(26); this.buoys.push({ p, img, x, y }); }
    // Ogopogo rig
    this.tail = this.add.image(460, WATER, 'ogTail').setOrigin(0.5, 1).setDepth(4).setVisible(false);
    for (let i = 0; i < 3; i++) this.humps.push(this.add.image(300 + i * 50, WATER + 30, 'ogHump').setOrigin(0.5, 1).setDepth(4));
    for (let i = 0; i < 9; i++) this.neck.push(this.add.image(0, 0, 'ogNeck').setDepth(5 + i * 0.01));
    this.head = this.add.image(0, 0, 'og_normal').setDepth(6);
    this.add.tileSprite(150, WATER, 330, 34, 'wfLake').setOrigin(0).setDepth(7).setAlpha(0.85);
    this.whirl = this.add.graphics().setDepth(7.5);
    this.chargeG = this.add.graphics().setDepth(90).setScrollFactor(0);
    this.finishInit({ music: 'ogopogo', follow: false });
    this.setBurp((GS.coffee as BurpId) || 'vanilla');
    this.cameras.main.setScroll(0, 0);
    this.intro();
    (window as unknown as { __SIMPS: Record<string, unknown> }).__SIMPS.og = this;
  }
  setFace(f: string, t = 0) { this.face = f; this.faceT = t; this.head.setTexture('og_' + f); }
  intro() {
    const g = this.goose;
    this.phase = 'cutscene'; g.mode = 'script'; g.playLoop('holdCup');
    MUSIC.stop(0.2);
    const shadow = this.add.ellipse(470, WATER + 10, 80, 10, 0x1a3a5a, 0.6).setDepth(8);
    this.tweens.add({ targets: shadow, x: 380, duration: 2200, ease: 'Sine.InOut' });
    this.time.delayedCall(1200, () => { g.playOnce('look'); emote(this, g.x, g.y - 40, '?', { life: 900 }); });
    this.time.delayedCall(2400, () => { shadow.destroy(); this.visible = true; this.hy = 300; this.ty = 150; this.tx = 400; SFX.splash(1.5); this.fx.drops(400, WATER, C.blu0, 20); shake(this, 600, 0.006); });
    this.time.delayedCall(3200, () => { this.humps.forEach((h, i) => this.tweens.add({ targets: h, y: WATER + 4, duration: 600, delay: i * 400 })); this.tail.setVisible(true); SFX.splash(0.8); });
    this.time.delayedCall(4800, () => { g.playLoop('holdCup'); this.say('HONK?', g.x, g.y - 44, 1200); });
    this.time.delayedCall(6000, () => { this.setFace('roar', 1.2); SFX.roar(); shake(this, 900, 0.01); this.fx.drops(this.hx + 20, this.hy + 10, C.blu0, 16); });
    this.time.delayedCall(7400, () => { this.phase = 'play'; g.mode = 'play'; MUSIC.play('ogopogo'); this.startPhase(1); });
  }
  bar() { this.game.events.emit('hud:boss', 'OGOPOGO', Math.max(0, this.hp) / 40); }
  startPhase(n: number) {
    this.bossPhase = n; this.atkT = 2; this.bar(); MUSIC.setIntensity(n - 1);
    const b = BURPS[this.burp!];
    if (n === 1) this.game.events.emit('hud:toast', 'PHASE 1: BUBBLE BURPS', C.lim0, `JUMP THE WAVES. BURP (${b.power}) AT OGOPOGO!`);
    if (n === 2) { this.game.events.emit('hud:toast', 'PHASE 2: LAKE CHAOS', C.blu0, 'ONLY ITS HEAD COUNTS. GET UP HIGH ON BUBBLES!'); this.dive(); }
    if (n === 3) { this.game.events.emit('hud:toast', 'PHASE 3: THE SUPER BURP', C.gold1, 'YOUR CUP IS GLOWING! HIT + DODGE TO CHARGE IT'); this.tx = 400; this.ty = 120; this.charge = Math.max(this.charge, 0.15); this.hazards.push({ rect: { x: 150, y: DOCK - 30, w: 160, h: 40 }, kind: 'push', strength: 22, active: () => this.bossPhase === 3 && !this.over }); }
  }
  dive() {
    this.ty = 330; SFX.splash(1.2); this.fx.drops(this.hx, WATER, C.blu0, 14);
    this.diveT = 1.8;
    const spots: [number, number][] = [[430, 70], [360, 60], [300, 92]];
    const [x, y] = spots[this.posIdx++ % spots.length];
    this.time.delayedCall(1800, () => { if (this.bossPhase === 2 && !this.over) { this.hx = x; this.tx = x; this.ty = y; SFX.splash(1); this.fx.drops(x, WATER, C.blu0, 12); this.setFace('roar', 0.6); SFX.roar(); } });
  }
  headRect() { return { x: this.hx - 26, y: this.hy - 22, w: 56, h: 44 }; }
  neckRect() { return { x: this.baseX - 12, y: this.hy + 20, w: 24, h: Math.max(0, WATER - this.hy - 20) }; }
  hitBoss(dmg: number, stun: number, sx: number, sy: number) {
    if (this.bossPhase === 0 || this.over || this.ty > WATER) return;
    if (this.bossPhase === 3) { this.charge = Math.min(1, this.charge + 0.12); this.setFace('hurt', 0.4); SFX.ogHurt(); this.fx.sparkle(sx, sy, 8, C.gold0); return; }
    this.hp -= dmg; this.bar();
    this.stun = Math.max(this.stun, stun); this.setFace('hurt', Math.max(0.4, stun)); SFX.ogHurt(); this.fx.bubbles(sx, sy, 6); GS.addScore(50 * dmg);
    emote(this, this.hx, this.hy - 40, ['BLUB!', 'GLORP!', 'HEY!', 'BLEH!'][Math.floor(Math.random() * 4)], { life: 600 });
    this.charge = Math.min(1, this.charge + 0.02);
    if (this.bossPhase === 1 && this.hp <= 25) this.startPhase(2);
    else if (this.bossPhase === 2 && this.hp <= 10) { this.hp = 10; this.startPhase(3); }
  }
  onShot(s: Projectile) {
    if (s.kind === 'super') {
      // Gerry's SUPER BURP: a heavy hit on the head (and a big boost to the cup in phase 3)
      if (overlap(s.rect(), this.headRect()) && this.ty < WATER) {
        if (this.bossPhase === 3) { this.charge = Math.min(1, this.charge + 0.2); this.setFace('dizzy', 0.8); SFX.ogHurt(); }
        else this.hitBoss(3, 1, s.x, s.y);
        emote(this, this.hx, this.hy - 44, 'SUPER BURP!', { life: 800 }); s.kill(); return true;
      }
      if (overlap(s.rect(), this.neckRect()) && this.ty < WATER) { s.kill(); return true; }
      return false;
    }
    if (s.kind !== 'burp') return false;
    const r = s.rect();
    // lavender (dream) bubbles freeze + pop waves; any burp pops spit
    for (const w of this.waves) if (w.alive && this.burp === 'lavender' && overlap(r, { x: w.x - 16, y: WATER - 26, w: 32, h: 26 })) { this.killWave(w, true); s.kill(); return true; }
    if (overlap(r, this.headRect())) { this.hitBoss(s.dmg, s.o.stun, s.x, s.y); s.kill(); return true; }
    if (overlap(r, this.neckRect()) && this.ty < WATER) {
      if (this.bossPhase === 1) { this.hitBoss(s.dmg, s.o.stun * 0.5, s.x, s.y); s.kill(); return true; }
      if (this.burp !== 'hazelnut') { s.vx = -s.vx * 0.6; SFX.bounce(); emote(this, s.x, s.y - 10, 'BOING', { life: 400 }); return false; }
    }
    return false;
  }
  spawnWave() { const img = this.add.image(470, WATER, 'wave').setOrigin(0.5, 1).setDepth(8); this.waves.push({ img, x: 470, alive: true, dodged: false }); SFX.splash(0.6); }
  killWave(w: Wv, frozen = false) { w.alive = false; if (frozen) { this.fx.sparkle(w.x, WATER - 14, 8, C.pur0); this.charge = Math.min(1, this.charge + 0.05); } this.tweens.add({ targets: w.img, alpha: 0, scaleY: 0.2, duration: 250, onComplete: () => w.img.destroy() }); }
  superBurp() {
    if (this.over) return;
    this.over = true; this.superReady = false;
    const g = this.goose;
    this.phase = 'cutscene'; g.mode = 'script';
    this.waves.forEach((w) => w.alive && this.killWave(w)); this.spits.forEach((s) => { s.alive = false; s.img.destroy(); });
    this.game.events.emit('hud:boss', null, 0);
    g.face(1); g.playOnce('sipCup'); SFX.slurp(); this.say('ONE LAST SIP...', g.x, g.y - 44, 1300);
    this.stun = 99; this.setFace('surprised');
    this.time.delayedCall(1400, () => { g.playLoop('reactFizz'); SFX.growl(); this.tweens.add({ targets: g.sprite, scaleX: 1.35, scaleY: 1.35, duration: 900, yoyo: true, hold: 300 }); });
    this.time.delayedCall(2900, () => {
      g.playOnce('burp'); SFX.burp(); SFX.burp(); SFX.whoosh(); shake(this, 800, 0.012); flash(this, 200, 255, 230, 255);
      const bub = this.add.image(g.x + 20, g.y - 30, 'bubble96').setDepth(40).setScale(0.15);
      this.tweens.add({ targets: bub, x: this.hx, y: this.hy, scale: 0.9, duration: 900, ease: 'Sine.Out', onUpdate: () => bub.setTint(Phaser.Display.Color.HSVToRGB((this.time.now / 400) % 1, 0.45, 1).color) });
      this.time.delayedCall(950, () => { achieve('super_burp'); this.setFace('dizzy'); this.ty = this.hy - 50; this.tweens.add({ targets: bub, y: this.hy - 50, duration: 1400, ease: 'Sine.InOut', onUpdate: () => { bub.x = this.hx; } }); });
      this.time.delayedCall(2600, () => { bub.destroy(); SFX.bigPop(); this.fx.confetti(this.hx, this.hy, 30); this.fx.bubbles(this.hx, this.hy, 20); this.ty = 330; this.time.delayedCall(500, () => { SFX.splash(2); this.fx.drops(this.hx, WATER, C.blu0, 30); shake(this, 600, 0.01); }); });
      this.time.delayedCall(1200, () => { this.tweens.add({ targets: this.head, angle: 720, duration: 1300, ease: 'Sine.InOut' }); SFX.whoosh(); emote(this, this.hx, this.hy - 46, '@_@', { life: 1200 }); });
      this.time.delayedCall(4300, () => { this.head.setAngle(0); this.ty = 150; this.tx = 400; this.setFace('sad'); SFX.splash(1); this.fx.drops(400, WATER, C.blu0, 12); emote(this, 400, 108, '...SORRY.', { life: 1200 }); });
      this.time.delayedCall(5600, () => { g.playOnce('honk'); SFX.honk(1.6); this.fx.honk(g.x + 12, g.y - 30, 1, true); emote(this, g.x, g.y - 44, 'HONK!!', { life: 1000 }); });
      this.time.delayedCall(6600, () => { this.setFace('happy'); for (let i = 0; i < 6; i++) this.time.delayedCall(i * 120, () => { SFX.bubble(); this.fx.bubbles(this.hx - 20, this.hy + 6, 3); }); emote(this, this.hx, this.hy - 46, 'BLUB BLUB!', { life: 1300 }); });
      this.time.delayedCall(7600, () => { g.playLoop('celebrate'); SFX.cheer(); this.game.events.emit('hud:toast', 'OGOPOGO IS A FRIEND!', C.lim0); });
      this.time.delayedCall(10200, () => { complete('ogopogo'); GS.addScore(10000); GS.persistRun(); this.goTo('TrueEnd'); });
    });
  }
  stepLevel(dt: number) {
    this.t += dt;
    for (const b of this.buoys) { const ny = b.y + Math.sin(this.t * 1.6 + b.x) * 3; b.p.dy = ny - b.p.y; b.p.y = ny; }
    if (this.phase !== 'play' || this.over) return;
    this.stun -= dt; this.atkT -= dt;
    const g = this.goose;
    const rate = this.bossPhase === 1 ? 3.6 : this.bossPhase === 2 ? 2.9 : 2.5;
    if (this.atkT <= 0 && this.stun <= 0 && this.ty < WATER) {
      this.atkT = rate;
      this.spawnWave();
      if (this.bossPhase >= 2) { const d = g.x - this.hx; const img = this.add.image(this.hx - 20, this.hy + 14, 'dot4').setTint(C.blu0).setScale(2).setDepth(9); this.spits.push({ img, x: img.x, y: img.y, vx: d * 0.9, vy: -150, alive: true }); this.setFace('roar', 0.4); SFX.splash(0.3); }
    }
    if (this.bossPhase === 2) { this.diveT -= dt; if (this.diveT <= -4.5) { this.diveT = 0; this.dive(); } }
    if (this.bossPhase === 3) { this.charge = Math.min(1, this.charge + dt * 0.025); this.tx = 400 + Math.sin(this.t * 0.8) * 30; }
    this.lakeBubT -= dt;
    if (this.lakeBubT <= 0 && this.bossPhase >= 2) { this.lakeBubT = 1.6; this.bubbles.spawn(180 + Math.random() * 130, WATER + 4, 15, 'rise', { vy: -26, maxStomps: 3, tint: 0xd8f8ff }); }
    for (const w of this.waves) {
      if (!w.alive) continue;
      w.x -= (this.bossPhase === 3 ? 140 : 120) * dt;
      const y = w.x < 310 ? DOCK + 2 : WATER;
      w.img.setPosition(Math.round(w.x), y);
      const r = { x: w.x - 12, y: y - 22, w: 24, h: 22 };
      if (overlap(this.gooseRect(), r)) this.damage(w.x);
      else if (!w.dodged && w.x < g.x - 14 && Math.abs(g.x - w.x) < 40) { w.dodged = true; if (this.bossPhase === 3) this.charge = Math.min(1, this.charge + 0.06); }
      if (w.x < -30) this.killWave(w);
    }
    for (const s of this.spits) {
      if (!s.alive) continue;
      s.vy += 300 * dt; s.x += s.vx * dt; s.y += s.vy * dt; s.img.setPosition(s.x, s.y);
      if (overlap(this.gooseRect(), { x: s.x - 5, y: s.y - 5, w: 10, h: 10 })) { this.damage(s.x); s.alive = false; s.img.destroy(); continue; }
      if (s.y > WATER + 10) { s.alive = false; s.img.destroy(); this.fx.drops(s.x, WATER, C.blu0, 4); }
    }
    if (this.charge >= 1 && !this.superReady) { this.superReady = true; this.game.events.emit('hud:toast', 'SUPER BURP READY!', C.gold0, this.touch ? 'PRESS POWER!' : 'PRESS C!'); SFX.chime(); }
  }
  /** Maple Leaf POWER HONK: briefly stuns Ogopogo, flattens nearby waves, nudges the cup in phase 3. */
  onPowerHonkLevel(x: number, y: number) {
    if (this.over || this.bossPhase === 0) return;
    for (const w of this.waves) if (w.alive && Math.abs(w.x - x) < 170) this.killWave(w, this.bossPhase === 3);
    for (const sp of this.spits) if (sp.alive && Math.hypot(sp.x - x, sp.y - y) < 170) { sp.alive = false; sp.img.destroy(); }
    if (this.ty < WATER && Math.hypot(this.hx - x, this.hy - y) < 260) {
      this.stun = Math.max(this.stun, 1.6); this.atkT = Math.max(this.atkT, 1.6); this.setFace('dizzy', 1.6); SFX.ogHurt();
      emote(this, this.hx, this.hy - 44, 'STUNNED!', { life: 900, color: C.gold1 });
      if (this.bossPhase === 3) this.charge = Math.min(1, this.charge + 0.08);
    }
  }
  useAbility() { if (this.superReady && this.phase === 'play') { this.superBurp(); return; } super.useAbility(); }
  frameLevel(dt: number) {
    this.lake.tilePositionX += dt * 6;
    // gentle vertical steer toward the head once a burp is roughly level with it (keeps every coffee viable)
    if (this.bossPhase >= 1 && !this.over && this.ty < WATER) for (const s of this.shots) if (s.active && s.kind === 'burp') {
      const dy = this.hy - s.y, dxs = this.hx - s.x;
      if (Math.abs(dy) < 55 && Math.sign(dxs) === Math.sign(s.vx) && Math.abs(dxs) < 260) { s.vy += Phaser.Math.Clamp(dy * 8, -600, 600) * dt; s.vy = Phaser.Math.Clamp(s.vy, -160, 160); }
    }
    for (const b of this.buoys) b.img.y = b.p.y + 4;
    // rig motion
    const k = Math.min(1, dt * 2.5);
    this.hx += (this.tx - this.hx) * k; this.hy += (this.ty - this.hy) * k * 1.2;
    const wob = this.stun > 0 ? Math.sin(this.t * 30) * 2 : Math.sin(this.t * 2) * 4;
    this.baseX = this.hx + 18;
    this.neck.forEach((n, i) => {
      const t = (i + 1) / (this.neck.length + 1);
      const x = this.baseX + Math.sin(t * Math.PI + this.t * 2) * 10 * (1 - t) + (this.hx - this.baseX) * t;
      const y = WATER + 6 + (this.hy + 16 - WATER - 6) * t;
      n.setPosition(Math.round(x + wob * t), Math.round(y)).setVisible(this.visible && y < WATER + 8);
    });
    this.head.setPosition(Math.round(this.hx + wob), Math.round(this.hy)).setVisible(this.visible && this.hy < WATER + 10).setFlipX(true);
    this.humps.forEach((h, i) => { h.x = 300 + i * 50 + Math.sin(this.t * 0.9 + i) * 14; if (this.bossPhase === 2 && this.ty > WATER) h.x = 200 + ((this.t * 60 + i * 60) % 260); });
    this.tail.x = 455 + Math.sin(this.t * 1.5) * 8;
    this.faceT -= dt;
    if (this.faceT <= 0 && this.face !== 'normal' && !this.over && this.phase === 'play') this.setFace('normal');
    // whirlpool
    this.whirl.clear();
    if (this.bossPhase === 3 && !this.over) for (let r = 0; r < 5; r++) { this.whirl.lineStyle(2, 0xffffff, 0.5).beginPath(); for (let a = 0; a < Math.PI * 2; a += 0.3) this.whirl.lineTo(390 + Math.cos(a + this.t * 3 - r) * (70 - r * 12), WATER + 10 + Math.sin(a + this.t * 3 - r) * (9 - r * 1.5)); this.whirl.strokePath(); }
    // charge cup
    const cg = this.chargeG.clear();
    if (this.bossPhase >= 1 && !this.over) {
      const glow = this.superReady ? 0.6 + Math.sin(this.t * 10) * 0.4 : 1;
      cg.fillStyle(C.ink, 0.8).fillRoundedRect(178, 248, 124, 18, 4).lineStyle(1, C.gold1).strokeRoundedRect(178.5, 248.5, 123, 17, 4);
      cg.fillStyle(C.wht).fillRect(184, 251, 9, 11).fillStyle(C.red1).fillRect(184, 255, 9, 2).fillStyle(C.wht).fillRect(193, 253, 2, 5);
      cg.fillStyle(C.blk1).fillRect(200, 254, 96, 6).fillStyle(BURPS[this.burp!].light, glow).fillRect(200, 254, Math.round(96 * this.charge), 6);
    }
    if (this.superReady && Controls.pressed('interact')) this.superBurp();
  }
}
