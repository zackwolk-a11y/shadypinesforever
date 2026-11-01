/** Soda Dimension enemies. Simple readable patterns; all stompable or poppable. */
import Phaser from 'phaser';
import type { LevelScene, EnemyLike, Rect } from '../levels/LevelScene';
import { SFX } from '../audio/sfx';
import { C } from '../art/palette';
import { GS } from '../systems/gamestate';
import { settings } from '../systems/settings';

abstract class Enemy implements EnemyLike {
  alive = true; stompable = true; contactDamage = 1; slows = false;
  sprite: Phaser.GameObjects.Sprite; x: number; y: number; w: number; h: number;
  hp = 1; stun = 0; flash = 0; dir = 1; t = Math.random() * 3;
  constructor(public s: LevelScene, x: number, y: number, tex: string, w: number, h: number, public minX = x - 40, public maxX = x + 40) {
    this.x = x; this.y = y; this.w = w; this.h = h;
    this.sprite = s.add.sprite(x, y, tex).setOrigin(0.5, 1).setDepth(42);
    if (settings().highContrast) this.sprite.preFX?.addGlow(0xff3355, 2, 0, false, 0.1, 8);
  }
  rect(): Rect { return { x: this.x - this.w / 2, y: this.y - this.h, w: this.w, h: this.h }; }
  abstract step(dt: number, s: LevelScene): void;
  frame(dt: number) {
    this.flash -= dt;
    this.sprite.setPosition(Math.round(this.x), Math.round(this.y)).setFlipX(this.dir < 0);
    this.sprite.setTintFill?.(0xffffff); if (this.flash <= 0) this.sprite.clearTint();
    if (this.stun > 0) this.sprite.setAngle(Math.sin(this.t * 30) * 8); else this.sprite.setAngle(0);
  }
  hit(dmg: number, dir: number, kind: string) {
    if (!this.alive) return;
    if (kind === 'honk') { this.stun = 1.2; this.s.fx.stars({ x: this.x, y: this.y - this.h + 30 }, 900); SFX.enemyHit(); return; }
    this.hp -= Math.max(1, dmg); this.flash = 0.12; this.x += dir * 6; SFX.enemyHit();
    if (this.hp <= 0) this.defeat();
  }
  stomp() { SFX.stomp(); this.defeat(); }
  defeat() {
    if (!this.alive) return;
    this.alive = false;
    SFX.enemyDefeat();
    this.s.fx.dust(this.x, this.y - this.h / 2, 8); this.s.fx.sparkle(this.x, this.y - this.h / 2, 6, C.gold0); this.s.fx.bubbles(this.x, this.y - this.h / 2, 4);
    GS.addScore(100);
    this.s.tweens.add({ targets: this.sprite, scaleX: 1.4, scaleY: 0.2, alpha: 0, duration: 260, onComplete: () => this.sprite.destroy() });
  }
}

