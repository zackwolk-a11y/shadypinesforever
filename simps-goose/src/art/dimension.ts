/** LEVEL 2b art — the Experimental Soda Dimension. */
import { C } from './palette';
import { Px, rng } from './px';
import { tridentInto, leafInto } from './motifs';
import { bubble } from './fx';
import { pxText, pxTextWidth } from './font';

export function dimSky(): Px {
  const g = new Px(480, 270);
  g.vgrad(0, 0, 480, 270, [0x2a1450, 0x5a2a8a, 0xb04aa0, 0xff8aa8, 0xffc78a]);
  // swirling rings
  for (let k = 0; k < 7; k++) g.ring(360, 70, 18 + k * 16, [C.pur0, C.pink, C.gold0, C.blu0][k % 4], 1, 70);
  const r = rng(4);
  for (let i = 0; i < 60; i++) g.set(r() * 480, r() * 160, 0xffffff, 120 + r() * 120);
  for (let i = 0; i < 14; i++) { const x = r() * 480, y = 40 + r() * 200, d = 4 + r() * 10; g.ring(x, y, d, C.bub1, 1, 110); g.set(x - d * 0.4, y - d * 0.4, 0xffffff); }
  return g;
}
export function dimFar(): Px {
  const W = 1400, g = new Px(W, 270);
  const r = rng(17);
  for (let i = 0; i < 14; i++) {
    const x = i * 100 + r() * 40, h = 90 + r() * 110, w = 26 + r() * 20, y = 270 - h;
    const col = [0x7a4aa8, 0x9a5ab8, 0x6a3a98][i % 3];
    g.rect(x + w * 0.35, y - 16, w * 0.3, 18, col); g.rect(x + w * 0.3, y - 22, w * 0.4, 6, col);
    g.rect(x, y, w, h, col); g.rect(x + 3, y + 4, 3, h - 8, 0xb88ad8);
    if (i % 2) tridentInto(g, x + w / 2, y + 20, 22, 0x5a2a7a, 0x5a2a7a, 0x8a5ab0);
  }
  for (let i = 0; i < 8; i++) { const x = 60 + i * 170 + r() * 50, y = 120 + r() * 80; g.circle(x, y, 18 + r() * 10, 0x8a3a90); g.circle(x + 14, y - 4, 14, 0x9a4aa0); g.line(x + 6, y - 20, x + 14, y - 34, 0x5a7a4a); }
  return g;
}
export function dimMid(): Px {
  const W = 1800, g = new Px(W, 270);
  const r = rng(29);
  // cream soda clouds
  for (let i = 0; i < 16; i++) { const x = r() * W, y = 60 + r() * 120; for (let k = 0; k < 5; k++) g.ellipse(x + k * 14, y + (k % 2) * 4, 16, 9, C.crm0, 190); }
  // fizzy falls (mango-orange) from floating rocks
  for (let i = 0; i < 6; i++) {
    const x = 120 + i * 300 + r() * 60, y = 40 + r() * 40;
    g.ellipse(x, y, 34, 12, 0x6a3a7a); g.ellipse(x, y - 4, 30, 8, C.leaf1);
    for (let yy = y + 8; yy < 270; yy++) { const w = 12 + (yy - y) * 0.05; for (let xx = -w / 2; xx < w / 2; xx++) g.set(x + xx, yy, (Math.floor(yy / 3 + xx) % 5) ? C.mng1 : C.mng0, 200); }
  }
  return g;
}
export function strawberryIsland(w: number): Px {
  const h = Math.round(w * 0.55);
  const g = new Px(w, h);
  g.poly([[0, 6], [w, 6], [w * 0.62, h], [w * 0.38, h]], C.chr1);
  g.poly([[w * 0.6, 6], [w, 6], [w * 0.62, h]], C.chr2);
  const r = rng(w);
  for (let i = 0; i < w * h / 70; i++) { const x = r() * w, y = 8 + r() * (h - 10); if (g.opaque(x, y)) g.set(x, y, C.gold0); }
  for (let x = 0; x < w; x += 6) g.poly([[x, 7], [x + 6, 7], [x + 3, 12 + (x % 12 ? 0 : 3)]], C.leaf1);
  g.rect(0, 0, w, 7, C.leaf1); g.hline(0, w - 1, 0, C.leaf0); g.hline(0, w - 1, 6, C.leaf2);
  g.outline(C.ink);
  return g;
}
export function cherryIsland(): Px {
  const g = new Px(64, 44);
  g.circle(18, 28, 15, C.chr1); g.circle(46, 28, 15, C.chr1); g.circle(14, 23, 5, C.chr0); g.circle(42, 23, 5, C.chr0);
  g.rect(0, 0, 64, 7, C.chr2); g.hline(0, 63, 0, C.chr0);
  g.line(18, 13, 32, 0, C.leaf2); g.line(46, 13, 32, 0, C.leaf2);
  g.outline(C.ink);
  return g;
}
export function citrusWheel(): Px {
  const g = new Px(120, 120);
  g.circle(60, 60, 58, C.lim2); g.circle(60, 60, 54, C.lim0); g.circle(60, 60, 50, 0xfff6b0);
  for (let k = 0; k < 10; k++) { const a = k / 10 * Math.PI * 2, a2 = (k + 1) / 10 * Math.PI * 2; g.poly([[60, 60], [60 + Math.cos(a + 0.06) * 46, 60 + Math.sin(a + 0.06) * 46], [60 + Math.cos(a2 - 0.06) * 46, 60 + Math.sin(a2 - 0.06) * 46]], C.lim1); }
  g.circle(60, 60, 6, 0xfff6b0);
  g.outline(C.ink);
  return g;
}
export function citrusPad(): Px { const g = new Px(30, 8); g.rect(0, 0, 30, 6, C.lim1); g.hline(0, 29, 0, C.lim0); g.rect(0, 5, 30, 2, C.lim3); g.outline(C.ink); return g; }
export function foamPad(): Px { const g = new Px(40, 14); for (const [x, r] of [[8, 7], [20, 8], [32, 7]]) g.shadedEllipse(x, 7, r, 6, [C.crm0, C.crm0, C.crm1, C.crm2]); g.outline(C.crm3); return g; }
export function rainbowTile(): Px {
  const g = new Px(32, 9);
  const cols = [C.red1, C.mng1, C.gold1, C.lim1, C.blu1, C.pur1];
  cols.forEach((c, i) => g.hline(0, 31, i + 1, c));
  g.hline(0, 31, 0, 0xffffff); g.hline(0, 31, 7, C.pur2);
  for (let x = 2; x < 32; x += 8) g.ring(x + 2, 4, 1, 0xffffff);
  g.hline(0, 31, 8, C.ink);
  return g;
}
export function geyserBase(): Px { const g = new Px(30, 12); g.ellipse(15, 8, 14, 5, C.pur2); g.ellipse(15, 6, 10, 3, C.blu0); g.outline(C.ink); return g; }
export function geyserCol(): Px { const g = new Px(16, 16); for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { const d = Math.abs(x - 7.5); if (d < 7) g.set(x, y, (x + y * 2) % 7 < 2 ? 0xffffff : d > 5 ? C.bub2 : C.bub1, 220); } return g; }
export function syrupRiver(): Px { const g = new Px(32, 16); g.rect(0, 0, 32, 16, C.pur1); g.rect(0, 0, 32, 3, C.pur0); for (let x = 0; x < 32; x += 8) { g.hline(x, x + 4, 6, C.pur0); g.hline(x + 4, x + 7, 11, C.pur2); } g.hline(0, 31, 15, C.pur2); return g; }
export function portalBottle(): Px {
  const g = new Px(72, 120);
  g.rect(26, 0, 20, 10, C.red1); g.rect(28, 10, 16, 18, C.gl1, 200);
  g.poly([[28, 28], [44, 28], [70, 50], [2, 50]], C.gl1, 200);
  g.rect(2, 50, 68, 70, C.gl1, 200);
  for (let y = 54; y < 118; y++) g.hline(4, 68, y, [C.red1, C.mng1, C.gold1, C.lim1, C.blu1, C.pur1][Math.floor((y - 54) / 11)], );
  g.rect(14, 64, 44, 30, C.wht); tridentInto(g, 36, 66, 26, C.red1, C.red2, C.red0);
  g.rect(5, 52, 3, 64, 0xffffff, 170);
  g.outline(C.ink);
  return g;
}
export function dimTap(): Px {
  const g = new Px(30, 40);
  g.rect(10, 6, 10, 30, C.st2); g.rect(4, 0, 22, 8, C.red1); tridentInto(g, 15, 0, 7, C.wht, C.wht, C.wht);
  g.rect(2, 12, 8, 4, C.st1); g.rect(20, 12, 8, 4, C.st1); g.rect(2, 16, 3, 4, C.st3); g.rect(25, 16, 3, 4, C.st3);
  g.rect(4, 34, 22, 6, C.blk1); leafInto(g, 11, 26, C.red1, 9);
  g.outline(C.ink);
  return g;
}
export function signPost(t: string): Px {
  const w = pxTextWidth(t) + 10; const g = new Px(w, 30);
  g.rect(w / 2 - 1, 12, 3, 18, C.wd2); g.rect(0, 0, w, 13, C.wd1); g.rect(1, 1, w - 2, 11, C.wd0); pxText(g, 5, 3, t, C.wd3);
  g.outline(C.ink); return g;
}
export { bubble };
