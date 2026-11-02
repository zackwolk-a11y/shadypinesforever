/** The Great Simps Stock-Up (warehouse) + owner set-piece props. */
import { C, R, type Ramp } from './palette';
import { Px, rng } from './px';
import { pxText, pxTextWidth } from './font';
import { tridentInto, leafInto } from './motifs';
import { bottleInto } from './fx';
import { bigTank } from './lab';

export const WH = { W: 1120, H: 360, FLOOR: 330 };
export const FL_COL: Record<string, Ramp> = { cola: R.cola, cream: R.cream, cherry: R.cherry };

export function warehouseWall(): Px {
  const W = 1200, H = 360, F = WH.FLOOR, g = new Px(W, H);
  g.rect(0, 0, W, H, 0x3a3e4c);
  for (let x = 0; x < W; x += 6) { g.vline(x, 0, F, 0x444858); g.vline(x + 3, 0, F, 0x30333f); }
  g.rect(0, 0, W, 26, C.blk2); for (let x = 0; x < W; x += 30) { g.line(x, 2, x + 15, 24, C.st4); g.line(x + 15, 24, x + 30, 2, C.st4); }
  // big back racks silhouettes full of cases
  const r = rng(5);
  for (let i = 0; i < 6; i++) {
    const x = 20 + i * 190, w = 150;
    for (const y of [70, 130, 190]) { g.rect(x, y, w, 4, C.gold2); for (let k = 0; k < 9; k++) { const col = [C.cb1, C.cb2, C.red2, C.cb1][Math.floor(r() * 4)]; g.rect(x + 4 + k * 16, y - 22, 14, 22, col); g.rect(x + 4 + k * 16, y - 22, 14, 2, C.cb0); } }
    g.rect(x, 40, 4, F - 40, C.blu3); g.rect(x + w - 4, 40, 4, F - 40, C.blu3);
  }
  g.rect(0, F - 10, W, 10, C.gold1); for (let x = 0; x < W; x += 12) g.poly([[x, F - 10], [x + 6, F - 10], [x, F], [x - 6, F]], C.blk1);
  const t = 'SIMPS WAREHOUSE - KELOWNA, B.C.'; g.rect(300, 34, pxTextWidth(t) + 30, 14, C.red1); pxText(g, 315, 38, t, C.wht); leafInto(g, 303, 36, C.wht, 9); tridentInto(g, 300 + pxTextWidth(t) + 22, 35, 11, C.wht, C.wht, C.wht);
  return g;
}
export function rack(w = 340): Px {
  const g = new Px(w, 150);
  for (const y of [0, 50, 100]) { g.rect(0, y, w, 6, C.gold1); g.hline(0, w - 1, y, C.gold0); g.hline(0, w - 1, y + 5, C.gold3); }
  for (const x of [0, w / 2 - 3, w - 6]) { g.rect(x, 0, 6, 150, C.blu2); g.vline(x + 1, 0, 149, C.blu1); for (let y = 8; y < 150; y += 10) g.set(x + 3, y, C.blu3); }
  // trident cross-bracing
  for (const x of [w / 4, (3 * w) / 4]) tridentInto(g, Math.round(x), 112, 30, C.red1, C.red2, C.red0);
  g.outline(C.ink);
  return g;
}
export function flavorBox(kind: string, big = false): Px {
  const w = big ? 30 : 18, h = big ? 26 : 16, g = new Px(w, h);
  const rp = FL_COL[kind] ?? R.card;
  g.rect(0, 0, w, h, C.cb1); g.rect(0, 0, w, 2, C.cb0); g.rect(w - 3, 0, 3, h, C.cb2); g.rect(w / 2 - 2, 0, 4, h / 2, C.cb0);
  g.rect(2, h / 2 - 2, w - 6, h / 2, rp[1]); g.rect(2, h / 2 - 2, w - 6, 1, rp[0]);
  bottleInto(g, w / 2 - 3, h / 2 - 3, rp, 4, h / 2 + 1, { label: false });
  if (big) { leafInto(g, 3, 3, C.red2, 9); }
  g.outline(C.ink);
  return g;
}
export function slotTag(kind: string): Px { const g = new Px(20, 8); const rp = FL_COL[kind]; g.rect(0, 0, 20, 8, C.wht); g.rect(1, 1, 6, 6, rp[1]); pxText(g, 8, 0, '', C.ink); g.hline(9, 18, 3, C.st2); g.hline(9, 15, 5, C.st2); g.outline(C.ink); return g; }
export function pallet(): Px { const g = new Px(44, 10); g.rect(0, 0, 44, 3, C.wd1); g.rect(0, 7, 44, 3, C.wd2); for (const x of [2, 20, 38]) g.rect(x, 3, 5, 4, C.wd3); g.outline(C.ink); return g; }
export function heavyCrate(): Px { const g = new Px(34, 30); g.rect(0, 0, 34, 30, C.wd2); for (let y = 2; y < 30; y += 7) { g.rect(1, y, 32, 5, C.wd1); g.hline(1, 32, y, C.wd0); } g.line(1, 1, 33, 29, C.wd3); g.line(33, 1, 1, 29, C.wd3); g.rect(10, 10, 14, 10, C.blk1); pxText(g, 11, 12, 'HVY', C.gold1); g.outline(C.ink); return g; }
export function truck(): Px {
  const w = 230, h = 120, g = new Px(w, h);
  // trailer box (rear faces the bay, doors open)
  g.rect(0, 6, 170, 92, C.wht); g.rect(0, 6, 170, 4, C.wl1); g.rect(0, 88, 170, 10, C.red1);
  g.rect(2, 12, 40, 80, C.blk2); // open rear doorway
  for (let x = 4; x < 40; x += 6) g.vline(x, 14, 88, C.blk1);
  pxText(g, 60, 26, 'SIMPS', C.red1, 3); pxText(g, 62, 50, 'MODERN BEVERAGE', C.blk1);
  tridentInto(g, 158, 18, 30, C.red1, C.red2, C.red0);
  leafInto(g, 60, 62, C.red1, 15, 2);
  pxText(g, 96, 70, 'PROUDLY', C.red2); pxText(g, 96, 79, 'CANADIAN', C.red2);
  // cab
  g.rect(172, 30, 54, 68, C.red1); g.rect(172, 30, 54, 3, C.red0); g.rect(186, 36, 34, 22, C.gl1); g.line(188, 38, 200, 56, 0xffffff);
  g.rect(222, 70, 6, 12, C.gold1); g.rect(172, 88, 56, 10, C.blk1);
  // wheels
  for (const x of [26, 120, 196]) { g.circle(x, 102, 13, C.ink); g.circle(x, 102, 7, C.st2); g.circle(x, 102, 3, C.st0); }
  g.outline(C.ink);
  return g;
}
export function forklift(): Px {
  const g = new Px(60, 56);
  g.rect(14, 22, 36, 24, C.gold1); g.rect(14, 22, 36, 3, C.gold0); g.rect(18, 4, 3, 22, C.blk1); g.rect(44, 4, 3, 22, C.blk1); g.rect(18, 2, 29, 3, C.blk1);
  g.rect(4, 0, 4, 50, C.st3); g.rect(0, 44, 16, 3, C.st2);
  tridentInto(g, 32, 26, 14, C.red1, C.red2, C.red0);
  for (const x of [20, 44]) { g.circle(x, 48, 7, C.ink); g.circle(x, 48, 3, C.st2); }
  g.outline(C.ink);
  return g;
}
export function bayDoor(): Px { const g = new Px(120, 140); for (let y = 0; y < 140; y += 6) { g.rect(0, y, 120, 5, C.st2); g.hline(0, 119, y, C.st1); } g.rect(50, 120, 20, 6, C.blk1); pxText(g, 30, 60, 'LOADING', C.blk1); pxText(g, 42, 70, 'BAY', C.blk1); g.outline(C.ink); return g; }
export function giftBox(open = false): Px {
  const g = new Px(30, 30);
  g.rect(2, 12, 26, 18, C.red1); g.rect(13, 12, 4, 18, C.gold1);
  if (!open) { g.rect(0, 6, 30, 7, C.red2); g.rect(13, 6, 4, 7, C.gold1); g.ellipse(10, 4, 5, 3, C.gold1); g.ellipse(20, 4, 5, 3, C.gold1); }
  leafInto(g, 4, 16, C.wht, 9); tridentInto(g, 23, 15, 11, C.wht, C.wht, C.wht);
  g.outline(C.ink);
  return g;
}
export function medallion(): Px { const g = new Px(22, 22); g.circle(11, 11, 10.5, C.gold3); g.circle(10.6, 10.6, 9.6, C.gold1); leafInto(g, 4, 3, C.gold0, 15); tridentInto(g, 11, 6, 10, C.red1, C.red1, C.red0); g.outline(C.ink); return g; }
export function ropeBarrier(): Px { const g = new Px(40, 34); for (const x of [3, 35]) { g.rect(x, 4, 3, 30, C.gold2); g.circle(x + 1.5, 4, 3, C.gold1); g.rect(x - 3, 31, 9, 3, C.gold3); } for (let x = 6; x < 35; x++) g.set(x, 8 + Math.sin((x - 6) / 29 * Math.PI) * 5, C.red1); g.outline(C.ink); return g; }
export function stockDoor(): Px { const g = new Px(48, 84); g.rect(0, 0, 48, 84, C.st3); g.rect(4, 4, 40, 80, C.st2); g.rect(8, 8, 32, 22, C.blk2); for (let x = 9; x < 40; x += 3) g.vline(x, 9, 29, C.st4); g.rect(6, 36, 36, 10, C.gold1); pxText(g, 7, 38, 'STOCK', C.blk1); g.rect(36, 52, 4, 8, C.st0); tridentInto(g, 24, 64, 14, C.red1); g.outline(C.ink); return g; }
export function gerryMachine(): Px {
  const w = 120, h = 104, g = new Px(w, h);
  g.rect(4, 10, w - 8, h - 10, C.st2); g.rect(4, 10, 6, h - 10, C.st1); g.rect(w - 10, 10, 6, h - 10, C.st3);
  const tanks: [number, Ramp][] = [[14, R.lime], [48, R.blue], [82, R.mango]];
  for (const [x, rp] of tanks) bigTank(g, x, 24, 24, 52, rp, 0.15);
  for (const x of [26, 60, 94]) { g.circle(x, 86, 6, C.wht); g.ring(x, 86, 6, C.st3); g.line(x, 86, x + 3, 82, C.red1); }
  for (const x of [8, w - 9]) tridentInto(g, x, 0, 16, C.red1, C.red2, C.red0);
  g.rect(30, 0, 60, 10, C.blk1); pxText(g, 33, 2, "GERRY'S LAB", C.red0);
  g.outline(C.ink);
  return g;
}
export function vial(rp: Ramp): Px { const g = new Px(10, 16); g.rect(3, 0, 4, 3, C.red1); g.rect(2, 3, 6, 12, C.gl1, 200); g.rect(2, 7, 6, 8, rp[1]); g.rect(2, 7, 6, 1, rp[0]); g.vline(3, 4, 13, 0xffffff); g.outline(C.ink); return g; }
export function sodaCup(): Px {
  const g = new Px(40, 56);
  g.poly([[2, 12], [38, 12], [33, 56], [7, 56]], C.wht); g.rect(2, 10, 36, 4, C.red1);
  g.rect(8, 22, 24, 22, C.red1); tridentInto(g, 20, 24, 18, C.wht, C.wht, C.wht);
  g.rect(24, 0, 3, 14, C.red0); g.rect(24, 0, 10, 3, C.red0);
  for (let i = 0; i < 4; i++) leafInto(g, 4 + i * 9, 47, C.red1, 9);
  g.outline(C.ink);
  return g;
}
export function rainbowGlass(): Px { const g = new Px(14, 22); const cols = [C.red1, C.mng1, C.gold1, C.lim1, C.blu1, C.pur1]; cols.forEach((c, i) => g.rect(2, 4 + i * 3, 10, 3, c)); g.rect(1, 2, 12, 2, C.wht); g.vline(3, 4, 20, 0xffffff); g.rect(4, 20, 6, 2, C.gl1); g.outline(C.ink); return g; }
export function cart(): Px { const g = new Px(40, 34); g.rect(2, 2, 36, 22, C.st3); g.rect(4, 4, 32, 18, C.st2); for (let i = 0; i < 3; i++) { g.rect(6 + i * 11, 6, 9, 14, [C.red1, C.cb1, C.red2][i]); g.rect(6 + i * 11, 6, 9, 2, C.cb0); } g.rect(0, 24, 40, 3, C.st4); for (const x of [8, 32]) { g.circle(x, 30, 3.5, C.ink); g.set(x, 30, C.st1); } g.rect(36, 0, 3, 10, C.red1); g.outline(C.ink); return g; }
export function crackedWall(): Px { const g = new Px(36, 36); g.rect(0, 0, 36, 36, 0x4a4e5e); for (let y = 0; y < 36; y += 9) for (let x = (y / 9) % 2 ? 0 : 6; x < 36; x += 12) { g.rect(x, y, 11, 8, 0x555a6a); g.hline(x, x + 10, y, 0x666b7b); } g.line(6, 4, 16, 18, C.ink); g.line(16, 18, 12, 30, C.ink); g.line(16, 18, 28, 22, C.ink); g.line(28, 22, 32, 10, C.ink); g.outline(C.ink); return g; }
export function wSwitch(on = false): Px { const g = new Px(16, 22); g.rect(0, 0, 16, 22, C.st3); g.rect(2, 2, 12, 18, on ? C.lim1 : C.red2); g.rect(6, on ? 4 : 12, 4, 6, C.wht); g.outline(C.ink); return g; }
export function gauge(label = 'JAM!'): Px { const g = new Px(40, 28); g.rect(0, 0, 40, 28, C.blk1); g.rect(2, 2, 36, 24, C.wht); g.rect(4, 18, 32, 5, C.red1); g.rect(16, 18, 8, 5, C.lim1); pxText(g, 4, 4, label, C.red1); g.outline(C.ink); return g; }
