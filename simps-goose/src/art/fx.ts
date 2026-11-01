/** Effects, collectibles, icons and UI pieces. All return Px buffers. */
import { C, R, type Ramp } from './palette';
import { Px } from './px';
import { pxText } from './font';

/** Soap/soda bubble with rim light, highlight crescent and faint rainbow sheen. */
export function bubble(d: number, opts: { tint?: number; strained?: boolean } = {}): Px {
  const g = new Px(d, d);
  const r = d / 2 - 0.5, c = d / 2;
  const tint = opts.tint ?? C.bub1;
  for (let y = 0; y < d; y++) for (let x = 0; x < d; x++) {
    const dx = x + 0.5 - c, dy = y + 0.5 - c, dd = Math.hypot(dx, dy) / r;
    if (dd > 1) continue;
    if (dd > 0.86) {
      // rim — brighter top-left, sheen colours along the lower right
      const ang = Math.atan2(dy, dx);
      let col = C.bub2;
      if (ang > 0.2 && ang < 1.0) col = C.pink; else if (ang > 1.0 && ang < 1.7) col = C.gold0; else if (ang < -1.6 && ang > -2.6) col = C.wht;
      g.set(x, y, col, 230);
    } else if (dd > 0.7) g.set(x, y, tint, 90);
    else g.set(x, y, tint, 38);
  }
  // highlight crescent
  const hr = r * 0.62;
  for (let a = -2.7; a < -1.5; a += 0.05) {
    g.set(c + Math.cos(a) * hr, c + Math.sin(a) * hr, C.wht, 255);
    if (d >= 24) g.set(c + Math.cos(a) * (hr - 1), c + Math.sin(a) * (hr - 1), C.wht, 160);
  }
  g.rect(Math.round(c - r * 0.42), Math.round(c - r * 0.5), Math.max(1, Math.round(d / 16)), Math.max(1, Math.round(d / 16)), C.wht);
  g.set(Math.round(c + r * 0.45), Math.round(c + r * 0.45), C.wht, 200);
  if (opts.strained) for (let k = 0; k < 3; k++) g.line(c + 1 + k * 2, c - r + 2 + k, c + 3 + k, c - r + 5 + k * 2, C.wht, 200);
  return g;
}

/** Stepped (pixel-art) radial glow, white — tinted + ADD-blended in engine. */
export function glow(d: number, bands = 5): Px {
  const g = new Px(d, d), c = d / 2;
  for (let y = 0; y < d; y++) for (let x = 0; x < d; x++) {
    const t = Math.hypot(x + 0.5 - c, y + 0.5 - c) / c;
    if (t > 1) continue;
    const step = Math.floor((1 - t) * bands) / bands;
    g.set(x, y, 0xffffff, Math.round(step * step * 255));
  }
  return g;
}

/** Light shaft (soft-edged trapezoid) for window light. */
export function shaft(w: number, h: number): Px {
  const g = new Px(w, h);
  for (let y = 0; y < h; y++) {
    const off = (y / h) * w * 0.45;
    for (let x = 0; x < w; x++) {
      const xx = x - off;
      const edge = Math.min(xx, w * 0.55 - xx) / 6;
      if (edge <= 0) continue;
      const a = Math.min(1, edge) * (1 - y / h) * 90;
      if (Px.bayer(x, y) * 90 < a) g.set(x, y, 0xffffff, Math.round(a));
    }
  }
  return g;
}

export function dot(d: number, col = 0xffffff): Px { const g = new Px(d, d); g.circle(d / 2, d / 2, d / 2, col); return g; }
export function square(d: number, col = 0xffffff): Px { const g = new Px(d, d); g.rect(0, 0, d, d, col); return g; }

export function droplet(): Px { // syrup drop collectible (tinted in engine) 9x12
  const g = new Px(9, 12);
  g.poly([[4.5, 0], [8, 6], [1, 6]], 0xffffff);
  g.circle(4.5, 7.5, 3.6, 0xffffff);
  g.outline(C.ink);
  return g;
}
export function dropletShade(): Px { // overlay: shade + highlight for droplet (not tinted)
  const g = new Px(9, 12);
  g.set(3, 6, 0xffffff); g.set(3, 7, 0xffffff); g.set(4, 4, 0xffffff);
  g.set(6, 9, C.ink3, 140); g.set(5, 10, C.ink3, 140); g.set(7, 8, C.ink3, 140);
  return g;
}

