/** Large cached scenery canvases: the store back wall, floor, and street layers. */
import { C, R, type Ramp } from './palette';
import { Px, rng } from './px';
import { pxText, pxTextWidth } from './font';
import { bottleInto } from './fx';
import { BG_W, WORLD_H, FLOOR, L, bgX } from '../gameplay/layout';

const BOTTLE_RAMPS: Ramp[] = [R.cola, R.cream, R.cherry, R.blue, R.lime, R.mango, R.purple, R.rootbeer, R.red, [C.pink, C.chr0, C.chr1, C.chr2], R.gold];

function bottleShelf(g: Px, x0: number, x1: number, y: number, seed: number, palette?: Ramp[]) {
  const r = rng(seed);
  // shelf board
  g.rect(x0 - 3, y, x1 - x0 + 6, 4, C.wd1); g.hline(x0 - 3, x1 + 2, y, C.wd0); g.hline(x0 - 3, x1 + 2, y + 3, C.wd3);
  g.rect(x0 - 3, y + 4, x1 - x0 + 6, 2, C.ink, 90);
  // brackets
  for (let x = x0 + 6; x < x1; x += 60) { g.rect(x, y + 4, 2, 5, C.blk1); }
  let x = x0;
  const pal = palette ?? BOTTLE_RAMPS;
  let group = Math.floor(r() * pal.length), left = 3 + Math.floor(r() * 4);
  while (x < x1 - 8) {
    if (left-- <= 0) { group = (group + 1 + Math.floor(r() * 2)) % pal.length; left = 3 + Math.floor(r() * 4); }
    const w = r() > 0.7 ? 8 : 6, h = 14 + Math.floor(r() * 3) * 2 + (w === 8 ? 4 : 0);
    const b = new Px(w + 2, h + 2);
    bottleInto(b, 1, 1, pal[group], w, h);
    b.outline(C.ink2);
    g.blit(b, x, y - h - 2);
    x += w + 2;
    if (r() > 0.93) x += 6;
  }
}

function subwayTile(g: Px, x0: number, y0: number, w: number, h: number) {
  g.rect(x0, y0, w, h, C.wl0);
  for (let y = y0; y < y0 + h; y += 6) {
    g.hline(x0, x0 + w - 1, y, C.wl2);
    const off = ((y - y0) / 6) % 2 ? 6 : 0;
    for (let x = x0 + off; x < x0 + w; x += 12) g.vline(x, y, y + 5, C.wl2);
    for (let x = x0 + off + 1; x < x0 + w; x += 12) g.set(x + 1, y + 1, 0xffffff);
  }
}

function bigWordmark(g: Px, x: number, y: number, s: string, scale: number, fill: number, shade: number) {
  pxText(g, x + scale, y + scale, s, shade, scale, 1);
  pxText(g, x, y, s, fill, scale, 1);
}

