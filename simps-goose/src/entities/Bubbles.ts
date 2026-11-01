/**
 * Pooled soda bubbles — floating platforms that rise, hover, wobble and pop.
 * Each bubble owns a moving one-way platform in the physics world.
 */
import Phaser from 'phaser';
import { PhysicsWorld, Platform } from '../systems/physics';
import { SFX } from '../audio/sfx';
import { CEIL, FLOOR } from '../gameplay/layout';

export type BubbleKind = 'rise' | 'hover' | 'drift';
export interface Bubble {
  active: boolean;
  img: Phaser.GameObjects.Image;
  shadow: Phaser.GameObjects.Image;
  plat: Platform;
  x: number; y: number; r: number;
  vx: number; vy: number;
  kind: BubbleKind;
  t: number; phase: number; anchorY: number; anchorX: number;
  stomps: number; maxStomps: number;
  tint: number;
  wob: number;
  life: number;
  spawnT: number;
}

export class BubbleManager {
  scene: Phaser.Scene; world: PhysicsWorld;
  pool: Bubble[] = [];
  onPop?: (b: Bubble) => void;
  standing: Bubble | null = null;
  constructor(scene: Phaser.Scene, world: PhysicsWorld, size = 26) {
    this.scene = scene; this.world = world;
    for (let i = 0; i < size; i++) {
      const img = scene.add.image(0, 0, 'bubble32').setDepth(45).setVisible(false);
      const shadow = scene.add.image(0, 0, 'shadow32').setDepth(18).setVisible(false);
      const plat = world.add({ x: -999, y: -999, w: 10, h: 4, kind: 'oneway', tag: 'bubble' });
      plat.active = false;
      const b: Bubble = { active: false, img, shadow, plat, x: 0, y: 0, r: 16, vx: 0, vy: 0, kind: 'rise', t: 0, phase: 0, anchorY: 0, anchorX: 0, stomps: 0, maxStomps: 3, tint: 0xffffff, wob: 0, life: 99, spawnT: 0 };
      plat.owner = b;
      plat.onLand = () => this.land(b);
      this.pool.push(b);
    }
  }
  spawn(x: number, y: number, r: number, kind: BubbleKind, opts: { vx?: number; vy?: number; tint?: number; maxStomps?: number; life?: number } = {}) {
    const b = this.pool.find((p) => !p.active);
    if (!b) return null;
    Object.assign(b, { active: true, x, y, r, kind, vx: opts.vx ?? 0, vy: opts.vy ?? -22, t: 0, phase: Math.random() * 6, anchorY: y, anchorX: x, stomps: 0, maxStomps: opts.maxStomps ?? 3, tint: opts.tint ?? 0xffffff, wob: 0, life: opts.life ?? 99, spawnT: 0 });
    const key = r <= 9 ? 'bubble16' : r <= 13 ? 'bubble24' : r <= 17 ? 'bubble32' : r <= 21 ? 'bubble40' : r <= 34 ? 'bubble64' : 'bubble96';
    const base = parseInt(key.replace('bubble', ''), 10);
    b.img.setTexture(key).setVisible(true).setTint(b.tint).setAlpha(1);
    b.img.setData('base', (r * 2) / base);
    b.img.setScale(0.1);
    b.shadow.setVisible(true);
    b.plat.active = true;
    b.plat.w = r * 1.5; b.plat.h = 4;
    this.place(b, 0);
    SFX.bubble();
    return b;
  }
  private land(b: Bubble) {
    b.stomps++;
    b.wob = 1;
    if (b.stomps >= b.maxStomps) this.scene.time.delayedCall(140, () => this.pop(b));
    else if (b.stomps === b.maxStomps - 1) b.img.setTint(0xffd0e0);
    SFX.bounce();
  }
  pop(b: Bubble) {
    if (!b.active) return;
    b.active = false; b.plat.active = false; b.plat.x = -999;
    b.img.setVisible(false); b.shadow.setVisible(false);
    SFX.pop(b.r / 14);
    this.onPop?.(b);
  }
  private place(b: Bubble, dt: number) {
    const prevY = b.plat.y, prevX = b.plat.x;
    const top = b.y - b.r * 0.62;
    b.plat.x = b.x - b.plat.w / 2; b.plat.y = top;
    b.plat.dx = dt > 0 ? b.plat.x - prevX : 0;
    b.plat.dy = dt > 0 ? b.plat.y - prevY : 0;
  }
  /** fixed-step update */
  step(dt: number) {
    for (const b of this.pool) {
      if (!b.active) continue;
      b.t += dt; b.spawnT += dt; b.life -= dt;
      if (b.kind === 'rise') { b.y += b.vy * dt; b.x += (b.vx + Math.sin(b.t * 1.6 + b.phase) * 10) * dt; }
      else if (b.kind === 'hover') { b.y = b.anchorY + Math.sin(b.t * 1.4 + b.phase) * 6; b.x = b.anchorX + Math.sin(b.t * 0.7 + b.phase) * 4; }
      else { b.x += b.vx * dt; b.y += b.vy * dt; b.vx *= Math.pow(0.6, dt); b.vy += (-18 - b.vy) * dt * 0.8; }
      // a goose standing on it pushes it down slightly
      if (b.plat.active && this.standing === b) b.y += 6 * dt;
      if (b.y - b.r < CEIL + 2 || b.life <= 0) { this.pop(b); continue; }
      this.place(b, dt);
    }
  }
  /** per-frame visuals */
  render(dt: number) {
    for (const b of this.pool) {
      if (!b.active) continue;
      b.wob = Math.max(0, b.wob - dt * 2.5);
      const base = b.img.getData('base') as number;
      const grow = Math.min(1, b.spawnT / 0.35);
      const w = Math.sin(b.t * 18) * 0.12 * b.wob;
      const breathe = Math.sin(b.t * 3 + b.phase) * 0.025;
      const strain = b.stomps >= b.maxStomps - 1 ? Math.sin(b.t * 40) * 0.04 : 0;
      b.img.setPosition(Math.round(b.x), Math.round(b.y)).setScale(base * grow * (1 + w + breathe + strain), base * grow * (1 - w - breathe + strain));
      const s = 1 - Math.min(1, (FLOOR - b.y) / 260);
      b.shadow.setPosition(Math.round(b.x), FLOOR + 1).setScale((b.r / 16) * (0.4 + s * 0.6), 0.5 + s * 0.5).setAlpha(0.15 + s * 0.45);
    }
  }
  activeCount() { return this.pool.filter((b) => b.active).length; }
}
