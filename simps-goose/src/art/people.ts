/**
 * Store customers, staff and street pedestrians — parametric 3/4-view people.
 * Frame 32x64, anchor bottom-centre (16, 63). ~2x the goose's height (art bible §2).
 */
import { C } from './palette';
import { Px } from './px';

export const PF_W = 32, PF_H = 64;
export interface PersonSpec {
  skin: [number, number];
  hair: number; hairStyle: 'short' | 'long' | 'bun' | 'curly' | 'cap' | 'bald' | 'slick';
  shirt: [number, number, number]; // hi, base, shade
  pants: [number, number];
  shoes: number;
  apron?: boolean; capColor?: number;
  bag?: 'basket' | 'tote' | null;
  glasses?: boolean;
  tall?: number; // -2..3
  beard?: 'full' | 'goatee'; vest?: boolean; jacket?: boolean; tattoo?: boolean; broad?: boolean; chibi?: boolean; tie?: number;
}
export interface PersonPose {
  stride: number; // -1..1
  bob: number;
  armF: number; armB: number; // arm angles (0 = down, + forward)
  mouth: 'smile' | 'o' | 'laugh' | 'flat' | 'grin';
  eyes: 'normal' | 'wide' | 'closed' | 'happy';
  lean: number;
  emote?: boolean;
  bottle?: 'hold' | 'pour' | 'drink' | 'clip';
}

const rot = (x: number, y: number, a: number) => [x * Math.cos(a) - y * Math.sin(a), x * Math.sin(a) + y * Math.cos(a)];