/** Store back wall at parallax 0.9 (see layout.bgX). */
export function storeBackWall(): Px {
  const W = BG_W, H = WORLD_H;
  const g = new Px(W, H);
  // ceiling
  g.rect(0, 0, W, 34, C.blk2);
  for (let x = 0; x < W; x += 48) { g.rect(x, 0, 4, 30, C.ink2); }
  g.rect(0, 10, W, 8, C.st4); g.hline(0, W - 1, 10, C.st3); g.hline(0, W - 1, 17, C.ink); // duct
  for (let x = 20; x < W; x += 90) { g.rect(x, 9, 4, 10, C.st3); }
  // skylight above the mezzanine (final ride target)
  const sx = bgX(L.skylight.x) - 40;
  g.rect(sx, 0, 80, 30, C.st3); g.vgrad(sx + 4, 0, 72, 26, [C.sky3, C.sky2, C.sky0]);
  for (let k = 1; k < 4; k++) g.rect(sx + k * 18 + 3, 0, 2, 26, C.st3);
  g.hline(sx, sx + 79, 26, C.st2);
  // upper wall charcoal
  g.rect(0, 34, W, 88, C.blk1);
  for (let y = 36; y < 122; y += 4) for (let x = (y / 4) % 2 ? 0 : 3; x < W; x += 7) g.set(x, y, C.blk0);
  g.hline(0, W - 1, 34, C.ink);
  // brand stripe
  g.rect(0, 118, W, 4, C.red1); g.hline(0, W - 1, 118, C.red0);
  // big wordmark (original lettering, not the official logo)
  const wmX = bgX(330);
  bigWordmark(g, wmX, 48, 'SIMPS', 5, C.wht, C.ink);
  pxText(g, wmX + 2, 90, 'MODERN BEVERAGE', C.red0, 1);
  pxText(g, wmX + 2, 102, 'KELOWNA, B.C.', C.wl2, 1);
  // bubble motif around wordmark
  for (let i = 0; i < 14; i++) { const r = rng(i + 70); g.ring(wmX + 150 + r() * 110, 46 + r() * 60, 2 + r() * 5, C.blu1, 1); }
  // section header boards
  const header = (wx: number, t: string, col: number) => {
    const x = bgX(wx), w = pxTextWidth(t) + 12;
    g.rect(x - w / 2, 70, w, 14, col); g.rect(x - w / 2 + 1, 71, w - 2, 12, C.blk2);
    pxText(g, x - w / 2 + 6, 73, t, col === C.wht ? C.wht : col);
    g.vline(x - w / 2 + 8, 34, 70, C.st3); g.vline(x + w / 2 - 8, 34, 70, C.st3);
  };
  header(780, 'SODA CONCENTRATES', C.wht);
  header(1170, 'CAFE SERIES', C.gold1);
  header(1600, 'ZERO SUGAR', C.lim0);
  header(2030, 'THE FIZZ BAR', C.red0);

  // lower wall: subway tile
  subwayTile(g, 0, 122, W, FLOOR - 122);
  // wall shelves with bottles (avoid fridges, chalkboard, fountain)
  const spans: [number, number][] = [[bgX(150), bgX(820)], [bgX(1080), bgX(1350)], [bgX(1510), bgX(1700)]];
  spans.forEach(([a, b], i) => { bottleShelf(g, a, b, 166, 11 + i); bottleShelf(g, a, b, 206, 31 + i); bottleShelf(g, a, b, 246, 51 + i); });
  // cafe series shelf: warmer palette
  bottleShelf(g, bgX(1080), bgX(1350), 166, 99, [R.cola, R.cream, R.gold, R.rootbeer, [C.pur0, C.pur1, C.pur2, C.ink2]]);

  // refrigerated cases
  const fx = bgX(L.fridges.x);
  for (let k = 0; k < 2; k++) {
    const x = fx + k * 100, y = 168, w = 96, h = FLOOR - y;
    g.rect(x, y - 14, w, 14, C.blk1); pxText(g, x + w / 2 - pxTextWidth('ICE COLD') / 2, y - 11, 'ICE COLD', C.blu0);
    g.rect(x, y, w, h, C.blk1);
    for (let d = 0; d < 2; d++) {
      const dx = x + 4 + d * 46, dw = 42;
      g.vgrad(dx, y + 4, dw, h - 14, [0xe8f8ff, C.gl1, C.gl2]);
      for (let sy = y + 30; sy < FLOOR - 14; sy += 30) {
        g.rect(dx, sy, dw, 2, C.st2);
        const r = rng(sy + d * 13 + k * 7);
        for (let bx = dx + 2; bx < dx + dw - 6; bx += 7) {
          const ramp = BOTTLE_RAMPS[Math.floor(r() * 8)];
          const b = new Px(7, 22); bottleInto(b, 1, 1, ramp, 5, 18); g.blit(b, bx, sy - 21);
        }
      }
      // glass reflections
      for (let t = 0; t < 2; t++) g.line(dx + 6 + t * 14, y + 6, dx + 22 + t * 14, y + h - 14, 0xffffff, 110);
      g.rect(dx + dw - 4, y + h / 2 - 10, 2, 20, C.st1);
    }
    g.rect(x, FLOOR - 10, w, 10, C.blk2);
  }

  // cafe-series sign panel behind checkout
  // lab door (foreshadowing Level 2) under the mezzanine
  const ldx = bgX(L.labDoor.x);
  g.rect(ldx, 238, 56, 92, C.st3); g.rect(ldx + 3, 241, 50, 89, C.st2);
  g.rect(ldx + 8, 252, 40, 26, C.blu3); g.rect(ldx + 10, 254, 36, 22, C.blu2);
  g.line(ldx + 12, 256, ldx + 26, 274, C.blu0, 120);
  g.rect(ldx + 6, 224, 44, 12, C.gold1); pxText(g, ldx + 8, 227, 'LAB', C.blk1); pxText(g, ldx + 28, 227, '->', C.blk1);
  g.rect(ldx + 6, 284, 44, 10, C.red1); pxText(g, ldx + 7, 286, 'STAFF', C.wht);
  g.rect(ldx + 44, 300, 3, 10, C.st0);
  // big window light patch near entrance + wainscot
  g.rect(0, FLOOR - 8, W, 8, C.blk1); g.hline(0, W - 1, FLOOR - 8, C.blk0);
  return g;
}

