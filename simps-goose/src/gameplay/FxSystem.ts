/** Pooled particle effects shared by all scenes. */
import Phaser from 'phaser';
import { C } from '../art/palette';

export class FxSystem {
  scene: Phaser.Scene;
  dustE: Phaser.GameObjects.Particles.ParticleEmitter;
  fizzE: Phaser.GameObjects.Particles.ParticleEmitter;
  dropE: Phaser.GameObjects.Particles.ParticleEmitter;
  sparkE: Phaser.GameObjects.Particles.ParticleEmitter;
  heartE: Phaser.GameObjects.Particles.ParticleEmitter;
  confE: Phaser.GameObjects.Particles.ParticleEmitter;
  steamE: Phaser.GameObjects.Particles.ParticleEmitter;
  bubE: Phaser.GameObjects.Particles.ParticleEmitter;
  constructor(scene: Phaser.Scene, depth = 70) {
    this.scene = scene;
    const P = (tex: string, cfg: Phaser.Types.GameObjects.Particles.ParticleEmitterConfig) => scene.add.particles(0, 0, tex, { emitting: false, ...cfg }).setDepth(depth);
    this.dustE = P('puff8', { lifespan: 450, speed: { min: 15, max: 55 }, angle: { min: 190, max: 350 }, scale: { start: 0.9, end: 0 }, alpha: { start: 0.8, end: 0 }, gravityY: -20 });
    this.fizzE = P('dot2', { lifespan: { min: 300, max: 800 }, speed: { min: 30, max: 110 }, angle: { min: 200, max: 340 }, gravityY: -80, scale: { start: 1, end: 0.4 }, alpha: { start: 1, end: 0 }, tint: [0xffffff, C.bub2, C.bub1] });
    this.dropE = P('dot3', { lifespan: 800, speed: { min: 60, max: 170 }, angle: { min: 200, max: 340 }, gravityY: 520, scale: { start: 1, end: 0.5 } });
    this.sparkE = P('sparkle', { lifespan: 500, speed: { min: 20, max: 70 }, scale: { start: 1, end: 0 }, rotate: { min: 0, max: 90 } });
    this.heartE = P('heart', { lifespan: 1100, speedY: { min: -40, max: -20 }, speedX: { min: -15, max: 15 }, scale: { start: 0.9, end: 0.3 }, alpha: { start: 1, end: 0 } });
    this.confE = P('leafConfetti', { lifespan: 2600, speed: { min: 60, max: 170 }, angle: { min: 220, max: 320 }, gravityY: 70, rotate: { start: 0, end: 540 }, tint: [C.red1, C.wht, C.red0], scale: { min: 0.6, max: 1 } });
    this.steamE = P('puff12', { lifespan: 900, speedY: { min: -40, max: -18 }, speedX: { min: -10, max: 10 }, scale: { start: 0.5, end: 1.4 }, alpha: { start: 0.55, end: 0 } });
    this.bubE = P('bubble16', { lifespan: 1800, speedY: { min: -60, max: -25 }, speedX: { min: -25, max: 25 }, scale: { min: 0.25, max: 0.7 }, alpha: { start: 1, end: 0.3 } });
  }
  dust(x: number, y: number, n = 6) { this.dustE.explode(n, x, y); }
  fizz(x: number, y: number, n = 10) { this.fizzE.explode(n, x, y); }
  drops(x: number, y: number, color: number, n = 10) { this.dropE.particleTint = color; this.dropE.explode(n, x, y); }
  sparkle(x: number, y: number, n = 6, tint = 0xffffff) { this.sparkE.particleTint = tint; this.sparkE.explode(n, x, y); }
  hearts(x: number, y: number, n = 3) { this.heartE.explode(n, x, y); }
  confetti(x: number, y: number, n = 30) { this.confE.explode(n, x, y); }
  steam(x: number, y: number, n = 3) { this.steamE.explode(n, x, y); }
  bubbles(x: number, y: number, n = 6) { this.bubE.explode(n, x, y); }
  honk(x: number, y: number, dir: number, big = false) {
    for (let i = 0; i < (big ? 4 : 3); i++) {
      const a = this.scene.add.image(x + dir * 4, y, 'honkArc').setDepth(75).setFlipX(dir < 0).setScale(0.4).setAlpha(0.95);
      this.scene.tweens.add({ targets: a, x: x + dir * (26 + i * 16) * (big ? 1.6 : 1), scale: (big ? 2.2 : 1.2) + i * 0.25, alpha: 0, delay: i * 70, duration: 420, ease: 'Quad.Out', onComplete: () => a.destroy() });
    }
  }
  splat(x: number, y: number, color: number) {
    const s = this.scene.add.image(x, y, 'splat').setTint(color).setDepth(20).setScale(0.3, 1).setAlpha(0.95);
    this.scene.tweens.add({ targets: s, scaleX: 1 + Math.random() * 0.6, duration: 160 });
    this.scene.tweens.add({ targets: s, alpha: 0, delay: 6000, duration: 1500, onComplete: () => s.destroy() });
  }
  stars(target: { x: number; y: number }, dur = 900) {
    for (let i = 0; i < 3; i++) {
      const s = this.scene.add.image(target.x, target.y, 'star').setDepth(76).setScale(0.7);
      const t0 = this.scene.time.now;
      const ev = () => {
        if (!s.active) return;
        const t = (this.scene.time.now - t0) / 1000;
        s.setPosition(target.x + Math.cos(t * 8 + i * 2.1) * 12, target.y - 30 + Math.sin(t * 8 + i * 2.1) * 4);
      };
      this.scene.events.on('postupdate', ev);
      this.scene.time.delayedCall(dur, () => { this.scene.events.off('postupdate', ev); s.destroy(); });
    }
  }
}
