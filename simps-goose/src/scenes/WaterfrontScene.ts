/**
 * LEVEL 3b — THE KELOWNA WATERFRONT. A peaceful stroll along Okanagan Lake and the
 * bubble-burp tutorial: targets, a beach ball to lift, a tree branch reached on your own
 * burp-bubble, a hedge target, a bubble bell that opens the dock — then a sit, and ripples.
 */
import Phaser from 'phaser';
import { C } from '../art/palette';
import { WF } from '../art/waterfront';
import { LevelScene, Rect, SwitchLike } from '../levels/LevelScene';
import { Person } from '../entities/Person';
import { emote } from '../entities/Emote';
import { GS } from '../systems/gamestate';
import { complete, unlock, StageId } from '../systems/save';
import { overlap } from '../systems/physics';
import { SFX } from '../audio/sfx';
import { MUSIC } from '../audio/music';
import { BurpId } from '../data/coffee';

const F = WF.FLOOR;
class Target implements SwitchLike {
  on = false; by: string[];
  img: Phaser.GameObjects.Image;
  constructor(public s: WaterfrontScene, public x: number, public y: number, public reward: () => void, tex = 'target0', by = ['shot']) { this.by = by; this.img = s.add.image(x, y, tex).setDepth(30).setScale(0.8); s.tweens.add({ targets: this.img, y: y - 3, yoyo: true, repeat: -1, duration: 700 + Math.random() * 300 }); }
  rect(): Rect { return { x: this.x - 13, y: this.y - 13, w: 26, h: 26 }; }
  activate() { if (this.on) return; this.on = true; this.img.setTexture('target1'); SFX.chime(); this.s.fx.sparkle(this.x, this.y, 8, C.gold0); this.reward(); }
}

