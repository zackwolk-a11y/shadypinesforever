/** Speech/emote balloons that pop in above characters. */
import Phaser from 'phaser';
import { txt } from '../art/font';
import { C } from '../art/palette';

export function emote(scene: Phaser.Scene, x: number, y: number, text: string, opts: { color?: number; life?: number; follow?: { x: number; y: number }; depth?: number } = {}) {
  const len = text.length;
  const key = len <= 2 ? 'balloonS' : len <= 4 ? 'balloonM' : len <= 11 ? 'balloonL' : 'balloonXL';
  const c = scene.add.container(Math.round(x), Math.round(y)).setDepth(opts.depth ?? 80);
  const img = scene.add.image(0, 0, key).setOrigin(0.5, 1);
  const wrap = key === 'balloonXL' ? wrapText(text, 20) : text;
  const t = txt(scene, 0, -img.height + (key === 'balloonXL' ? 3 : 4), wrap, { outline: false, color: opts.color ?? C.ink, align: 'center' });
  c.add([img, t]);
  c.setScale(0.2);
  scene.tweens.add({ targets: c, scale: 1, duration: 220, ease: 'Back.Out' });
  scene.tweens.add({ targets: c, y: c.y - 6, duration: 900, ease: 'Sine.Out' });
  const life = opts.life ?? 1300;
  scene.time.delayedCall(life, () => scene.tweens.add({ targets: c, scale: 0, alpha: 0, duration: 160, onComplete: () => c.destroy() }));
  if (opts.follow) {
    const f = opts.follow, dy = y - f.y;
    const ev = scene.events.on('postupdate', () => { if (c.active) c.x = Math.round(f.x); else scene.events.off('postupdate', ev as never); });
    void dy;
  }
  return c;
}
function wrapText(s: string, n: number) {
  const words = s.split(' '); const lines: string[] = []; let cur = '';
  for (const w of words) { if ((cur + ' ' + w).trim().length > n) { lines.push(cur.trim()); cur = w; } else cur += ' ' + w; }
  lines.push(cur.trim());
  return lines.slice(0, 2).join('\n');
}
