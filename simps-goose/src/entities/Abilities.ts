/** Flavor-power helpers: foam clouds (Cream Soda) and cherry bubbles (Black Cherry). */
import Phaser from 'phaser';
import { PhysicsWorld, Platform } from '../systems/physics';
import { SFX } from '../audio/sfx';
import { FLOOR } from '../gameplay/layout';

export class Foam {
  img: Phaser.GameObjects.Image;
  plat: Platform;
  t = 0; life = 4.6; startY: number; liftTo: number; active = true;
  constructor(scene: Phaser.Scene, world: PhysicsWorld, x: number, feetY: number, lift: number) {
    this.startY = feetY; this.liftTo = feetY - lift;
    this.plat = world.add({ x: x - 20, y: feetY, w: 40, h: 4, kind: 'oneway', tag: 'foam' });
    this.plat.owner = this;
    this.img = scene.add.image(x, feetY + 7, 'foam').setDepth(44).setScale(0.2);
    scene.tweens.add({ targets: this.img, scale: 1, duration: 260, ease: 'Back.Out' });
    SFX.foam();
  }
  step(dt: number) {
    if (!this.active) return;
    this.t += dt;
    const prevY = this.plat.y;
    const k = Math.min(1, this.t / 0.55);
    const ease = 1 - Math.pow(1 - k, 3);
    const y = this.startY + (this.liftTo - this.startY) * ease + Math.sin(this.t * 3) * (k >= 1 ? 1.5 : 0);
    this.plat.dy = y - prevY; this.plat.dx = 0; this.plat.y = y;
    this.img.y = Math.round(y + 7);
    if (this.t > this.life - 0.8) { const f = (this.life - this.t) / 0.8; this.img.setAlpha(Math.max(0, f)).setScale(0.8 + f * 0.2, Math.max(0.1, f)); }
    if (this.t >= this.life) this.kill();
  }
  kill() { if (!this.active) return; this.active = false; this.plat.active = false; this.img.destroy(); SFX.pop(1.4); }
}

export class CherryShot {
  img: Phaser.GameObjects.Image;
  x: number; y: number; vx: number; vy: number;
  bounces = 0; active = true; t = 0;
  constructor(scene: Phaser.Scene, x: number, y: number, dir: number) {
    this.x = x; this.y = y; this.vx = dir * 210; this.vy = -150;
    this.img = scene.add.image(x, y, 'cherryShot').setDepth(46);
    SFX.shoot();
  }
  rect() { return { x: this.x - 6, y: this.y - 6, w: 12, h: 12 }; }
  step(dt: number, world: PhysicsWorld): 'ok' | 'pop' {
    if (!this.active) return 'pop';
    this.t += dt;
    this.vy += 520 * dt;
    let nx = this.x + this.vx * dt;
    const r = 6;
    for (const p of world.platforms) {
      if (!p.active || p.kind !== 'solid' || p.tag === 'floor' || p.tag === 'ceiling' || p.tag === 'boxwall') continue;
      if (nx + r > p.x && nx - r < p.x + p.w && this.y + r > p.y && this.y - r < p.y + p.h) { this.vx *= -0.8; nx = this.x; this.bounce(); break; }
    }
    this.x = nx;
    let ny = this.y + this.vy * dt;
    if (ny + r > FLOOR) { ny = FLOOR - r; this.vy = -Math.abs(this.vy) * 0.72; this.bounce(); }
    for (const p of world.platforms) {
      if (!p.active || p.tag === 'floor' || p.tag === 'ceiling') continue;
      if (this.vy > 0 && this.x > p.x && this.x < p.x + p.w && this.y + r <= p.y + 1 && ny + r >= p.y) { ny = p.y - r; this.vy = -Math.abs(this.vy) * 0.72; this.bounce(); break; }
    }
    this.y = ny;
    this.img.setPosition(Math.round(this.x), Math.round(this.y)).setRotation(this.t * this.vx * 0.03);
    if (this.bounces > 4 || this.t > 4) { this.kill(); return 'pop'; }
    return 'ok';
  }
  bounce() { this.bounces++; SFX.bounce(); this.img.setScale(1.25, 0.8); this.img.scene.tweens.add({ targets: this.img, scaleX: 1, scaleY: 1, duration: 120 }); }
  kill() { if (!this.active) return; this.active = false; this.img.destroy(); SFX.pop(0.8); }
}

/** Trident Lift — a piston platform that cycles once the fountain is pressurised. */
export class TridentLift {
  head: Phaser.GameObjects.Image; shaft: Phaser.GameObjects.TileSprite; plat: Platform;
  x: number; low: number; high: number; t = 0; running = false; y: number;
  constructor(scene: Phaser.Scene, world: PhysicsWorld, x: number, low: number, high: number) {
    this.x = x; this.low = low; this.high = high; this.y = low;
    this.shaft = scene.add.tileSprite(x, FLOOR, 10, 1, 'piston').setOrigin(0.5, 1).setDepth(33);
    this.head = scene.add.image(x, low, 'liftHead').setOrigin(0.5, 0).setDepth(34);
    this.plat = world.add({ x: x - 22, y: low, w: 44, h: 5, kind: 'oneway', tag: 'lift' });
  }
  step(dt: number) {
    const prev = this.y;
    if (this.running) { this.t += dt; const k = (1 - Math.cos(this.t * Math.PI * 2 / 5)) / 2; this.y = this.low + (this.high - this.low) * k; }
    this.plat.y = this.y; this.plat.dy = this.y - prev; this.plat.dx = 0;
  }
  render() { this.head.y = Math.round(this.y); this.shaft.height = Math.max(1, FLOOR - Math.round(this.y) - 10); }
}
