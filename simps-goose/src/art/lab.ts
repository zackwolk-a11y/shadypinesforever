/** LEVEL 2 art — The Honkin' Soda Lab. Industrial teal/steel + Simps red, colourful syrups. */
import { C, R, type Ramp } from './palette';
import { Px, rng } from './px';
import { pxText, pxTextWidth } from './font';
import { tridentInto, leafInto } from './motifs';
import { bottleInto } from './fx';

export const LAB = { W: 2800, H: 420, FLOOR: 390, PAR: 0.85 };
export const labBgX = (wx: number) => Math.round(240 + (wx - 240) * LAB.PAR);
export const LAB_BG_W = labBgX(LAB.W) + 248;
const TEAL: Ramp = [0x6fb3b0, 0x3f7f86, 0x2c5a63, 0x1d3c46];
const SYRUPS: Ramp[] = [R.cola, R.cream, R.cherry, R.blue, R.lime, R.mango, R.purple];

function panelWall(g: Px, x0: number, y0: number, w: number, h: number) {
  g.rect(x0, y0, w, h, TEAL[2]);
  for (let y = y0; y < y0 + h; y += 32) { g.hline(x0, x0 + w - 1, y, TEAL[3]); g.hline(x0, x0 + w - 1, y + 1, TEAL[1]); }
  for (let x = x0; x < x0 + w; x += 48) { g.vline(x, y0, y0 + h - 1, TEAL[3]); for (let y = y0 + 6; y < y0 + h; y += 32) { g.set(x + 4, y, TEAL[0]); g.set(x + 43, y, TEAL[0]); } }
  for (let i = 0; i < w * h / 900; i++) { const r = rng(i + x0)(); const yy = y0 + ((i * 37) % h); g.set(x0 + r * w, yy, TEAL[1]); }
}
export function bigTank(g: Px, x: number, y: number, w: number, h: number, ramp: Ramp, fill = 0.7) {
  g.rect(x - 3, y - 6, w + 6, 6, C.st3); g.rect(x - 3, y + h, w + 6, 8, C.st3);
  g.hline(x - 3, x + w + 2, y - 6, C.st1); g.hline(x - 3, x + w + 2, y + h, C.st1);
  g.rect(x, y, w, h, C.gl2, 150);
  const ly = y + Math.round(h * (1 - fill));
  g.rect(x, ly, w, y + h - ly, ramp[1]); g.rect(x + w - Math.max(3, w / 5), ly, Math.max(3, w / 5), y + h - ly, ramp[2]);
  g.hline(x, x + w - 1, ly, ramp[0]); g.hline(x, x + w - 1, ly + 1, ramp[0]);
  const r = rng(x + y);
  for (let k = 0; k < w * h / 120; k++) g.ring(x + 3 + r() * (w - 6), ly + 4 + r() * (y + h - ly - 6), 0.8 + r() * 1.5, ramp[0]);
  g.rect(x + 2, y + 2, 2, h - 4, 0xffffff, 150); g.rect(x + 6, y + 2, 1, h - 4, 0xffffff, 70);
  for (const bx of [x - 3, x + w]) for (let yy = y; yy < y + h; yy += 12) g.rect(bx, yy, 3, 2, C.st2);
}
export function labBackWall(): Px {
  const W = LAB_BG_W, H = LAB.H, F = LAB.FLOOR;
  const g = new Px(W, H);
  panelWall(g, 0, 0, W, H);
  // ceiling girders
  g.rect(0, 0, W, 22, C.blk2);
  for (let x = 0; x < W; x += 24) { g.line(x, 2, x + 12, 20, C.st4); g.line(x + 12, 20, x + 24, 2, C.st4); }
  g.hline(0, W - 1, 21, C.st3);
  // hazard stripe baseboard
  for (let x = 0; x < W; x += 8) g.poly([[x, F - 12], [x + 4, F - 12], [x, F - 4], [x - 4, F - 4]], C.gold1);
  g.rect(0, F - 12, W, 2, C.blk1); g.rect(0, F - 4, W, 4, C.blk1);
  // big background syrup tanks
  const r = rng(91);
  for (let i = 0; i < 16; i++) {
    const x = 60 + i * 160 + r() * 40, w = 34 + r() * 26, h = 120 + r() * 90, y = F - 20 - h;
    bigTank(g, x, y, w, h, SYRUPS[i % SYRUPS.length], 0.45 + r() * 0.45);
    // pipe from tank top into ceiling
    g.rect(x + w / 2 - 3, 22, 6, y - 28, C.st3); g.vline(x + w / 2 - 2, 22, y - 7, C.st1);
    if (i % 3 === 0) leafInto(g, x + w / 2 - 4, y + 20, C.red1, 9);
  }
  // transparent horizontal syrup pipes
  for (const [py, ramp] of [[60, R.cherry], [86, R.blue], [112, R.mango]] as [number, Ramp][]) {
    g.rect(0, py, W, 8, C.gl2, 120); g.rect(0, py + 2, W, 4, ramp[1], 220);
    for (let x = 0; x < W; x += 22) g.rect(x, py + 3, 6, 2, ramp[0]);
    for (let x = 40; x < W; x += 150) { g.rect(x, py - 2, 6, 12, C.st2); g.vline(x + 1, py - 2, py + 9, C.st0); }
  }
  // giant trident gear emblems + signage
  for (const [wx, s] of [[400, 120], [1500, 140], [2500, 150]]) {
    const x = labBgX(wx);
    g.ring(x, 190, s / 2, C.st3, 6); for (let a = 0; a < Math.PI * 2; a += Math.PI / 8) g.rect(x + Math.cos(a) * (s / 2 + 3) - 3, 190 + Math.sin(a) * (s / 2 + 3) - 3, 6, 6, C.st3);
    g.circle(x, 190, s / 2 - 8, TEAL[3]);
    tridentInto(g, x, 190 - s * 0.36, Math.round(s * 0.72), C.red1, C.red2, C.red0);
  }
  const sign = (wx: number, y: number, t: string, col: number) => { const x = labBgX(wx), w = pxTextWidth(t) + 14; g.rect(x - w / 2, y, w, 15, C.blk1); g.rect(x - w / 2 + 1, y + 1, w - 2, 13, C.blk2); pxText(g, x - w / 2 + 7, y + 4, t, col); };
  sign(220, 140, 'SIMPS R&D - AUTHORIZED GEESE ONLY', C.gold1);
  sign(1000, 132, 'PROUDLY CANADIAN FIZZ SCIENCE', C.wht);
  sign(1900, 128, 'CARBONATION: HANDLE WITH HONK', C.red0);
  sign(2600, 120, 'SUPER SODA - DO NOT DRINK', C.lim0);
  return g;
}
export function labFloor(): Px {
  const g = new Px(64, 30);
  g.rect(0, 0, 64, 30, C.st3); g.rect(0, 0, 64, 2, C.st1); g.hline(0, 63, 2, C.st4);
  for (let y = 5; y < 30; y += 6) for (let x = (y / 6) % 2 ? 0 : 4; x < 64; x += 8) { g.line(x, y, x + 3, y + 2, C.st2); g.set(x + 1, y, C.st0); }
  return g;
}
export function console_(): Px {
  const w = 96, h = 44, g = new Px(w, h);
  g.poly([[0, 10], [w, 10], [w - 6, h], [6, h]], C.st2); g.rect(0, 6, w, 6, C.st1); g.hline(0, w - 1, 6, C.st0);
  g.rect(6, 16, w - 12, 18, C.blk1);
  const cols = [C.red1, C.lim1, C.gold1, C.blu1, C.chr0];
  for (let i = 0; i < 10; i++) g.rect(10 + i * 8, 19 + (i % 2) * 6, 5, 4, cols[i % 5]);
  g.rect(w / 2 - 14, 0, 28, 8, C.blk2); g.rect(w / 2 - 12, 1, 24, 6, C.lim2); g.hline(w / 2 - 10, w / 2 + 6, 3, C.lim0);
  tridentInto(g, 8, 37, 6, C.red1); leafInto(g, w - 15, 35, C.red1, 9);
  g.outline(C.ink);
  return g;
}
export function mixerMachine(): Px {
  const w = 72, h = 96, g = new Px(w, h);
  g.rect(4, 20, w - 8, h - 20, C.st2); g.rect(4, 20, 5, h - 20, C.st1); g.rect(w - 9, 20, 5, h - 20, C.st3);
  g.rect(0, h - 8, w, 8, C.blk1); g.rect(0, h - 5, w, 2, C.red1);
  // three pump bottles on top
  [R.cola, R.cream, R.cherry].forEach((ramp, i) => { bottleInto(g, 12 + i * 18, 0, ramp, 9, 20, { cap: C.blk1 }); g.rect(14 + i * 18, 0, 5, 2, C.blk1); });
  // glass beaker window
  g.rect(16, 30, 40, 40, C.st4); g.rect(18, 32, 36, 36, C.gl2); g.rect(18, 50, 36, 18, C.chr0, 160);
  g.rect(20, 33, 2, 34, 0xffffff, 150);
  // screen + dials
  g.rect(16, 74, 40, 10, C.blk2); pxText(g, 19, 76, 'MIX-O', C.lim0);
  g.circle(10, 80, 3, C.st0); g.circle(62, 80, 3, C.st0);
  tridentInto(g, 36, 21, 8, C.red1);
  g.outline(C.ink);
  return g;
}
export function superMachine(): Px {
  const w = 168, h = 170, g = new Px(w, h);
  g.shadedEllipse(84, 30, 70, 26, R.steel);
  g.rect(10, 30, w - 20, h - 30, C.st2); g.rect(10, 30, 8, h - 30, C.st1); g.rect(w - 18, 30, 8, h - 30, C.st3);
  const ramps = [R.cola, R.cream, R.cherry, R.blue, R.lime];
  ramps.forEach((rp, i) => bigTank(g, 22 + i * 26, 48, 18, 76, rp, 0.5 + (i % 3) * 0.15));
  g.rect(20, 132, w - 40, 14, C.blk1); pxText(g, w / 2 - pxTextWidth('SUPER SODA 9000') / 2, 136, 'SUPER SODA 9000', C.red0);
  g.rect(0, h - 16, w, 16, C.blk1); g.rect(0, h - 10, w, 3, C.red1); leafInto(g, w / 2 - 4, h - 13, C.wht, 9);
  tridentInto(g, 84, 0, 26, C.red1, C.red2, C.red0);
  g.outline(C.ink);
  return g;
}
export function glassBlock(): Px {
  const g = new Px(22, 22);
  g.rect(0, 0, 22, 22, C.st3); g.rect(2, 2, 18, 18, C.gl1, 190);
  g.line(4, 16, 14, 4, 0xffffff, 200); g.line(8, 18, 18, 8, 0xffffff, 110);
  g.rect(2, 9, 18, 4, C.gold1); pxText(g, 3, 9, '', C.blk1);
  for (let x = 3; x < 20; x += 4) g.rect(x, 10, 2, 2, C.blk1);
  g.outline(C.ink);
  return g;
}
export function syrupSurface(ramp: Ramp): Px {
  const g = new Px(32, 14);
  g.rect(0, 2, 32, 12, ramp[1]); g.rect(0, 8, 32, 6, ramp[2]);
  for (let x = 0; x < 32; x++) { const y = Math.round(2 + Math.sin(x / 32 * Math.PI * 2) * 1.5); g.set(x, y, ramp[0]); g.set(x, y - 1, ramp[0]); }
  g.ring(8, 9, 1.5, ramp[0]); g.ring(22, 6, 1, ramp[0]);
  return g;
}
export function conveyor(): Px {
  const g = new Px(32, 12);
  g.rect(0, 0, 32, 12, C.blk1); g.rect(0, 1, 32, 3, C.blk0);
  for (let x = 0; x < 32; x += 8) { g.rect(x, 1, 4, 3, C.st3); g.circle(x + 4, 8, 2.5, C.st2); g.set(x + 3, 7, C.st0); }
  return g;
}
export function vent(kind: 'steam' | 'jet'): Px {
  const g = new Px(28, 10);
  g.rect(0, 2, 28, 8, C.blk1); g.rect(2, 0, 24, 4, kind === 'jet' ? C.blu2 : C.st3);
  for (let x = 4; x < 25; x += 4) g.vline(x, 0, 3, C.blk2);
  if (kind === 'jet') { g.rect(10, 5, 8, 3, C.blu0); } else { g.rect(10, 5, 8, 3, C.red1); }
  g.outline(C.ink);
  return g;
}
export function gate(): Px {
  const g = new Px(18, 130);
  g.rect(0, 0, 18, 130, C.st3); for (let y = 0; y < 130; y += 10) g.hline(0, 17, y, C.st4);
  g.rect(2, 0, 3, 130, C.st1); g.rect(13, 0, 3, 130, C.st4);
  for (let y = 20; y < 120; y += 40) tridentInto(g, 9, y, 14, C.red1, C.red2, C.red0);
  g.outline(C.ink);
  return g;
}
export function target(on: boolean): Px {
  const g = new Px(28, 28);
  g.circle(14, 14, 13, C.blk1); g.circle(14, 14, 11, on ? C.lim1 : C.red1); g.circle(14, 14, 7, C.wht); g.circle(14, 14, 4, on ? C.lim1 : C.red1);
  tridentInto(g, 14, 7, 13, on ? C.lim2 : C.red2, on ? C.lim2 : C.red2, on ? C.lim0 : C.red0);
  g.outline(C.ink);
  return g;
}
export function lever(on: boolean): Px {
  const g = new Px(20, 28);
  g.rect(3, 20, 14, 8, C.st3); g.rect(3, 20, 14, 2, C.st1);
  const ang = on ? 0.6 : -0.6;
  const ex = 10 + Math.sin(ang) * 16, ey = 22 - Math.cos(ang) * 16;
  g.line(10, 22, ex, ey, C.st1); g.line(11, 22, ex + 1, ey, C.st2);
  tridentInto(g, Math.round(ex), Math.round(ey) - 4, 9, C.red1, C.red2, C.red0);
  g.outline(C.ink);
  return g;
}
export function armFrame(f: number): Px {
  const g = new Px(48, 60);
  g.rect(18, 0, 12, 8, C.st3);
  const a1 = -0.3 + Math.sin(f * Math.PI / 2) * 0.5, a2 = 0.9 + Math.cos(f * Math.PI / 2) * 0.4;
  const j1x = 24 + Math.sin(a1) * 22, j1y = 6 + Math.cos(a1) * 22;
  const j2x = j1x + Math.sin(a2) * 20, j2y = j1y + Math.cos(a2) * 20;
  for (const o of [-1, 0, 1]) { g.line(24 + o, 6, j1x + o, j1y, C.gold1); g.line(j1x + o, j1y, j2x + o, j2y, C.gold1); }
  g.circle(j1x, j1y, 3, C.st2); g.circle(24, 6, 3.5, C.st2);
  g.line(j2x - 4, j2y, j2x - 4, j2y + 6, C.st3); g.line(j2x + 4, j2y, j2x + 4, j2y + 6, C.st3); g.hline(j2x - 4, j2x + 4, j2y, C.st3);
  g.outline(C.ink);
  return g;
}
export function fruit(kind: 'cherry' | 'lemon' | 'mango' | 'coconut' | 'strawberry'): Px {
  const g = new Px(12, 12);
  if (kind === 'cherry') { g.circle(4, 8, 3, C.chr1); g.circle(8, 8, 3, C.chr1); g.line(4, 5, 6, 1, C.leaf2); g.line(8, 5, 6, 1, C.leaf2); g.set(3, 7, C.chr0); }
  else if (kind === 'lemon') { g.shadedEllipse(6, 7, 5, 4, R.lime, 0.2); }
  else if (kind === 'mango') { g.shadedEllipse(6, 7, 5, 4, R.mango, -0.5); g.set(9, 3, C.leaf1); }
  else if (kind === 'coconut') { g.shadedEllipse(6, 7, 5, 5, [C.wd1, C.wd2, C.wd3, C.wd4]); g.set(5, 5, C.wd4); g.set(7, 5, C.wd4); }
  else { g.poly([[1, 4], [11, 4], [6, 11]], C.chr1); g.rect(3, 2, 6, 2, C.leaf1); g.set(4, 6, C.gold0); g.set(7, 7, C.gold0); }
  g.outline(C.ink);
  return g;
}
export function catwalk(w: number): Px {
  const g = new Px(w, 10);
  g.rect(0, 0, w, 4, C.st2); g.hline(0, w - 1, 0, C.st0);
  for (let x = 0; x < w; x += 6) g.line(x, 4, x + 3, 9, C.st3);
  g.hline(0, w - 1, 9, C.st3);
  g.outline(C.ink);
  return g;
}
