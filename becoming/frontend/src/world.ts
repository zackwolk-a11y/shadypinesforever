// Typed access to the exported world (tools/export_world.py). Never edited by hand.
import raw from "./generated/world.json";

export interface Door { building: string; name: string; kind: string; owner: string | null; x: number; y: number; interior: string }
export interface Zone { id: string; name: string; kind: string; privacy: string; rects: number[][] }
export interface Resident {
  id: string; name: string; title: string; tension: string; reasoning: string; disclaimer: string; interests: string[];
  home: { building: string; x: number; y: number }; portrait: string; frames: Record<string, number>;
}

export const WORLD = raw as unknown as {
  width: number; height: number; art: { image: string; px_per_tile: number };
  walkable: string[]; doors: Door[]; zones: Zone[]; residents: Resident[];
  founder: { id: string; name: string; title: string; note: string; portrait: string; frames: Record<string, number> };
};

export const T = WORLD.art.px_per_tile;

/** Standalone builds embed every image as a data: URI in window.__ASSETS. */
export function assetUrl(path: string): string {
  const embedded = (window as any).__ASSETS as Record<string, string> | undefined;
  return embedded?.[path] ?? path;
}

export function walkable(tx: number, ty: number): boolean {
  return ty >= 0 && ty < WORLD.height && tx >= 0 && tx < WORLD.width && WORLD.walkable[ty][tx] === "1";
}

export function doorAt(tx: number, ty: number): Door | undefined {
  return WORLD.doors.find((d) => d.x === tx && d.y === ty);
}

export function zoneCenter(z: Zone): { x: number; y: number } {
  const [x0, y0, x1, y1] = z.rects[0];
  return { x: Math.round((x0 + x1) / 2), y: Math.round((y0 + y1) / 2) };
}

/** 4-neighbour A* over the walkable grid. Returns tiles excluding the start, or null. */
export function findPath(sx: number, sy: number, gx: number, gy: number): { x: number; y: number }[] | null {
  if (!walkable(gx, gy)) return null;
  const key = (x: number, y: number) => y * WORLD.width + x;
  const open = new Map<number, { x: number; y: number; g: number; f: number }>();
  const came = new Map<number, number>();
  const gScore = new Map<number, number>();
  const h = (x: number, y: number) => Math.abs(x - gx) + Math.abs(y - gy);
  open.set(key(sx, sy), { x: sx, y: sy, g: 0, f: h(sx, sy) });
  gScore.set(key(sx, sy), 0);
  while (open.size) {
    let best: { x: number; y: number; g: number; f: number } | undefined;
    for (const n of open.values()) if (!best || n.f < best.f) best = n;
    const cur = best!;
    if (cur.x === gx && cur.y === gy) {
      const path: { x: number; y: number }[] = [];
      let k = key(gx, gy);
      while (came.has(k)) { path.unshift({ x: k % WORLD.width, y: Math.floor(k / WORLD.width) }); k = came.get(k)!; }
      return path;
    }
    open.delete(key(cur.x, cur.y));
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      const nx = cur.x + dx, ny = cur.y + dy;
      if (!walkable(nx, ny)) continue;
      const g = cur.g + 1, k = key(nx, ny);
      if (g < (gScore.get(k) ?? Infinity)) {
        gScore.set(k, g); came.set(k, key(cur.x, cur.y));
        open.set(k, { x: nx, y: ny, g, f: g + h(nx, ny) });
      }
    }
  }
  return null;
}
