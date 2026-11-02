/**
 * LEVEL 2 BOSS — CARBONATION CATASTROPHE (the Carbonator 3000).
 * ONE simple rule for the whole fight: it spits fizzy bubbles — HONK at a bubble (or jump on it)
 * and it flies back into the machine. 9 returns win. Each phase just adds bubbles / speed.
 */
import Phaser from 'phaser';
import { C } from '../art/palette';
import { LevelScene, Rect, SwitchLike } from '../levels/LevelScene';
import { emote } from '../entities/Emote';
import { achieve } from '../data/achievements';
import { GS } from '../systems/gamestate';
import { complete, unlock, addUnique, StageId } from '../systems/save';
import { shake, flash } from '../systems/camfx';
import { overlap } from '../systems/physics';
import { SFX } from '../audio/sfx';
import { MUSIC } from '../audio/music';
import { txt } from '../art/font';

const W = 560, H = 300, F = 280, MX = 280;
type Flavor = 'cola' | 'cream' | 'cherry';
const FCOL: Record<Flavor, number> = { cola: C.cola0, cream: C.crm1, cherry: C.chr0 };
interface BBubble { img: Phaser.GameObjects.Image; x: number; y: number; vx: number; vy: number; reflected: boolean; target: Sw | null; life: number; alive: boolean }
interface Hazard2 { img: Phaser.GameObjects.Image; x: number; y: number; vx: number; vy: number; kind: 'wave' | 'blob' | 'puddle' | 'bomb'; life: number; alive: boolean }

class Sw implements SwitchLike {
  on = false; by: string[];
  img: Phaser.GameObjects.Image;
  constructor(public s: BossCarbScene, public x: number, public y: number, tex: string, by: string[], public onHit: (src: string) => void, public w = 28, public h = 30) { this.by = by; this.img = s.add.image(x, y, tex).setDepth(30); }
  rect(): Rect { return { x: this.x - this.w / 2, y: this.y - this.h / 2, w: this.w, h: this.h }; }
  activate(src: string) { this.onHit(src); }
}

export class BossCarbScene extends LevelScene {
  stage: StageId = 'carb';
  body!: Phaser.GameObjects.Image; eyes!: Phaser.GameObjects.Image; crest!: Phaser.GameObjects.Image; needles: Phaser.GameObjects.Image[] = []; arms: Phaser.GameObjects.Sprite[] = []; tankGlow!: Phaser.GameObjects.Image;
  bossPhase = 0; hp = 9; t = 0; atkT = 0; flavor: Flavor = 'cola'; flavorT = 0; hits2 = 0;
  bubblesB: BBubble[] = []; hz: Hazard2[] = [];
  pswitches: Sw[] = []; taps: Record<Flavor, Sw> = {} as Record<Flavor, Sw>; valves3: Sw[] = [];
  foamH = 0; foamImg!: Phaser.GameObjects.TileSprite; jets: { x: number; on: boolean; img: Phaser.GameObjects.Image }[] = [];
  moodT = 0; over = false; hintLine!: Phaser.GameObjects.BitmapText;
  constructor() { super('BossCarb'); }