export function drawPerson(s: PersonSpec, p: PersonPose): Px {
  const g = new Px(PF_W, PF_H);
  const ax = 15, ay = 62;
  const T = s.tall ?? 0;
  const hipY = ay - 19 - T + p.bob;
  const shY = hipY - 17;
  const lean = p.lean;
  const tx = ax + lean * 0.5;

  // back arm
  const arm = (ang: number, shoulderX: number, front: boolean) => {
    const [ex, ey] = rot(0, 15, -ang);
    const sx = shoulderX, sy = shY + 2;
    const col = front ? s.shirt[1] : s.shirt[2];
    g.line(sx, sy, sx + ex * 0.5, sy + ey * 0.5, col);
    g.line(sx + 1, sy, sx + 1 + ex * 0.5, sy + ey * 0.5, col);
    g.line(sx + ex * 0.5, sy + ey * 0.5, sx + ex, sy + ey, front ? s.skin[0] : s.skin[1]);
    g.line(sx + 1 + ex * 0.5, sy + ey * 0.5, sx + 1 + ex, sy + ey, front ? s.skin[0] : s.skin[1]);
    g.circle(sx + ex + 0.5, sy + ey + 0.5, 1.6, front ? s.skin[0] : s.skin[1]);
    if (s.tattoo) { const ink = front ? 0x56679a : 0x45527c; g.set(Math.round(sx + ex * 0.66), Math.round(sy + ey * 0.66), ink); g.set(Math.round(sx + 1 + ex * 0.78), Math.round(sy + ey * 0.78), ink); } // small forearm tattoo
    return [sx + ex, sy + ey];
  };
  arm(p.armB, tx - 5 + lean, false);

  // legs
  const leg = (dx: number, st: number, col: number) => {
    const hx = tx + dx;
    const fx = ax + dx + st * 5, fy = ay;
    const kx = (hx + fx) / 2 + Math.abs(st) * 1.5, ky = (hipY + fy) / 2;
    for (const o of [0, 1, 2]) { g.line(hx + o - 1, hipY, kx + o - 1, ky, col); g.line(kx + o - 1, ky, fx + o - 1, fy - 2, col); }
    g.rect(fx - 2, fy - 2, 6, 2, s.shoes);
    g.set(fx + 3, fy - 2, C.ink2);
  };
  leg(-2, -p.stride, s.pants[1]);
  leg(2, p.stride, s.pants[0]);

  // torso
  g.fill(tx - 7 + lean, shY, tx + 7 + lean, hipY + 1, (x, y) => {
    const t = (y - shY) / (hipY - shY);
    const w = (s.broad ? 7 : 6) - t * 0.6;
    const xx = x - (tx + lean * (1 - t));
    if (xx < -w || xx > w) return -1;
    if (xx > w - 2.5) return s.shirt[2];
    if (xx < -w + 2 && y < shY + 6) return s.shirt[0];
    return s.shirt[1];
  });
  // collar / neckline
  g.rect(tx - 1 + lean, shY - 2, 3, 3, s.skin[1]);
  if (s.vest) {
    g.fill(tx - 7 + lean, shY, tx + 7 + lean, hipY + 1, (x, y) => {
      const t = (y - shY) / (hipY - shY), w = (s.broad ? 7 : 6) - t * 0.6, xx = x - (tx + lean * (1 - t));
      if (xx < -w || xx > w) return -1;
      if (Math.abs(xx - 0.5) < 3.5 - (y - shY) * 0.45 && y < shY + 8) return -1; // V-neck shows the white shirt
      return xx > w - 2 ? C.blk2 : C.blk1;
    });
    const cx = Math.round(tx + lean + 0.5);
    const tc = s.tie ?? C.blk2;
    g.vline(cx, shY - 1, shY + 8, tc); g.vline(cx + 1, shY, shY + 7, tc === C.blk2 ? C.blk0 : C.red2);
    for (const yy of [shY + 1, shY + 4, shY + 7]) g.set(cx, yy, tc === C.blk2 ? C.st1 : C.red0);
    g.set(cx, shY + 11, C.blk0); g.set(cx, shY + 14, C.blk0);
  }
  if (s.jacket) {
    const cx = Math.round(tx + lean + 0.5);
    g.rect(cx - 2, shY, 4, 7, C.blk2); // black tee
    g.vline(cx + 2, shY + 1, hipY, C.st2); // zipper
    g.rect(cx - 4, shY - 2, 2, 3, C.blk0); g.rect(cx + 3, shY - 2, 2, 3, C.blk0); // stand collar
    g.vline(tx - 4 + lean, shY + 3, hipY - 2, C.blk0); g.set(tx - 3 + lean, shY + 6, 0x7a7088); g.set(tx + 4 + lean, shY + 9, 0x7a7088);
  }
  if (s.apron) {
    g.fill(tx - 4 + lean, shY + 4, tx + 5 + lean, hipY + 6, (x, y) => {
      const xx = x - (tx + lean * 0.8);
      if (xx < -4.5 || xx > 4.5) return -1;
      return xx > 2.5 ? C.blk2 : C.blk1;
    });
    g.hline(tx - 3 + lean, tx + 4 + lean, shY + 12, C.red1); // red brand band
    const ax0 = Math.round(tx + lean + 0.5); g.vline(ax0, shY + 6, shY + 10, C.red1); g.set(ax0 - 2, shY + 6, C.red1); g.set(ax0 + 2, shY + 6, C.red1); g.hline(ax0 - 2, ax0 + 2, shY + 8, C.red1); g.set(ax0 - 2, shY + 7, C.red1); g.set(ax0 + 2, shY + 7, C.red1);
    g.set(tx - 4 + lean, shY + 3, C.blk1); g.set(tx + 4 + lean, shY + 3, C.blk1);
  }
  if (s.bag === 'tote') {
    g.rect(tx - 9 + lean, hipY - 6, 6, 8, C.crm1); g.line(tx - 8 + lean, hipY - 6, tx - 5 + lean, shY + 2, C.crm2);
    g.rect(tx - 8 + lean, hipY - 3, 4, 1, C.red1);
  }

  // head (owners use a slightly bigger, more expressive head — K scales every head feature)
  const K = s.chibi ? 1.2 : 1;
  const hx = tx + lean + 1, hy = shY - (s.chibi ? 8 : 7);
  const RX = 5 * K, RY = 6 * K;
  g.ellipse(hx, hy, RX, RY, s.skin[0]);
  g.fill(hx - RX, hy - RY, hx + RX, hy + RY, (x, y) => {
    const nx = (x + 0.5 - hx) / RX, ny = (y + 0.5 - hy) / RY;
    if (nx * nx + ny * ny > 1) return -1;
    return nx < -0.45 || ny > 0.7 ? s.skin[1] : -1;
  });
  if (!s.chibi) { g.set(hx + RX, hy + 1, s.skin[0]); g.set(hx - RX + 1, hy, s.skin[1]); } // nose, ear
  const H = s.hair;
  if (s.chibi) ownerHair(g, s, hx, hy, RX, RY);
  const inHead = (x: number, y: number, ox = 0.6, oy = 1, sx = 1.12, sy = 1) => { const nx = (x + .5 - hx) / (RX * sx), ny = (y + .5 - hy + oy) / (RY * sy); return nx * nx + ny * ny <= 1; };
  if (!s.chibi) switch (s.hairStyle) {
    case 'short': g.fill(hx - RX - 1, hy - RY - 1, hx + RX, hy, (x, y) => inHead(x, y) && (y < hy - 2 || x < hx - 2) ? H : -1); break;
    case 'long': g.fill(hx - RX - 1, hy - RY - 1, hx + RX, hy + 8, (x, y) => (inHead(x, y, 0, 1, 1.16, 1.03) && (y < hy - 2 || x < hx - 1)) || (x < hx - 1 && x > hx - RX - 2 && y >= hy && y < hy + 9) ? H : -1); break;
    case 'bun': g.fill(hx - RX - 1, hy - RY - 1, hx + RX, hy, (x, y) => inHead(x, y) && (y < hy - 2 || x < hx - 2) ? H : -1); g.circle(hx - 4, hy - 6, 2.5, H); break;
    case 'curly': for (let k = 0; k < 9; k++) { const a = Math.PI * (0.9 + k * 0.14); g.circle(hx + Math.cos(a) * 4.8, hy - 1 + Math.sin(a) * 5.5, 2.2, H); } break;
    case 'cap': g.fill(hx - 6, hy - 7, hx + 5, hy - 2, (x, y) => inHead(x, y) ? (s.capColor ?? C.red1) : -1); g.rect(hx, hy - 3, 7, 2, s.capColor ?? C.red1); g.rect(hx - 6, hy - 2, 3, 4, H); break;
    case 'bald': g.set(hx - 2, hy - RY + 1, C.wht); g.set(hx - 1, hy - RY + 1, C.wht); g.set(hx - 2, hy - RY + 2, 0xffffff); g.set(hx - 3, hy - RY + 2, C.wht); break;
    case 'slick': {
      // faded undercut at the back/side, tall dark quiff swept forward over the brow
      g.fill(hx - RX - 1, hy - 4, hx - 2, hy + 1, (x, y) => inHead(x, y, 0, 0, 1.08, 1) && x < hx - 2 ? 0x5e5866 : -1);
      g.fill(hx - RX - 1, hy - RY - 4, hx + RX + 1, hy - 2, (x, y) => { const nx = (x + .5 - hx) / (RX * 1.15), ny = (y + .5 - hy + 3) / (RY * 1.0); return nx * nx + ny * ny <= 1 && y < hy - 2 && x > hx - RX + 1 ? H : -1; });
      g.rect(hx + 2, hy - 3, 4, 2, H); g.set(hx + RX, hy - 2, H); g.set(hx + RX + 1, hy - 3, H);
      g.hline(hx - 2, hx + 3, hy - RY - 2, 0x6a6070); g.set(hx + 4, hy - RY - 1, 0x6a6070);
      break;
    }
  }
  if (!s.chibi && s.beard === 'full') g.fill(hx - RX, hy, hx + RX, hy + RY + 1, (x, y) => { const nx = (x + .5 - hx) / (RX * 1.02), ny = (y + .5 - hy) / (RY * 1.05); if (nx * nx + ny * ny > 1 || x < hx - 3) return -1; const edge = nx * nx + ny * ny > 0.6; return (y >= hy + 4 || (edge && y >= hy + 1)) ? (Px.bayer(x, y) > 0.8 ? s.skin[1] : H) : -1; });
  if (!s.chibi && s.beard === 'goatee') { g.hline(hx + 2, hx + 4, hy + 2, H); g.rect(hx + 2, hy + 5, 2, 2, H); g.set(hx + 2, hy + 7, H); g.hline(hx - 1, hx + 1, hy + 6, H); }
  if (s.hairStyle === 'cap' && s.apron) g.set(hx - 1, hy - 5, C.wht);

  // front arm
  const hand = arm(p.armF, tx + 3 + lean, true);
  if (p.bottle) {
    const [bx, by] = hand;
    if (p.bottle === 'clip') { g.rect(bx - 2, by - 6, 6, 8, C.wd1); g.rect(bx - 1, by - 5, 4, 6, C.wht); g.hline(bx, bx + 1, by - 3, C.st2); g.hline(bx, bx + 2, by - 1, C.st2); g.rect(bx, by - 7, 2, 2, C.st2); }
    else if (p.bottle === 'pour') { g.line(bx, by - 2, bx + 5, by + 1, C.red1); g.line(bx, by - 3, bx + 5, by, C.red1); g.set(bx + 6, by + 1, C.wht); g.set(bx + 7, by + 3, C.chr0); g.set(bx + 7, by + 5, C.chr0); g.set(bx + 7, by + 7, C.chr0); }
    else { g.rect(bx - 1, by - 7, 3, 7, C.red1); g.rect(bx, by - 9, 1, 2, C.gl1); g.rect(bx - 1, by - 5, 3, 2, C.wht); g.set(bx - 1, by - 7, C.red0); }
  }
  if (s.bag === 'basket') {
    g.rect(hand[0] - 3, hand[1] + 1, 9, 6, C.red1); g.rect(hand[0] - 3, hand[1] + 1, 9, 1, C.red0);
    g.line(hand[0] - 2, hand[1] + 1, hand[0], hand[1] - 2, C.red2); g.line(hand[0] + 5, hand[1] + 1, hand[0] + 1, hand[1] - 2, C.red2);
    g.rect(hand[0] - 1, hand[1] - 1, 2, 3, C.chr1); g.rect(hand[0] + 2, hand[1] - 2, 2, 4, C.blu1);
  }

  g.outline(C.ink);

  // face
  if (s.chibi) { ownerFace(g, s, p, hx, hy); return g; }
  const ey = hy - 1;
  const eye = (x: number) => {
    if (p.eyes === 'normal') { g.set(x, ey, C.ink); g.set(x, ey + 1, C.ink); }
    else if (p.eyes === 'wide') { g.rect(x - 1, ey - 1, 3, 3, C.wht); g.set(x, ey, C.ink); }
    else if (p.eyes === 'closed') { g.hline(x - 1, x, ey + 1, C.ink); }
    else { g.set(x - 1, ey + 1, C.ink); g.set(x, ey, C.ink); g.set(x + 1, ey + 1, C.ink); }
  };
  eye(hx + 1); eye(hx + 4);
  if (s.glasses) { g.hline(hx, hx + 5, ey - 1, C.ink2); g.ring(hx + 1.5, ey + 0.5, 2, C.ink2); g.ring(hx + 4.5, ey + 0.5, 2, C.ink2); }
  const my = hy + 3;
  switch (p.mouth) {
    case 'smile': g.set(hx + 2, my, C.ink); g.set(hx + 3, my + 1, C.red2); g.set(hx + 4, my, C.ink); break;
    case 'grin': g.hline(hx + 1, hx + 4, my, C.ink); g.hline(hx + 2, hx + 3, my + 1, C.wht); break;
    case 'o': g.rect(hx + 2, my, 2, 2, C.red3); break;
    case 'laugh': g.rect(hx + 1, my, 4, 2, C.red3); g.hline(hx + 1, hx + 4, my, C.wht); break;
    case 'flat': g.hline(hx + 2, hx + 3, my, C.ink); break;
  }
  if (p.emote) { g.set(hx - 3, hy + 1, C.pink); g.set(hx + 5, hy + 2, C.pink); }
  return g;
}

