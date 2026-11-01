/** LEVEL 3b/3c art — the Kelowna waterfront on Okanagan Lake, Ogopogo, the sunset finale. */
import { C, R } from './palette';
import { Px, rng } from './px';
import { tridentInto, leafInto } from './motifs';
import { pxText } from './font';

export const WF = { W: 1600, H: 270, FLOOR: 230, WATER: 238 };
export function wfSky(sunset = false): Px {
  const g = new Px(480, 270);
  g.vgrad(0, 0, 480, 200, sunset ? [0x3a2a6a, 0x8a3a7a, 0xe0607a, 0xffa060, 0xffd890] : [C.sky3, C.sky2, 0xcfeaf6, C.sky0]);
  const r = rng(sunset ? 5 : 6);
  for (let i = 0; i < 7; i++) { const x = r() * 480, y = 20 + r() * 80, s = 10 + r() * 16; for (let k = 0; k < 4; k++) g.ellipse(x + k * s * 0.7, y + (k % 2) * 3, s, s * 0.4, sunset ? 0xffb0a0 : 0xffffff, 150); }
  if (sunset) { g.circle(330, 150, 26, 0xffe8a0); g.circle(330, 150, 34, 0xffe0a0, 70); }
  else g.circle(400, 50, 14, 0xfff6d8);
  return g;
}
export function wfHills(sunset = false): Px {
  const W = 900, g = new Px(W, 270);
  const ridge = (base: number, amp: number, col: number, seed: number) => { const r = rng(seed); const p = [r() * 6, r() * 6]; for (let x = 0; x < W; x++) { const t = base - amp * (0.55 + 0.3 * Math.sin(x / 110 + p[0]) + 0.15 * Math.sin(x / 41 + p[1])); g.vline(x, t, 200, col); } };
  ridge(160, 80, sunset ? 0x6a4a8a : C.mt0, 2); ridge(176, 56, sunset ? 0x4a3a6a : C.mt1, 3);
  // far shore skyline (generic downtown silhouettes)
  const r = rng(9);
  for (let x = 300; x < 620; x += 10 + r() * 14) { const h = 10 + r() * 30; g.rect(x, 190 - h, 8 + r() * 8, h, sunset ? 0x3a2a5a : C.mt2); for (let wy = 190 - h + 3; wy < 188; wy += 4) if (r() > 0.5) g.set(x + 3, wy, sunset ? C.gold1 : C.mt0); }
  g.rect(0, 188, W, 4, sunset ? 0x4a3a6a : C.hill2);
  return g;
}
export function wfLake(sunset = false): Px {
  const g = new Px(480, 80);
  g.vgrad(0, 0, 480, 80, sunset ? [0x8a4a8a, 0x5a3a7a, 0x2a2a5a] : [C.blu0, C.blu1, C.blu2]);
  const r = rng(13);
  for (let i = 0; i < 140; i++) { const x = r() * 480, y = r() * 80, w = 3 + r() * 10; g.hline(x, x + w, y, sunset ? (r() > 0.5 ? 0xffc080 : 0xd080a0) : 0xffffff, ); }
  if (sunset) for (let y = 0; y < 80; y += 3) g.hline(320 - 20 + Math.sin(y) * 4, 340 + 20 - y / 6, y, 0xffe0a0);
  return g;
}
export function wfTrees(): Px {
  const W = 1200, g = new Px(W, 270), r = rng(21);
  for (let i = 0; i < 18; i++) {
    const x = i * 66 + r() * 30, h = 70 + r() * 50, y = 236;
    g.rect(x - 3, y - h * 0.5, 6, h * 0.5, C.wd3);
    for (let k = 0; k < 6; k++) g.shadedEllipse(x + (r() - 0.5) * 30, y - h * 0.62 - r() * h * 0.38, 14 + r() * 8, 11 + r() * 5, R.leaf);
  }
  return g;
}
export function path(): Px { const g = new Px(32, 40); g.rect(0, 0, 32, 6, C.hill1); g.hline(0, 31, 0, C.hill0); g.rect(0, 6, 32, 34, C.side1); for (let x = 0; x < 32; x += 8) g.vline(x, 6, 39, C.side2); g.rect(0, 6, 32, 2, C.side0); return g; }
export function bench(): Px { const g = new Px(44, 26); g.rect(2, 8, 40, 4, C.wd1); g.rect(2, 0, 40, 4, C.wd1); g.rect(2, 14, 40, 3, C.wd2); g.rect(4, 4, 3, 22, C.blk1); g.rect(37, 4, 3, 22, C.blk1); leafInto(g, 18, 0, C.red1, 9); g.outline(C.ink); return g; }
export function picnic(): Px { const g = new Px(56, 26); g.rect(0, 0, 56, 5, C.wd1); for (let x = 0; x < 56; x += 8) g.vline(x, 0, 4, C.wd3); g.line(10, 5, 4, 25, C.wd2); g.line(46, 5, 52, 25, C.wd2); g.rect(0, 14, 56, 3, C.wd2); g.rect(18, -0, 10, 0, C.red1); g.outline(C.ink); return g; }
export function flowers(): Px { const g = new Px(48, 14), r = rng(3); for (let i = 0; i < 12; i++) { const x = 2 + r() * 44, y = 4 + r() * 6; g.vline(x, y, 13, C.leaf2); g.circle(x, y, 1.6, [C.red0, C.gold1, C.pink, C.wht][i % 4]); } return g; }
export function dock(w: number): Px { const g = new Px(w, 30); g.rect(0, 0, w, 6, C.wd1); for (let x = 0; x < w; x += 10) g.vline(x, 0, 5, C.wd3); g.hline(0, w - 1, 0, C.wd0); for (let x = 6; x < w; x += 40) g.rect(x, 6, 6, 24, C.wd3); g.outline(C.ink); return g; }
export function sailboat(): Px { const g = new Px(48, 52); g.poly([[4, 40], [44, 40], [38, 50], [10, 50]], C.wht); g.rect(4, 40, 40, 2, C.red1); g.vline(24, 4, 40, C.wd3); g.poly([[25, 6], [25, 38], [44, 38]], C.wht); g.poly([[23, 10], [23, 38], [8, 38]], C.red0); leafInto(g, 12, 26, C.wht, 9); g.outline(C.ink); return g; }
export function flagPole(): Px { const g = new Px(8, 90); g.rect(3, 0, 2, 90, C.st1); g.circle(4, 1, 2, C.gold1); g.outline(C.ink); return g; }
export function bike(): Px { const g = new Px(30, 18); g.ring(7, 11, 6, C.ink2, 2); g.ring(23, 11, 6, C.ink2, 2); g.line(7, 11, 14, 4, C.red1); g.line(14, 4, 23, 11, C.red1); g.line(14, 4, 14, 11, C.red1); g.line(7, 11, 14, 11, C.red1); g.line(20, 2, 23, 11, C.st2); return g; }
export function ripple(): Px { const g = new Px(40, 10); g.ellipse(20, 5, 19, 4.5, 0xffffff, 200); g.ellipse(20, 5, 16, 3, 0xffffff, 0); for (let y = 0; y < 10; y++) for (let x = 0; x < 40; x++) { const d = ((x - 20) / 19) ** 2 + ((y - 5) / 4.5) ** 2; if (d < 0.6) g.clear(x, y); } return g; }
export function wave(): Px { const g = new Px(40, 26); g.poly([[0, 26], [8, 10], [18, 2], [30, 4], [36, 12], [28, 10], [24, 16], [40, 26]], C.blu1); g.poly([[8, 10], [18, 2], [30, 4], [36, 12], [28, 10], [20, 8]], C.blu0); for (let x = 16; x < 34; x += 4) g.set(x, 4, 0xffffff); g.outline(C.ink); return g; }
export function splash(): Px { const g = new Px(36, 26); for (const [x, h] of [[6, 14], [12, 22], [18, 26], [24, 20], [30, 12]]) { g.rect(x - 2, 26 - h, 4, h, C.blu0); g.circle(x, 26 - h, 2.5, 0xffffff); } g.outline(C.blu3); return g; }