  create() {
    this.levelName = 'BOSS: CARBONATION CATASTROPHE';
    this.initLevel({ w: W, h: H, floor: F, bg: 0x1d3c46, spawn: { x: 60, y: F } });
    this.reset();
    this.add.image(0, 0, 'labWall').setOrigin(0).setScrollFactor(0.4, 1).setDepth(0).setTint(0xb0a0c0);
    this.addPlatform(-40, F, W + 80, 40, 'solid', 'floor'); this.add.tileSprite(0, F, W, 30, 'labFloor').setOrigin(0).setDepth(15);
    this.addPlatform(-40, 0, 44, H, 'solid', 'wallL'); this.addPlatform(W - 4, 0, 44, H, 'solid', 'wallR'); this.addPlatform(-40, -40, W + 80, 50, 'solid', 'ceiling');
    for (const [x0, x1, y] of [[34, 130, 210], [430, 526, 210], [36, 104, 120], [456, 524, 120]] as [number, number, number][]) { this.addPlatform(x0, y, x1 - x0, 5, 'oneway', 'catwalk'); this.add.tileSprite(x0, y, x1 - x0, 10, 'catwalk80').setOrigin(0).setDepth(27); }
    this.addPlatform(236, 88, 88, 5, 'oneway', 'bossTop');
    // the machine
    this.tankGlow = this.add.image(MX, F - 70, 'glow128').setScale(2.2, 1.2).setBlendMode(Phaser.BlendModes.ADD).setAlpha(0.25).setDepth(19);
    this.body = this.add.image(MX, F, 'carbBody').setOrigin(0.5, 1).setDepth(20);
    this.eyes = this.add.image(MX, F - 124, 'eyes_dizzy').setDepth(21);
    this.crest = this.add.image(MX, F - 196, 'trident44').setOrigin(0.5, 0.75).setDepth(21);
    for (const x of [MX - 76, MX + 76]) this.needles.push(this.add.image(x, F - 126, 'needle').setOrigin(0.5, 0.9).setDepth(21));
    for (const [x, flip] of [[MX - 118, false], [MX + 118, true]] as [number, boolean][]) this.arms.push(this.add.sprite(x, F - 170, 'arm0').setOrigin(0.5, 0).setFlipX(flip).setDepth(19).play('arm'));
    this.foamImg = this.add.tileSprite(0, F, W, 0, 'foamFlood').setOrigin(0, 1).setDepth(44);
    this.finishInit({ music: 'boss', follow: true });
    this.hintLine = this.add.existing(txt(this, 240, 256, this.touch ? 'HONK (OR JUMP ON) A BUBBLE TO SEND IT BACK!' : 'HONK (X) OR JUMP ON A BUBBLE TO SEND IT BACK!', { align: 'center', color: C.gold0 })).setScrollFactor(0).setDepth(150).setVisible(false) as Phaser.GameObjects.BitmapText;
    this.cameras.main.setDeadzone(80, 60);
    this.intro();
    (window as unknown as { __SIMPS: Record<string, unknown> }).__SIMPS.boss = this;
  }
  reset() { this.bossPhase = 0; this.hp = 9; this.t = 0; this.atkT = 2; this.hits2 = 0; this.bubblesB = []; this.hz = []; this.pswitches = []; this.valves3 = []; this.needles = []; this.arms = []; this.jets = []; this.foamH = 0; this.over = false; }

