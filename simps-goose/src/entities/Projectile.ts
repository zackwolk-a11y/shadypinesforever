/** Generic bouncing projectile: cherry bubbles, electric fizz, pink fizz, fizz trail, coffee burps. */
import Phaser from 'phaser';
import { PhysicsWorld } from '../systems/physics';
import { SFX } from '../audio/sfx';

export type ShotKind = 'cherry' | 'electric' | 'trail' | 'burp' | 'boss';
export interface ShotOpts { tex: string; vx: number; vy: number; gravity?: number; bounces?: number; life?: number; r?: number; dmg?: number; kind?: ShotKind; tint?: number; scale?: number; floorY?: number; ignoreTags?: string[]; noSound?: boolean; restitution?: number; stun?: number; spin?: boolean }
export class Projectile {
  img: Phaser.GameObjects.Image;
  x: number; y: number; vx: number; vy: number;
  bounces = 0; active = true; t = 0;
  o: Required<Omit<ShotOpts, 'tint' | 'floorY' | 'ignoreTags'>> & { tint?: number; floorY?: number; ignoreTags: string[] };
  constructor(scene: Phaser.Scene, x: number, y: number, opts: ShotOpts) {
    this.o = { gravity: 520, bounces: 4, life: 4, r: 6, dmg: 1, kind: 'cherry', scale: 1, noSound: false, restitution: 0.72, stun: 0.4, spin: true, ignoreTags: [], ...opts };
    this.x = x; this.y = y; this.vx = opts.vx; this.vy = opts.vy;
    this.img = scene.add.image(x, y, opts.tex).setDepth(46).setScale(this.o.scale);
    if (opts.tint !== undefined) this.img.setTint(opts.tint);
    if (!this.o.noSound) SFX.shoot();
  }
  get kind() { return this.o.kind; }
  get dmg() { return this.o.dmg; }
  rect() { const r = this.o.r; return { x: this.x - r, y: this.y - r, w: r * 2, h: r * 2 }; }
  step(dt: number, world: PhysicsWorld): 'ok' | 'pop' {
    if (!this.active) return 'pop';
    this.t += dt;
    this.vy += this.o.gravity * dt;
    const r = this.o.r;
    let nx = this.x + this.vx * dt;
    for (const p of world.platforms) {
      if (!p.active || p.kind !== 'solid' || p.tag === 'floor' || p.tag === 'ceiling' || (p.tag && this.o.ignoreTags.includes(p.tag))) continue;
      if (nx + r > p.x && nx - r < p.x + p.w && this.y + r > p.y && this.y - r < p.y + p.h) { this.vx *= -0.85; nx = this.x; this.bounce(); break; }
    }
    this.x = nx;
    let ny = this.y + this.vy * dt;
    if (this.o.floorY !== undefined && ny + r > this.o.floorY && this.vy > 0) { ny = this.o.floorY - r; this.vy = -Math.abs(this.vy) * this.o.restitution; this.bounce(); }
    for (const p of world.platforms) {
      if (!p.active || p.tag === 'ceiling' || (p.tag && this.o.ignoreTags.includes(p.tag))) continue;
      if (this.vy > 0 && this.x > p.x && this.x < p.x + p.w && this.y + r <= p.y + 1 && ny + r >= p.y) { ny = p.y - r; this.vy = -Math.abs(this.vy) * this.o.restitution; this.bounce(); break; }
      if (this.vy < 0 && p.kind === 'solid' && this.x > p.x && this.x < p.x + p.w && this.y - r >= p.y + p.h - 1 && ny - r <= p.y + p.h) { ny = p.y + p.h + r; this.vy = Math.abs(this.vy) * this.o.restitution; this.bounce(); break; }
    }
    this.y = ny;
    this.img.setPosition(Math.round(this.x), Math.round(this.y));
    if (this.o.spin) this.img.setRotation(this.t * this.vx * 0.03);
    if (this.bounces > this.o.bounces || this.t > this.o.life) { this.kill(); return 'pop'; }
    return 'ok';
  }
  bounce() {
    this.bounces++;
    if (this.o.kind !== 'trail') SFX.bounce();
    const s = this.o.scale;
    this.img.setScale(s * 1.25, s * 0.8);
    this.img.scene.tweens.add({ targets: this.img, scaleX: s, scaleY: s, duration: 120 });
  }
  kill() { if (!this.active) return; this.active = false; this.img.destroy(); if (this.o.kind !== 'trail') SFX.pop(0.8); }
}
