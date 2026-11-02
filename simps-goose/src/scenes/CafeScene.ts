/**
 * LEVEL 3a — ONE LAST SIP: the café. Stool → barista → specialty coffee mini-game →
 * the first burp → Bubble Burp unlocked → practice targets → out the door to the lake.
 */
import Phaser from 'phaser';
import { C } from '../art/palette';
import { CAFE } from '../art/cafe';
import { LevelScene, Rect, SwitchLike } from '../levels/LevelScene';
import { Person } from '../entities/Person';
import { emote } from '../entities/Emote';
import { CoffeeResult } from './CoffeeScene';
import { BURPS } from '../data/coffee';
import { achieve } from '../data/achievements';
import { GS } from '../systems/gamestate';
import { addUnique, update, unlock, complete, StageId } from '../systems/save';
import { Controls } from '../systems/input';
import { SFX } from '../audio/sfx';

const F = CAFE.FLOOR;
class Target implements SwitchLike {
  on = false; by = ['shot', 'honk'];
  img: Phaser.GameObjects.Image;
  constructor(public s: CafeScene, public x: number, public y: number) { this.img = s.add.image(x, y, 'target0').setDepth(25).setScale(0.8); }
  rect(): Rect { return { x: this.x - 12, y: this.y - 12, w: 24, h: 24 }; }
  activate(src: string) { if (this.on || (src === 'honk')) { if (src === 'honk') emote(this.s, this.x, this.y - 18, 'BURP AT IT!', { life: 700 }); return; } this.on = true; this.img.setTexture('target1'); SFX.chime(); this.s.fx.sparkle(this.x, this.y, 8, C.gold0); this.s.addPickup('bean', this.x, this.y + 30); this.s.targetsHit++; }
}