  intro() {
    this.phase = 'cutscene';
    this.time.delayedCall(600, () => { this.eyes.setTexture('eyes_normal'); SFX.rumble(0.8); SFX.chime(); });
    this.time.delayedCall(1100, () => emote(this, MX, F - 210, 'CARBONATOR 3000 ONLINE.', { life: 1600 }));
    this.time.delayedCall(2600, () => { this.eyes.setTexture('eyes_angry'); emote(this, MX, F - 210, 'PRESSURE: CRITICAL!', { life: 1400 }); SFX.hiss(1); shake(this, 400, 0.006); });
    this.time.delayedCall(3600, () => { this.goose.playOnce('honk'); this.time.delayedCall(140, () => { SFX.honk(1.3); this.fx.honk(this.goose.x + 14, this.goose.y - 30, 1, true); }); });
    this.time.delayedCall(4300, () => { this.phase = 'play'; this.startPhase(1); });
  }
  bossBar() { this.game.events.emit('hud:boss', 'CARBONATOR 3000', this.hp / 9); }
  startPhase(n: number) {
    this.bossPhase = n; this.atkT = 1.5; this.hintLine.setVisible(true);
    this.bossBar();
    MUSIC.setIntensity(n - 1);
    const msg = ['', 'HONK THE BUBBLES BACK AT IT!', 'FASTER! KEEP SENDING THEM BACK!', 'LAST PHASE! SAME TRICK, MORE BUBBLES!'][n];
    this.game.events.emit('hud:toast', `PHASE ${n} OF 3`, n === 3 ? C.red0 : C.gold1, msg);
    if (n === 3) eyesMood(this, 'panic');
  }
  damageBoss(n = 1) {
    this.hp -= n; this.bossBar();
    this.eyes.setTexture('eyes_hurt'); this.moodT = 0.8;
    SFX.explosion(); shake(this, 300, 0.007); flash(this, 100, 255, 200, 200);
    this.fx.confetti(MX, F - 150, 10); this.fx.bubbles(MX, F - 120, 10);
    GS.addScore(500);
    if (this.bossPhase === 1 && this.hp <= 6) this.time.delayedCall(900, () => this.startPhase(2));
    else if (this.bossPhase === 2 && this.hp <= 3) this.time.delayedCall(900, () => this.startPhase(3));
    else if (this.hp <= 0) this.victory();
  }
  setFlavor(fl: Flavor) {
    this.flavor = fl;
    this.tankGlow.setTint(FCOL[fl]);
    for (const k of Object.keys(this.taps) as Flavor[]) this.taps[k].img.setTexture(`tap_${k}${k === fl ? 1 : 0}`);
    SFX.ui('move');
  }
  tapHit(fl: Flavor) {
    if (this.bossPhase !== 2) return;
    const tp = this.taps[fl];
    if (fl !== this.flavor) { this.fx.steam(tp.x, tp.y - 10, 4); emote(this, tp.x, tp.y - 30, 'WRONG FLAVOR!', { life: 800 }); SFX.ui('back'); return; }
    // syrup jet into the machine
    const beam = this.add.graphics().setDepth(45);
    beam.lineStyle(6, FCOL[fl]).lineBetween(tp.x, tp.y - 10, MX, F - 110).lineStyle(2, 0xffffff, 0.8).lineBetween(tp.x, tp.y - 10, MX, F - 110);
    this.tweens.add({ targets: beam, alpha: 0, duration: 500, onComplete: () => beam.destroy() });
    SFX.pump(); SFX.fizz(0.6, 1.4);
    this.hits2++;
    this.damageBoss();
    this.setFlavor((['cola', 'cream', 'cherry'] as Flavor[])[(['cola', 'cream', 'cherry'].indexOf(fl) + 1 + Math.floor(Math.random() * 2)) % 3]);
  }
  valveHit(v: Sw) {
    if (v.on || this.bossPhase !== 3) return;
    v.on = true;
    this.tweens.add({ targets: v.img, rotation: Math.PI * 4, duration: 800 });
    SFX.valve(); SFX.hiss(1);
    this.damageBoss();
    this.foamH = Math.max(10, this.foamH - 8);
  }

  // ---------------------------------------------------------------- attacks
  launchBubble() {
    const dir = this.goose.x < MX ? -1 : 1;
    const img = this.add.image(MX + dir * 30, F - 120, 'bubble32').setDepth(46).setTint(0xd8f8ff);
    this.bubblesB.push({ img, x: img.x, y: img.y, vx: dir * (55 + this.bossPhase * 10 + Math.random() * 30), vy: -110, reflected: false, target: null, life: 8, alive: true });
    SFX.bubble(); this.arms.forEach((a) => a.anims.msPerFrame = 120);
  }
  reflect(b: BBubble) {
    b.reflected = true; b.target = null; b.img.setTint(0xfff0a0);
    SFX.bounce(); this.fx.sparkle(b.x, b.y, 6, C.gold0);
  }
  popB(b: BBubble) { b.alive = false; b.img.destroy(); SFX.pop(1.4); this.fx.drops(b.x, b.y, C.bub2, 8); }
  attack2() {
    const fl = this.flavor;
    if (fl === 'cola') for (const d of [-1, 1]) { const img = this.add.image(MX + d * 70, F, 'fizzWave').setOrigin(0.5, 1).setDepth(43).setFlipX(d < 0); this.hz.push({ img, x: img.x, y: F, vx: d * 150, vy: 0, kind: 'wave', life: 4, alive: true }); SFX.rumble(0.3); }
    else if (fl === 'cream') for (let i = 0; i < 3; i++) { const x = 40 + Math.random() * (W - 80); const img = this.add.image(x, 20, 'foamBlob').setDepth(43); this.hz.push({ img, x, y: 20, vx: 0, vy: 120, kind: 'blob', life: 6, alive: true }); }
    else for (let i = 0; i < 2; i++) { const d = this.goose.x < MX ? -1 : 1; const img = this.add.image(MX, F - 130, 'cherryShot').setDepth(43).setScale(1.3); this.hz.push({ img, x: MX, y: F - 130, vx: d * (90 + i * 60), vy: -200, kind: 'bomb', life: 4, alive: true }); SFX.shoot(); }
  }

