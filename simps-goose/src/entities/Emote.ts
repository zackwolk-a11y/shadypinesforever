/** Speech/emote balloons sized to their text (crisp pixel rectangles, ink outline). */
import Phaser from 'phaser';
import { txt } from '../art/font';
import { C } from '../art/palette';

export function emote(scene: Phaser.Scene, x: number, y: number, text: string, opts: { color?: number; life?: number; depth?: number } = {}) {
  const lines = wrapText(text, 18);
  const w = Math.max(...lines.map((l) => l.length)) * 6 + 7;
  const h = lines.length * 10 + 5;
  const c = scene.add.container(Math.round(x), Math.round(y)).setDepth(opts.depth ?? 80);
  const g = scene.add.graphics();
  const L = -Math.round(w / 2), T = -h - 4;
  g.fillStyle(C.ink).fillRect(L - 1, T, w + 2, h).fillRect(L, T - 1, w, h + 2);
  g.fillStyle(C.wht).fillRect(L, T, w, h);
  g.fillStyle(C.wl1).fillRect(L, T + h - 1, w, 1);
  g.fillStyle(C.ink).fillTriangle(-4, T + h, 3, T + h, -3, 1);
  g.fillStyle(C.wht).fillTriangle(-3, T + h - 1, 1, T + h - 1, -2, -1);
  const t = txt(scene, 0, T + 3, lines.join('\n'), { outline: false, color: opts.color ?? C.ink, align: 'center' });
  c.add([g, t]);
  c.setScale(0.2);
  scene.tweens.add({ targets: c, scale: 1, duration: 220, ease: 'Back.Out' });
  scene.tweens.add({ targets: c, y: c.y - 6, duration: 900, ease: 'Sine.Out' });
  scene.time.delayedCall(opts.life ?? 1300, () => scene.tweens.add({ targets: c, scale: 0, alpha: 0, duration: 160, onComplete: () => c.destroy() }));
  return c;
}
function wrapText(s: string, n: number) {
  const words = s.split(' '); const lines: string[] = []; let cur = '';
  for (const w of words) { if ((cur + ' ' + w).trim().length > n) { lines.push(cur.trim()); cur = w; } else cur += ' ' + w; }
  lines.push(cur.trim());
  return lines.slice(0, 3);
}