export function star(): Px { const g = new Px(9, 9); g.poly([[4.5, 0], [6, 3.5], [9, 4], [6.5, 6], [7.5, 9], [4.5, 7.2], [1.5, 9], [2.5, 6], [0, 4], [3, 3.5]], C.gold1); g.set(4, 3, C.gold0); g.set(4, 4, C.gold0); g.outline(C.ink); return g; }
export function sparkle(): Px { const g = new Px(7, 7); g.vline(3, 0, 6, 0xffffff); g.hline(0, 6, 3, 0xffffff); g.set(3, 3, C.gold0); return g; }
export function heart(): Px { const g = new Px(9, 8); g.circle(2.5, 2.5, 2.5, C.red1); g.circle(6.5, 2.5, 2.5, C.red1); g.poly([[0.3, 3.2], [8.7, 3.2], [4.5, 7.6]], C.red1); g.set(2, 1, C.red0); g.set(2, 2, C.wht); g.outline(C.ink); return g; }
export function puff(d: number): Px { const g = new Px(d, d); g.shadedEllipse(d / 2, d / 2, d / 2 - 1, d / 2 - 1, [0xffffff, 0xf2eef5, 0xd8d4e2, 0xc0bcd0]); return g; }

/** Honk sound-wave arc ")" */
export function honkArc(): Px {
  const g = new Px(14, 28);
  for (let a = -1.05; a <= 1.05; a += 0.02) {
    const x = Math.cos(a) * 11, y = 14 + Math.sin(a) * 12;
    g.rect(x, y, 2, 1, 0xffffff);
  }
  g.outline(C.ink);
  return g;
}

/** Speech balloon (content text is overlaid at runtime). */
export function balloon(w: number, h: number): Px {
  const g = new Px(w, h + 5);
  g.rect(2, 0, w - 4, h, C.wht); g.rect(0, 2, w, h - 4, C.wht); g.rect(1, 1, w - 2, h - 2, C.wht);
  g.poly([[w / 2 - 3, h - 1], [w / 2 + 2, h - 1], [w / 2 - 2, h + 4]], C.wht);
  g.hline(2, w - 3, h - 1, C.wl1);
  g.outline(C.ink);
  return g;
}

/** Cream-soda foam cloud platform 44x18 */
export function foamCloud(): Px {
  const g = new Px(48, 20);
  const blobs = [[10, 11, 7], [20, 8, 8], [31, 9, 8], [39, 12, 6], [24, 13, 9], [14, 13, 7], [34, 13, 7]];
  for (const [x, y, r] of blobs) g.shadedEllipse(x + 1, y + 1, r, r * 0.8, [C.crm0, C.crm0, C.crm1, C.crm2]);
  for (const [x, y, r] of blobs) g.set(x - r * 0.4, y - r * 0.3, 0xffffff);
  g.ring(17, 9, 1.6, C.crm2); g.ring(30, 7, 1.2, C.crm2); g.ring(37, 13, 1.4, C.crm2);
  g.outline(C.crm3);
  return g;
}

/** Cherry-blast projectile: a pink bubble with a cherry pair inside. */
export function cherryBubble(): Px {
  const g = bubble(14, { tint: C.chr0 });
  const c = new Px(14, 14);
  c.circle(5, 9, 2.4, C.chr1); c.circle(9, 9.5, 2.4, C.chr1); c.set(4, 8, C.chr0); c.set(8, 8, C.chr0);
  c.line(5, 7, 8, 3, C.leaf2); c.line(9, 7, 8, 3, C.leaf2); c.set(9, 3, C.leaf1);
  g.blit(c, 0, 0);
  return g;
}

/** Flavor HUD icons 16x16 */
export function flavorIcon(kind: 'cola' | 'cream' | 'cherry' | 'none'): Px {
  const g = new Px(16, 16);
  if (kind === 'cola') {
    bottleInto(g, 4, 0, R.cola, 8, 16);
    g.set(1, 3, C.wht); g.set(13, 2, C.wht); g.set(14, 6, C.bub2); g.set(1, 8, C.bub2);
  } else if (kind === 'cream') {
    for (const [x, y, r] of [[5, 9, 4], [10, 8, 5], [8, 11, 4], [12, 11, 3]]) g.shadedEllipse(x, y, r, r * 0.85, [C.crm0, C.crm0, C.crm1, C.crm2]);
    g.outline(C.ink);
    g.set(9, 5, C.wht);
  } else if (kind === 'cherry') {
    g.circle(5, 11, 3.5, C.chr1); g.circle(11, 11.5, 3.5, C.chr1); g.set(4, 9, C.chr0); g.set(10, 10, C.chr0); g.set(4, 10, C.wht);
    g.line(5, 8, 9, 2, C.leaf2); g.line(11, 8, 9, 2, C.leaf2); g.poly([[9, 2], [14, 1], [12, 4]], C.leaf1);
    g.outline(C.ink);
  } else {
    g.ring(8, 8, 6, C.st2, 1);
  }
  return g;
}

