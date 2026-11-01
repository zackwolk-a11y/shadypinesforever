/**
 * Store customers, staff and street pedestrians — parametric 3/4-view people.
 * Frame 32x64, anchor bottom-centre (16, 63). ~2x the goose's height (art bible §2).
 */
import { C } from './palette';
import { Px } from './px';

export const PF_W = 32, PF_H = 64;
export interface PersonSpec {
  skin: [number, number];
  hair: number; hairStyle: 'short' | 'long' | 'bun' | 'curly' | 'cap' | 'bald';
  shirt: [number, number, number]; // hi, base, shade
  pants: [number, number];
  shoes: number;
  apron?: boolean; capColor?: number;
  bag?: 'basket' | 'tote' | null;
  glasses?: boolean;
  tall?: number; // -2..2
}
export interface PersonPose {
  stride: number; // -1..1
  bob: number;
  armF: number; armB: number; // arm angles (0 = down, + forward)
  mouth: 'smile' | 'o' | 'laugh' | 'flat' | 'grin';
  eyes: 'normal' | 'wide' | 'closed' | 'happy';
  lean: number;
  emote?: boolean;
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
  g.fill(tx - 6 + lean, shY, tx + 6 + lean, hipY + 1, (x, y) => {
    const t = (y - shY) / (hipY - shY);
    const w = 6 - t * 0.6;
    const xx = x - (tx + lean * (1 - t));
    if (xx < -w || xx > w) return -1;
    if (xx > w - 2.5) return s.shirt[2];
    if (xx < -w + 2 && y < shY + 6) return s.shirt[0];
    return s.shirt[1];
  });
  // collar / neckline
  g.rect(tx - 1 + lean, shY - 2, 3, 3, s.skin[1]);
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

  // head
  const hx = tx + lean + 1, hy = shY - 7;
  g.ellipse(hx, hy, 5, 6, s.skin[0]);
  g.fill(hx - 5, hy - 6, hx + 5, hy + 6, (x, y) => {
    const nx = (x + 0.5 - hx) / 5, ny = (y + 0.5 - hy) / 6;
    if (nx * nx + ny * ny > 1) return -1;
    return nx < -0.45 || ny > 0.7 ? s.skin[1] : -1;
  });
  g.set(hx + 5, hy + 1, s.skin[0]); // nose
  // hair
  const H = s.hair;
  switch (s.hairStyle) {
    case 'short': g.fill(hx - 6, hy - 7, hx + 5, hy, (x, y) => { const nx = (x + .5 - hx) / 5.6, ny = (y + .5 - hy + 1) / 6; return nx * nx + ny * ny <= 1 && (y < hy - 2 || x < hx - 2) ? H : -1; }); break;
    case 'long': g.fill(hx - 6, hy - 7, hx + 5, hy + 8, (x, y) => { const nx = (x + .5 - hx) / 5.8, ny = (y + .5 - hy + 1) / 6.2; const inHead = nx * nx + ny * ny <= 1; return (inHead && (y < hy - 2 || x < hx - 1)) || (x < hx - 1 && x > hx - 7 && y >= hy && y < hy + 9) ? H : -1; }); break;
    case 'bun': g.fill(hx - 6, hy - 7, hx + 5, hy, (x, y) => { const nx = (x + .5 - hx) / 5.6, ny = (y + .5 - hy + 1) / 6; return nx * nx + ny * ny <= 1 && (y < hy - 2 || x < hx - 2) ? H : -1; }); g.circle(hx - 4, hy - 6, 2.5, H); break;
    case 'curly': for (let k = 0; k < 9; k++) { const a = Math.PI * (0.9 + k * 0.14); g.circle(hx + Math.cos(a) * 4.8, hy - 1 + Math.sin(a) * 5.5, 2.2, H); } break;
    case 'cap': g.fill(hx - 6, hy - 7, hx + 5, hy - 2, (x, y) => { const nx = (x + .5 - hx) / 5.6, ny = (y + .5 - hy + 1) / 6; return nx * nx + ny * ny <= 1 ? (s.capColor ?? C.red1) : -1; }); g.rect(hx, hy - 3, 7, 2, s.capColor ?? C.red1); g.rect(hx - 6, hy - 2, 3, 4, H); break;
    case 'bald': g.set(hx - 2, hy - 5, C.wht); break;
  }
  if (s.hairStyle === 'cap' && s.apron) g.set(hx - 1, hy - 5, C.wht);

  // front arm
  const hand = arm(p.armF, tx + 3 + lean, true);
  if (s.bag === 'basket') {
    g.rect(hand[0] - 3, hand[1] + 1, 9, 6, C.red1); g.rect(hand[0] - 3, hand[1] + 1, 9, 1, C.red0);
    g.line(hand[0] - 2, hand[1] + 1, hand[0], hand[1] - 2, C.red2); g.line(hand[0] + 5, hand[1] + 1, hand[0] + 1, hand[1] - 2, C.red2);
    g.rect(hand[0] - 1, hand[1] - 1, 2, 3, C.chr1); g.rect(hand[0] + 2, hand[1] - 2, 2, 4, C.blu1);
  }

  g.outline(C.ink);

  // face
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
  cust_e: { skin: [C.sk3, C.sk4], hair: C.hr0, hairStyle: 'short', shirt: [C.blu0, C.blu1, C.blu2], pants: [C.st2, C.st3], shoes: C.wht, tall: 2 },
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
