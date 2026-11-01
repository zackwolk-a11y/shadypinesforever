/** Carbonation Catastrophe — giant malfunctioning carbonation machine + attack sprites. */
import { C, R } from './palette';
import { Px } from './px';
import { pxText, pxTextWidth } from './font';
import { leafInto } from './motifs';
import { bigTank } from './lab';

export function carbBody(): Px {
  const w = 220, h = 196, g = new Px(w, h);
  // body
  g.shadedEllipse(110, 40, 96, 34, R.steel);
  g.rect(14, 40, w - 28, h - 40, C.st2); g.rect(14, 40, 10, h - 40, C.st1); g.rect(w - 24, 40, 10, h - 40, C.st3);
  for (let y = 48; y < h; y += 24) g.hline(14, w - 15, y, C.st3);
  for (let x = 20; x < w - 16; x += 14) for (let y = 52; y < h; y += 24) g.set(x, y, C.st0);
  // three flavour tanks
  [R.cola, R.cream, R.cherry].forEach((rp, i) => bigTank(g, 34 + i * 56, 104, 40, 68, rp, 0.75));
  // face screen
  g.rect(60, 50, 100, 44, C.blk2); g.rect(62, 52, 96, 40, 0x10301c);
  // gauge housings (needles are separate sprites)
  for (const x of [34, 186]) { g.circle(x, 70, 14, C.st3); g.circle(x, 70, 12, C.wht); }
  // base + name plate
  g.rect(0, h - 18, w, 18, C.blk1); g.rect(0, h - 12, w, 3, C.red1);
  const t = 'CARBONATOR 3000'; g.rect(w / 2 - pxTextWidth(t) / 2 - 4, h - 20, pxTextWidth(t) + 8, 10, C.blk2); pxText(g, w / 2 - pxTextWidth(t) / 2, h - 19, t, C.red0);
  leafInto(g, 8, h - 15, C.wht, 9); leafInto(g, w - 17, h - 15, C.wht, 9);
  g.outline(C.ink);
  return g;
}
export function bossEyes(mood: 'normal' | 'angry' | 'hurt' | 'panic' | 'dizzy'): Px {
  const g = new Px(92, 36);
  const col = mood === 'hurt' ? C.red0 : mood === 'panic' ? C.gold1 : C.lim0;
  for (const cx of [24, 68]) {
    if (mood === 'hurt') { for (let k = -8; k <= 8; k++) { g.rect(cx + k, 14 + k * 0.8, 2, 2, col); g.rect(cx + k, 14 - k * 0.8, 2, 2, col); } continue; }
    if (mood === 'dizzy') { g.ring(cx, 14, 9, col, 2); g.ring(cx, 14, 4, col, 2); continue; }
    const r = mood === 'panic' ? 11 : 9;
    g.ring(cx, 14, r, col, 2); g.circle(cx + (mood === 'panic' ? 0 : 2), 15, mood === 'panic' ? 3 : 5, col);
    if (mood === 'angry') { g.line(cx - 12, cx < 40 ? 2 : 8, cx + 10, cx < 40 ? 8 : 2, col); g.line(cx - 12, cx < 40 ? 3 : 9, cx + 10, cx < 40 ? 9 : 3, col); }
  }
  // mouth
  if (mood === 'panic') { g.ring(46, 30, 4, col, 2); }
  else if (mood === 'angry') { for (let x = 30; x < 62; x += 4) g.rect(x, 28 + ((x / 4) % 2) * 2, 3, 2, col); }
  else g.hline(36, 56, 30, col);
  return g;
}
export function flavorTap(color: number, lit: boolean): Px {
  const g = new Px(26, 40);
  g.rect(8, 8, 10, 28, C.st2); g.vline(9, 8, 35, C.st0);
  g.circle(13, 8, 9, lit ? color : C.st3); g.circle(13, 8, 6, lit ? 0xffffff : C.st2); g.circle(13, 8, 4, color);
  g.rect(16, 18, 9, 4, C.st1); g.rect(22, 22, 3, 4, C.st3);
  g.rect(2, 34, 22, 6, C.blk1);
  g.outline(lit ? 0xffffff : C.ink);
  return g;
}
export function fizzWave(): Px { const g = new Px(26, 16); for (let i = 0; i < 4; i++) g.shadedEllipse(4 + i * 6, 12 - (i % 2) * 3, 4, 4 + (i % 2) * 2, [C.wht, C.cola0, C.cola1, C.cola2]); g.outline(C.ink); return g; }
export function foamBlob(): Px { const g = new Px(18, 16); g.shadedEllipse(9, 9, 8, 6, [C.crm0, C.crm0, C.crm1, C.crm2]); g.shadedEllipse(6, 6, 4, 3, [C.crm0, C.crm0, C.crm1, C.crm2]); g.outline(C.crm3); return g; }
export function foamFlood(): Px { const g = new Px(32, 24); g.rect(0, 4, 32, 20, C.crm1); for (let x = 0; x < 32; x += 8) { g.circle(x + 4, 5, 5, C.crm0); g.ring(x + 2, 12, 1.5, C.crm2); } g.rect(0, 16, 32, 8, C.crm2); return g; }
