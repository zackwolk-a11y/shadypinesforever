/**
 * THE GOOSE — parametric pixel-art character.
 * A pose (neck curve, head tilt, beak opening, eye state, wing angle, legs, tail, squash)
 * is rasterised to a 48x48 frame. Animations are lists of poses, so every frame shares
 * exactly the same proportions, palette, light direction and outline rules.
 */
import { C, R } from './palette';
import { Px } from './px';

export const GF = 48; // frame size
const AX = 22, AY = 45; // anchor (between feet, on the ground)

export type Eye = 'normal' | 'wide' | 'closed' | 'happy' | 'squint' | 'spiral' | 'heart' | 'look' | 'mischief' | 'shock';
export interface Pose {
  bx: number; by: number; // body centre offset from anchor
  sx: number; sy: number; // body squash/stretch
  rot: number; // body rotation (neg = chest up)
  hx: number; hy: number; // head centre offset from body centre
  bend: number; // neck bend
  tilt: number; // head tilt (rad, + = beak down)
  headDir: 1 | -1; // -1 = looking backwards
  beak: number; // 0..1 open
  eye: Eye;
  pdx: number; pdy: number; // pupil offset (wide eyes)
  wing: number; // 0 folded .. 1 fully raised
  wingFar: number; // far wing raised amount (-1 hidden)
  legA: [number, number]; legB: [number, number]; // foot dx, lift
  tuck: boolean; // legs tucked (sitting / riding)
  tail: number; // tail wag
  puff: number; // feather puff (react)
  cheeks: number; // 0..1 cheek puff (blowing)
  blush: number;
  lump: number; // -1 none, else 0..1 along the neck (swallowing)
  brow: number; // 0 none, + mischievous, - worried
  front: boolean; // head turned to camera
  cup: number; // 0 none, 1 cup held in beak / under wing
  bellyRumble: number;
}

const BASE: Pose = {
  bx: -1, by: -11, sx: 1, sy: 1, rot: -0.1,
  hx: 9, hy: -19, bend: 2.5, tilt: 0, headDir: 1,
  beak: 0, eye: 'normal', pdx: 0, pdy: 0,
  wing: 0, wingFar: -1,
  legA: [2, 0], legB: [-2, 0], tuck: false,
  tail: 0, puff: 0, cheeks: 0, blush: 0, lump: -1, brow: 0, front: false, cup: 0, bellyRumble: 0,
};

const rotp = (x: number, y: number, a: number) => [x * Math.cos(a) - y * Math.sin(a), x * Math.sin(a) + y * Math.cos(a)];

