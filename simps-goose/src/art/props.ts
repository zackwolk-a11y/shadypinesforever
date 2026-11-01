/** Store props — original Simps-inspired furniture & machines. */
import { C, R } from './palette';
import { Px, rng } from './px';
import { pxText, pxTextWidth } from './font';
import { bottleInto } from './fx';

export function crate(w = 34, h = 26): Px {
  const g = new Px(w, h);
  g.rect(0, 0, w, h, C.wd3);
  const planks = Math.max(2, Math.round(h / 9));
  const ph = (h - 2) / planks;
  for (let i = 0; i < planks; i++) {
    const y = Math.round(1 + i * ph), hh = Math.round(ph) - 2;
    g.rect(1, y, w - 2, hh, C.wd1);
    g.hline(1, w - 2, y, C.wd0);
    g.hline(1, w - 2, y + hh - 1, C.wd2);
    for (let k = 0; k < 3; k++) { const r = rng(i * 7 + k + w)(); g.hline(4 + r * (w - 14), 4 + r * (w - 14) + 5, y + 2 + k % 2, C.wd2); }
  }
  g.rect(0, 0, 4, h, C.wd2); g.rect(w - 4, 0, 4, h, C.wd2); g.vline(1, 0, h - 1, C.wd1); g.vline(w - 3, 0, h - 1, C.wd1);
  for (const yy of [2, h - 3]) { g.set(2, yy, C.st2); g.set(w - 3, yy, C.st2); }
  // brand stamp (original: red disc + white S)
  const cx = Math.round(w / 2), cy = Math.round(h / 2);
  g.circle(cx, cy, 5, C.red2); g.circle(cx - 0.5, cy - 0.5, 4.5, C.red1);
  pxText(g, cx - 2, cy - 4, 'S', C.wht);
  g.outline(C.ink);
  return g;
}

export function cardboard(seed: number, w = 24, h = 22): Px {
  const r = rng(seed);
  const g = new Px(w, h);
  g.rect(0, 0, w, h, C.cb1);
  g.rect(0, 0, w, 3, C.cb0);
  g.rect(w - 4, 0, 4, h, C.cb2);
  g.vline(Math.round(w / 2), 0, 3, C.cb3);
  g.rect(Math.round(w / 2) - 2, 0, 4, h * 0.4, C.cb0); // tape
  g.hline(0, w - 1, 3, C.cb2);
  if (r() > 0.4) { g.vline(4, 9, 14, C.cb3); g.set(3, 10, C.cb3); g.set(5, 10, C.cb3); g.vline(8, 9, 14, C.cb3); g.set(7, 10, C.cb3); g.set(9, 10, C.cb3); }
  else { g.rect(3, 10, 9, 6, C.wht); g.hline(4, 10, 12, C.blk1); g.hline(4, 8, 14, C.blk1); }
  g.rect(w - 9, h - 7, 4, 3, C.red2);
  g.outline(C.ink);
  return g;
}

/** Display gondola: top is a walkable platform. Bottles are separate sprites. */
export function gondola(w = 112, h = 74): Px {
  const g = new Px(w, h);
  // pegboard back
  g.rect(3, 4, w - 6, h - 12, C.wl2);
  for (let y = 8; y < h - 10; y += 5) for (let x = 7; x < w - 6; x += 5) g.set(x, y, C.wl3);
  // shelves
  for (const sy of [0, 25, 49]) {
    g.rect(0, sy, w, 5, C.wd1); g.hline(0, w - 1, sy, C.wd0); g.hline(0, w - 1, sy + 4, C.wd3);
    g.rect(2, sy + 5, w - 4, 2, C.ink2, 120); // shadow under shelf
    // price strip
    if (sy > 0) { g.hline(2, w - 3, sy + 3, C.wht); for (let x = 10; x < w - 6; x += 22) g.rect(x, sy + 2, 6, 3, C.gold1); }
  }
  // uprights
  g.rect(0, 0, 4, h, C.blk1); g.vline(1, 0, h, C.blk0); g.rect(w - 4, 0, 4, h, C.blk1); g.vline(w - 3, 0, h, C.blk0);
  // base kick plate
  g.rect(0, h - 8, w, 8, C.blk1); g.hline(0, w - 1, h - 8, C.blk0); g.rect(0, h - 5, w, 2, C.red1);
  g.outline(C.ink);
  return g;
}

