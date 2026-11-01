/** Soda Dimension creatures — 5 enemy types, each with idle/move, attack, hurt frames. */
import { C, R } from './palette';
import { Px } from './px';
import { tridentInto } from './motifs';

function eyes(g: Px, x: number, y: number, mood: 'normal' | 'angry' | 'hurt' | 'happy', gap = 4) {
  for (const ex of [x, x + gap]) {
    if (mood === 'hurt') { g.line(ex - 1, y - 1, ex + 1, y + 1, C.ink); g.line(ex - 1, y + 1, ex + 1, y - 1, C.ink); continue; }
    g.rect(ex - 1, y - 1, 3, 3, C.wht); g.rect(ex, y, 2, 2, C.ink); g.set(ex, y, C.wht);
    if (mood === 'angry') g.line(ex - 1, y - 3 + (ex === x ? 0 : 1), ex + 2, y - 2 - (ex === x ? 0 : 1), C.ink);
  }
}
export function fizzSprite(f: 'idle0' | 'idle1' | 'jump' | 'hurt'): Px {
  const g = new Px(20, 20);
  const sy = f === 'idle1' ? 0.8 : f === 'jump' ? 1.2 : 1, sx = 2 - sy;
  const cy = 13 - (f === 'jump' ? 2 : 0);
  g.shadedEllipse(10, cy, 7 * sx, 6.5 * sy, R.blue);
  g.ring(10, cy, 7 * Math.max(sx, sy) - 0.5, C.blu0);
  for (const [x, y] of [[7, cy - 9], [12, cy - 11], [15, cy - 8]]) g.ring(x, y, 1.2, C.bub2);
  eyes(g, 7, cy - 1, f === 'hurt' ? 'hurt' : f === 'jump' ? 'angry' : 'normal');
  g.hline(8, 11, cy + 3, C.blu3);
  g.outline(C.ink);
  return g;
}
export function syrupSlug(f: 'crawl0' | 'crawl1' | 'hurt'): Px {
  const g = new Px(28, 18);
  const st = f === 'crawl1' ? 2 : 0;
  g.shadedEllipse(14 - st / 2, 12, 11 + st, 5, R.cola);
  g.rect(4, 14, 20 + st, 3, C.cola2);
  g.set(9, 9, C.cola0); g.set(10, 9, C.cola0);
  // eye stalks
  for (const x of [19, 23]) { g.line(x, 9, x + 1, 3, C.cola1); }
  eyes(g, 20, 2, f === 'hurt' ? 'hurt' : 'normal', 4);
  g.outline(C.ink);
  // drip
  g.set(6, 17, C.cola1);
  return g;
}
export function bottleBot(f: 'walk0' | 'walk1' | 'alert' | 'hurt'): Px {
  const g = new Px(20, 30);
  const leg = f === 'walk1' ? 2 : 0;
  g.line(7, 24, 5 + leg, 29, C.st2); g.line(13, 24, 15 - leg, 29, C.st2); g.hline(3 + leg, 7 + leg, 29, C.st3); g.hline(13 - leg, 17 - leg, 29, C.st3);
  g.rect(8, 0, 4, 3, C.red1); g.rect(8, 3, 4, 4, C.gl1);
  g.poly([[8, 7], [12, 7], [16, 11], [4, 11]], C.chr1);
  g.rect(4, 11, 12, 14, C.chr1); g.rect(13, 11, 3, 14, C.chr2);
  g.rect(4, 15, 12, 7, C.wht); tridentInto(g, 10, 15, 7, C.red1, C.red1, C.red1);
  g.vline(5, 8, 23, 0xffffff);
  g.rect(5, 9, 10, 3, C.blk1);
  const ec = f === 'alert' ? C.red0 : f === 'hurt' ? C.st2 : C.lim0;
  g.rect(6, 10, 2, 1, ec); g.rect(12, 10, 2, 1, ec);
  g.outline(C.ink);
  return g;
}
export function foamMonster(f: 'small0' | 'small1' | 'big0' | 'big1' | 'hurt'): Px {
  const big = f.startsWith('big');
  const w = big ? 56 : 30, h = big ? 50 : 28;
  const g = new Px(w, h);
  const wob = f.endsWith('1') ? 1 : 0;
  const n = big ? 9 : 5;
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2;
    const r = (big ? 13 : 7) + ((i + wob) % 2) * 2;
    g.shadedEllipse(w / 2 + Math.cos(a) * (big ? 12 : 6), h / 2 + 3 + Math.sin(a) * (big ? 9 : 5), r, r * 0.85, [C.crm0, C.crm0, C.crm1, C.crm2]);
  }
  g.shadedEllipse(w / 2, h / 2 + 2, big ? 18 : 10, big ? 16 : 9, [C.crm0, C.crm0, C.crm1, C.crm2]);
  for (let i = 0; i < (big ? 8 : 4); i++) g.ring(6 + (i * 7) % (w - 10), 6 + (i * 5) % (h - 10), 1.3, C.crm2);
  const ey = h / 2 - (big ? 2 : 1);
  eyes(g, w / 2 - (big ? 6 : 3), ey, f === 'hurt' ? 'hurt' : big ? 'angry' : 'normal', big ? 10 : 5);
  if (big) { g.rect(w / 2 - 6, ey + 7, 12, 4, C.cola2); g.hline(w / 2 - 5, w / 2 + 5, ey + 7, C.wht); }
  else g.hline(w / 2 - 2, w / 2 + 2, ey + 4, C.crm3);
  g.outline(C.crm3);
  return g;
}
export function fruitFlyer(f: 'fly0' | 'fly1' | 'dive' | 'hurt'): Px {
  const g = new Px(24, 20);
  const up = f === 'fly0';
  // wings
  g.ellipse(6, up ? 5 : 10, 5, 2.5, C.wht, 210); g.ellipse(18, up ? 5 : 10, 5, 2.5, C.wht, 210);
  // strawberry body
  g.poly([[5, 8], [19, 8], [12, 19]], C.chr1); g.rect(7, 6, 10, 3, C.leaf1); g.set(12, 5, C.leaf2);
  g.poly([[14, 8], [19, 8], [12, 19]], C.chr2);
  for (const [x, y] of [[9, 12], [13, 11], [11, 15], [15, 13]]) g.set(x, y, C.gold0);
  eyes(g, 9, 10, f === 'hurt' ? 'hurt' : f === 'dive' ? 'angry' : 'normal', 5);
  g.outline(C.ink);
  return g;
}
export const ENEMY_FRAMES: Record<string, () => Px> = {
  fs_idle0: () => fizzSprite('idle0'), fs_idle1: () => fizzSprite('idle1'), fs_jump: () => fizzSprite('jump'), fs_hurt: () => fizzSprite('hurt'),
  sl_crawl0: () => syrupSlug('crawl0'), sl_crawl1: () => syrupSlug('crawl1'), sl_hurt: () => syrupSlug('hurt'),
  bb_walk0: () => bottleBot('walk0'), bb_walk1: () => bottleBot('walk1'), bb_alert: () => bottleBot('alert'), bb_hurt: () => bottleBot('hurt'),
  fm_small0: () => foamMonster('small0'), fm_small1: () => foamMonster('small1'), fm_big0: () => foamMonster('big0'), fm_big1: () => foamMonster('big1'), fm_hurt: () => foamMonster('hurt'),
  ff_fly0: () => fruitFlyer('fly0'), ff_fly1: () => fruitFlyer('fly1'), ff_dive: () => fruitFlyer('dive'), ff_hurt: () => fruitFlyer('hurt'),
};