export function drawGoose(pp: Partial<Pose>): Px {
  const p: Pose = { ...BASE, ...pp };
  const g = new Px(GF, GF);
  const bcx = AX + p.bx, bcy = AY + p.by;
  const rx = (10 + p.puff * 1.5) * p.sx, ry = (7 + p.puff * 1.2) * p.sy;

  // ---------- legs + feet (behind body) ----------
  const hipY = bcy + ry * 0.55;
  const legs: [[number, number], number][] = [[p.legB, C.go3], [p.legA, C.go2]];
  if (!p.tuck) {
    for (const [[fdx, lift], col] of legs) {
      const fx = AX + fdx, fy = AY - lift;
      const hx = bcx + fdx * 0.4 + 1;
      g.line(hx, hipY, fx, fy - 1, col);
      g.line(hx + 1, hipY, fx + 1, fy - 1, col);
      // webbed foot
      const fc = col === C.go2 ? C.go1 : C.go2;
      g.poly([[fx - 1, fy - 1], [fx + 5, fy + 0.2], [fx + 5, fy + 1], [fx - 2, fy + 1]], fc);
      g.set(fx + 4, fy, C.go3);
    }
  } else {
    // tucked feet peeking under the body
    g.rect(bcx - 2, bcy + ry - 1, 4, 2, C.go2);
    g.rect(bcx + 2, bcy + ry - 1, 4, 2, C.go1);
  }

  // ---------- far wing (when spread) ----------
  if (p.wingFar >= 0) {
    const sh = [bcx + 2, bcy - 3];
    const a = -0.2 - p.wingFar * 1.5;
    const [wx, wy] = rotp(-6, 1, a);
    g.shadedEllipse(sh[0] + wx + 1, sh[1] + wy - 1, 8, 4, [C.gw2, C.gw3, C.gw3, C.gw4], a);
  }

  // ---------- tail ----------
  const tb = rotp(-rx + 1, -2, p.rot);
  const tx = bcx + tb[0], ty = bcy + tb[1];
  const tw = p.tail * 2;
  g.poly([[tx + 3, ty - 3], [tx - 5, ty - 6 + tw], [tx - 4, ty - 3 + tw], [tx - 6, ty - 1 + tw], [tx + 3, ty + 3]], C.gw2);
  g.poly([[tx + 3, ty - 2], [tx - 3, ty - 5 + tw], [tx + 3, ty + 1]], C.gw1);

  // ---------- body ----------
  g.shadedEllipse(bcx, bcy, rx, ry, R.goose, p.rot);
  // chest bulge
  const ch = rotp(rx * 0.55, -ry * 0.15, p.rot);
  g.shadedEllipse(bcx + ch[0], bcy + ch[1], rx * 0.5, ry * 0.85, R.goose, p.rot - 0.4);
  // belly shade band (gives volume)
  for (let x = Math.floor(bcx - rx + 3); x < bcx + rx - 3; x++) {
    const yy = bcy + ry * Math.sqrt(Math.max(0, 1 - ((x + 0.5 - bcx) / rx) ** 2)) - 1;
    g.set(x, yy, C.gw3);
    if (Px.bayer(x, 1) > 0.5) g.set(x, yy - 1, C.gw2);
  }

  // ---------- neck ----------
  const nb = rotp(rx * 0.62, -ry * 0.55, p.rot);
  const n0x = bcx + nb[0], n0y = bcy + nb[1];
  const hcx = p.front ? bcx + p.hx * 0.6 : bcx + p.hx, hcy = bcy + p.hy;
  const mx = (n0x + hcx) / 2, my = (n0y + hcy) / 2;
  const dx = hcx - n0x, dy = hcy - n0y;
  const len = Math.hypot(dx, dy) || 1;
  const cx1 = mx + (-dy / len) * -p.bend, cy1 = my + (dx / len) * -p.bend;
  const pts: [number, number, number][] = [];
  const steps = Math.max(8, Math.ceil(len * 1.4));
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const x = (1 - t) * (1 - t) * n0x + 2 * (1 - t) * t * cx1 + t * t * hcx;
    const y = (1 - t) * (1 - t) * n0y + 2 * (1 - t) * t * cy1 + t * t * hcy;
    let r = 3.6 - t * 1.0;
    if (p.lump >= 0) r += Math.max(0, 1.8 - Math.abs(t - (1 - p.lump)) * 9);
    pts.push([x, y, r]);
  }
  for (const [x, y, r] of pts) g.circle(x, y, r, C.gw2);
  for (const [x, y, r] of pts) g.circle(x - 0.6, y - 0.4, r - 1, C.gw1);
  for (const [x, y, r] of pts) if (r > 2.2) g.circle(x - 1.2, y - 0.6, r - 2.3, C.gw0);

  // ---------- head ----------
  const hr = 4.6 + p.cheeks * 0.8;
  g.shadedEllipse(hcx, hcy, hr + 0.4, hr - 0.2 + p.cheeks * 0.4, R.goose, p.tilt);
  if (p.cheeks > 0) g.shadedEllipse(hcx + 2 * p.headDir, hcy + 1.5, 3 * p.cheeks + 1, 2.5 * p.cheeks + 0.5, R.goose);

  // ---------- beak ----------
  const dir = p.front ? 1 : p.headDir;
  const bt = p.tilt;
  const B = (x: number, y: number, a = 0): number[] => {
    const [qx, qy] = rotp(x, y, bt + a);
    return [hcx + qx * dir, hcy + qy];
  };
  if (p.front) {
    // front-facing beak: a wide wedge pointing down-ish toward the viewer
    g.poly([[hcx - 3, hcy + 1], [hcx + 3, hcy + 1], [hcx + 1, hcy + 6], [hcx - 1, hcy + 6]], C.go1);
    g.hline(hcx - 2, hcx + 1, hcy + 1, C.go0);
    if (p.beak > 0.2) g.rect(hcx - 1, hcy + 3, 2, 2, C.red2);
  } else {
    const op = p.beak * 0.55;
    if (p.beak > 0.05) {
      // mouth interior
      g.poly([B(3, 0), B(9, -0.2, -op), B(8, 1.2, op)], C.red2);
    }
    // lower jaw
    g.poly([B(3, 0.6), B(8, 1.0, op), B(8, 2.0, op), B(3, 2.6)], C.go2);
    // upper jaw
    g.poly([B(2.6, -2.2), B(4.5, -1.8, -op * 0.6), B(9.5, -0.2, -op), B(9.6, 0.8, -op), B(3, 0.9)], C.go1);
    const hl = B(4, -1.4, -op * 0.5), hl2 = B(7, -0.6, -op);
    g.line(hl[0], hl[1], hl2[0], hl2[1], C.go0);
    const ns = B(5, -0.6, -op * 0.6);
    g.set(ns[0], ns[1], C.go3);
  }

  // ---------- near wing ----------
  {
    const sh = [bcx + 3, bcy - 3];
    const a = 0.25 - p.wing * 1.9 + p.rot;
    const [wx, wy] = rotp(-5.5, 1.5, a);
    const ex = sh[0] + wx, ey = sh[1] + wy;
    g.shadedEllipse(ex, ey, 7.5 + p.puff, 4.4, [C.gw2, C.gw3, C.gw3, C.gw4], a);
    g.shadedEllipse(ex - 0.6, ey - 0.6, 6.3 + p.puff, 3.3, [C.gw0, C.gw1, C.gw1, C.gw2], a);
    // primary feather tips
    for (let k = 0; k < 3; k++) {
      const [fx, fy] = rotp(-6 - k * 0.2, 1 + k * 1.2 - 1, a);
      const [fx2, fy2] = rotp(-3, 1 + k * 1.2 - 1, a);
      g.line(ex + fx, ey + fy, ex + fx2, ey + fy2, C.gw3);
    }
  }

  // ---------- outline ----------
  g.outline(C.ink);

  // ---------- face details (after outline so they read crisp) ----------
  const eyeOff = p.front ? null : B(0.2, -1.7);
  const drawEye = (ex: number, ey: number, mirror = 1) => {
    ex = Math.round(ex); ey = Math.round(ey);
    switch (p.eye) {
      case 'normal':
      case 'mischief':
        g.rect(ex, ey, 2, 2, C.ink); g.set(ex, ey, C.wht); g.set(ex + 1, ey + 2, C.ink);
        break;
      case 'look':
        g.rect(ex + (p.pdx > 0 ? 1 : 0), ey + (p.pdy > 0 ? 1 : 0), 2, 2, C.ink);
        break;
      case 'wide':
      case 'shock':
        g.rect(ex - 1, ey - 1, 4, 4, C.wht);
        g.hline(ex - 1, ex + 2, ey - 2, C.ink);
        g.vline(ex - 2, ey - 1, ey + 2, C.ink); g.vline(ex + 3, ey - 1, ey + 2, C.ink);
        g.hline(ex - 1, ex + 2, ey + 3, C.ink);
        if (p.eye === 'wide') g.rect(ex + Math.round(p.pdx) * mirror, ey + Math.round(p.pdy), 2, 2, C.ink);
        else g.set(ex + 1, ey + 1, C.ink);
        break;
      case 'closed':
        g.hline(ex - 1, ex + 2, ey + 1, C.ink);
        break;
      case 'happy':
        g.set(ex - 1, ey + 1, C.ink); g.set(ex, ey, C.ink); g.set(ex + 1, ey, C.ink); g.set(ex + 2, ey + 1, C.ink);
        break;
      case 'squint':
        g.line(ex - 1, ey - 1, ex + 2, ey + 1, C.ink); g.line(ex - 1, ey + 2, ex + 2, ey + 1, C.ink);
        break;
      case 'spiral':
        g.ring(ex + 0.5, ey + 0.5, 2.5, C.ink); g.set(ex, ey, C.ink); g.set(ex + 1, ey + 1, C.red1);
        break;
      case 'heart':
        g.set(ex - 1, ey, C.red1); g.set(ex + 1, ey, C.red1); g.hline(ex - 1, ex + 1, ey + 1, C.red1); g.set(ex, ey + 2, C.red1); g.set(ex, ey + 1, C.red0);
        break;
    }
    if (p.brow !== 0 && p.eye !== 'closed') {
      const d = p.brow > 0 ? 1 : -1;
      g.line(ex - 1, ey - 3 - (d > 0 ? 0 : 1), ex + 2, ey - 3 + (d > 0 ? 1 : -0), C.ink);
    }
  };
  if (p.front) {
    drawEye(hcx - 3, hcy - 2, -1);
    drawEye(hcx + 2, hcy - 2, 1);
  } else if (eyeOff) drawEye(eyeOff[0] - (dir < 0 ? 1 : 0), eyeOff[1], dir);

  if (p.cup > 0) {
    // little white Simps coffee cup (red trident band), held by the near wing tip
    const cx = Math.round(bcx + 7), cy = Math.round(bcy - 2);
    g.rect(cx - 3, cy - 5, 7, 8, C.ink); g.rect(cx - 2, cy - 4, 5, 6, C.wht); g.rect(cx - 2, cy - 2, 5, 2, C.red1); g.set(cx, cy - 2, C.wht);
    g.rect(cx + 3, cy - 3, 2, 3, C.ink); g.set(cx + 3, cy - 2, C.wht);
    if (p.cup > 1) { g.rect(cx - 2, cy - 6, 5, 1, C.cola1); }
  }
  if (p.bellyRumble > 0) { for (let k = 0; k < 3; k++) g.set(bcx - 4 + k * 3, bcy + 3 + (k % 2), C.gw3); }
  if (p.blush > 0) {
    const bp = p.front ? [hcx - 4, hcy + 1] : B(0, 1.8);
    g.set(bp[0], bp[1], C.pink); g.set(bp[0] + 1, bp[1], C.pink);
    if (p.front) { g.set(hcx + 3, hcy + 1, C.pink); g.set(hcx + 4, hcy + 1, C.pink); }
  }
  return g;
}