export function checkout(w = 112, h = 44): Px {
  const g = new Px(w, h);
  g.rect(0, 5, w, h - 5, C.wd2);
  for (let x = 2; x < w - 2; x += 6) { g.rect(x, 7, 5, h - 14, C.wd1); g.vline(x, 7, h - 8, C.wd0); g.vline(x + 4, 7, h - 8, C.wd3); }
  g.rect(0, 0, w, 6, C.blk1); g.hline(0, w - 1, 0, C.blk0); g.hline(0, w - 1, 5, C.ink2);
  g.rect(0, h - 6, w, 6, C.blk1); g.rect(0, h - 4, w, 1, C.red1);
  // front sign panel
  const tw = pxTextWidth('THANK YOU!');
  g.rect(w / 2 - tw / 2 - 4, 13, tw + 8, 13, C.blk1);
  pxText(g, w / 2 - tw / 2, 16, 'THANK YOU!', C.wht);
  g.outline(C.ink);
  return g;
}

export function register(): Px {
  const g = new Px(26, 22);
  g.poly([[2, 10], [24, 10], [22, 21], [4, 21]], C.blk1);
  g.hline(3, 23, 10, C.blk0);
  for (let x = 6; x < 20; x += 3) for (let y = 13; y < 19; y += 3) g.rect(x, y, 2, 2, C.st2);
  g.rect(13, 0, 12, 9, C.blk2); g.rect(14, 1, 10, 7, C.lim2); g.hline(15, 22, 3, C.lim0); g.hline(15, 19, 5, C.lim0);
  g.vline(18, 9, 10, C.blk1);
  g.outline(C.ink);
  return g;
}

export function sampleCounter(w = 104, h = 40): Px {
  const g = new Px(w, h);
  g.rect(0, 0, w, 6, C.wht); g.hline(0, w - 1, 0, 0xffffff); g.rect(0, 5, w, 2, C.st2);
  for (let i = 0; i < 18; i++) { const r = rng(i + 3); g.line(r() * w, 1 + r() * 4, r() * w, 1 + r() * 4, C.wl1); } // marble veins
  g.rect(2, 7, w - 4, h - 7, C.blk1);
  g.rect(2, 7, 3, h - 7, C.blk0);
  g.rect(2, h - 7, w - 4, 2, C.red1);
  const t = 'TASTE TEST';
  pxText(g, w / 2 - pxTextWidth(t) / 2, 14, t, C.wht);
  // flavor dots
  [C.cola1, C.crm1, C.chr1].forEach((c, i) => { g.circle(w / 2 - 16 + i * 16, 29, 3, c); g.set(w / 2 - 17 + i * 16, 28, C.wht); });
  g.outline(C.ink);
  return g;
}

export function chalkboard(): Px {
  const w = 86, h = 66;
  const g = new Px(w, h);
  g.rect(0, 0, w, h - 10, C.wd2); g.rect(3, 3, w - 6, h - 16, C.blk1);
  for (let i = 0; i < 40; i++) { const r = rng(i + 99); g.set(4 + r() * (w - 8), 4 + r() * (h - 18), C.blk0); }
  pxText(g, w / 2 - pxTextWidth('FREE SAMPLES') / 2, 7, 'FREE SAMPLES', C.gold0);
  g.hline(8, w - 9, 16, C.wl2);
  const items: [string, number][] = [['COLA', C.cola0], ['CREAM SODA', C.crm1], ['BLACK CHERRY', C.chr0]];
  items.forEach(([s, c], i) => { g.circle(9, 23 + i * 10, 2.5, c); pxText(g, 14, 20 + i * 10, s, C.wht); });
  // legs
  g.rect(10, h - 10, 4, 10, C.wd3); g.rect(w - 14, h - 10, 4, 10, C.wd3);
  g.outline(C.ink);
  return g;
}