  victory() {
    if (this.over) return;
    this.over = true;
    this.phase = 'cutscene'; this.goose.mode = 'script';
    this.game.events.emit('hud:boss', null, 0); this.hintLine.setVisible(false);
    MUSIC.cut();
    this.eyes.setTexture('eyes_dizzy');
    for (let i = 0; i < 8; i++) this.time.delayedCall(i * 220, () => { SFX.explosion(); this.fx.confetti(MX + (Math.random() - 0.5) * 200, F - Math.random() * 180, 14); this.fx.bubbles(MX + (Math.random() - 0.5) * 200, F - Math.random() * 180, 10); shake(this, 200, 0.01); });
    this.time.delayedCall(1900, () => {
      flash(this, 600);
      for (const o of [this.body, this.eyes, this.crest, ...this.needles, ...this.arms, this.tankGlow]) this.tweens.add({ targets: o, alpha: 0, scale: 1.4, duration: 600 });
      for (let i = 0; i < 40; i++) this.fx.steamE.explode(1, MX + (Math.random() - 0.5) * 240, F - Math.random() * 200);
      this.foamH = 0;
      achieve('master_of_fizz'); complete('carb'); unlock('cafe');
      GS.addScore(5000);
      if (addUnique('collected', 'carb:badge:0')) { /* first time */ }
      this.game.events.emit('hud:badge', true);
      this.game.events.emit('hud:toast', 'CARBONATOR DEFEATED!', C.gold1, 'SIMPS CERTIFIED FIZZ MASTER BADGE EARNED');
      this.goose.playLoop('celebrate'); SFX.cheer(); SFX.honk(1.2);
    });
    // the goose is blasted back into the store → fake ending
    this.time.delayedCall(4200, () => {
      const g = this.goose; g.mode = 'ride'; g.ride = { x: g.x, y: g.y };
      this.tweens.add({ targets: g.ride, y: -60, duration: 1100, ease: 'Quad.In' });
      SFX.whoosh(); this.say('HOOOONK!', g.x, g.y - 40, 900);
    });
    this.time.delayedCall(5400, () => { GS.persistRun(); this.goTo('FakeEnd'); });
  }