/** Fizz Sprite — hops between two points, sometimes leaps toward the goose. */
export class FizzSprite extends Enemy {
  vy = 0; baseY: number; airborne = false;
  constructor(s: LevelScene, x: number, y: number, minX?: number, maxX?: number) { super(s, x, y, 'fs_idle0', 14, 14, minX, maxX); this.baseY = y; this.sprite.play('fs_idle'); }
  step(dt: number, s: LevelScene) {
    this.t += dt; this.stun -= dt;
    if (this.stun > 0) return;
    if (!this.airborne && this.t > 1.1) {
      this.t = 0; this.airborne = true;
      const near = Math.abs(s.goose.x - this.x) < 90;
      this.vy = near ? -260 : -170; this.dir = near ? Math.sign(s.goose.x - this.x) || 1 : this.dir;
      this.sprite.stop(); this.sprite.setTexture('fs_jump');
    }
    if (this.airborne) {
      this.vy += 700 * dt; this.y += this.vy * dt; this.x += this.dir * 50 * dt;
      if (this.x < this.minX || this.x > this.maxX) { this.dir *= -1; this.x = Phaser.Math.Clamp(this.x, this.minX, this.maxX); }
      if (this.y >= this.baseY) { this.y = this.baseY; this.airborne = false; this.sprite.play('fs_idle'); if (Math.random() < 0.3) SFX.bounce(); }
    }
  }
}
/** Syrup Slug — slow crawler; touching it makes the goose sticky-slow (no damage). */
export class SyrupSlug extends Enemy {
  constructor(s: LevelScene, x: number, y: number, minX?: number, maxX?: number) { super(s, x, y, 'sl_crawl0', 22, 10, minX, maxX); this.sprite.play('sl_crawl'); this.contactDamage = 0; this.slows = true; this.hp = 2; }
  step(dt: number) {
    this.t += dt; this.stun -= dt; if (this.stun > 0) return;
    this.x += this.dir * 14 * dt;
    if (this.x < this.minX || this.x > this.maxX) this.dir *= -1;
    if (Math.random() < dt * 2) this.s.fx.drops(this.x - this.dir * 10, this.y - 2, C.cola1, 1);
  }
}
/** Bottle Bot — patrols, charges when it spots the goose. */
export class BottleBot extends Enemy {
  alert = 0;
  constructor(s: LevelScene, x: number, y: number, minX?: number, maxX?: number) { super(s, x, y, 'bb_walk0', 14, 26, minX, maxX); this.sprite.play('bb_walk'); this.hp = 2; }
  step(dt: number, s: LevelScene) {
    this.t += dt; this.stun -= dt; if (this.stun > 0) return;
    const g = s.goose;
    if (Math.abs(g.x - this.x) < 110 && Math.abs(g.y - this.y) < 30 && Math.sign(g.x - this.x) === this.dir) { if (this.alert <= 0) { SFX.enemyHit(); } this.alert = 0.6; }
    this.alert -= dt;
    const sp = this.alert > 0 ? 85 : 30;
    if (this.alert > 0) { this.sprite.stop(); this.sprite.setTexture('bb_alert'); } else if (!this.sprite.anims.isPlaying) this.sprite.play('bb_walk');
    this.x += this.dir * sp * dt;
    if (this.x < this.minX) { this.x = this.minX; this.dir = 1; } if (this.x > this.maxX) { this.x = this.maxX; this.dir = -1; }
  }
}
/** Foam Monster — swells up to block the route, then shrinks. Pop it while small or with shots. */
export class FoamMonster extends Enemy {
  big = false; cycle = 0;
  constructor(s: LevelScene, x: number, y: number) { super(s, x, y, 'fm_small0', 24, 22, x, x); this.sprite.play('fm_small'); this.hp = 4; }
  step(dt: number) {
    this.stun -= dt;
    this.cycle += dt * (this.stun > 0 ? 0.3 : 1);
    const want = (this.cycle % 4.5) > 2.4;
    if (want !== this.big) {
      this.big = want;
      this.w = want ? 50 : 24; this.h = want ? 46 : 22;
      this.sprite.play(want ? 'fm_big' : 'fm_small');
      this.stompable = !want;
      if (want) { SFX.foam(); this.s.fx.bubbles(this.x, this.y - 20, 6); }
    }
  }
  hit(dmg: number, dir: number, kind: string) { if (kind === 'honk') { this.cycle = 0; this.big = true; } super.hit(dmg, dir, kind === 'honk' ? 'cherry' : kind); }
}
/** Fruit Flyer — bobs in the air, dives at the goose. */
export class FruitFlyer extends Enemy {
  hx: number; hy: number; diving = 0; vx = 0; vy = 0;
  constructor(s: LevelScene, x: number, y: number) { super(s, x, y, 'ff_fly0', 16, 14, x - 60, x + 60); this.hx = x; this.hy = y; this.sprite.play('ff_fly'); this.sprite.setOrigin(0.5, 0.5); }
  rect(): Rect { return { x: this.x - 8, y: this.y - 7, w: 16, h: 14 }; }
  step(dt: number, s: LevelScene) {
    this.t += dt; this.stun -= dt;
    if (this.stun > 0) { this.y += 40 * dt; return; }
    const g = s.goose;
    if (this.diving <= 0 && Math.abs(g.x - this.x) < 80 && g.y > this.y && g.y - this.y < 160 && this.t > 1.5) {
      this.diving = 1.1; this.t = 0; const d = Math.hypot(g.x - this.x, g.y - 20 - this.y); this.vx = (g.x - this.x) / d * 150; this.vy = (g.y - 20 - this.y) / d * 150;
      this.sprite.stop(); this.sprite.setTexture('ff_dive'); SFX.whoosh();
    }
    if (this.diving > 0) { this.diving -= dt; this.x += this.vx * dt; this.y += this.vy * dt; if (this.diving <= 0) this.sprite.play('ff_fly'); }
    else { this.x += (this.hx + Math.sin(this.t * 1.3) * 50 - this.x) * dt * 2; this.y += (this.hy + Math.sin(this.t * 3) * 8 - this.y) * dt * 2; this.dir = Math.cos(this.t * 1.3) > 0 ? 1 : -1; }
  }
}