export function pumpBottle(ramp: typeof R.cola): Px {
  const g = new Px(14, 34);
  // pump head
  g.rect(3, 0, 8, 2, C.blk1); g.rect(9, 1, 4, 2, C.blk1); g.rect(6, 2, 2, 6, C.st2);
  bottleInto(g, 2, 7, ramp, 10, 26, { cap: C.blk1 });
  g.outline(C.ink);
  return g;
}

export function sampleCup(col: number): Px {
  const g = new Px(9, 9);
  g.poly([[0, 0], [9, 0], [7.5, 9], [1.5, 9]], C.gl1, 170);
  g.poly([[1, 3], [8, 3], [7.2, 8], [1.8, 8]], col);
  g.hline(1, 7, 3, 0xffffff);
  g.vline(1, 1, 7, 0xffffff);
  g.outline(C.ink);
  return g;
}

/** FIZZ-O-MATIC 3000 — fictional soda fountain machine. 128x168 */
export function fountain(): Px {
  const w = 128, h = 168;
  const g = new Px(w, h);
  // dome
  g.shadedEllipse(64, 22, 44, 18, R.steel);
  g.rect(20, 22, 88, 6, C.st2);
  // upper housing
  g.rect(8, 26, 112, 80, C.st1);
  g.rect(8, 26, 6, 80, C.st0); g.rect(114, 26, 6, 80, C.st3);
  g.hline(8, 119, 26, C.st0);
  // tanks
  const tanks: [number, typeof R.cola][] = [[18, R.cola], [51, R.cream], [84, R.cherry]];
  for (const [tx, ramp] of tanks) {
    g.rect(tx - 2, 34, 30, 62, C.st3);
    g.rect(tx, 36, 26, 58, C.gl2);
    g.rect(tx, 48, 26, 46, ramp[1]);
    g.rect(tx + 19, 48, 7, 46, ramp[2]);
    g.hline(tx, tx + 25, 48, ramp[0]);
    g.hline(tx, tx + 25, 49, ramp[0]);
    for (let k = 0; k < 7; k++) { const r = rng(tx + k); g.circle(tx + 3 + r() * 20, 52 + r() * 38, 0.8 + r(), ramp[0]); }
    g.rect(tx + 2, 37, 2, 55, 0xffffff, 170); g.rect(tx + 6, 37, 1, 55, 0xffffff, 90);
    g.rect(tx - 2, 32, 30, 4, C.st2); g.rect(tx - 2, 94, 30, 4, C.st2);
    for (const bx of [tx, tx + 24]) { g.set(bx, 33, C.st0); g.set(bx, 95, C.st0); }
  }
  // pipes between tanks
  for (const px of [46, 79]) { g.rect(px, 40, 4, 50, C.st2); g.vline(px, 40, 89, C.st0); }
  // name plate
  g.rect(28, 98, 72, 10, C.blk1); g.hline(28, 99, 98, C.blk0);
  pxText(g, 64 - pxTextWidth('FIZZ-O-MATIC') / 2, 99, 'FIZZ-O-MATIC', C.red0);
  // nozzle bar
  g.rect(6, 108, 116, 8, C.st2); g.hline(6, 121, 108, C.st0); g.hline(6, 121, 115, C.st3);
  for (let i = 0; i < 4; i++) { const nx = 24 + i * 26; g.rect(nx, 116, 6, 6, C.st1); g.rect(nx + 1, 122, 4, 3, C.st3); g.rect(nx + 2, 125, 2, 1, C.blk1); }
  // drip tray / base cabinet
  g.rect(4, 132, 120, 6, C.st2); for (let x = 6; x < 122; x += 3) g.vline(x, 133, 136, C.st4);
  g.rect(8, 138, 112, 30, C.blk1);
  g.rect(8, 138, 112, 2, C.blk0);
  g.rect(8, 150, 112, 4, C.red1); g.hline(8, 119, 150, C.red0);
  for (let x = 14; x < 118; x += 16) { g.set(x, 143, C.st2); g.set(x, 162, C.st2); }
  g.outline(C.ink);
  return g;
}