/** Owner heads (Dave + Gerry): clean 3/4 chibi faces, readable at 1x. */
const mix = (a: number, b: number, t: number) => { const ch = (s: number) => Math.round(((a >> s) & 255) * (1 - t) + ((b >> s) & 255) * t); return (ch(16) << 16) | (ch(8) << 8) | ch(0); };
function ownerHair(g: Px, s: PersonSpec, hx: number, hy: number, RX: number, RY: number) {
  const inH = (x: number, y: number) => { const nx = (x + 0.5 - hx) / RX, ny = (y + 0.5 - hy) / RY; return nx * nx + ny * ny <= 1; };
  const H = s.hair, HL = mix(H, 0xffffff, 0.22);
  // ear on the back side
  g.rect(hx - 4, hy - 1, 2, 3, s.skin[1]); g.set(hx - 3, hy, s.skin[0]);
  if (s.hairStyle === 'bald') {
    // shiny scalp highlight
    g.hline(hx - 2, hx, hy - 6, 0xfff2e0); g.set(hx - 3, hy - 5, 0xfff2e0); g.set(hx - 1, hy - 5, 0xffe4cc);
  } else if (s.hairStyle === 'slick') {
    // faded sides (skin tinted by hair), dark top swept up and forward into a quiff
    const fade = mix(s.skin[1], H, 0.35);
    g.fill(hx - 6, hy - 4, hx - 1, hy - 1, (x, y) => inH(x, y) && !(x >= hx - 4 && x <= hx - 3 && y >= hy - 1) ? fade : -1);
    g.fill(hx - 7, hy - 10, hx + 7, hy - 3, (x, y) => {
      const nx = (x + 0.5 - hx) / (RX + 0.6), ny = (y + 0.5 - (hy - 2)) / (RY + 0.4);
      const cap = nx * nx + ny * ny <= 1 && y <= hy - 4 && x >= hx - 5;
      const quiff = y >= hy - 9 && y <= hy - 6 && x >= hx - 3 && x <= hx + 6 - Math.max(0, hy - 7 - y);
      return cap || quiff ? H : -1;
    });
    g.hline(hx - 2, hx + 3, hy - 8, HL); g.set(hx + 4, hy - 7, HL);
  }
  // beards (solid, trimmed — no dithering)
  const Bd = s.beard ? H : 0;
  if (s.beard === 'full') {
    g.fill(hx - 4, hy, hx + 6, hy + 8, (x, y) => {
      if (!inH(x, y)) return -1;
      if (y >= hy + 3) return x >= hx - 3 ? Bd : -1;            // jaw + chin
      if (x <= hx - 2 && x >= hx - 3) return Bd;                // sideburn
      if (y === hy + 2 && x >= hx + 1 && x <= hx + 5) return Bd; // moustache
      return -1;
    });
    g.hline(hx - 2, hx + 4, hy + 7, mix(Bd, 0x000000, 0.25));
  } else if (s.beard === 'goatee') {
    g.hline(hx + 1, hx + 5, hy + 2, Bd);                       // moustache
    g.set(hx + 1, hy + 3, Bd); g.set(hx + 1, hy + 4, Bd); g.set(hx + 5, hy + 3, Bd); g.set(hx + 5, hy + 4, Bd);
    g.rect(hx + 2, hy + 5, 3, 2, Bd);                          // chin
    g.fill(hx - 3, hy + 1, hx + 6, hy + 7, (x, y) => inH(x, y) && g.get(x, y) === s.skin[0] && (x + y) % 3 === 0 && (x < hx + 1 || y > hy + 4) && x > hx - 3 ? mix(s.skin[0], H, 0.3) : -1); // stubble
  }
}
function ownerFace(g: Px, s: PersonSpec, p: PersonPose, hx: number, hy: number) {
  const ey = hy - 1, brow = s.hairStyle === 'bald' ? mix(s.hair, 0x000000, 0.2) : s.hair;
  // brows (raised when surprised)
  const by = ey - (p.eyes === 'wide' ? 3 : 2);
  g.hline(hx, hx + 1, by, brow); g.hline(hx + 3, hx + 4, by, brow);
  const eye = (x: number) => {
    if (p.eyes === 'normal') { g.rect(x, ey, 1, 2, C.ink); }
    else if (p.eyes === 'wide') { g.rect(x - 1, ey - 1, 2, 3, C.wht); g.rect(x, ey, 1, 2, C.ink); }
    else if (p.eyes === 'closed') { g.hline(x - 1, x, ey + 1, C.ink); }
    else { g.set(x - 1, ey + 1, C.ink); g.set(x, ey, C.ink); g.set(x + 1, ey + 1, C.ink); }
  };
  eye(hx + 1); eye(hx + 4);
  g.set(hx + 5, hy + 1, s.skin[1]); // nose shade
  const my = hy + 3, lip = s.beard === 'full' ? s.skin[0] : C.ink;
  switch (p.mouth) {
    case 'smile': g.set(hx + 2, my, lip); g.hline(hx + 3, hx + 4, my + 1, lip); g.set(hx + 5, my, lip); break;
    case 'grin': g.hline(hx + 2, hx + 5, my, C.ink); g.hline(hx + 2, hx + 5, my + 1, C.wht); g.hline(hx + 3, hx + 4, my + 2, C.ink); break;
    case 'o': g.rect(hx + 3, my, 2, 2, C.red3); break;
    case 'laugh': g.rect(hx + 2, my, 4, 3, C.red3); g.hline(hx + 2, hx + 5, my, C.wht); break;
    case 'flat': g.hline(hx + 2, hx + 4, my + 1, lip); break;
  }
  if (p.emote) { g.set(hx - 1, hy + 1, C.pink); g.set(hx + 6, hy + 1, C.pink); }
}