/** Repeating wood floor tile, 64x30. */
export function floorTile(): Px {
  const g = new Px(64, 30);
  g.rect(0, 0, 64, 30, C.wd2);
  g.rect(0, 0, 64, 3, C.wd0); g.hline(0, 63, 3, C.wd3);
  for (let row = 0; row < 3; row++) {
    const y = 4 + row * 9;
    g.rect(0, y, 64, 8, row % 2 ? C.wd2 : C.wd1);
    g.hline(0, 63, y + 8, C.wd3);
    const off = row * 21 % 64;
    g.vline((off + 30) % 64, y, y + 7, C.wd3); g.vline((off + 62) % 64, y, y + 7, C.wd3);
    const r = rng(row + 4);
    for (let k = 0; k < 5; k++) g.hline(r() * 60, r() * 60 + 4, y + 2 + Math.floor(r() * 5), row % 2 ? C.wd1 : C.wd0);
  }
  for (let x = 0; x < 64; x++) if (Px.bayer(x, 0) > 0.5) g.set(x, 1, 0xffffff);
  return g;
}

// ----------------------------------------------------------------- STREET (intro) ----
export const STREET_W = 1000;
export function streetSky(): Px {
  const g = new Px(480, 270);
  g.vgrad(0, 0, 480, 200, [C.sky3, C.sky2, 0xc9e6f2, C.sky0, C.sky1]);
  // soft clouds
  const r = rng(3);
  for (let i = 0; i < 6; i++) {
    const cx = r() * 480, cy = 20 + r() * 70, s = 10 + r() * 14;
    for (let k = 0; k < 4; k++) g.ellipse(cx + k * s * 0.7, cy + (k % 2) * 3, s, s * 0.45, 0xffffff, 150);
  }
  g.circle(400, 60, 14, 0xfff6d8); g.circle(400, 60, 20, 0xfff6d8, 60);
  return g;
}
export function streetMountains(): Px {
  const W = 700, g = new Px(W, 270);
  const r = rng(8);
  const ridge = (base: number, amp: number, col: number, hi: number, seed: number) => {
    const rr = rng(seed);
    const ph = [rr() * 6, rr() * 6, rr() * 6];
    for (let x = 0; x < W; x++) {
      const top = base - amp * (0.5 + 0.3 * Math.sin(x / 90 + ph[0]) + 0.15 * Math.sin(x / 37 + ph[1]) + 0.05 * Math.sin(x / 11 + ph[2]));
      g.vline(x, top, 200, col);
      g.set(x, top, hi);
    }
  };
  ridge(150, 70, C.mt0, 0xd8d6ee, 1);
  ridge(165, 50, C.mt1, C.mt0, 2);
  // Okanagan Lake sliver
  g.rect(0, 168, W, 12, C.blu1); g.hline(0, W - 1, 168, C.blu0);
  for (let i = 0; i < 40; i++) g.hline(r() * W, r() * W + 6, 170 + r() * 9, C.blu0);
  ridge(196, 26, C.hill1, C.hill0, 3);
  for (let i = 0; i < 70; i++) { const x = r() * W, y = 176 + r() * 24; g.poly([[x, y - 6], [x + 3, y + 2], [x - 3, y + 2]], C.hill2); }
  return g;
}
export function streetTrees(): Px {
  const W = 800, g = new Px(W, 270);
  const r = rng(12);
  for (let i = 0; i < 16; i++) {
    const x = i * 52 + r() * 30, h = 40 + r() * 30, y = 228;
    g.rect(x - 2, y - h * 0.4, 4, h * 0.4, C.wd3);
    for (let k = 0; k < 5; k++) g.shadedEllipse(x + (r() - 0.5) * 16, y - h * 0.55 - r() * h * 0.4, 10 + r() * 6, 9 + r() * 4, [C.leaf1, C.leaf2, C.leaf2, C.leaf3]);
  }
  // distant buildings silhouettes
  for (let x = 0; x < W; x += 34 + r() * 30) { const h = 40 + r() * 50; g.rect(x, 228 - h, 26 + r() * 20, h, C.mt2); for (let wy = 228 - h + 6; wy < 220; wy += 8) for (let wx = x + 4; wx < x + 22; wx += 6) g.rect(wx, wy, 2, 3, C.mt1); }
  return g;
}
export const STOREFRONT = { x: 430, w: 330, doorX: 588, doorY: 152, winBottleX: 520, winBottleY: 176 };
export function streetFront(): Px {
  const W = STREET_W, H = 270, g = new Px(W, H);
  const GY = 226;
  // building A — brick
  g.rect(0, 40, 260, GY - 40, C.brick1);
  for (let y = 40; y < GY; y += 4) { g.hline(0, 259, y, C.brick2); for (let x = (y / 4) % 2 ? 0 : 6; x < 260; x += 12) g.vline(x, y, y + 3, C.brick2); }
  for (let x = 0; x < 260; x += 3) if (Px.bayer(x, 2) > 0.6) g.set(x, 42, C.brick0);
  for (let wx = 20; wx < 240; wx += 56) { g.rect(wx, 60, 30, 36, C.wl1); g.rect(wx + 2, 62, 26, 32, C.gl2); g.line(wx + 4, 64, wx + 14, 92, 0xffffff, 90); g.rect(wx - 2, 96, 34, 3, C.wl2); }
  g.rect(14, 140, 220, 86, C.leaf3); g.rect(18, 146, 120, 70, C.gl2); g.rect(150, 150, 34, 76, C.wd3);
  g.rect(14, 124, 220, 16, C.leaf2); pxText(g, 60, 129, 'RECORDS & BOOKS', C.crm0);
  // building C — pastel
  g.rect(790, 60, 210, GY - 60, C.crm1);
  for (let y = 64; y < GY; y += 6) g.hline(790, 999, y, C.crm2);
  for (let wx = 808; wx < 990; wx += 50) { g.rect(wx, 78, 28, 38, C.wht); g.rect(wx + 2, 80, 24, 34, C.gl1); }
  g.rect(800, 150, 190, 76, C.wd2); g.rect(808, 156, 110, 62, C.gl2); g.rect(930, 158, 30, 68, C.wd3);
  for (let x = 800; x < 990; x += 14) g.poly([[x, 138], [x + 14, 138], [x + 14, 148], [x + 7, 152], [x, 148]], (x / 14) % 2 ? C.blu1 : C.wht);
  pxText(g, 820, 128, 'BAKERY', C.wd3);

  // ------ SIMPS storefront (original art; brand colours red / black / white) ------
  const sx = STOREFRONT.x, sw = STOREFRONT.w;
  g.rect(sx - 20, 50, sw + 40, GY - 50, C.wht);
  for (let y = 52; y < 112; y += 4) { g.hline(sx - 20, sx + sw + 19, y, C.wl1); for (let x = sx - 20 + ((y / 4) % 2 ? 0 : 6); x < sx + sw + 20; x += 12) g.vline(x, y, y + 3, C.wl1); }
  for (let wx = sx; wx < sx + sw; wx += 66) { g.rect(wx + 8, 62, 34, 36, C.blk1); g.rect(wx + 10, 64, 30, 32, C.gl2); g.line(wx + 12, 66, wx + 24, 94, 0xffffff, 100); for (let k = 0; k < 3; k++) g.ellipse(wx + 16 + k * 8, 92, 4, 3, C.leaf1); }
  g.rect(sx - 10, 112, sw + 20, GY - 112, C.blk1);
  g.rect(sx - 10, 112, sw + 20, 2, C.blk0);
  // sign band
  bigWordmark(g, sx + sw / 2 - pxTextWidth('SIMPS', 3) / 2, 116, 'SIMPS', 3, C.wht, C.red2);
  // awning
  for (let x = sx - 6; x < sx + sw + 6; x += 12) {
    g.poly([[x, 140], [x + 12, 140], [x + 12, 150], [x + 6, 154], [x, 150]], ((x - sx) / 12) % 2 ? C.wht : C.red1);
    g.hline(x, x + 11, 140, ((x - sx) / 12) % 2 ? 0xffffff : C.red0);
  }
  g.rect(sx - 8, 138, sw + 16, 2, C.red2);
  // windows with display shelves
  const win = (x: number, w: number, seed: number) => {
    g.rect(x - 3, 156, w + 6, 64, C.blk2);
    g.vgrad(x, 158, w, 58, [C.wd3, C.wd2, C.wd3]);
    g.rect(x, 158, w, 58, C.gold1, 40);
    bottleShelf(g, x + 4, x + w - 4, 184, seed);
    bottleShelf(g, x + 4, x + w - 4, 210, seed + 5);
    for (let t = 0; t < 3; t++) g.line(x + 6 + t * 24, 160, x + 26 + t * 24, 214, 0xffffff, 70);
    g.rect(x - 3, 216, w + 6, 6, C.blk0);
  };
  win(sx + 6, 140, 70);
  win(sx + 210, 112, 90);
  g.rect(STOREFRONT.doorX - 4, 150, 48, 76, C.blk2);
  pxText(g, sx + 222, 160, 'SODA * SYRUPS', C.wht);
  // sidewalk + road
  g.rect(0, GY, W, 22, C.side0);
  for (let x = 0; x < W; x += 24) g.vline(x, GY, GY + 21, C.side2);
  g.hline(0, W - 1, GY, 0xffffff);
  g.rect(0, GY + 20, W, 4, C.side2);
  g.rect(0, GY + 24, W, H - GY - 24, C.road1);
  for (let x = 0; x < W; x += 3) for (let y = GY + 25; y < H; y += 3) if (rng(x * 977 + y)() > 0.8) g.set(x, y, C.road2);
  for (let x = 10; x < W; x += 60) g.rect(x, 262, 28, 2, C.wht);
  return g;
}
export function lampPost(): Px {
  const g = new Px(20, 110);
  g.rect(8, 14, 4, 92, C.blk1); g.vline(9, 14, 105, C.blk0); g.rect(5, 104, 10, 6, C.blk1);
  g.rect(3, 4, 14, 12, C.blk1); g.rect(5, 6, 10, 8, C.gold0); g.rect(6, 0, 8, 4, C.blk1);
  g.rect(14, 40, 6, 18, C.red1); g.rect(15, 42, 4, 14, C.red0);
  g.outline(C.ink);
  return g;
}
export function sandwichBoard(): Px {
  const g = new Px(34, 40);
  g.poly([[4, 0], [30, 0], [34, 40], [0, 40]], C.wd2);
  g.rect(5, 3, 24, 30, C.blk1);
  pxText(g, 7, 5, 'SODA', C.wht); pxText(g, 7, 14, 'SYRUP', C.red0); pxText(g, 7, 23, 'OPEN', C.gold1);
  g.outline(C.ink);
  return g;
}
export function planterTree(): Px {
  const g = new Px(56, 96);
  g.rect(26, 40, 5, 44, C.wd3);
  const r = rng(77);
  for (let k = 0; k < 9; k++) g.shadedEllipse(28 + (r() - 0.5) * 30, 26 + (r() - 0.5) * 30, 11 + r() * 5, 9 + r() * 4, R.leaf);
  g.rect(10, 80, 36, 16, C.st3); g.rect(10, 80, 36, 3, C.st2);
  for (let k = 0; k < 6; k++) { g.circle(14 + k * 6, 79, 2, k % 2 ? C.red0 : C.gold1); }
  g.outline(C.ink);
  return g;
}
export function bird(frame: number): Px {
  const g = new Px(10, 8);
  g.ellipse(5, 5, 3.5, 2.5, C.wd2); g.circle(7.5, 3.5, 2, C.wd2); g.set(9, 3, C.go2); g.set(8, 3, C.ink);
  if (frame === 1) g.poly([[3, 4], [6, 0], [7, 4]], C.wd3); else g.poly([[3, 5], [7, 5], [4, 7]], C.wd3);
  g.set(1, 5, C.wd3);
  g.outline(C.ink);
  return g;
}