// --------------------------------------------------------------------------------------
// Animation library. Each entry: frames (poses), frame rate, loop.
// --------------------------------------------------------------------------------------
export interface AnimDef { frames: Partial<Pose>[]; fps: number; loop: boolean }
const S = Math.sin, PI = Math.PI;
const range = (n: number, f: (i: number, t: number) => Partial<Pose>) => Array.from({ length: n }, (_, i) => f(i, i / n));

export const GOOSE_ANIMS: Record<string, AnimDef> = {
  idle: { fps: 5, loop: true, frames: range(6, (_i, t) => ({ sy: 1 + S(t * 2 * PI) * 0.035, sx: 1 - S(t * 2 * PI) * 0.02, hy: -19 + Math.round(S(t * 2 * PI) * 0.8), tail: S(t * 4 * PI) * 0.5, eye: _i === 4 ? 'closed' : 'normal' })) },
  look: {
    fps: 5, loop: true, frames: [
      { eye: 'normal' }, { hx: 8, hy: -20, tilt: -0.15 }, { hx: 7, hy: -21, tilt: -0.35, eye: 'look', pdy: -1 },
      { hx: 7, hy: -21, tilt: -0.35, eye: 'look', pdy: -1 }, { hx: 4, hy: -20, headDir: -1, tilt: 0.1, bend: 4 },
      { hx: 3, hy: -20, headDir: -1, tilt: 0.15, bend: 4, eye: 'mischief', brow: 1 }, { hx: 3, hy: -20, headDir: -1, tilt: 0.15, bend: 4, eye: 'closed' }, { hx: 9, hy: -19 },
    ],
  },
  walk: {
    fps: 11, loop: true, frames: range(6, (i, t) => {
      const ph = t * 2 * PI;
      return {
        rot: -0.1 + S(ph) * 0.07, by: -11 - Math.abs(S(ph)) * 1.2, hx: 10 + Math.round(S(ph * 2) * 0.8), hy: -19 + Math.round(Math.abs(S(ph)) * -1),
        legA: [2 + Math.round(S(ph) * 3), Math.max(0, Math.round(-Math.cos(ph) * 2))], legB: [-2 - Math.round(S(ph) * 3), Math.max(0, Math.round(Math.cos(ph) * 2))],
        tail: S(ph) * 1, wing: 0.03,
      };
    }),
  },
  run: {
    fps: 15, loop: true, frames: range(6, (i, t) => {
      const ph = t * 2 * PI;
      return {
        rot: 0.05 + S(ph) * 0.05, by: -11 - Math.abs(S(ph)) * 2, sx: 1.05, sy: 0.95, hx: 15, hy: -14 + Math.round(S(ph * 2)), bend: -1, tilt: 0.15,
        legA: [3 + Math.round(S(ph) * 5), Math.max(0, Math.round(-Math.cos(ph) * 3))], legB: [-1 - Math.round(S(ph) * 5), Math.max(0, Math.round(Math.cos(ph) * 3))],
        tail: S(ph) * 1.5, wing: 0.25 + S(ph) * 0.15, wingFar: 0.15, eye: 'mischief', brow: 1, beak: i % 3 === 0 ? 0.2 : 0,
      };
    }),
  },
  crouch: { fps: 20, loop: false, frames: [{ sy: 0.82, sx: 1.12, by: -9, hx: 10, hy: -15, wing: 0.1 }] },
  jump: { fps: 12, loop: true, frames: [{ sy: 1.12, sx: 0.9, by: -12, hx: 8, hy: -22, wing: 0.9, wingFar: 0.8, legA: [1, 3], legB: [-2, 4], tail: 1 }, { sy: 1.08, sx: 0.93, by: -12, hx: 8, hy: -22, wing: 0.7, wingFar: 0.6, legA: [1, 3], legB: [-2, 4], tail: 1 }] },
  fall: { fps: 10, loop: true, frames: [{ hx: 9, hy: -21, wing: 0.55, wingFar: 0.4, legA: [3, 1], legB: [-1, 2], eye: 'wide', pdy: 1 }, { hx: 9, hy: -21, wing: 0.45, wingFar: 0.3, legA: [3, 1], legB: [-1, 2], eye: 'wide', pdy: 1 }] },
  flap: { fps: 16, loop: true, frames: range(4, (i, t) => ({ hx: 9, hy: -21, wing: 0.5 + S(t * 2 * PI) * 0.5, wingFar: 0.4 + S(t * 2 * PI + 0.4) * 0.5, legA: [2, 2], legB: [-2, 3], beak: 0.1, eye: 'happy' })) },
  land: { fps: 16, loop: false, frames: [{ sy: 0.78, sx: 1.18, by: -8, hx: 11, hy: -14, wing: 0.3 }, { sy: 0.9, sx: 1.08, by: -10, hx: 10, hy: -17 }, { sy: 1.03, sx: 0.98 }] },
  honk: {
    fps: 12, loop: false, frames: [
      { hx: 5, hy: -17, bend: 4, tilt: 0.3, sy: 0.95, eye: 'closed', brow: 1 },
      { hx: 4, hy: -16, bend: 5, tilt: 0.35, sy: 0.9, sx: 1.05, eye: 'closed', brow: 1 },
      { hx: 15, hy: -24, bend: -1, tilt: -0.35, beak: 1, eye: 'wide', sy: 1.1, sx: 0.95, wing: 0.5, wingFar: 0.4, tail: 1.5 },
      { hx: 16, hy: -25, bend: -1, tilt: -0.4, beak: 1, eye: 'wide', sy: 1.12, sx: 0.94, wing: 0.7, wingFar: 0.6, tail: -1.5 },
      { hx: 16, hy: -25, bend: -1, tilt: -0.4, beak: 0.9, eye: 'wide', sy: 1.1, wing: 0.5, wingFar: 0.4, tail: 1.5 },
      { hx: 12, hy: -22, tilt: -0.1, beak: 0.2, eye: 'mischief', brow: 1 },
    ],
  },
  drink: {
    fps: 8, loop: false, frames: [
      { hx: 12, hy: -14, tilt: 0.5, eye: 'look', pdy: 1 }, { hx: 15, hy: -8, bend: -3, tilt: 0.9, eye: 'look', pdy: 1 },
      { hx: 16, hy: -6, bend: -3, tilt: 1.0, eye: 'closed' }, { hx: 16, hy: -5, bend: -3, tilt: 1.05, eye: 'closed', sy: 0.97 },
      { hx: 16, hy: -6, bend: -3, tilt: 1.0, eye: 'closed', sy: 1.0 }, { hx: 16, hy: -5, bend: -3, tilt: 1.05, eye: 'closed', sy: 0.97 },
    ],
  },
  swallow: {
    fps: 9, loop: false, frames: [
      { hx: 9, hy: -22, tilt: -0.5, eye: 'closed', cheeks: 0.6 }, { hx: 8, hy: -23, tilt: -0.6, eye: 'closed', lump: 0.05 },
      { hx: 8, hy: -23, tilt: -0.5, eye: 'closed', lump: 0.3 }, { hx: 8, hy: -22, tilt: -0.4, eye: 'closed', lump: 0.55 },
      { hx: 9, hy: -21, tilt: -0.2, eye: 'closed', lump: 0.8 }, { hx: 9, hy: -20, eye: 'normal', puff: 0.3 },
    ],
  },
  // Cola: eyes pop, feathers puff, vibrating with fizz
  reactFizz: { fps: 18, loop: true, frames: range(4, (i) => ({ eye: 'shock', puff: 1, hx: 9 + (i % 2 ? 1 : -1), hy: -23, bend: 1, beak: 0.4, wing: 0.6 + (i % 2) * 0.3, wingFar: 0.5, sx: 1.06, sy: 1.08, tail: i % 2 ? 2 : -2, legA: [2, i % 2], legB: [-2, (i + 1) % 2] })) },
  // Cream soda: dreamy, hearts, swaying
  reactDreamy: { fps: 6, loop: true, frames: range(6, (_i, t) => ({ eye: 'heart', blush: 1, hx: 9 + S(t * 2 * PI) * 2, hy: -20, tilt: S(t * 2 * PI) * 0.3, bend: 3 + S(t * 2 * PI) * 2, rot: -0.1 + S(t * 2 * PI) * 0.05, tail: S(t * 4 * PI) * 1.5, wing: 0.15 })) },
  // Black cherry: sour pucker then delight
  reactSour: {
    fps: 9, loop: true, frames: [
      { eye: 'squint', hx: 6, hy: -17, bend: 4, cheeks: 0.8, sy: 0.92, puff: 0.4, blush: 1 }, { eye: 'squint', hx: 6, hy: -16, bend: 4, cheeks: 1, sy: 0.9, sx: 1.06, puff: 0.6, blush: 1 },
      { eye: 'squint', hx: 7, hy: -17, bend: 4, cheeks: 0.9, sy: 0.92, puff: 0.5, blush: 1 }, { eye: 'wide', hx: 11, hy: -24, beak: 0.6, wing: 0.8, wingFar: 0.7, sy: 1.1, blush: 1 },
    ],
  },
  blow: { fps: 8, loop: false, frames: [{ cheeks: 0.5, hx: 11, hy: -20 }, { cheeks: 1, hx: 11, hy: -20, eye: 'closed' }, { cheeks: 1, hx: 12, hy: -20, eye: 'closed', beak: 0.25 }, { cheeks: 0.3, hx: 12, hy: -20, beak: 0.4, eye: 'wide' }] },
  ride: { fps: 4, loop: true, frames: [{ tuck: true, by: -8, hx: 10, hy: -18, eye: 'happy', wing: 0.3, wingFar: 0.2, tail: 1 }, { tuck: true, by: -8, hx: 10, hy: -19, eye: 'happy', wing: 0.45, wingFar: 0.35, tail: -1, beak: 0.3 }] },
  hurt: { fps: 10, loop: true, frames: [{ eye: 'spiral', sy: 0.85, sx: 1.12, hx: 4, hy: -15, tilt: 0.6, wing: 0.8, wingFar: 0.6, beak: 0.5, puff: 0.6 }, { eye: 'spiral', sy: 0.88, sx: 1.1, hx: 3, hy: -16, tilt: 0.4, wing: 0.6, wingFar: 0.5, beak: 0.4, puff: 0.6 }] },
  celebrate: { fps: 12, loop: true, frames: range(6, (_i, t) => ({ eye: 'happy', beak: 0.7, hx: 10, hy: -23 - S(t * 2 * PI) * 1.5, tilt: -0.3, wing: 0.6 + S(t * 4 * PI) * 0.4, wingFar: 0.5 + S(t * 4 * PI + 0.5) * 0.4, sy: 1 + S(t * 2 * PI) * 0.05, tail: S(t * 4 * PI) * 2, legA: [2, 0], legB: [-2, 0] })) },
  dash: { fps: 20, loop: true, frames: [{ sx: 1.25, sy: 0.82, rot: 0.15, by: -10, hx: 18, hy: -13, bend: 0, tilt: 0.2, wing: 0.15, wingFar: 0.1, legA: [-4, 2], legB: [-7, 3], eye: 'mischief', brow: 1, tail: -2 }, { sx: 1.22, sy: 0.84, rot: 0.15, by: -10, hx: 18, hy: -13, bend: 0, tilt: 0.2, wing: 0.2, wingFar: 0.15, legA: [-5, 3], legB: [-6, 2], eye: 'mischief', brow: 1, tail: 2 }] },
  burp: { fps: 12, loop: false, frames: [{ cheeks: 0.8, hx: 10, hy: -21, eye: 'closed', puff: 0.3 }, { cheeks: 1, hx: 12, hy: -22, eye: 'closed', puff: 0.5 }, { hx: 14, hy: -22, beak: 1, eye: 'wide', tilt: -0.2, wing: 0.4 }, { hx: 12, hy: -21, beak: 0.5, eye: 'happy' }] },
  sipCup: { fps: 6, loop: false, frames: [{ cup: 2, hx: 10, hy: -16, tilt: 0.7, eye: 'look', pdy: 1 }, { cup: 2, hx: 9, hy: -12, bend: -2, tilt: 1.0, eye: 'closed' }, { cup: 2, hx: 9, hy: -12, bend: -2, tilt: 1.05, eye: 'closed', sy: 0.97 }, { cup: 2, hx: 9, hy: -13, tilt: 0.9, eye: 'closed' }, { cup: 1, hx: 9, hy: -20, eye: 'happy', blush: 1 }] },
  holdCup: { fps: 4, loop: true, frames: [{ cup: 1, eye: 'normal' }, { cup: 1, hy: -20, eye: 'normal' }, { cup: 1, eye: 'closed' }] },
  sit: { fps: 3, loop: true, frames: [{ tuck: true, by: -8, hx: 9, hy: -18, eye: 'normal' }, { tuck: true, by: -8, hx: 9, hy: -19, eye: 'normal' }, { tuck: true, by: -8, hx: 9, hy: -18, eye: 'closed' }] },
  sitCup: { fps: 3, loop: true, frames: [{ tuck: true, by: -8, hx: 9, hy: -18, cup: 1 }, { tuck: true, by: -8, hx: 9, hy: -19, cup: 1 }, { tuck: true, by: -8, hx: 9, hy: -18, cup: 1, eye: 'closed' }] },
  laugh: { fps: 10, loop: true, frames: [{ eye: 'happy', beak: 0.8, hx: 11, hy: -21, tilt: -0.3, wing: 0.3, sy: 1.04 }, { eye: 'happy', beak: 0.4, hx: 10, hy: -19, tilt: -0.1, wing: 0.15, sy: 0.96 }] },
  offer: { fps: 4, loop: true, frames: [{ cup: 1, hx: 14, hy: -18, bend: 1, eye: 'happy', wing: 0.35 }, { cup: 1, hx: 15, hy: -18, bend: 1, eye: 'happy', wing: 0.4, blush: 1 }] },
  growl: { fps: 10, loop: false, frames: [{ bellyRumble: 1, sx: 1.05, sy: 0.95, hx: 7, hy: -16, tilt: 0.6, eye: 'look', pdy: 1 }, { bellyRumble: 1, sx: 0.96, sy: 1.04, hx: 7, hy: -16, tilt: 0.6, eye: 'look', pdy: 1 }, { bellyRumble: 1, sx: 1.05, sy: 0.95, hx: 7, hy: -16, tilt: 0.6, eye: 'wide', pdy: 1 }, { hx: 9, hy: -20, eye: 'wide', brow: -1 }] },
  swim: { fps: 6, loop: true, frames: [{ tuck: true, by: -6, hx: 10, hy: -16, eye: 'wide', wing: 0.5, wingFar: 0.4, beak: 0.3 }, { tuck: true, by: -5, hx: 10, hy: -15, eye: 'wide', wing: 0.8, wingFar: 0.7 }] },
  frontHonk: { fps: 8, loop: false, frames: [{ front: true, hx: 4, hy: -21, eye: 'closed' }, { front: true, hx: 4, hy: -24, eye: 'wide', beak: 1 }, { front: true, hx: 4, hy: -24, eye: 'wide', beak: 1 }, { front: true, hx: 4, hy: -21, eye: 'normal' }] },
  front: { fps: 3, loop: true, frames: [{ front: true, hx: 4, hy: -21, eye: 'normal' }, { front: true, hx: 4, hy: -21, eye: 'normal' }, { front: true, hx: 4, hy: -21, eye: 'closed' }] },
  lookUp: { fps: 6, loop: false, frames: [{ hx: 7, hy: -24, tilt: -0.5, eye: 'look', pdy: -1 }, { hx: 6, hy: -28, tilt: -0.7, eye: 'look', pdy: -1, sy: 1.04 }, { hx: 6, hy: -30, tilt: -0.75, eye: 'wide', pdy: -1, pdx: 1, sy: 1.06, bend: 1 }] },
  tilt: { fps: 4, loop: false, frames: [{ hx: 6, hy: -30, tilt: -0.3, eye: 'wide', pdx: 1 }, { hx: 5, hy: -29, tilt: 0.25, eye: 'wide', pdx: 1, pdy: -1, bend: 3 }] },
  shrug: { fps: 6, loop: false, frames: [{ hx: 8, hy: -20, eye: 'look', wing: 0.4, wingFar: 0.3 }, { hx: 8, hy: -21, tilt: 0.3, eye: 'closed', wing: 0.6, wingFar: 0.5, brow: -1 }, { hx: 8, hy: -21, tilt: 0.3, eye: 'closed', wing: 0.6, wingFar: 0.5, brow: -1 }, { hx: 9, hy: -19 }] },
};

/** Render every animation into one sheet canvas. Returns frame rects keyed `anim_i`. */
export function buildGooseSheet() {
  const names = Object.keys(GOOSE_ANIMS);
  const cols = 8;
  const totalFrames = names.reduce((s, n) => s + GOOSE_ANIMS[n].frames.length, 0);
  const rows = Math.ceil(totalFrames / cols);
  const sheet = new Px(cols * GF, rows * GF);
  const frames: { name: string; x: number; y: number }[] = [];
  let k = 0;
  for (const n of names) {
    GOOSE_ANIMS[n].frames.forEach((pose, i) => {
      const x = (k % cols) * GF, y = Math.floor(k / cols) * GF;
      sheet.blit(drawGoose(pose), x, y);
      frames.push({ name: `${n}_${i}`, x, y });
      k++;
    });
  }
  return { sheet, frames };
}