export class CafeScene extends LevelScene {
  stage: StageId = 'cafe';
  barista!: Person; served = false; burpReady = false; targetsHit = 0; exiting = false; sat = false;
  stoolX = 470;
  constructor() { super('Cafe'); }
  create() {
    this.levelName = 'LEVEL 3: ONE LAST SIP';
    this.initLevel({ w: CAFE.W, h: CAFE.H, floor: F, bg: 0xf4dcb4, spawn: { x: 40, y: F } });
    this.served = false; this.burpReady = false; this.targetsHit = 0; this.exiting = false; this.sat = false;
    this.add.image(0, 0, 'cafeWall').setOrigin(0).setScrollFactor(0.88, 1).setDepth(0);
    for (const wx of [100, 480, 860]) this.add.image(wx * 0.88, 40, 'shaft').setOrigin(0.2, 0).setScale(0.9, 0.75).setBlendMode(Phaser.BlendModes.ADD).setAlpha(0.28).setTint(0xffe2a0).setScrollFactor(0.88, 1).setDepth(55);
    this.add.tileSprite(0, F, CAFE.W, 30, 'cafeFloor').setOrigin(0).setDepth(15);
    this.addPlatform(-40, F, CAFE.W + 80, 40, 'solid', 'floor'); this.addPlatform(-40, 0, 44, CAFE.H, 'solid', 'wallL'); this.addPlatform(CAFE.W - 4, 0, 44, CAFE.H, 'solid', 'wallR');
    this.add.image(26, F, 'cafeDoor').setOrigin(0.5, 1).setDepth(5);
    this.add.image(CAFE.W - 30, F, 'cafeDoor').setOrigin(0.5, 1).setDepth(5);
    this.add.tileSprite(0, 2, CAFE.W, 22, 'bunting').setOrigin(0).setDepth(6).setAlpha(0.9);
    for (const x of [90, 220]) { this.add.image(x, F, 'cafeTable').setOrigin(0.5, 1).setDepth(28); this.addPlatform(x - 22, F - 34, 44, 5, 'oneway', 'table'); this.add.image(x - 8, F - 34, 'mug_a').setOrigin(0.5, 1).setDepth(29); }
    // counter + gear
    this.addPlatform(330, F - 52, 300, 5, 'oneway', 'counter');
    this.barista = new Person(this, 'barista', 520, F, { staff: true, depth: 26, facing: -1 }); this.people.push(this.barista);
    this.add.image(480, F, 'cafeCounter').setOrigin(0.5, 1).setDepth(29);
    this.add.image(580, F - 52, 'espresso').setOrigin(0.5, 1).setDepth(30);
    this.add.image(372, F - 52, 'pastryCase').setOrigin(0.5, 1).setDepth(30);
    this.add.image(560, F - 140, 'flag0').setDepth(6);
    for (const x of [430, 470, 510]) { this.add.image(x - 70, F, 'stool').setOrigin(0.5, 1).setDepth(31); }
    this.stoolX = 400;
    this.addPlatform(this.stoolX - 8, F - 30, 16, 5, 'oneway', 'stool');
    // high shelf with a golden leaf (bubble-platform practice)
    this.addPlatform(700, 120, 70, 5, 'oneway', 'shelf'); const sg = this.add.graphics().setDepth(27); sg.fillStyle(C.wd1).fillRect(700, 120, 70, 5).fillStyle(C.wd0).fillRect(700, 120, 70, 1);
    this.add.image(712, 120, 'mug_b').setOrigin(0.5, 1).setDepth(28); this.add.image(756, 120, 'mug_a').setOrigin(0.5, 1).setDepth(28);
    this.addPickup('leaf', 735, 100);
    for (let i = 0; i < 4; i++) this.addPickup('bean', 120 + i * 40, F - 50);
    this.addCrackedWall(890, F, 'star');
    this.finishInit({ music: 'cafe' });
    if (GS.coffee) { this.setBurp(GS.coffee as never); this.served = true; this.burpReady = true; this.spawnTargets(); }
    const g = this.goose;
    this.addPrompt(this.key('use'), () => !this.served && Math.abs(g.x - this.stoolX) < 50, () => this.served, () => ({ x: this.stoolX, y: F - 74 }));
    this.addPrompt(this.key('power'), () => this.burpReady && this.targetsHit < 3 && this.phase === 'play', () => this.targetsHit >= 3, () => ({ x: g.x, y: g.y - 46 }));
    this.addPrompt(this.key('use'), () => this.burpReady && g.x > 640 && g.x < 790 && g.y > F - 4 && this.phase === 'play', () => this.counts.leaf > 0, () => ({ x: 735, y: 80 }));
    unlock('cafe');
    update((s) => { s.fakeEndingSeen = true; });
    this.phase = 'intro'; this.goose.body.vx = 60;
    this.time.delayedCall(600, () => { if (this.phase === 'intro') this.phase = 'play'; });
    (window as unknown as { __SIMPS: Record<string, unknown> }).__SIMPS.cafe = this;
  }
  spawnTargets() { for (const [x, y] of [[650, 170], [820, 150], [880, 200]] as [number, number][]) this.switches.push(new Target(this, x, y)); }
  onInteract() {
    if (!this.served && Math.abs(this.goose.x - this.stoolX) < 50) { this.order(); return true; }
    return false;
  }
  order() {
    const g = this.goose, b = this.barista;
    this.phase = 'cutscene'; g.mode = 'script';
    const sx = g.body.x, sy = g.body.y, ex = this.stoolX - 7, ey = F - 30 - g.body.h;
    g.playLoop('jump'); SFX.jump();
    this.tweens.addCounter({ from: 0, to: 1, duration: 380, onUpdate: (tw: Phaser.Tweens.Tween) => { const k = tw.getValue() as number; g.body.x = sx + (ex - sx) * k; g.body.y = sy + (ey - sy) * k - Math.sin(k * Math.PI) * 20; g.face(1); g.syncSprite(0.016); }, onComplete: () => { g.playLoop('sit'); SFX.land(); } });
    b.setState('walk'); b.facing = -1;
    this.tweens.add({ targets: b.sprite, x: 440, duration: 800, onComplete: () => b.setState('idle', 99) });
    this.time.delayedCall(1000, () => { b.say('WHAT CAN I GET YOU?', 1700); SFX.hey(1.1); });
    this.time.delayedCall(2600, () => { g.playOnce('honk'); this.time.delayedCall(140, () => { SFX.honk(1); this.fx.honk(g.x + 12, g.y - 30, 1); emote(this, g.x, g.y - 44, 'HONK!', { life: 1000 }); }); });
    this.time.delayedCall(3800, () => { b.say('SOMETHING SPECIAL. GOT IT.', 1800); b.setState('gesture', 2); });
    this.time.delayedCall(5400, () => {
      this.scene.pause(); this.phase = 'picker';
      this.scene.launch('Coffee', { onDone: (r: CoffeeResult) => { this.scene.resume(); Controls.consumeAll(); this.served = true; this.serve(r); } });
      this.scene.bringToTop('Coffee');
    });
  }
  serve(r: CoffeeResult) {
    const g = this.goose, b = this.barista;
    this.phase = 'cutscene';
    GS.coffee = r.burp; GS.addScore(300 + Math.round(r.quality * 200));
    addUnique('coffees', r.burp); addUnique('flavors', 'cafe_' + r.burp); if (r.second) addUnique('flavors', 'cafe_' + r.second);
    achieve('coffee_break');
    b.say(`ONE ${r.name}. ENJOY!`, 2000); SFX.espresso(1); SFX.froth(0.8);
    g.playLoop('sitCup');
    const sip = (at: number) => this.time.delayedCall(at, () => { g.playOnce('sipCup'); SFX.slurp(); this.time.delayedCall(850, () => g.playLoop('sitCup')); });
    sip(1900);
    this.time.delayedCall(3200, () => { g.playOnce('growl'); SFX.growl(); this.say('*RUMBLE*', g.x, g.y - 44, 900); });
    this.time.delayedCall(4300, () => { g.playOnce('burp'); SFX.burp(); const bub = this.add.image(g.x + 14, g.y - 30, 'bubble16').setTint(BURPS[r.burp].light).setScale(0.5).setDepth(47); this.tweens.add({ targets: bub, y: bub.y - 50, scale: 0.8, duration: 1500, ease: 'Sine.Out', onComplete: () => { bub.destroy(); SFX.pop(0.7); this.fx.sparkle(bub.x, bub.y, 4); } }); });
    this.time.delayedCall(6000, () => { g.playLoop('sitCup'); emote(this, g.x, g.y - 44, '!!', { life: 900 }); b.setState('laugh', 1.2); SFX.laugh(1.1); });
    sip(6900);
    this.time.delayedCall(8200, () => { g.playOnce('burp'); SFX.burp(); SFX.burp(); const bub = this.add.image(g.x + 16, g.y - 32, 'bubble32').setTint(BURPS[r.burp].light).setScale(0.3).setDepth(47); this.tweens.add({ targets: bub, y: bub.y - 70, scale: 1.1, duration: 1800, ease: 'Sine.Out', onComplete: () => { bub.destroy(); SFX.pop(1.3); this.fx.confetti(bub.x, bub.y, 12); } }); });
    this.time.delayedCall(10200, () => {
      this.setBurp(r.burp); this.burpReady = true;
      this.game.events.emit('hud:toast', `BUBBLE BURP: ${BURPS[r.burp].power}!`, BURPS[r.burp].light, this.touch ? 'POWER: BURP   SIP: BUBBLE PLATFORM' : 'C: BURP   E: BUBBLE PLATFORM');
      SFX.powerup();
      g.mode = 'play'; g.playLoop('idle'); g.body.vy = -100; this.phase = 'play';
      this.spawnTargets();
      GS.persistRun();
    });
  }
  frameLevel() {
    const g = this.goose;
    if (!this.exiting && this.burpReady && g.x > CAFE.W - 50 && this.phase === 'play') {
      this.exiting = true; complete('cafe'); unlock('waterfront'); SFX.door();
      this.levelClear('Waterfront', { title: 'COFFEE TIME!', delay: 2600 });
    }
    if (!this.burpReady && g.x > CAFE.W - 60 && this.phase === 'play') { g.body.x = CAFE.W - 60 - g.body.w; if (Math.random() < 0.02) emote(this, g.x, g.y - 44, 'COFFEE FIRST!', { life: 800 }); }
  }
}