export const PERSON_ANIMS: Record<string, { frames: PersonPose[]; fps: number; loop: boolean }> = (() => {
  const base: PersonPose = { stride: 0, bob: 0, armF: 0.1, armB: -0.1, mouth: 'smile', eyes: 'normal', lean: 0 };
  const P = (o: Partial<PersonPose>): PersonPose => ({ ...base, ...o });
  return {
    idle: { fps: 3, loop: true, frames: [P({}), P({ bob: 1 }), P({ bob: 1, eyes: 'closed' }), P({})] },
    walk: { fps: 8, loop: true, frames: [P({ stride: 1, armF: -0.5, armB: 0.5 }), P({ stride: 0, bob: -1 }), P({ stride: -1, armF: 0.5, armB: -0.5 }), P({ stride: 0, bob: -1 })] },
    shock: { fps: 10, loop: true, frames: [P({ armF: 2.6, armB: -2.6, mouth: 'o', eyes: 'wide', lean: -2, bob: -2 }), P({ armF: 2.8, armB: -2.8, mouth: 'o', eyes: 'wide', lean: -2, bob: -1 })] },
    laugh: { fps: 8, loop: true, frames: [P({ armF: 0.9, armB: -0.3, mouth: 'laugh', eyes: 'happy', lean: -2, emote: true }), P({ armF: 1.1, armB: -0.2, mouth: 'laugh', eyes: 'closed', lean: -3, bob: 1, emote: true })] },
    flee: { fps: 12, loop: true, frames: [P({ stride: 1, armF: 2.4, armB: -2.4, mouth: 'o', eyes: 'wide', lean: 2 }), P({ stride: 0, bob: -1, armF: 2.7, armB: -2.7, mouth: 'o', eyes: 'wide', lean: 2 }), P({ stride: -1, armF: 2.4, armB: -2.4, mouth: 'o', eyes: 'wide', lean: 2 }), P({ stride: 0, bob: -1, armF: 2.7, armB: -2.7, mouth: 'o', eyes: 'wide', lean: 2 })] },
    gesture: { fps: 4, loop: true, frames: [P({ armF: 1.4, mouth: 'grin' }), P({ armF: 1.6, mouth: 'grin', bob: -1 })] },
    wave: { fps: 6, loop: true, frames: [P({ armF: 2.6, mouth: 'grin' }), P({ armF: 3.0, mouth: 'grin' })] },
    cheer: { fps: 8, loop: true, frames: [P({ armF: 2.9, armB: -2.9, mouth: 'laugh', eyes: 'happy', bob: -2 }), P({ armF: 2.6, armB: -2.6, mouth: 'laugh', eyes: 'happy', bob: 0 })] },
    talk: { fps: 7, loop: true, frames: [P({ armF: 0.5, mouth: 'o' }), P({ armF: 0.6, mouth: 'smile', bob: -1 }), P({ armF: 0.9, mouth: 'grin' }), P({ armF: 0.6, mouth: 'smile' })] },
    point: { fps: 4, loop: true, frames: [P({ armF: 1.57, mouth: 'grin' }), P({ armF: 1.6, mouth: 'o', bob: -1 })] },
    pour: { fps: 4, loop: true, frames: [P({ armF: 1.25, mouth: 'grin', bottle: 'pour' }), P({ armF: 1.35, mouth: 'smile', bottle: 'pour', bob: -1 })] },
    drink: { fps: 3, loop: true, frames: [P({ armF: 2.5, mouth: 'flat', bottle: 'drink', eyes: 'closed', lean: -1 }), P({ armF: 2.6, mouth: 'flat', bottle: 'drink', eyes: 'closed', lean: -2 })] },
    hold: { fps: 3, loop: true, frames: [P({ armF: 0.9, mouth: 'grin', bottle: 'hold' }), P({ armF: 0.95, mouth: 'smile', bottle: 'hold', bob: -1 })] },
    toast: { fps: 6, loop: true, frames: [P({ armF: 2.8, mouth: 'laugh', bottle: 'hold', eyes: 'happy' }), P({ armF: 2.9, mouth: 'laugh', bottle: 'hold', eyes: 'happy', bob: -2 })] },
    clip: { fps: 2, loop: true, frames: [P({ armF: 0.9, mouth: 'flat', bottle: 'clip' }), P({ armF: 0.95, mouth: 'smile', bottle: 'clip' })] },
    catch: { fps: 8, loop: true, frames: [P({ armF: 2.3, armB: -1.2, mouth: 'o', eyes: 'wide', bottle: 'hold', lean: -1 }), P({ armF: 2.1, armB: -1, mouth: 'grin', bottle: 'hold' })] },
    browse: { fps: 2, loop: true, frames: [P({ armF: 1.0, mouth: 'flat' }), P({ armF: 1.1, mouth: 'flat', eyes: 'closed' }), P({ armF: 1.0, mouth: 'flat' }), P({ armF: 1.2, mouth: 'smile' })] },
  };
})();