export function gauge(): Px {
  const g = new Px(26, 26);
  g.circle(13, 13, 12.5, C.st2); g.circle(12.5, 12.5, 11, C.st0); g.circle(13, 13, 10, C.wht);
  for (let a = Math.PI * 0.75, i = 0; a <= Math.PI * 2.25 + 0.01; a += Math.PI * 1.5 / 18, i++) {
    const col = i < 9 ? C.green : i < 14 ? C.gold1 : C.red1;
    g.set(13 + Math.cos(a) * 8.5, 13 + Math.sin(a) * 8.5, col);
    g.set(13 + Math.cos(a) * 7.6, 13 + Math.sin(a) * 7.6, col);
  }
  g.rect(9, 18, 8, 3, C.blk1); pxText(g, 10, 15, '', C.ink);
  g.outline(C.ink);
  return g;
}
export function needle(): Px { const g = new Px(3, 10); g.vline(1, 0, 8, C.red1); g.set(1, 9, C.ink); g.rect(0, 8, 3, 2, C.ink); return g; }
export function beacon(): Px { const g = new Px(10, 8); g.shadedEllipse(5, 5, 4, 4, R.red); g.rect(1, 6, 8, 2, C.st2); g.set(3, 3, C.wht); g.outline(C.ink); return g; }

export function valveWheel(): Px {
  const g = new Px(24, 24);
  g.ring(12, 12, 11, C.red1, 3); g.ring(12, 12, 11, C.red0, 1);
  for (let a = 0; a < Math.PI * 2; a += Math.PI / 2) g.line(12, 12, 12 + Math.cos(a) * 9, 12 + Math.sin(a) * 9, C.red2);
  g.circle(12, 12, 3, C.st1); g.set(11, 11, C.wht);
  for (let a = Math.PI / 4; a < Math.PI * 2; a += Math.PI / 2) g.circle(12 + Math.cos(a) * 10.5, 12 + Math.sin(a) * 10.5, 1.5, C.red2);
  g.outline(C.ink);
  return g;
}
export function valvePost(): Px {
  const g = new Px(30, 52);
  g.rect(11, 10, 8, 42, C.st2); g.vline(12, 10, 51, C.st0); g.vline(17, 10, 51, C.st3);
  g.rect(8, 46, 14, 6, C.st3);
  g.rect(2, 24, 26, 16, C.blk1); g.rect(3, 25, 24, 14, C.gold1);
  pxText(g, 4, 25, 'PULL', C.blk1); pxText(g, 4, 32, 'ME!', C.red2);
  g.outline(C.ink);
  return g;
}

export function sign(text: string[], w: number, colors = { bg: C.wht, fg: C.red1, border: C.blk1 }): Px {
  const h = text.length * 9 + 6;
  const g = new Px(w, h);
  g.rect(0, 0, w, h, colors.border); g.rect(2, 2, w - 4, h - 4, colors.bg);
  text.forEach((t, i) => pxText(g, Math.round(w / 2 - pxTextWidth(t) / 2), 4 + i * 9, t, colors.fg));
  g.outline(C.ink);
  return g;
}

export function mezzanine(w = 236): Px {
  const h = 34;
  const g = new Px(w, h);
  // railing (behind deck)
  g.hline(0, w - 1, 2, C.blk1); g.hline(0, w - 1, 3, C.blk0);
  for (let x = 4; x < w; x += 14) g.rect(x, 3, 2, 18, C.blk1);
  g.hline(0, w - 1, 11, C.blk1);
  // deck
  g.rect(0, 20, w, 5, C.wd1); g.hline(0, w - 1, 20, C.wd0);
  for (let x = 0; x < w; x += 18) g.vline(x, 21, 24, C.wd3);
  g.rect(0, 25, w, 9, C.blk1); g.hline(0, w - 1, 25, C.blk0);
  for (let x = 6; x < w; x += 20) g.set(x, 29, C.st1);
  g.outline(C.ink);
  return g;
}
export function beam(h: number): Px { const g = new Px(10, h); g.rect(0, 0, 10, h, C.blk1); g.rect(3, 0, 4, h, C.blk0); g.rect(0, 0, 10, 3, C.blk0); g.outline(C.ink); return g; }