/** Simps-inspired bottle (original art). w ~7..12, h ~16..32 */
export function bottleInto(g: Px, x: number, y: number, ramp: Ramp, w = 7, h = 18, opts: { cap?: number; label?: boolean; fill?: number } = {}) {
  const neckW = Math.max(3, Math.round(w * 0.4));
  const nx = x + Math.floor((w - neckW) / 2);
  const capH = Math.max(2, Math.round(h * 0.1));
  const neckH = Math.round(h * 0.18);
  const shH = Math.round(h * 0.1);
  const bodyY = y + capH + neckH + shH;
  const bodyH = h - (bodyY - y);
  // cap
  g.rect(nx - 0, y, neckW, capH, opts.cap ?? C.blk1);
  g.hline(nx, nx + neckW - 1, y, C.blk0);
  // neck glass
  g.rect(nx, y + capH, neckW, neckH, C.gl1, 200);
  // shoulder
  g.poly([[nx, y + capH + neckH], [nx + neckW, y + capH + neckH], [x + w, bodyY], [x, bodyY]], ramp[1]);
  // body liquid
  const fill = opts.fill ?? 1;
  g.rect(x, bodyY, w, bodyH, ramp[1]);
  g.rect(x + w - 2, bodyY, 2, bodyH, ramp[2]);
  g.vline(x + w - 1, bodyY, bodyY + bodyH - 1, ramp[3]);
  if (fill < 1) g.rect(x, bodyY, w, Math.round(bodyH * (1 - fill)), C.gl1, 160);
  // label (black/white with red mark — original design)
  if (opts.label !== false && bodyH > 6) {
    const ly = bodyY + Math.round(bodyH * 0.25), lh = Math.max(3, Math.round(bodyH * 0.45));
    g.rect(x, ly, w, lh, C.wht);
    g.rect(x, ly, w, 1, C.blk1);
    g.rect(x, ly + lh - 1, w, 1, C.blk1);
    g.rect(x + Math.floor(w / 2) - 1, ly + 1 + Math.floor((lh - 2) / 2) - 1, 2, Math.max(1, Math.min(2, lh - 2)), C.red1);
    if (w >= 9) g.hline(x + 2, x + w - 3, ly + lh - 2, ramp[1]);
    g.vline(x + w - 1, ly, ly + lh - 1, C.wl2);
  }
  // glass highlight stripe
  g.vline(x + 1, y + capH + 1, bodyY + bodyH - 2, 0xffffff, );
  g.vline(nx + 1, y + capH, y + capH + neckH, 0xffffff);
}
export function bottle(ramp: Ramp, w = 7, h = 18, opts: { cap?: number; label?: boolean; fill?: number } = {}): Px {
  const g = new Px(w + 2, h + 2);
  bottleInto(g, 1, 1, ramp, w, h, opts);
  g.outline(C.ink);
  return g;
}

/** Golden bottle (rare collectible) 12x22 */
export function goldenBottle(): Px {
  const g = new Px(14, 24);
  bottleInto(g, 2, 1, R.gold, 9, 21, { cap: C.red1 });
  g.outline(C.ink);
  return g;
}

/** Keycap prompt 13x13 with glyph */
export function keycap(label: string): Px {
  const w = Math.max(13, label.length * 6 + 5);
  const g = new Px(w, 14);
  g.rect(1, 1, w - 2, 12, C.st3); g.rect(1, 1, w - 2, 10, C.wht); g.rect(2, 2, w - 4, 8, C.wl0);
  g.outline(C.ink);
  pxText(g, Math.round((w - (label.length * 6 - 1)) / 2), 2, label, C.ink);
  return g;
}

/** Splat decal on the floor (tinted) */
export function splat(): Px {
  const g = new Px(20, 6);
  g.ellipse(10, 3, 8, 2.2, 0xffffff); g.ellipse(4, 3.5, 2, 1.2, 0xffffff); g.ellipse(17, 2.5, 1.6, 1.2, 0xffffff);
  g.set(1, 3, 0xffffff); g.set(19, 4, 0xffffff);
  return g;
}

/** Soft ground shadow ellipse */
export function shadowBlob(w: number): Px {
  const h = Math.max(3, Math.round(w / 4));
  const g = new Px(w, h);
  g.ellipse(w / 2, h / 2, w / 2, h / 2, C.ink, 110);
  g.ellipse(w / 2, h / 2, w / 2 - 2, h / 2 - 0.8, C.ink, 70);
  return g;
}
