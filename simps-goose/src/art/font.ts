/**
 * Original 5x7 pixel font, rendered to two bitmap fonts:
 *  - 'px'  : plain glyphs (6x9 cells), tint-able
 *  - 'pxo' : glyphs with a baked 1px ink outline + drop shadow (8x11 cells)
 * Lower-case input is upper-cased by the text helpers.
 */
import Phaser from 'phaser';
import { C } from './palette';
import { Px } from './px';

export const G: Record<string, string> = {
  A: '01110,10001,10001,11111,10001,10001,10001',
  B: '11110,10001,10001,11110,10001,10001,11110',
  C: '01110,10001,10000,10000,10000,10001,01110',
  D: '11110,10001,10001,10001,10001,10001,11110',
  E: '11111,10000,10000,11110,10000,10000,11111',
  F: '11111,10000,10000,11110,10000,10000,10000',
  G: '01110,10001,10000,10111,10001,10001,01111',
  H: '10001,10001,10001,11111,10001,10001,10001',
  I: '01110,00100,00100,00100,00100,00100,01110',
  J: '00111,00010,00010,00010,00010,10010,01100',
  K: '10001,10010,10100,11000,10100,10010,10001',
  L: '10000,10000,10000,10000,10000,10000,11111',
  M: '10001,11011,10101,10101,10001,10001,10001',
  N: '10001,11001,10101,10011,10001,10001,10001',
  O: '01110,10001,10001,10001,10001,10001,01110',
  P: '11110,10001,10001,11110,10000,10000,10000',
  Q: '01110,10001,10001,10001,10101,10010,01101',
  R: '11110,10001,10001,11110,10100,10010,10001',
  S: '01111,10000,10000,01110,00001,00001,11110',
  T: '11111,00100,00100,00100,00100,00100,00100',
  U: '10001,10001,10001,10001,10001,10001,01110',
  V: '10001,10001,10001,10001,10001,01010,00100',
  W: '10001,10001,10001,10101,10101,10101,01010',
  X: '10001,10001,01010,00100,01010,10001,10001',
  Y: '10001,10001,01010,00100,00100,00100,00100',
  Z: '11111,00001,00010,00100,01000,10000,11111',
  '0': '01110,10001,10011,10101,11001,10001,01110',
  '1': '00100,01100,00100,00100,00100,00100,01110',
  '2': '01110,10001,00001,00010,00100,01000,11111',
  '3': '11110,00001,00001,01110,00001,00001,11110',
  '4': '00010,00110,01010,10010,11111,00010,00010',
  '5': '11111,10000,11110,00001,00001,10001,01110',
  '6': '00110,01000,10000,11110,10001,10001,01110',
  '7': '11111,00001,00010,00100,01000,01000,01000',
  '8': '01110,10001,10001,01110,10001,10001,01110',
  '9': '01110,10001,10001,01111,00001,00010,01100',
  ' ': '00000,00000,00000,00000,00000,00000,00000',
  '!': '00100,00100,00100,00100,00100,00000,00100',
  '?': '01110,10001,00001,00010,00100,00000,00100',
  '.': '00000,00000,00000,00000,00000,00000,00100',
  ',': '00000,00000,00000,00000,00000,00100,01000',
  "'": '00100,00100,01000,00000,00000,00000,00000',
  '"': '01010,01010,00000,00000,00000,00000,00000',
  ':': '00000,00100,00000,00000,00000,00100,00000',
  ';': '00000,00100,00000,00000,00000,00100,01000',
  '-': '00000,00000,00000,01110,00000,00000,00000',
  '+': '00000,00100,00100,11111,00100,00100,00000',
  '=': '00000,00000,11111,00000,11111,00000,00000',
  '/': '00001,00010,00010,00100,01000,01000,10000',
  '(': '00010,00100,01000,01000,01000,00100,00010',
  ')': '01000,00100,00010,00010,00010,00100,01000',
  '&': '01100,10010,10100,01000,10101,10010,01101',
  '%': '11001,11010,00010,00100,01000,01011,10011',
  '#': '01010,11111,01010,01010,01010,11111,01010',
  '<': '00010,00100,01000,10000,01000,00100,00010',
  '>': '01000,00100,00010,00001,00010,00100,01000',
  '_': '00000,00000,00000,00000,00000,00000,11111',
  '*': '00000,01010,11111,11111,01110,00100,00000', // heart
  '^': '00100,01110,11111,00100,00100,00100,00000', // up arrow
  '~': '00000,00100,00110,11111,00110,00100,00000', // right arrow
  '@': '00000,01100,11110,11111,01111,00110,00000', // droplet-ish
  '$': '00100,01110,11111,11111,11111,01110,00000', // bubble/circle
};