export const PEOPLE: Record<string, PersonSpec> = {
  emp_sam: { skin: [C.sk1, C.sk2], hair: C.hr1, hairStyle: 'cap', capColor: C.red1, shirt: [C.wht, C.st1, C.st2], pants: [C.blk1, C.blk2], shoes: C.ink2, apron: true },
  emp_jo: { skin: [C.sk3, C.sk4], hair: C.hr0, hairStyle: 'bun', shirt: [C.blk0, C.blk1, C.blk2], pants: [C.blu3, C.ink2], shoes: C.wht, apron: true },
  cust_a: { skin: [C.sk0, C.sk1], hair: C.hr3, hairStyle: 'long', shirt: [C.red0, C.red1, C.red2], pants: [C.blu2, C.blu3], shoes: C.wht, bag: 'basket' },
  cust_b: { skin: [C.sk2, C.sk3], hair: C.hr0, hairStyle: 'curly', shirt: [C.lim0, C.lim2, C.lim3], pants: [C.cb2, C.cb3], shoes: C.ink2, bag: 'tote' },
  cust_c: { skin: [C.sk0, C.sk1], hair: C.hr4, hairStyle: 'short', shirt: [C.pur0, C.pur1, C.pur2], pants: [C.blk0, C.blk1], shoes: C.cola2, glasses: true, tall: 1 },
  cust_d: { skin: [C.sk1, C.sk2], hair: C.hr2, hairStyle: 'bun', shirt: [C.mng0, C.mng1, C.mng2], pants: [C.blu1, C.blu2], shoes: C.red1, tall: -1 },
  dave: { skin: [C.sk0, C.sk1], hair: C.hr1, hairStyle: 'bald', beard: 'full', shirt: [0xffffff, C.wl0, C.wl2], pants: [C.st3, C.st4], shoes: C.wd3, vest: true, tattoo: true, tall: 3, broad: true, chibi: true, tie: C.red2 },
  gerry: { skin: [C.sk0, C.sk1], hair: C.hr0, hairStyle: 'slick', beard: 'goatee', shirt: [C.blk0, C.blk1, C.blk2], pants: [0x4a6aa8, 0x2f4a7e], shoes: C.blk2, jacket: true, tall: 3, chibi: true },
  cust_e: { skin: [C.sk3, C.sk4], hair: C.hr0, hairStyle: 'short', shirt: [C.blu0, C.blu1, C.blu2], pants: [C.st2, C.st3], shoes: C.wht, tall: 2 },
  lab_tech: { skin: [C.sk1, C.sk2], hair: C.hr3, hairStyle: 'bun', shirt: [0xffffff, C.wl0, C.wl2], pants: [C.blk0, C.blk1], shoes: C.ink2, glasses: true },
  barista: { skin: [C.sk2, C.sk3], hair: C.hr1, hairStyle: 'curly', shirt: [C.crm1, C.crm2, C.crm3], pants: [C.blk1, C.blk2], shoes: C.cola2, apron: true },
  jogger: { skin: [C.sk0, C.sk1], hair: C.hr2, hairStyle: 'long', shirt: [C.pink, C.chr0, C.chr1], pants: [C.blk0, C.blk1], shoes: C.wht, tall: 1 },
  cyclist: { skin: [C.sk3, C.sk4], hair: C.hr0, hairStyle: 'cap', capColor: C.blu1, shirt: [C.lim0, C.lim1, C.lim2], pants: [C.blu2, C.blu3], shoes: C.ink2 },
};

export function buildPeopleSheet(key: string) {
  const spec = PEOPLE[key];
  const names = Object.keys(PERSON_ANIMS);
  const total = names.reduce((s, n) => s + PERSON_ANIMS[n].frames.length, 0);
  const sheet = new Px(PF_W * total, PF_H);
  const frames: { name: string; x: number; y: number }[] = [];
  let k = 0;
  for (const n of names) PERSON_ANIMS[n].frames.forEach((pose, i) => {
    sheet.blit(drawPerson(spec, pose), k * PF_W, 0);
    frames.push({ name: `${n}_${i}`, x: k * PF_W, y: 0 });
    k++;
  });
  return { sheet, frames };
}