export class WaterfrontScene extends LevelScene {
  stage: StageId = 'waterfront';
  birds: { s: Phaser.GameObjects.Sprite; flown: boolean }[] = [];
  runners: { p: Person; v: number; bike?: Phaser.GameObjects.Image }[] = [];
  ball!: Phaser.GameObjects.Image; ballLifted = false; gatePlat!: ReturnType<LevelScene['addPlatform']>; gateImg!: Phaser.GameObjects.Rectangle;
  sat = false; layers: Phaser.GameObjects.TileSprite[] = []; lake!: Phaser.GameObjects.TileSprite;
  constructor() { super('Waterfront'); }
  create() {
    this.levelName = 'THE KELOWNA WATERFRONT';
    this.initLevel({ w: WF.W, h: WF.H, floor: F, bg: C.sky2, spawn: { x: 30, y: F } });
    this.birds = []; this.runners = []; this.ballLifted = false; this.sat = false; this.layers = [];
    this.add.image(0, 0, 'wfSky').setOrigin(0).setScrollFactor(0).setDepth(0);
    this.layers.push(this.add.tileSprite(0, 0, 480, 270, 'wfHills').setOrigin(0).setScrollFactor(0).setDepth(1));
    this.lake = this.add.tileSprite(0, 190, 480, 80, 'wfLake').setOrigin(0).setScrollFactor(0).setDepth(2);
    this.layers.push(this.add.tileSprite(0, 0, 480, 270, 'wfTrees').setOrigin(0).setScrollFactor(0).setDepth(3));
    for (const x of [280, 980]) this.add.image(x, 214, 'sailboat').setOrigin(0.5, 1).setScrollFactor(0.4, 1).setDepth(2.5);
    // path + dock
    this.add.tileSprite(0, F, 1300, 40, 'wfPath').setOrigin(0).setDepth(15);
    this.addPlatform(-40, F, 1340, 40, 'solid', 'floor');
    this.add.tileSprite(1290, F - 8, 310, 30, 'dock80').setOrigin(0).setDepth(16);
    this.addPlatform(1290, F - 8, 320, 6, 'oneway', 'dock');
    this.add.rectangle(1290, WF.WATER, 320, 40, C.blu1).setOrigin(0).setDepth(14);
    this.hazards.push({ rect: { x: 1290, y: WF.WATER + 4, w: 320, h: 40 }, kind: 'pit' });
    this.addPlatform(-40, 0, 44, WF.H, 'solid', 'wallL'); this.addPlatform(WF.W, 0, 40, WF.H, 'solid', 'wallR');
    // park furniture, flags, flowers, birds
    for (const x of [150, 900, 1280]) { this.add.image(x, F, 'flagPole').setOrigin(0.5, 1).setDepth(20); this.add.sprite(x + 2, F - 80, 'flag0').setOrigin(0, 0.5).setDepth(21).play('flag'); }
    for (const x of [60, 380, 620, 1100]) this.add.image(x, F + 1, 'flowers').setOrigin(0.5, 1).setDepth(17);
    for (const x of [240, 700, 1230]) { this.add.image(x, F, 'bench').setOrigin(0.5, 1).setDepth(18); this.addPlatform(x - 20, F - 18, 40, 5, 'oneway', 'bench'); const b = this.add.sprite(x + 8, F - 26, 'bird0').setDepth(19).setTint(0xf0f0f0); this.birds.push({ s: b, flown: false }); }
    this.add.image(470, F, 'picnic').setOrigin(0.5, 1).setDepth(18); this.addPlatform(442, F - 26, 56, 5, 'oneway', 'picnic');
    // challenge 1: floating targets
    const bean = (x: number, y: number) => () => this.addPickup('bean', x, y);
    this.switches.push(new Target(this, 320, 150, bean(320, 190)), new Target(this, 370, 120, bean(370, 190)), new Target(this, 420, 165, bean(420, 190)));
    // challenge 2: beach ball hiding a golden leaf
    this.ball = this.add.image(580, F, 'bubble24').setOrigin(0.5, 1).setTint(C.red0).setDepth(30);
    this.add.image(580, F - 12, 'leaf9').setDepth(31).setScale(0.8);
    // challenge 3: tall tree branch (bubble platform)
    this.add.rectangle(800, F, 10, 120, C.wd3).setOrigin(0.5, 1).setDepth(19);
    for (let k = 0; k < 5; k++) this.add.image(780 + k * 12, 108 + (k % 2) * 6, 'glow64').setTint(C.leaf2).setDepth(18).setScale(0.6).setAlpha(0.9);
    this.addPlatform(770, 116, 70, 5, 'oneway', 'branch'); const br = this.add.graphics().setDepth(20); br.fillStyle(C.wd2).fillRect(770, 116, 70, 5);
    this.addPickup('star', 790, 96); this.addPickup('leaf', 825, 96);
    // challenge 4: target behind the hedge
    this.addPlatform(996, F - 26, 26, 26, 'solid', 'hedge'); const hd = this.add.graphics().setDepth(20); hd.fillStyle(C.leaf2).fillRoundedRect(994, F - 28, 30, 28, 8).fillStyle(C.leaf1).fillRoundedRect(997, F - 26, 18, 10, 5); // a low hedge: just hop over
    this.switches.push(new Target(this, 1060, 196, bean(1060, 214)));
    // challenge 5: bubble bell opens the dock gate
    this.gatePlat = this.addPlatform(1336, F - 60, 8, 60, 'solid', 'gate');
    this.gateImg = this.add.rectangle(1336, F - 60, 8, 54, C.wd2).setOrigin(0).setDepth(22);
    this.switches.push(new Target(this, 1318, 178, () => { this.world.remove(this.gatePlat); this.tweens.add({ targets: this.gateImg, angle: -80, duration: 500 }); SFX.door(); this.game.events.emit('hud:toast', 'DING! THE DOCK IS OPEN', C.gold1); }, 'target0', ['shot', 'honk']));
    // beans over the water + drops along the path
    this.addDropLine(1380, 1520, 150, 5);
    for (let i = 0; i < 8; i++) this.addPickup('bean', 80 + i * 130, F - 16);
    this.addPickup('leaf', 1450, 120);
    this.addCrackedWall(1100, F, 'star'); this.addHighStash(300, 70, 'star');
    this.add.image(1570, F - 8, 'bench').setOrigin(0.5, 1).setDepth(18);
    // joggers + cyclist
    this.runners.push({ p: new Person(this, 'jogger', 900, F, { staff: true, state: 'walk' }), v: -55 });
    const cy = new Person(this, 'cyclist', 200, F - 6, { staff: true, state: 'idle' });
    this.runners.push({ p: cy, v: 90, bike: this.add.image(200, F, 'bike').setOrigin(0.5, 1).setDepth(31) });
    this.runners.forEach((r) => this.people.push(r.p));
    this.finishInit({ music: 'waterfront' });
    this.setBurp((GS.coffee as BurpId) || 'vanilla');
    const g = this.goose;
    this.addPrompt(this.key('power'), () => g.x > 250 && g.x < 440 && this.phase === 'play', () => this.switches.slice(0, 3).every((s) => s.on), () => ({ x: g.x, y: g.y - 46 }));
    this.addPrompt(this.key('use'), () => g.x > 700 && g.x < 790 && g.y > F - 4, () => this.counts.star > 0, () => ({ x: g.x, y: g.y - 46 }));
    unlock('waterfront');
    this.phase = 'intro'; g.body.vx = 60; this.time.delayedCall(500, () => { if (this.phase === 'intro') this.phase = 'play'; });
    (window as unknown as { __SIMPS: Record<string, unknown> }).__SIMPS.wf = this;
  }
  onHonkLevel(x: number) { this.scareBirds(x); }
  scareBirds(x: number) {
    for (const b of this.birds) if (!b.flown && Math.abs(b.s.x - x) < 110) {
      b.flown = true; b.s.play('bird_fly'); SFX.tweet(); emote(this, b.s.x, b.s.y - 10, 'SQUAWK!', { life: 700 });
      this.tweens.add({ targets: b.s, x: b.s.x - 160, y: -30, duration: 1700, ease: 'Quad.In' });
    }
  }
  stepLevel(dt: number) {
    for (const r of this.runners) {
      r.p.sprite.x += r.v * dt; r.p.facing = Math.sign(r.v);
      if (r.p.sprite.x < -30) r.p.sprite.x = 1300; if (r.p.sprite.x > 1320) r.p.sprite.x = -20;
      if (r.p.state !== 'walk' && r.p.state !== 'react' && r.p.state !== 'laugh' && !r.bike) r.p.setState('walk');
      r.p.target = r.p.sprite.x + Math.sign(r.v) * 100;
      if (r.bike) r.bike.setPosition(r.p.sprite.x, F).setFlipX(r.v < 0);
      r.p.sprite.anims.timeScale = r.bike ? 0.01 : 1.8;
    }
  }
  frameLevel(dt: number) {
    const cam = this.cameras.main;
    this.layers[0].tilePositionX = cam.scrollX * 0.15; this.layers[1].tilePositionX = cam.scrollX * 0.55;
    this.lake.tilePositionX = cam.scrollX * 0.25 + this.elapsed * 3;
    for (const s of this.shots) if (s.active) {
      this.scareBirds(s.x);
      if (!this.ballLifted && overlap(s.rect(), { x: 568, y: F - 24, w: 24, h: 24 })) {
        this.ballLifted = true; s.kill(); SFX.bubble();
        const enc = this.add.image(this.ball.x, F - 12, 'bubble32').setDepth(31);
        this.tweens.add({ targets: [this.ball, enc], y: '-=70', duration: 900, ease: 'Sine.Out', yoyo: true, hold: 2600, onComplete: () => enc.destroy() });
        this.addPickup('leaf', 580, F - 14);
        emote(this, 580, F - 110, 'WHEEE!', { life: 900 });
      }
    }
    const g = this.goose;
    if (!this.sat && g.x > 1545 && g.y < F && this.phase === 'play') this.sitDown();
    void dt;
  }
  sitDown() {
    this.sat = true; const g = this.goose;
    this.phase = 'cutscene'; g.mode = 'script';
    g.body.x = 1570 - 7; g.body.y = F - 8 - 18 - g.body.h; g.face(1); g.syncSprite(0.016);
    g.playLoop('sitCup');
    MUSIC.stop(1.5);
    this.time.delayedCall(1200, () => { g.playOnce('sipCup'); SFX.slurp(); this.time.delayedCall(900, () => g.playLoop('sitCup')); });
    this.cameras.main.stopFollow(); this.cameras.main.pan(1460, 150, 1500, 'Sine.easeInOut');
    for (let i = 0; i < 6; i++) this.time.delayedCall(2400 + i * 400, () => { const r = this.add.image(1480 + Math.random() * 100, 196 + Math.random() * 20, 'ripple').setScrollFactor(1).setDepth(3).setScale(0.3).setAlpha(0.9); this.tweens.add({ targets: r, scale: 1.6, alpha: 0, duration: 1600, onComplete: () => r.destroy() }); SFX.splash(0.3); });
    this.time.delayedCall(4200, () => { emote(this, g.x, g.y - 40, '?', { life: 1000 }); g.playLoop('holdCup'); });
    this.time.delayedCall(5600, () => { complete('waterfront'); unlock('ogopogo'); GS.persistRun(); this.goTo('Ogopogo'); });
  }
}