export const FONT_CHARS = Object.keys(G).join('');

function build(scene: Phaser.Scene, key: string, outlined: boolean) {
  const cw = outlined ? 8 : 6, ch = outlined ? 11 : 9;
  const chars = FONT_CHARS;
  const perRow = 16;
  const rows = Math.ceil(chars.length / perRow);
  const p = new Px(cw * perRow, ch * rows);
  [...chars].forEach((chr, i) => {
    const gx = (i % perRow) * cw, gy = Math.floor(i / perRow) * ch;
    const rowsDef = G[chr].split(',');
    const ox = outlined ? 1 : 0, oy = outlined ? 1 : 1;
    const cell = new Px(cw, ch);
    rowsDef.forEach((r, y) => [...r].forEach((b, x) => { if (b === '1') cell.set(ox + x, oy + y, 0xffffff); }));
    if (outlined) {
      // drop shadow then outline
      const sh = new Px(cw, ch);
      rowsDef.forEach((r, y) => [...r].forEach((b, x) => { if (b === '1') sh.set(ox + x, oy + y + 1, C.ink); }));
      sh.blit(cell, 0, 0);
      sh.outline(C.ink, true);
      // re-colour: keep top rows bright, bottom slightly warm (gives a subtle gradient when tinted)
      p.blit(sh, gx, gy);
    } else p.blit(cell, gx, gy);
  });
  scene.textures.addCanvas(key + '_img', p.toCanvas());
  const data = Phaser.GameObjects.RetroFont.Parse(scene, {
    image: key + '_img',
    width: cw,
    height: ch,
    chars,
    charsPerRow: perRow,
    'offset.x': 0,
    'offset.y': 0,
    'spacing.x': 0,
    'spacing.y': 0,
    lineSpacing: 2,
  } as unknown as Phaser.Types.GameObjects.BitmapText.RetroFontConfig);
  // RetroFont uses the cell *width* as the base size; use the cell height so fontSize 9/11 = exact 1:1 pixels
  (data as unknown as { data: { size: number } }).data.size = ch;
  scene.cache.bitmapFont.add(key, data);
}

export function buildFonts(scene: Phaser.Scene) {
  build(scene, 'px', false);
  build(scene, 'pxo', true);
}

/** Helper: create bitmap text (auto upper-case, glyph-filtered). */
export function txt(scene: Phaser.Scene, x: number, y: number, s: string, opts: { outline?: boolean; color?: number; size?: number; align?: 'left' | 'center' | 'right' } = {}) {
  const font = opts.outline === false ? 'px' : 'pxo';
  const clean = s.toUpperCase().split('').map((ch) => (ch === '\n' || FONT_CHARS.includes(ch) ? ch : ' ')).join('');
  const t = scene.add.bitmapText(x, y, font, clean, (opts.outline === false ? 9 : 11) * (opts.size ?? 1));
  if (opts.color !== undefined) t.setTint(opts.color);
  const al = opts.align ?? 'left';
  t.setOrigin(al === 'center' ? 0.5 : al === 'right' ? 1 : 0, 0);
  if (al === 'center') t.setCenterAlign();
  if (al === 'right') t.setRightAlign();
  t.setLetterSpacing(opts.outline === false ? 0 : -2);
  return t;
}

/** Bake text straight into a Px buffer (for signage). */
export function pxText(g: import('./px').Px, x: number, y: number, s: string, col: number, scale = 1, spacing = 1) {
  let cx = x;
  for (const ch of s.toUpperCase()) {
    const def = G[ch] ?? G[' '];
    def.split(',').forEach((row, yy) => [...row].forEach((b, xx) => { if (b === '1') g.rect(cx + xx * scale, y + yy * scale, scale, scale, col); }));
    cx += (5 + spacing) * scale;
  }
  return cx - x;
}
export const pxTextWidth = (s: string, scale = 1, spacing = 1) => s.length * (5 + spacing) * scale - spacing * scale;
