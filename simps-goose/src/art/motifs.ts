/**
 * RECURRING VISUAL LANGUAGE — the Simps red trident + Canadian maple leaf.
 * Original pixel interpretations; every prop, platform, HUD piece and effect that
 * carries the motif is drawn through these helpers so it stays consistent.
 */
import { C } from './palette';
import { Px } from './px';

/**
 * Trident: centre prong up, two side prongs curving up from a U crossbar,
 * shaft running down to an arrowhead. (cx, top) = tip of centre prong, h = total height.
 */
export function tridentInto(g: Px, cx: number, top: number, h: number, col = C.red1, shade = C.red2, hi = C.red0) {
  const s = h / 44; // design grid is 44 tall
  const T = Math.max(1, Math.round(3 * s)); // stroke
  const half = Math.max(1, Math.floor(T / 2));
  const y = (v: number) => Math.round(top + v * s);
  const x = (v: number) => Math.round(cx + v * s);
  // centre shaft
  g.rect(cx - half, y(5), T, y(36) - y(5), col);
  // centre tip
  g.poly([[cx + 0.5, y(0)], [x(4.2) + 0.5, y(7)], [x(-4.2) + 0.5, y(7)]], col);
  // U crossbar + side prongs (stroke along an arc)
  for (let a = 0; a <= Math.PI; a += 0.02 / Math.max(0.5, s)) {
    const px = cx + Math.cos(a) * 10 * s, py = top + (20 + Math.sin(a) * 6) * s;
    g.rect(Math.round(px - half), Math.round(py - half), T, T, col);
  }
  for (const d of [-1, 1]) {
    // prong rising from crossbar end, flaring outward at the top
    for (let v = 6; v <= 20; v += 0.25 / Math.max(0.5, s)) {
      const flare = Math.max(0, (12 - v) / 12) * 3;
      g.rect(Math.round(cx + d * (10 + flare) * s - half), Math.round(top + v * s), T, T, col);
    }
    // barb tip pointing up/outward
    const tx = cx + d * 13.5 * s, ty = top + 2 * s;
    g.poly([[tx + 0.5, ty], [tx + d * -3.5 * s + 0.5, ty + 7 * s], [tx + d * 3 * s + 0.5, ty + 6 * s]], col);
  }
  // bottom arrowhead
  g.poly([[cx + 0.5, y(44)], [x(5) + 0.5, y(34)], [x(-5) + 0.5, y(34)]], col);
  // shading: right edge of shaft & highlight left
  if (h >= 20) {
    g.vline(cx + half, y(7), y(35), shade);
    g.vline(cx - half, y(7), y(33), hi);
  }
}
export function trident(h: number, col = C.red1, outline = true): Px {
  const w = Math.ceil(h * 0.75) + 4;
  const g = new Px(w, h + 3);
  tridentInto(g, Math.floor(w / 2), 1, h, col, col === C.red1 ? C.red2 : col, col === C.red1 ? C.red0 : col);
  if (outline) g.outline(C.ink);
  return g;
}

const LEAF15 = [
  '.......#.......',
  '......###......',
  '..#...###...#..',
  '..##.#####.##..',
  '...#########...',
  '#..#########..#',
  '###############',
  '.#############.',
  '..###########..',
  '....#######....',
  '...#########...',
  '..###.###.###..',
  '.......#.......',
  '.......#.......',
  '.......#.......',
];
const LEAF9 = ['....#....', '...###...', '#..###..#', '##.###.##', '.#######.', '..#####..', '.#######.', '....#....', '....#....'];
export function leafInto(g: Px, x: number, y: number, col = C.red1, size: 9 | 15 = 9, scale = 1) {
  const m = size === 15 ? LEAF15 : LEAF9;
  m.forEach((row, j) => [...row].forEach((c, i) => { if (c === '#') g.rect(x + i * scale, y + j * scale, scale, scale, col); }));
}
export function maple(size: 9 | 15 = 9, col = C.red1, scale = 1, outline = true): Px {
  const g = new Px(size * scale + 2, size * scale + 2);
  leafInto(g, 1, 1, col, size, scale);
  if (outline) g.outline(C.ink);
  return g;
}
/** Golden maple leaf collectible with a shine pixel row */
export function goldenLeaf(): Px {
  const g = new Px(17, 17);
  leafInto(g, 1, 1, C.gold1, 15);
  leafInto(g, 1, 0, C.gold1, 15);
  for (let j = 0; j < 17; j++) for (let i = 0; i < 17; i++) if (g.opaque(i, j) && i + j < 12) g.set(i, j, C.gold0);
  g.vline(8, 3, 14, C.gold2);
  g.outline(C.gold3);
  return g;
}

/** Waving Canadian flag frame (original pixel rendering). 26x14 + pole stub */
export function canadaFlag(frame: number, w = 26, h = 14): Px {
  const g = new Px(w + 2, h + 6);
  const band = Math.round(w / 4);
  const leaf = new Px(w, h);
  for (let x = 0; x < w; x++) for (let yy = 0; yy < h; yy++) leaf.set(x, yy, x < band || x >= w - band ? C.red1 : C.wht);
  leafInto(leaf, Math.round(w / 2 - 4.5), Math.round(h / 2 - 4.5), C.red1, 9);
  for (let x = 0; x < w; x++) {
    const off = Math.round(Math.sin(x / w * Math.PI * 2 + frame * Math.PI / 2) * 1.6 * (x / w));
    const shade = Math.sin(x / w * Math.PI * 2 + frame * Math.PI / 2 + 0.8) > 0.4;
    for (let yy = 0; yy < h; yy++) {
      const v = leaf.get(x, yy);
      const r = v & 255, gg = (v >> 8) & 255, b = (v >> 16) & 255;
      let c = (r << 16) | (gg << 8) | b;
      if (shade) c = c === C.wht ? C.wl1 : c === C.red1 ? C.red2 : c;
      g.set(x + 1, yy + 2 + off, c);
    }
  }
  g.outline(C.ink);
  return g;
}

