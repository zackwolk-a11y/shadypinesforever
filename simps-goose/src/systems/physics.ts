/**
 * Small deterministic platformer physics (AABB), run at a fixed 120 Hz step.
 * Supports solid blocks, one-way platforms, and moving one-way platforms (bubbles,
 * foam) that carry whatever stands on them.
 */
export interface Platform {
  x: number; y: number; w: number; h: number;
  kind: 'solid' | 'oneway';
  dx: number; dy: number; // displacement applied this step (movers)
  active: boolean;
  tag?: string;
  owner?: unknown;
  onLand?: (b: Body) => void;
}
export class Body {
  x = 0; y = 0; w = 14; h = 20;
  vx = 0; vy = 0;
  onGround = false;
  ground: Platform | null = null;
  hitWall = 0; // -1 left, 1 right
  hitHead = false;
  dropThrough = 0;
  constructor(x: number, y: number, w: number, h: number) { this.x = x; this.y = y; this.w = w; this.h = h; }
  get cx() { return this.x + this.w / 2; }
  get bottom() { return this.y + this.h; }
}
export const overlap = (a: { x: number; y: number; w: number; h: number }, b: { x: number; y: number; w: number; h: number }) =>
  a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;

export class PhysicsWorld {
  platforms: Platform[] = [];
  add(p: Omit<Platform, 'dx' | 'dy' | 'active'> & Partial<Platform>): Platform {
    const pl: Platform = { dx: 0, dy: 0, active: true, ...p } as Platform;
    this.platforms.push(pl);
    return pl;
  }
  remove(p: Platform) { const i = this.platforms.indexOf(p); if (i >= 0) this.platforms.splice(i, 1); p.active = false; }

  move(b: Body, dt: number) {
    // ride the platform we stood on last step
    const g = b.ground;
    if (g && g.active && b.onGround) {
      b.x += g.dx;
      if (g.dy !== 0) b.y = g.y - b.h;
    }
    b.hitWall = 0; b.hitHead = false;
    // ---- X
    b.x += b.vx * dt;
    for (const p of this.platforms) {
      if (!p.active || p.kind !== 'solid') continue;
      if (!overlap(b, p)) continue;
      const fromLeft = b.x + b.w / 2 < p.x + p.w / 2;
      if (fromLeft) { b.x = p.x - b.w; b.hitWall = 1; } else { b.x = p.x + p.w; b.hitWall = -1; }
      if ((b.vx > 0 && fromLeft) || (b.vx < 0 && !fromLeft)) b.vx = 0;
    }
    // ---- Y
    const prevBottom = b.y + b.h;
    b.y += b.vy * dt;
    b.onGround = false;
    let ground: Platform | null = null;
    for (const p of this.platforms) {
      if (!p.active) continue;
      if (p.kind === 'solid') {
        if (!overlap(b, p)) continue;
        if (b.vy >= 0 && prevBottom <= p.y + Math.max(2, b.vy * dt + 1)) {
          b.y = p.y - b.h; b.vy = 0; b.onGround = true; ground = p;
        } else if (b.vy < 0) {
          b.y = p.y + p.h; b.vy = 0; b.hitHead = true;
        } else {
          // embedded (e.g. spawned inside) – push up
          b.y = p.y - b.h; b.onGround = true; ground = p;
        }
      } else {
        if (b.dropThrough > 0) continue;
        if (b.vy < 0 && p.dy >= 0) continue;
        const bx0 = b.x + 2, bx1 = b.x + b.w - 2;
        if (bx1 <= p.x || bx0 >= p.x + p.w) continue;
        const prevTop = p.y - p.dy;
        const nb = b.y + b.h;
        if (prevBottom <= prevTop + 1.5 && nb >= p.y - 0.01) {
          b.y = p.y - b.h; b.vy = Math.min(b.vy, 0); if (b.vy < 0 && p.dy < 0) b.vy = 0;
          b.onGround = true; ground = p;
        }
      }
    }
    if (ground && ground !== b.ground) ground.onLand?.(b);
    b.ground = ground;
    if (b.dropThrough > 0) b.dropThrough -= dt;
  }

  /** Highest surface top under point (for shadows). */
  surfaceBelow(x: number, y: number, ignore?: unknown): number {
    let best = Infinity;
    for (const p of this.platforms) {
      if (!p.active || p.owner === ignore) continue;
      if (x < p.x || x > p.x + p.w) continue;
      if (p.y >= y - 1 && p.y < best) best = p.y;
    }
    return best;
  }
}
