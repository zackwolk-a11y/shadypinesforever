/** LEVEL 3a art — a cozy independent Kelowna café. Warm wood, sunlight, Simps café syrups. */
import { C, R, type Ramp } from './palette';
import { Px, rng } from './px';
import { pxText, pxTextWidth } from './font';
import { tridentInto, leafInto } from './motifs';
import { bottleInto } from './fx';

export const CAFE = { W: 960, H: 270, FLOOR: 240 };
export const CAFE_SYRUP_RAMPS: Record<string, Ramp> = {
  vanilla: [C.wht, C.crm0, C.crm1, C.crm2], saltedcaramel: [C.gold0, C.gold1, C.gold2, C.gold3], hazelnut: [C.wd0, C.cola0, C.cola1, C.cola2],
  peppermint: [0xe8fff4, C.lim0, C.lim1, C.lim2], lavender: [C.pur0, C.pur1, C.pur2, C.ink2], marshmallow: [C.wht, C.crm0, C.wd0, C.wd1],
};
export function cafeWall(): Px {
  const W = 1100, H = 270, F = CAFE.FLOOR, g = new Px(W, H);
  // upper wall: warm plaster; lower: wood wainscot
  g.vgrad(0, 0, W, F - 70, [0xf4dcb4, 0xe9c99a]);
  g.rect(0, F - 70, W, 70, C.wd2);
  for (let x = 0; x < W; x += 10) { g.vline(x, F - 70, F - 1, C.wd3); g.vline(x + 1, F - 70, F - 1, C.wd1); }
  g.rect(0, F - 74, W, 5, C.wd1); g.hline(0, W - 1, F - 74, C.wd0);
  // windows with the lake view + sunlight
  for (const wx of [40, 380, 760]) {
    g.rect(wx, 30, 120, 110, C.wd3);
    g.vgrad(wx + 5, 35, 110, 100, [C.sky3, C.sky2, C.sky0]);
    for (let x = wx + 5; x < wx + 115; x++) { const t = 95 + Math.sin(x / 13) * 8; g.vline(x, t, 115, C.mt1); }
    g.rect(wx + 5, 112, 110, 23, C.blu1); for (let x = wx + 8; x < wx + 112; x += 9) g.hline(x, x + 4, 118 + (x % 3) * 4, C.blu0);
    g.rect(wx + 58, 35, 4, 100, C.wd3); g.rect(wx + 5, 82, 110, 4, C.wd3);
    g.rect(wx - 4, 136, 128, 6, C.wd1);
    for (let k = 0; k < 3; k++) g.line(wx + 10 + k * 30, 38, wx + 30 + k * 30, 130, 0xffffff, 80);
  }
  // chalk menu board (real Simps café syrup names)
  const mx = 200; g.rect(mx, 26, 160, 100, C.wd3); g.rect(mx + 4, 30, 152, 92, C.blk1);
  pxText(g, mx + 80 - pxTextWidth('SIMPS CAFE SYRUPS') / 2, 34, 'SIMPS CAFE SYRUPS', C.gold0);
  ['VANILLA', 'SALTED CARAMEL', 'HAZELNUT', 'PEPPERMINT', 'LAVENDER', 'TOASTED MARSHMALLOW'].forEach((t, i) => { leafInto(g, mx + 8, 46 + i * 12, C.red0, 9); pxText(g, mx + 20, 47 + i * 12, t, C.wht); });
  // shelf of Simps café syrups
  const sx = 540; g.rect(sx, 80, 190, 5, C.wd1); g.rect(sx, 120, 190, 5, C.wd1);
  const ramps = Object.values(CAFE_SYRUP_RAMPS);
  for (let i = 0; i < 16; i++) { const b = new Px(12, 26); bottleInto(b, 1, 1, ramps[i % 6], 9, 24); b.outline(C.ink2); g.blit(b, sx + 4 + i * 11.5, i < 16 ? (i % 2 ? 55 : 95) : 0); }
  g.rect(sx + 50, 14, 90, 22, C.red1); tridentInto(g, sx + 60, 16, 17, C.wht, C.wht, C.wht); pxText(g, sx + 70, 21, 'CAFE SERIES', C.wht);
  // plants + hanging pendant flag
  for (const px of [180, 520, 900]) { g.rect(px, 150, 18, 14, C.wl1); const r = rng(px); for (let k = 0; k < 6; k++) g.shadedEllipse(px + 9 + (r() - 0.5) * 22, 142 - r() * 18, 6, 4, R.leaf, r() * 2); }
  g.rect(0, F, W, 2, C.wd3);
  return g;
}
export function cafeFloor(): Px { const g = new Px(48, 30); g.rect(0, 0, 48, 30, C.wd1); for (let y = 0; y < 30; y += 10) { g.hline(0, 47, y, C.wd3); g.vline((y * 3) % 48, y, y + 9, C.wd3); } g.rect(0, 0, 48, 2, C.wd0); return g; }
export function cafeCounter(w = 300): Px {
  const h = 52, g = new Px(w, h);
  g.rect(0, 0, w, 7, C.wht); g.rect(0, 6, w, 2, C.st2);
  g.rect(2, 8, w - 4, h - 8, C.wd2); for (let x = 6; x < w - 4; x += 8) { g.vline(x, 10, h - 4, C.wd3); g.vline(x + 1, 10, h - 4, C.wd1); }
  g.rect(w / 2 - 50, 20, 100, 14, C.blk1); pxText(g, w / 2 - pxTextWidth('KELOWNA COFFEE CO.') / 2, 24, 'KELOWNA COFFEE CO.', C.crm0);
  leafInto(g, w / 2 - 66, 22, C.red1, 9); tridentInto(g, w / 2 + 60, 20, 13, C.red1);
  g.outline(C.ink);
  return g;
}
export function espressoMachine(): Px {
  const g = new Px(64, 50);
  g.rect(2, 4, 60, 40, C.st1); g.rect(2, 4, 60, 4, C.st0); g.rect(56, 4, 6, 40, C.st3);
  g.rect(8, 0, 48, 5, C.red1); tridentInto(g, 32, 10, 12, C.red1, C.red2, C.red0);
  for (const x of [14, 42]) { g.rect(x, 26, 10, 6, C.blk1); g.rect(x + 3, 32, 4, 4, C.st3); }
  g.circle(32, 32, 5, C.wht); g.circle(32, 32, 4, C.st0); g.set(33, 30, C.red1);
  g.rect(0, 44, 64, 6, C.st3); for (let x = 2; x < 62; x += 3) g.vline(x, 45, 48, C.st4);
  g.outline(C.ink);
  return g;
}
export function pastryCase(): Px {
  const g = new Px(70, 40);
  g.rect(0, 0, 70, 40, C.wd2); g.rect(3, 3, 64, 30, C.gl1, 170);
  for (let i = 0; i < 6; i++) { const x = 8 + (i % 3) * 20, y = 12 + Math.floor(i / 3) * 12; g.shadedEllipse(x + 4, y + 3, 6, 3.5, i % 2 ? R.cream : R.wood); if (i % 2) leafInto(g, x, y - 1, C.red1, 9); }
  g.line(6, 4, 20, 30, 0xffffff, 120);
  g.outline(C.ink);
  return g;
}
export function stool(): Px { const g = new Px(20, 30); g.ellipse(10, 4, 9, 4, C.red1); g.ellipse(10, 3, 8, 2.5, C.red0); g.rect(9, 7, 3, 20, C.st2); g.rect(4, 26, 13, 3, C.st3); g.hline(5, 15, 18, C.st2); g.outline(C.ink); return g; }
export function cafeTable(): Px { const g = new Px(44, 34); g.rect(0, 0, 44, 5, C.wd1); g.hline(0, 43, 0, C.wd0); g.rect(20, 5, 4, 26, C.wd3); g.rect(12, 30, 20, 4, C.wd3); g.rect(6, -0, 8, 0, C.wht); g.outline(C.ink); return g; }
export function mug(col: number): Px { const g = new Px(12, 12); g.rect(1, 2, 8, 9, C.wht); g.rect(9, 4, 2, 4, C.wht); g.rect(2, 2, 6, 2, col); g.rect(1, 6, 8, 2, C.red1); g.outline(C.ink); return g; }
export function cafeDoor(): Px {
  const g = new Px(46, 84);
  g.rect(0, 0, 46, 84, C.wd3); g.rect(4, 4, 38, 80, C.wd1); g.rect(9, 9, 28, 40, C.sky2); g.rect(9, 38, 28, 11, C.blu1);
  g.rect(34, 50, 4, 8, C.gold1); g.rect(10, 56, 26, 10, C.red1); pxText(g, 12, 58, 'LAKE', C.wht);
  leafInto(g, 18, 70, C.red1, 9);
  g.outline(C.ink);
  return g;
}
