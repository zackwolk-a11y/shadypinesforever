/**
 * STORE LEVEL DEFINITION (data-driven). All gameplay geometry for the slice lives here.
 * Coordinates are world pixels; FLOOR is the walkable floor top.
 */
export const WORLD_W = 2440;
export const WORLD_H = 360;
export const FLOOR = 330;
export const CEIL = 26;
export const BG_PARALLAX = 0.9;
export const VIEW_W = 480, VIEW_H = 270;
/** where a world-x lands on the parallax back-wall canvas when the camera is centred on it */
export const bgX = (wx: number) => Math.round(VIEW_W / 2 + (wx - VIEW_W / 2) * BG_PARALLAX);
export const BG_W = bgX(WORLD_W) + VIEW_W / 2 + 8;

export type SolidKind = 'solid' | 'oneway';
export interface SolidDef { x: number; y: number; w: number; h: number; kind: SolidKind; tag?: string }

export const L = {
  door: { x: 30 },
  baskets: { x: 104 },
  plantA: { x: 160 },
  crate1: { x: 300, w: 34, h: 26 },
  crate2: { x: 356, w: 34, h: 52 },
  gondola1: { x: 420, w: 112, h: 74 },
  crateTower: { x: 572, w: 34, h: 78 },
  wallShelf: { x: 626, y: 212, w: 70 },
  gondola2: { x: 716, w: 112, h: 74 },
  fridges: { x: 862, w: 200 },
  checkout: { x: 1110, w: 112, h: 44 },
  sample: { x: 1390, w: 104, h: 40 },
  boxWall: { x: 1580, cols: 2, rows: 4, bw: 24, bh: 22 },
  fountain: { x: 1772, w: 128, h: 168 },
  noHonkSign: { x: 1700 },
  vents: [1950, 2050],
  mezz: { x: 2160, y: 168, w: 236 },
  valve: { x: 2330 },
  skylight: { x: 2290 },
  labDoor: { x: 2260 },
  plantB: { x: 2395 },
};

export function solids(): SolidDef[] {
  const s: SolidDef[] = [
    { x: -40, y: 0, w: 52, h: WORLD_H, kind: 'solid', tag: 'wallL' },
    { x: WORLD_W - 12, y: 0, w: 60, h: WORLD_H, kind: 'solid', tag: 'wallR' },
    { x: -40, y: FLOOR, w: WORLD_W + 80, h: 60, kind: 'solid', tag: 'floor' },
    { x: -40, y: -40, w: WORLD_W + 80, h: CEIL + 40, kind: 'solid', tag: 'ceiling' },
    { x: L.crate1.x, y: FLOOR - L.crate1.h, w: L.crate1.w, h: L.crate1.h, kind: 'solid', tag: 'crate1' },
    { x: L.crate2.x, y: FLOOR - L.crate2.h, w: L.crate2.w, h: L.crate2.h, kind: 'solid', tag: 'crate2' },
    { x: L.gondola1.x, y: FLOOR - L.gondola1.h, w: L.gondola1.w, h: 6, kind: 'oneway', tag: 'gondola1' },
    { x: L.crateTower.x, y: FLOOR - L.crateTower.h, w: L.crateTower.w, h: L.crateTower.h, kind: 'solid', tag: 'tower' },
    { x: L.wallShelf.x, y: L.wallShelf.y, w: L.wallShelf.w, h: 5, kind: 'oneway', tag: 'wallShelf' },
    { x: L.gondola2.x, y: FLOOR - L.gondola2.h, w: L.gondola2.w, h: 6, kind: 'oneway', tag: 'gondola2' },
    { x: L.checkout.x, y: FLOOR - L.checkout.h, w: L.checkout.w, h: L.checkout.h, kind: 'solid', tag: 'checkout' },
    { x: L.sample.x, y: FLOOR - L.sample.h, w: L.sample.w, h: L.sample.h, kind: 'solid', tag: 'sample' },
    { x: L.mezz.x, y: L.mezz.y, w: L.mezz.w, h: 8, kind: 'oneway', tag: 'mezz' },
  ];
  return s;
}