export function baskets(): Px {
  const g = new Px(30, 24);
  for (let i = 0; i < 4; i++) {
    const y = 4 + i * 4;
    g.poly([[1, y], [29, y], [27, y + 10], [3, y + 10]], i === 3 ? C.red1 : C.red2);
    g.hline(1, 28, y, C.red0);
  }
  for (let x = 5; x < 26; x += 4) g.vline(x, 18, 23, C.red3);
  g.line(4, 4, 10, 0, C.blk1); g.line(25, 4, 19, 0, C.blk1); g.hline(10, 19, 0, C.blk1);
  g.outline(C.ink);
  return g;
}

export function plant(): Px {
  const g = new Px(34, 50);
  const r = rng(5);
  for (let i = 0; i < 9; i++) {
    const a = -Math.PI / 2 + (i - 4) * 0.33 + (r() - 0.5) * 0.2;
    const L = 14 + r() * 8;
    const ex = 17 + Math.cos(a) * L, ey = 32 + Math.sin(a) * L;
    g.line(17, 32, ex, ey, C.leaf2);
    g.shadedEllipse(ex, ey, 6, 3.4, R.leaf, a);
    g.line(ex - Math.cos(a) * 4, ey - Math.sin(a) * 4, ex + Math.cos(a) * 4, ey + Math.sin(a) * 4, C.leaf2);
  }
  g.poly([[7, 32], [27, 32], [24, 49], [10, 49]], C.wht); g.rect(7, 32, 20, 3, C.wl1); g.vline(23, 35, 48, C.wl2);
  g.outline(C.ink);
  return g;
}

export function pendant(): Px {
  const g = new Px(20, 14);
  g.poly([[6, 2], [14, 2], [19, 11], [1, 11]], C.blk1); g.hline(6, 14, 2, C.blk0); g.line(5, 4, 2, 10, C.blk0);
  g.rect(4, 11, 12, 2, C.gold0); g.rect(7, 12, 6, 2, 0xffffff);
  g.rect(9, 0, 2, 2, C.blk2);
  g.outline(C.ink);
  return g;
}

export function doorInterior(): Px {
  const w = 48, h = 82;
  const g = new Px(w, h);
  g.rect(0, 0, w, h, C.blk1);
  g.vgrad(5, 5, w - 10, h - 10, [C.sky2, C.sky0, C.side0]);
  g.rect(5, h - 26, w - 10, 21, C.side1);
  // street beyond
  g.rect(8, 30, 10, 30, C.brick1); g.rect(30, 26, 14, 34, C.leaf2);
  g.line(5, 5, 20, h - 6, 0xffffff, 60); g.line(10, 5, 25, h - 6, 0xffffff, 40);
  g.rect(w - 12, 40, 4, 10, C.st1);
  g.rect(14, 12, 20, 9, C.red1); pxText(g, 15, 13, 'OPEN', C.wht);
  g.outline(C.ink);
  return g;
}

/** Storefront door (street) frames: 0 closed .. 3 wide open (perspective swing) */
export function streetDoor(frame: number): Px {
  const w = 40, h = 74;
  const g = new Px(w, h);
  g.rect(0, 0, w, h, C.blk2); // dark interior visible
  g.rect(2, 2, w - 4, h - 2, C.ink2);
  // warm interior light spill
  g.rect(4, 10, w - 8, h - 12, C.wd3);
  g.rect(6, 20, w - 12, 30, C.gold2, 120);
  const open = frame / 3;
  const dw = Math.round((w - 4) * (1 - open * 0.8));
  g.rect(2, 2, dw, h - 2, C.blk1);
  if (dw > 8) {
    g.rect(5, 6, dw - 6, h - 16, C.gl2); g.rect(5, 6, dw - 6, h - 16, C.sky2, 80);
    g.line(6, 8, 6 + (dw - 8) * 0.6, h - 14, 0xffffff, 120);
    g.rect(dw - 3, 36, 2, 8, C.st1);
    if (dw > 22) { g.rect(8, 14, Math.min(20, dw - 12), 8, C.red1); pxText(g, 9, 15, dw > 30 ? 'OPEN' : 'OP', C.wht); }
  }
  g.outline(C.ink);
  return g;
}
