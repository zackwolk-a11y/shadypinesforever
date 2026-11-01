/** The tasting counter: flavor picker, sip → swallow → reaction → power. */
import Phaser from 'phaser';
import type { StoreScene } from '../scenes/StoreScene';
import { Controls } from '../systems/input';
import { SFX } from '../audio/sfx';
import { FLAVORS, FLAVOR_ORDER, FlavorId } from './flavors';
import { FLOOR, L } from './layout';
import { emote } from '../entities/Emote';
import { addUnique, save } from '../systems/save';
import { achieve } from '../data/achievements';
import { shake } from '../systems/camfx';

export const CUP_X = [L.sample.x + 56, L.sample.x + 72, L.sample.x + 88];
const TOP = FLOOR - L.sample.h;

export class Sampling {
  s: StoreScene;
  cups: Phaser.GameObjects.Image[] = [];
  idx = 0;
  greeted = false;
  constructor(s: StoreScene) {
    this.s = s;
    FLAVOR_ORDER.forEach((id, i) => {
      this.cups.push(s.add.image(CUP_X[i], TOP + 1, 'cup_' + id).setOrigin(0.5, 1).setDepth(31));
      s.add.image(L.sample.x + 12 + i * 13, TOP + 1, 'pump_' + id).setOrigin(0.5, 1).setDepth(28);
    });
  }
  inZone() { const g = this.s.goose; return g.x > L.sample.x - 26 && g.x < L.sample.x + L.sample.w + 10 && g.y > TOP - 30; }
  nearGreet() { return Math.abs(this.s.goose.x - (L.sample.x + 40)) < 150; }
  update() {
    if (!this.greeted && this.nearGreet()) {
      this.greeted = true;
      const sam = this.s.sam;
      sam.say('FREE SAMPLES! HOP UP!', 2200); sam.setState('gesture', 2.5); SFX.hey(1.1);
    }
    if (this.s.phase !== 'picker') return;
    if (Controls.pressed('left')) { this.idx = (this.idx + 2) % 3; SFX.ui('move'); this.highlight(); }
    if (Controls.pressed('right')) { this.idx = (this.idx + 1) % 3; SFX.ui('move'); this.highlight(); }
    if (Controls.pressed('interact') || Controls.pressed('jump')) this.choose(this.idx);
    else if (Controls.pressed('honk') || Controls.pressed('back')) this.close();
  }
  open() {
    this.s.phase = 'picker';
    this.s.goose.body.vx = 0;
    this.idx = Math.max(0, FLAVOR_ORDER.indexOf((this.s.power ?? 'cola') as FlavorId));
    SFX.ui('ok');
    Controls.consume('interact'); Controls.consume('confirm'); Controls.consume('jump');
    this.s.sam.setState('gesture', 3);
    this.highlight();
  }
  pick(i: number) { if (this.s.phase !== 'picker') return; this.idx = i; this.choose(i); }
  highlight() {
    this.cups.forEach((c, i) => { this.s.tweens.killTweensOf(c); c.y = TOP + 1; if (i === this.idx) this.s.tweens.add({ targets: c, y: TOP - 3, yoyo: true, repeat: -1, duration: 260, ease: 'Sine.InOut' }); });
    this.s.game.events.emit('hud:picker', { open: true, idx: this.idx });
  }
  close() {
    this.cups.forEach((c) => { this.s.tweens.killTweensOf(c); c.y = TOP + 1; });
    this.s.game.events.emit('hud:picker', { open: false, idx: this.idx });
    if (this.s.phase === 'picker') this.s.phase = 'play';
    SFX.ui('back');
  }
  choose(i: number) {
    const id = FLAVOR_ORDER[i];
    this.cups.forEach((c) => { this.s.tweens.killTweensOf(c); c.y = TOP + 1; });
    this.s.game.events.emit('hud:picker', { open: false, idx: i });
    SFX.ui('ok');
    this.drink(id);
  }
  drink(id: FlavorId) {
    const s = this.s, g = s.goose, f = FLAVORS[id];
    const cup = this.cups[FLAVOR_ORDER.indexOf(id)];
    s.phase = 'cutscene';
    g.mode = 'script'; g.ride = null;
    const tx = cup.x - 17, ty = TOP;
    g.face(1);
    const hop = (done: () => void) => {
      if (Math.abs(g.y - ty) < 2 && Math.abs(g.x - tx) < 2) return done();
      g.playLoop('jump'); SFX.jump();
      const sx = g.body.x, sy = g.body.y, ex = tx - g.body.w / 2, ey = ty - g.body.h;
      const peak = Math.min(sy, ey) - 26;
      s.tweens.addCounter({ from: 0, to: 1, duration: 420, onUpdate: (tw: Phaser.Tweens.Tween) => {
        const k = tw.getValue() as number;
        g.body.x = sx + (ex - sx) * k;
        g.body.y = (1 - k) * (1 - k) * sy + 2 * (1 - k) * k * peak + k * k * ey;
        g.syncSprite(0.016);
      }, onComplete: () => { g.squash(1.25, 0.8); SFX.land(); s.fx.dust(g.x, g.y, 4); done(); } });
    };
    hop(() => {
      s.sam.setState('gesture', 2);
      g.playOnce('drink');
      SFX.slurp();
      s.time.delayedCall(450, () => { cup.setTexture('cup_empty'); s.fx.drops(cup.x, cup.y - 6, f.light, 4); });
      s.time.delayedCall(800, () => { g.playOnce('swallow'); SFX.gulp(); });
      s.time.delayedCall(1500, () => this.react(id));
    });
  }
  react(id: FlavorId) {
    const s = this.s, g = s.goose, f = FLAVORS[id];
    g.playLoop(f.react);
    const head = { x: g.x + 10, y: g.y - 28 };
    if (id === 'cola') {
      SFX.fizz(1.2, 1.4); SFX.honk(0.7);
      shake(s, 400, 0.004);
      for (let k = 0; k < 10; k++) s.time.delayedCall(k * 110, () => s.fx.fizz(g.x + 4, g.y - 20, 6));
      emote(s, g.x + 6, g.y - 44, 'FIZZ!!', { life: 1100, color: f.color });
    } else if (id === 'cream') {
      SFX.sparkle(); SFX.honk(0.55);
      for (let k = 0; k < 5; k++) s.time.delayedCall(k * 230, () => s.fx.hearts(head.x, head.y, 1));
      s.fx.sparkle(head.x, head.y, 8, 0xfff1c0);
      s.tweens.add({ targets: g.sprite, y: g.sprite.y - 3, yoyo: true, repeat: 2, duration: 220 });
    } else {
      SFX.oh(1.6);
      s.time.delayedCall(700, () => { SFX.honk(1.2); s.fx.sparkle(head.x, head.y, 10, 0xff5f87); s.fx.drops(head.x, head.y, f.light, 8); });
      emote(s, g.x + 6, g.y - 44, '!!', { life: 1300, color: f.color });
    }
    s.time.delayedCall(1450, () => {
      s.setPower(id);
      addUnique('flavors', id);
      if (FLAVOR_ORDER.every((f) => save().flavors.includes(f))) achieve('flavor_explorer');
      s.sam.say(f.staffLine, 1800); s.sam.setState('laugh', 1.2); SFX.laugh(1.15);
      g.mode = 'play'; g.playLoop('idle'); g.wasGround = true;
      s.phase = 'play';
      const cup = this.cups[FLAVOR_ORDER.indexOf(id)];
      s.time.delayedCall(2500, () => { cup.setTexture('cup_' + id); s.fx.sparkle(cup.x, cup.y - 5, 3); });
    });
  }
}
