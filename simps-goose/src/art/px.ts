/**
 * Px — a tiny software rasteriser used to author all pixel art in code.
 * Everything is drawn into an RGBA buffer at native (1:1) resolution, then pushed to
 * a canvas and registered as a Phaser texture. No anti-aliasing ever happens here.
 */
import type { Ramp } from './palette';

const BAYER4 = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5].map((v) => (v + 0.5) / 16);

export function rgba(c: number, a = 255) {
  return ((a & 255) << 24) | ((c & 0xff) << 16) | (c & 0xff00) | ((c >> 16) & 0xff);
}

export class Px {
  w: number;
  h: number;
  d: Uint32Array;
  constructor(w: number, h: number) {
    this.w = w;
    this.h = h;
    this.d = new Uint32Array(w * h);
  }
  static bayer(x: number, y: number) {
    return BAYER4[(y & 3) * 4 + (x & 3)];
  }
  inb(x: number, y: number) {
    return x >= 0 && y >= 0 && x < this.w && y < this.h;
  }
  get(x: number, y: number) {
    x |= 0; y |= 0;
    return this.inb(x, y) ? this.d[y * this.w + x] : 0;
  }
  opaque(x: number, y: number) {
    return (this.get(x, y) >>> 24) > 0;
  }
  set(x: number, y: number, c: number, a = 255) {
    x = Math.floor(x); y = Math.floor(y);
    if (!this.inb(x, y)) return;
    if (a >= 255) { this.d[y * this.w + x] = rgba(c, 255); return; }
    // alpha blend over existing
    const i = y * this.w + x;
    const o = this.d[i];
    const oa = (o >>> 24) / 255, na = a / 255;
    const outA = na + oa * (1 - na);
    if (outA <= 0) return;
    const or = o & 255, og = (o >> 8) & 255, ob = (o >> 16) & 255;
    const nr = (c >> 16) & 255, ng = (c >> 8) & 255, nb = c & 255;
    const r = (nr * na + or * oa * (1 - na)) / outA;
    const g = (ng * na + og * oa * (1 - na)) / outA;
    const b = (nb * na + ob * oa * (1 - na)) / outA;
    this.d[i] = ((Math.round(outA * 255) & 255) << 24) | ((Math.round(b) & 255) << 16) | ((Math.round(g) & 255) << 8) | (Math.round(r) & 255);
  }
  clear(x: number, y: number) {
    if (this.inb(x | 0, y | 0)) this.d[(y | 0) * this.w + (x | 0)] = 0;
  }
  rect(x: number, y: number, w: number, h: number, c: number, a = 255) {
    for (let j = Math.floor(y); j < Math.floor(y + h); j++) for (let i = Math.floor(x); i < Math.floor(x + w); i++) this.set(i, j, c, a);
  }
  hline(x0: number, x1: number, y: number, c: number) {
    for (let x = Math.floor(Math.min(x0, x1)); x <= Math.floor(Math.max(x0, x1)); x++) this.set(x, y, c);
  }
  vline(x: number, y0: number, y1: number, c: number) {
    for (let y = Math.floor(Math.min(y0, y1)); y <= Math.floor(Math.max(y0, y1)); y++) this.set(x, y, c);
  }
  line(x0: number, y0: number, x1: number, y1: number, c: number, a = 255) {
    x0 = Math.round(x0); y0 = Math.round(y0); x1 = Math.round(x1); y1 = Math.round(y1);
    const dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0);
    const sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
    let err = dx + dy;
    for (;;) {
      this.set(x0, y0, c, a);
      if (x0 === x1 && y0 === y1) break;
      const e2 = 2 * err;
      if (e2 >= dy) { err += dy; x0 += sx; }
      if (e2 <= dx) { err += dx; y0 += sy; }
    }
  }
  /** Generic shape fill: f returns colour (or -1 to skip) for every pixel in the box. */
  fill(x0: number, y0: number, x1: number, y1: number, f: (x: number, y: number) => number) {
    for (let y = Math.floor(y0); y <= Math.ceil(y1); y++)
      for (let x = Math.floor(x0); x <= Math.ceil(x1); x++) {
        const c = f(x, y);
        if (c >= 0) this.set(x, y, c);
      }
  }
  ellipse(cx: number, cy: number, rx: number, ry: number, c: number, a = 255) {
    for (let y = Math.floor(cy - ry); y <= Math.ceil(cy + ry); y++)
      for (let x = Math.floor(cx - rx); x <= Math.ceil(cx + rx); x++) {
        const nx = (x + 0.5 - cx) / rx, ny = (y + 0.5 - cy) / ry;
        if (nx * nx + ny * ny <= 1) this.set(x, y, c, a);
      }
  }
  circle(cx: number, cy: number, r: number, c: number, a = 255) {
    this.ellipse(cx, cy, r, r, c, a);
  }
  ring(cx: number, cy: number, r: number, c: number, thick = 1, a = 255) {
    for (let y = Math.floor(cy - r - 1); y <= Math.ceil(cy + r + 1); y++)
      for (let x = Math.floor(cx - r - 1); x <= Math.ceil(cx + r + 1); x++) {
        const d = Math.hypot(x + 0.5 - cx, y + 0.5 - cy);
        if (d <= r && d > r - thick) this.set(x, y, c, a);
      }
  }
  /**
   * Shaded (optionally rotated) ellipse lit from the top-left. Ramp = [hi, base, shade, deep].
   * Light direction and thresholds are fixed by the art bible so every object agrees.
   */
  shadedEllipse(cx: number, cy: number, rx: number, ry: number, ramp: Ramp, rot = 0, opts: { dither?: boolean; light?: number } = {}) {
    const cos = Math.cos(-rot), sin = Math.sin(-rot);
    const R = Math.max(rx, ry) + 1;
    const lb = opts.light ?? 0;
    for (let y = Math.floor(cy - R); y <= Math.ceil(cy + R); y++)
      for (let x = Math.floor(cx - R); x <= Math.ceil(cx + R); x++) {
        const px = x + 0.5 - cx, py = y + 0.5 - cy;
        const lx = (px * cos - py * sin) / rx, ly = (px * sin + py * cos) / ry;
        const d = lx * lx + ly * ly;
        if (d > 1) continue;
        // world-space normal approx for lighting
        const nx = px / Math.max(rx, ry), ny = py / Math.max(rx, ry);
        let l = -(nx * 0.55 + ny * 0.85) + 0.15 + lb; // -1..1
        if (d > 0.72) l -= 0.25; // rim darkening
        const t = opts.dither === false ? 0 : (Px.bayer(x, y) - 0.5) * 0.18;
        l += t;
        const c = l > 0.55 ? ramp[0] : l > -0.1 ? ramp[1] : l > -0.6 ? ramp[2] : ramp[3];
        this.set(x, y, c);
      }
  }
  /** Fill polygon (even-odd scanline). */
  poly(pts: number[][], c: number, a = 255) {
    let minY = Infinity, maxY = -Infinity;
    for (const p of pts) { minY = Math.min(minY, p[1]); maxY = Math.max(maxY, p[1]); }
    for (let y = Math.floor(minY); y <= Math.ceil(maxY); y++) {
      const yy = y + 0.5;
      const xs: number[] = [];
      for (let i = 0; i < pts.length; i++) {
        const a1 = pts[i], b1 = pts[(i + 1) % pts.length];
        if ((a1[1] <= yy && b1[1] > yy) || (b1[1] <= yy && a1[1] > yy)) {
          xs.push(a1[0] + ((yy - a1[1]) / (b1[1] - a1[1])) * (b1[0] - a1[0]));
        }
      }
      xs.sort((p, q) => p - q);
      for (let k = 0; k + 1 < xs.length; k += 2)
        for (let x = Math.round(xs[k]); x < Math.round(xs[k + 1]); x++) this.set(x, y, c, a);
    }
  }
  /** 1px outline around all opaque pixels (outside only). diag=true includes diagonals. */
  outline(c: number, diag = false) {
    const add: number[] = [];
    for (let y = 0; y < this.h; y++)
      for (let x = 0; x < this.w; x++) {
        if (this.opaque(x, y)) continue;
        if (this.opaque(x + 1, y) || this.opaque(x - 1, y) || this.opaque(x, y + 1) || this.opaque(x, y - 1) ||
          (diag && (this.opaque(x + 1, y + 1) || this.opaque(x - 1, y - 1) || this.opaque(x - 1, y + 1) || this.opaque(x + 1, y - 1)))) add.push(x, y);
      }
    for (let i = 0; i < add.length; i += 2) this.set(add[i], add[i + 1], c);
  }
  /** Replace colour a with b everywhere. */
  swap(a: number, b: number) {
    const A = rgba(a), B = rgba(b);
    for (let i = 0; i < this.d.length; i++) if (this.d[i] === A) this.d[i] = B;
  }
  blit(src: Px, dx: number, dy: number, flipX = false) {
    for (let y = 0; y < src.h; y++)
      for (let x = 0; x < src.w; x++) {
        const v = src.d[y * src.w + x];
        const a = v >>> 24;
        if (!a) continue;
        const tx = dx + (flipX ? src.w - 1 - x : x), ty = dy + y;
        if (!this.inb(tx, ty)) continue;
        if (a === 255) this.d[ty * this.w + tx] = v;
        else this.set(tx, ty, ((v & 255) << 16) | (v & 0xff00) | ((v >> 16) & 255), a);
      }
  }
  flipV(): Px { const o = new Px(this.w, this.h); for (let y = 0; y < this.h; y++) for (let x = 0; x < this.w; x++) o.d[(this.h - 1 - y) * this.w + x] = this.d[y * this.w + x]; return o; }
  /** Draw dithered vertical gradient between colours. */
  vgrad(x: number, y: number, w: number, h: number, cols: number[]) {
    for (let j = 0; j < h; j++) {
      const t = (j / Math.max(1, h - 1)) * (cols.length - 1);
      for (let i = 0; i < w; i++) {
        const k = Math.min(cols.length - 2, Math.floor(t));
        const f = t - k;
        this.set(x + i, y + j, f > Px.bayer(x + i, y + j) ? cols[k + 1] : cols[k]);
      }
    }
  }
  toCanvas(): HTMLCanvasElement {
    const cv = document.createElement('canvas');
    cv.width = this.w;
    cv.height = this.h;
    const ctx = cv.getContext('2d')!;
    const img = ctx.createImageData(this.w, this.h);
    new Uint32Array(img.data.buffer).set(this.d);
    ctx.putImageData(img, 0, 0);
    return cv;
  }
}

/** Deterministic PRNG so generated art is identical every boot. */
export function rng(seed: number) {
  let s = seed >>> 0 || 1;
  return () => {
    s ^= s << 13; s >>>= 0;
    s ^= s >> 17;
    s ^= s << 5; s >>>= 0;
    return s / 4294967296;
  };
}
