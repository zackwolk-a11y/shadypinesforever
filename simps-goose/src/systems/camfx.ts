/** Camera effects that respect the accessibility settings. */
import Phaser from 'phaser';
import { settings } from './settings';
export function shake(scene: Phaser.Scene, dur: number, intensity: number) {
  const s = settings();
  if (s.reduceShake) return;
  scene.cameras.main.shake(dur, intensity);
}
export function flash(scene: Phaser.Scene, dur = 150, r = 255, g = 255, b = 255) {
  if (settings().reduceFlash) { scene.cameras.main.fadeIn(Math.min(dur * 2, 300), r * 0.3, g * 0.3, b * 0.3); return; }
  scene.cameras.main.flash(dur, r, g, b);
}
