/** Interactive store props: knockable shelf bottles and the delivery box wall. */
import Phaser from 'phaser';
import { PhysicsWorld, Platform } from '../systems/physics';
import { SFX } from '../audio/sfx';
import { FLOOR } from '../gameplay/layout';

export class ShelfBottle {
  img: Phaser.GameObjects.Image;
  state: 'rest' | 'fall' | 'down' = 'rest';
  vx = 0; vy = 0; va = 0;
  wob = 0; wobT = 0;
  bounces = 0;
  canHurt = false;
  knockable: boolean;
  baseY: number;
  constructor(scene: Phaser.Scene, x: number, y: number, tex: string, knockable: boolean, depth = 31) {
    this.img = scene.add.image(x, y, tex).setOrigin(0.5, 1).setDepth(depth);
    this.knockable = knockable;
    this.baseY = y;
  }
  get x() { return this.img.x; }
  get y() { return this.img.y; }
  jiggle(amt = 1) { if (this.state !== 'rest') return; this.wob = Math.max(this.wob, amt); }
  knock(dir: number, power = 1, canHurt = false) {
    if (this.state !== 'rest' || !this.knockable) { this.jiggle(1); return; }
    this.state = 'fall';
    this.canHurt = canHurt;
    this.vx = dir * (40 + Math.random() * 50) * power; this.vy = -90 - Math.random() * 60;
    this.va = dir * (6 + Math.random() * 6);
    this.img.setDepth(42);
    SFX.clink(1 + Math.random() * 0.3);
  }
  step(dt: number, world: PhysicsWorld) {
    if (this.state === 'rest') {
      if (this.wob > 0) { this.wobT += dt; this.wob = Math.max(0, this.wob - dt * 1.4); this.img.rotation = Math.sin(this.wobT * 28) * 0.18 * this.wob; }
      else this.img.rotation = 0;
      return;
    }
    if (this.state === 'down') return;
    const prevY = this.img.y;
    this.vy += 900 * dt;
    this.img.x += this.vx * dt; this.img.y += this.vy * dt;
    this.img.rotation += this.va * dt;
    const floor = Math.min(FLOOR, world.surfaceBelow(this.img.x, prevY - 1));
    if (this.img.y >= floor && this.vy > 0) {
      this.img.y = floor;
      this.bounces++;
      SFX.clink(0.8 + Math.random() * 0.4);
      if (this.bounces >= 3 || Math.abs(this.vy) < 80) {
        this.state = 'down';
        this.img.setRotation(Math.sign(this.va || 1) * Math.PI / 2).setOrigin(0.5, 0.75);
        this.img.setDepth(21);
      } else { this.vy *= -0.38; this.vx *= 0.6; this.va *= 0.6; }
    }
  }
}

export class BoxWall {
  scene: Phaser.Scene;
  boxes: Phaser.GameObjects.Image[] = [];
  plat: Platform;
  toppled = false;
  x: number; w: number; h: number;
  constructor(scene: Phaser.Scene, world: PhysicsWorld, x: number, cols: number, rows: number, bw: number, bh: number) {
    this.scene = scene; this.x = x; this.w = cols * bw; this.h = rows * bh;
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
      const img = scene.add.image(x + c * bw + bw / 2 + (r % 2 ? 1 : -1), FLOOR - r * bh - bh / 2, 'box' + ((r * cols + c) % 3)).setDepth(36);
      this.boxes.push(img);
    }
    this.plat = world.add({ x, y: FLOOR - this.h, w: this.w, h: this.h, kind: 'solid', tag: 'boxwall' });
  }
  rect() { return { x: this.x, y: FLOOR - this.h, w: this.w, h: this.h }; }
  wobble() { if (this.toppled) return; this.boxes.forEach((b, i) => this.scene.tweens.add({ targets: b, angle: { from: -3, to: 3 }, yoyo: true, duration: 70, repeat: 2, delay: i * 15, onComplete: () => b.setAngle(0) })); SFX.crash(); }
  topple(dir: number, world: PhysicsWorld, onDust?: (x: number, y: number) => void) {
    if (this.toppled) return;
    this.toppled = true;
    world.remove(this.plat);
    SFX.crash();
    this.boxes.forEach((b, i) => {
      const tx = b.x + dir * (20 + Math.random() * 110) + (i % 2) * dir * 10;
      const peak = b.y - 30 - Math.random() * 40;
      const land = FLOOR - 11;
      const spin = dir * (90 + Math.random() * 270);
      this.scene.tweens.add({ targets: b, x: tx, duration: 650 + i * 40, ease: 'Quad.Out' });
      this.scene.tweens.add({ targets: b, angle: spin, duration: 650 + i * 40, ease: 'Quad.Out', onComplete: () => b.setAngle(Math.round(spin / 90) * 90) });
      this.scene.tweens.chain({ targets: b, tweens: [
        { y: peak, duration: 200 + i * 10, ease: 'Quad.Out' },
        { y: land, duration: 300 + i * 25, ease: 'Bounce.Out', onComplete: () => { onDust?.(b.x, FLOOR); b.setDepth(22); } },
      ] });
    });
  }
}