  stepLevel(dt: number) {
    if (this.phase !== 'play' || this.over) return;
    this.t += dt; this.atkT -= dt;
    const g = this.goose;
    // bubbles only — slow and readable; later phases add a second bubble
    const live = this.bubblesB.filter((b) => b.alive && !b.reflected).length;
    if (this.atkT <= 0 && live < this.bossPhase) { this.atkT = [0, 2.8, 2.3, 2.0][this.bossPhase]; this.launchBubble(); }
    // boss bubbles
    for (const b of this.bubblesB) {
      if (!b.alive) continue;
      b.life -= dt;
      if (b.reflected) {
        const tx = MX, ty = F - 120, dx = tx - b.x, dy = ty - b.y, d = Math.hypot(dx, dy);
        b.vx = dx / d * 300; b.vy = dy / d * 300;
        if (d < 16) { this.popB(b); this.damageBoss(); emote(this, MX, F - 170, ['BLORP!', 'FZZT!', 'OOF!'][Math.floor(Math.random() * 3)], { life: 600 }); continue; }
      } else {
        b.vy += 300 * dt;
        if (b.y > F - 16 && b.vy > 0) { b.y = F - 16; b.vy = -Math.abs(b.vy) * 0.92; SFX.bounce(); }
        if (b.x < 20 || b.x > W - 20) b.vx *= -1;
        const gr = this.gooseRect();
        const br = { x: b.x - 14, y: b.y - 14, w: 28, h: 28 };
        if (overlap(gr, br)) {
          if (g.body.vy > 40 && g.body.y + g.body.h - br.y < 12) { g.body.vy = -300; this.reflect(b); }
          else { this.damage(b.x); this.popB(b); continue; }
        }
      }
      b.x += b.vx * dt; b.y += b.vy * dt;
      if (b.life <= 0) this.popB(b);
    }
    for (const h of this.hz) {
      if (!h.alive) continue;
      h.life -= dt;
      if (h.kind === 'bomb') { h.vy += 500 * dt; if (h.y > F - 6 && h.vy > 0) { h.vy *= -0.7; h.y = F - 6; SFX.bounce(); } }
      if (h.kind === 'blob' && h.y >= F - 6) { h.kind = 'puddle'; h.vy = 0; h.y = F; h.img.setOrigin(0.5, 1).setScale(1.6, 0.6); h.life = 2.2; SFX.foam(); }
      h.x += h.vx * dt; h.y += h.vy * dt;
      h.img.setPosition(Math.round(h.x), Math.round(h.y));
      const r = h.kind === 'puddle' ? { x: h.x - 14, y: F - 6, w: 28, h: 6 } : { x: h.x - 8, y: h.y - (h.kind === 'wave' ? 14 : 8), w: 16, h: 14 };
      if (overlap(this.gooseRect(), r)) { if (h.kind === 'puddle') g.speedMul = 0.4; else { this.damage(h.x); if (h.kind !== 'wave') { h.alive = false; h.img.destroy(); continue; } } }
      if (h.life <= 0 || h.x < -20 || h.x > W + 20) { h.alive = false; h.img.destroy(); }
    }
  }
  onHonkLevel(x: number, y: number) {
    if (this.bossPhase === 0) return;
    for (const b of this.bubblesB) if (b.alive && !b.reflected && Math.hypot(b.x - x, b.y - y) < 110) this.reflect(b);
  }
  onShot(s: { x: number; y: number; kill: () => void }) {
    if (this.bossPhase === 0) return false;
    for (const b of this.bubblesB) if (b.alive && !b.reflected && Math.hypot(b.x - s.x, b.y - s.y) < 22) { this.reflect(b); s.kill(); return true; }
    return false;
  }
  frameLevel(dt: number) {
    this.crest.setRotation(Math.sin(this.time.now / 300) * (this.bossPhase === 3 ? 0.5 : 0.15) + (this.bossPhase >= 2 ? this.time.now / 800 : 0));
    this.needles.forEach((n, i) => n.setRotation(-1.5 + (1 - this.hp / 9) * 3 + Math.sin(this.time.now / (90 + i * 40)) * (0.2 + this.bossPhase * 0.15)));
    this.body.x = MX + (this.bossPhase === 3 ? Math.round(Math.sin(this.time.now / 25)) : 0);
    this.moodT -= dt;
    if (this.moodT <= 0 && !this.over && this.bossPhase > 0) this.eyes.setTexture(this.bossPhase === 3 ? 'eyes_panic' : 'eyes_angry');
    this.foamImg.height = Math.round(this.foamH); this.foamImg.tilePositionX += dt * 20;
    for (const j of this.jets) if (j.on && Math.random() < dt * 25) this.fx.fizz(j.x, F - 10 - Math.random() * 150, 3);

  }
}
function eyesMood(s: BossCarbScene, m: string) { s.eyes.setTexture('eyes_' + m); }