/** Bunting segment (96 wide, sagging string) — red/white pennants, leaf on white */
export function bunting(): Px {
  const W = 96, g = new Px(W, 22);
  const sag = (x: number) => 2 + Math.sin((x / W) * Math.PI) * 6;
  for (let x = 0; x < W; x++) g.set(x, sag(x), C.ink2);
  for (let i = 0; i < 6; i++) {
    const px = 4 + i * 16, py = sag(px + 6);
    const red = i % 2 === 0;
    g.poly([[px, py], [px + 12, py], [px + 6, py + 12]], red ? C.red1 : C.wht);
    g.hline(px, px + 11, py, red ? C.red0 : 0xffffff);
    if (!red) { g.set(px + 6, py + 3, C.red1); g.hline(px + 5, px + 7, py + 4, C.red1); g.set(px + 6, py + 5, C.red1); }
    else { g.vline(px + 6, py + 2, py + 6, C.wht); g.set(px + 5, py + 2, C.wht); g.set(px + 7, py + 2, C.wht); }
  }
  return g;
}

/** "Certified" badge collectible: red disc, white ring, trident. 20x20 */
export function badge(d = 20): Px {
  const g = new Px(d, d), c = d / 2;
  g.circle(c, c, c - 0.5, C.red2);
  g.circle(c - 0.4, c - 0.4, c - 1.5, C.red1);
  g.ring(c, c, c - 2.5, C.wht, 1);
  tridentInto(g, Math.floor(c), Math.round(d * 0.22), Math.round(d * 0.58), C.wht, C.wl1, C.wht);
  g.set(Math.round(d * 0.25), Math.round(d * 0.3), C.red0);
  g.outline(C.ink);
  return g;
}

/** The big red TRIDENT DISPLAY stand (gameplay geometry). 76x126, pedestal included. */
export const TRIDENT_STAND = { w: 76, h: 126, pedestalH: 30 };
/** local ledge spans [x0, x1, topY] — U-bottom, left prong, right prong, centre tip */
export const TRIDENT_LEDGES: [number, number, number][] = [[26, 50, 58], [7, 23, 22], [53, 69, 22], [31, 45, 12]];
export function tridentStand(): Px {
  const { w, h } = TRIDENT_STAND;
  const g = new Px(w, h);
  // the trident sculpture (h~104) sits on a pedestal
  tridentInto(g, Math.floor(w / 2), 0, 104, C.red1, C.red2, C.red0);
  // standable ledges get a bright top edge so players read them as platforms
  for (const [x0, x1, y] of TRIDENT_LEDGES) g.hline(x0 + 1, x1 - 1, y, C.red0);
  // pedestal (30 tall): black with white band + maple leaf
  const ph = TRIDENT_STAND.pedestalH;
  g.rect(4, h - ph, w - 8, ph, C.blk1); g.rect(4, h - ph, w - 8, 2, C.blk0); g.rect(0, h - 4, w, 4, C.blk2);
  g.rect(4, h - 14, w - 8, 3, C.wht);
  leafInto(g, Math.floor(w / 2) - 4, h - ph + 5, C.red1, 9);
  tridentInto(g, 14, h - ph + 5, 12, C.wht, C.wht, C.wht); tridentInto(g, w - 15, h - ph + 5, 12, C.wht, C.wht, C.wht);
  g.outline(C.ink);
  return g;
}

/** Squashed floor decal (painted floor graphic) — leaf or trident, ~60x10 */
export function floorDecal(kind: 'leaf' | 'trident'): Px {
  const big = new Px(64, 64);
  if (kind === 'leaf') leafInto(big, 2, 2, 0xffffff, 15, 4);
  else tridentInto(big, 32, 2, 60, 0xffffff, 0xffffff, 0xffffff);
  const g = new Px(64, 12);
  for (let y = 0; y < 12; y++) for (let x = 0; x < 64; x++) {
    const sy = Math.floor((y / 12) * 64);
    if (big.opaque(x, sy)) g.set(x, y, 0xffffff);
  }
  return g;
}
/** Trident Lift — piston platform head (44x12) */
export function liftHead(): Px {
  const g = new Px(46, 14);
  g.rect(1, 1, 44, 5, C.red1); g.hline(1, 44, 1, C.red0); g.rect(1, 6, 44, 2, C.red2);
  g.rect(15, 8, 16, 5, C.st2);
  for (let x = 4; x < 44; x += 12) g.set(x, 3, C.wht);
  g.outline(C.ink);
  const t = new Px(46, 14); t.blit(g, 0, 0);
  tridentInto(t, 23, 0, 7, C.wht, C.wht, C.wht);
  return t;
}
export function pistonShaft(): Px { const g = new Px(10, 16); g.rect(1, 0, 8, 16, C.st2); g.vline(2, 0, 15, C.st0); g.vline(7, 0, 15, C.st3); g.hline(1, 8, 15, C.st3); return g; }
