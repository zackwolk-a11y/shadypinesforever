/** Collectibles, checkpoints and power icons added for the full game. */
import { C, R } from './palette';
import { Px } from './px';
import { pxText } from './font';
import { tridentInto, leafInto } from './motifs';
import { bubble, bottleInto } from './fx';

export function recipeCard(): Px {
  const g = new Px(16, 20);
  g.rect(1, 1, 14, 18, C.wht); g.rect(1, 1, 14, 5, C.red1); tridentInto(g, 8, 1, 5, C.wht, C.wht, C.wht);
  for (let y = 8; y < 17; y += 2) g.hline(3, y % 4 ? 12 : 10, y, C.st2);
  g.rect(10, 13, 4, 4, C.chr0); g.set(11, 14, C.wht);
  g.outline(C.ink);
  return g;
}
export function bubbleStar(): Px {
  const g = bubble(18, { tint: C.blu0 });
  const s = new Px(18, 18);
  s.poly([[9, 3], [11, 7.5], [15.5, 8], [12, 11], [13, 15.5], [9, 13], [5, 15.5], [6, 11], [2.5, 8], [7, 7.5]], C.gold1);
  s.set(8, 7, C.gold0); s.set(9, 8, C.gold0);
  g.blit(s, 0, 0);
  return g;
}
export function coffeeBean(): Px {
  const g = new Px(10, 12);
  g.shadedEllipse(5, 6, 3.8, 5, [C.cola0, C.cola1, C.cola2, C.cola3], 0.3);
  g.line(4, 2, 6, 10, C.cola3); g.set(3, 3, C.wd0);
  g.outline(C.ink);
  return g;
}
export function goldenGoose(): Px {
  const g = new Px(22, 22);
  g.circle(11, 11, 10.5, C.gold3); g.circle(10.6, 10.6, 9.6, C.gold1); g.ring(11, 11, 8, C.gold2);
  // goose head silhouette
  g.circle(10, 8, 3, C.wht); g.rect(8, 9, 3, 7, C.wht); g.poly([[12, 7], [16, 8], [12, 9]], C.go1); g.set(10, 7, C.ink);
  g.set(6, 5, C.gold0); g.set(5, 6, C.gold0);
  g.outline(C.ink);
  return g;
}
export function electricShot(): Px {
  const g = bubble(16, { tint: C.blu0 });
  g.line(9, 3, 6, 8, C.gold0); g.line(6, 8, 10, 8, C.gold0); g.line(10, 8, 7, 13, C.gold0);
  return g;
}
export function foamCloudW(w: number): Px {
  const h = Math.round(w * 0.42);
  const g = new Px(w + 4, h + 2);
  const n = Math.round(w / 8);
  for (let i = 0; i < n; i++) {
    const x = 6 + (i / (n - 1)) * (w - 10), y = h * 0.55 + Math.sin(i * 1.7) * h * 0.15, r = h * (0.32 + (i % 3) * 0.07);
    g.shadedEllipse(x, y, r, r * 0.8, [C.crm0, C.crm0, C.crm1, C.crm2]);
  }
  for (let i = 0; i < n; i++) g.ring(8 + i * (w - 12) / n, h * 0.45 + (i % 2) * 3, 1.3, C.crm2);
  g.outline(C.crm3);
  return g;
}
/** Trident checkpoint post. state 0 = idle (flag down), 1/2 = raised & waving */
export function checkpoint(state: number): Px {
  const g = new Px(26, 46);
  g.rect(4, 6, 2, 40, C.st2); g.vline(4, 6, 45, C.st0); g.rect(1, 42, 8, 4, C.blk1);
  tridentInto(g, 5, 0, 9, C.red1, C.red2, C.red0);
  if (state === 0) { g.rect(6, 30, 10, 8, C.st2); g.rect(6, 30, 10, 2, C.st1); }
  else {
    const wv = state === 2 ? 1 : 0;
    for (let x = 0; x < 18; x++) { const off = Math.round(Math.sin(x / 4 + wv * 2) * 1.2); g.vline(6 + x, 10 + off, 21 + off, x < 4 || x > 13 ? C.red1 : C.wht); }
    leafInto(g, 11, 12 + wv, C.red1, 9);
  }
  g.outline(C.ink);
  return g;
}
export function powerIcon(kind: string): Px {
  const g = new Px(16, 16);
  switch (kind) {
    case 'rocket': g.circle(6, 10, 3.5, C.chr1); g.circle(10, 9, 3.5, C.chr1); g.set(5, 9, C.chr0); g.poly([[1, 12], [4, 9], [4, 15]], C.gold1); g.line(9, 6, 12, 1, C.leaf2); break;
    case 'cloud9': for (const [x, y, r] of [[5, 10, 4], [10, 8, 5], [12, 11, 3]]) g.shadedEllipse(x, y, r, r * 0.85, [C.crm0, C.crm0, C.crm1, C.crm2]); pxText(g, 7, 6, '9', C.red1); break;
    case 'tropical': g.shadedEllipse(8, 10, 5, 4.5, R.mango, -0.4); g.poly([[8, 0], [12, 5], [4, 5]], C.lim1); g.rect(7, 4, 2, 3, C.lim1); break;
    case 'shield': g.circle(8, 8, 7, C.chr2); g.circle(8, 8, 5.5, C.chr3); g.ring(8, 8, 7, C.chr0); tridentInto(g, 8, 3, 9, C.wht, C.wht, C.wht); break;
    case 'electric': g.circle(8, 8, 7, C.blu2); g.line(9, 2, 5, 8, C.gold0); g.line(5, 8, 10, 8, C.gold0); g.line(10, 8, 6, 14, C.gold0); break;
    case 'float': g.rect(3, 5, 9, 10, C.rbr1); g.rect(3, 3, 9, 3, C.crm0); g.ellipse(6, 3, 3, 2, C.crm0); g.rect(12, 7, 2, 5, C.wl2); break;
    case 'pinkfizz': g.circle(4, 10, 3, C.chr0); g.circle(8, 6, 3, C.pink); g.circle(12, 10, 3, C.chr0); break;
    case 'burp': g.rect(3, 6, 9, 9, C.wht); g.rect(3, 9, 9, 2, C.red1); g.rect(12, 8, 2, 4, C.wht); g.ring(9, 3, 2.5, C.bub2); break;
  }
  g.outline(C.ink);
  return g;
}
export function syrupBottleBig(ramp: typeof R.cola): Px { const g = new Px(14, 30); bottleInto(g, 2, 1, ramp, 10, 27); g.outline(C.ink); return g; }