// --------------------------------------------------------------- OGOPOGO (original cartoon)
const OG: [number, number, number, number] = [0x9ff0c0, 0x3fbf7f, 0x23866a, 0x14504a];
const BELLY = [0xf0ffd0, 0xc8f0a0, 0x9ad08a, 0x5a9a6a] as [number, number, number, number];
export type OgFace = 'normal' | 'roar' | 'hurt' | 'dizzy' | 'sad' | 'happy' | 'drink' | 'burp' | 'surprised';
export function ogHead(face: OgFace): Px {
  const g = new Px(64, 52);
  // snout + head
  g.shadedEllipse(26, 26, 22, 20, OG);
  g.shadedEllipse(46, 32, 16, 11, OG, 0.1);
  // fins / frills
  g.poly([[10, 12], [2, 0], [18, 8]], C.blu1); g.poly([[18, 6], [16, -0], [26, 6]], C.blu1);
  g.poly([[6, 30], [0, 40], [12, 36]], C.blu1);
  // belly jaw
  g.shadedEllipse(40, 40, 18, 6, BELLY);
  const open = face === 'roar' || face === 'surprised' || face === 'happy' || face === 'burp';
  if (open) { g.poly([[30, 36], [62, 34], [58, 48], [34, 46]], C.red3); g.poly([[34, 44], [56, 44], [52, 47], [38, 47]], C.chr0); for (let x = 36; x < 60; x += 5) { g.poly([[x, 36], [x + 2, 36], [x + 1, 39]], C.wht); } }
  else if (face === 'sad') g.line(36, 42, 56, 40, OG[3]);
  else g.line(34, 40, 58, 38, OG[3]);
  if (face === 'drink') { g.rect(56, 34, 8, 10, C.wht); g.rect(56, 37, 8, 2, C.red1); }
  // nostrils
  g.set(56, 27, OG[3]); g.set(59, 28, OG[3]);
  g.outline(C.ink);
  // eyes (big + expressive)
  const ex = 28, ey = 18;
  if (face === 'hurt') { g.line(ex - 5, ey - 4, ex + 5, ey + 4, C.ink); g.line(ex - 5, ey + 4, ex + 5, ey - 4, C.ink); }
  else if (face === 'dizzy') { g.ring(ex, ey, 6, C.ink); g.ring(ex, ey, 3, C.ink); }
  else if (face === 'happy' || face === 'burp') { for (let k = -5; k <= 5; k++) g.set(ex + k, ey + Math.abs(k) * 0.6 - 2, C.ink); }
  else {
    const big = face === 'surprised' ? 8 : 7;
    g.circle(ex, ey, big, C.wht); g.ring(ex, ey, big, C.ink);
    const pd = face === 'sad' ? 2 : 0;
    g.circle(ex + 2, ey + pd, face === 'surprised' ? 2.5 : 3.5, C.ink); g.set(ex + 1, ey - 1 + pd, C.wht);
    if (face === 'roar') g.line(ex - 7, ey - 9, ex + 6, ey - 5, C.ink);
    if (face === 'sad') { g.line(ex - 6, ey - 7, ex + 6, ey - 10, C.ink); g.set(ex - 6, ey + 8, C.blu0); g.set(ex - 6, ey + 9, C.blu0); }
  }
  if (face === 'burp') { g.ring(58, 22, 3, C.bub2); g.ring(62, 14, 2, C.bub2); }
  return g;
}
export function ogNeck(): Px { const g = new Px(22, 22); g.shadedEllipse(11, 11, 10, 10, OG); g.shadedEllipse(14, 13, 5, 6, BELLY); g.outline(C.ink); return g; }
export function ogHump(): Px { const g = new Px(50, 26); g.shadedEllipse(25, 26, 23, 22, OG); g.poly([[18, 6], [22, -0], [28, 5]], C.blu1); g.poly([[30, 7], [34, 2], [38, 9]], C.blu1); for (let x = 10; x < 42; x += 6) g.set(x, 16 + (x % 4), OG[0]); g.outline(C.ink); for (let x = 0; x < 50; x++) for (let y = 24; y < 26; y++) g.clear(x, y); return g; }
export function ogTail(): Px { const g = new Px(40, 30); g.shadedEllipse(14, 24, 12, 8, OG); g.poly([[20, 20], [38, 0], [32, 18]], OG[1]); g.poly([[30, 6], [40, 2], [36, 14]], C.blu1); g.outline(C.ink); return g; }
export function panorama(): Px {
  const g = new Px(480, 270);
  g.blit(wfSky(true), 0, 0);
  const hills = wfHills(true); for (let y = 0; y < 270; y++) for (let x = 0; x < 480; x++) { const v = hills.d[y * 900 + x + 200]; if (v >>> 24) g.d[y * 480 + x] = v; }
  g.blit(wfLake(true), 0, 192);
  // Kelowna waterfront silhouettes + Ogopogo humps
  for (let x = 0; x < 140; x += 14) g.rect(x, 186 - (x % 28) - 8, 12, 14 + (x % 28), 0x2a1a3a);
  g.rect(0, 222, 480, 48, 0x1a1a3a, 0); 
  tridentInto(g, 240, 20, 30, C.red1, C.red2, C.red0);
  pxText(g, 4, 260, '', C.wht);
  return g;
}
