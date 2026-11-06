// ============================================================================
// THE 333 DIMENSIONS OF MADNESS — core utilities, canvas, bitmap font
// ============================================================================
const W = 640, H = 360, TS = 16;
const canvas = document.getElementById('screen');
const ctx = canvas.getContext('2d');
ctx.imageSmoothingEnabled = false;
const G = { state: 'boot', t: 0, frame: 0, dt: 1 / 60, scale: 1, debug: false, paused: false };

const clamp = (v, a, b) => v < a ? a : v > b ? b : v;
const lerp = (a, b, t) => a + (b - a) * t;
const sign = v => v < 0 ? -1 : v > 0 ? 1 : 0;
const approach = (v, t, s) => v < t ? Math.min(v + s, t) : Math.max(v - s, t);
const dist = (ax, ay, bx, by) => Math.hypot(bx - ax, by - ay);
const ease = { out: t => 1 - (1 - t) * (1 - t), in: t => t * t, inOut: t => t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2,
  back: t => { const c = 1.7; return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); },
  elastic: t => t === 0 || t === 1 ? t : Math.pow(2, -10 * t) * Math.sin((t * 10 - .75) * 2.094) + 1 };
const overlap = (a, b) => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
function mulberry(seed) { return function () { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
let rnd = mulberry(333);
const R = (a = 1, b) => b === undefined ? rnd() * a : a + rnd() * (b - a);
const RI = (a, b) => Math.floor(R(a, b + 1));
const pick = arr => arr[Math.floor(rnd() * arr.length)];
function hashStr(s) { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
function makeCanvas(w, h) { const c = document.createElement('canvas'); c.width = Math.max(1, w | 0); c.height = Math.max(1, h | 0); const x = c.getContext('2d'); x.imageSmoothingEnabled = false; c.ctx = x; return c; }
function hsl(h, s, l, a = 1) { return `hsla(${h},${s}%,${l}%,${a})`; }

// ---------------------------------------------------------------- resize / scaling
function resize() {
  const vw = window.innerWidth, vh = window.innerHeight;
  let s = Math.min(vw / W, vh / H);
  if (s >= 2) s = Math.floor(s * 2) / 2; // crisp half-integer steps on big screens
  G.scale = s;
  canvas.style.width = Math.floor(W * s) + 'px';
  canvas.style.height = Math.floor(H * s) + 'px';
}
window.addEventListener('resize', resize); resize();

// ---------------------------------------------------------------- 5x7 bitmap font
const FONT_ROWS = {
  A: [14, 17, 17, 31, 17, 17, 17], B: [30, 17, 17, 30, 17, 17, 30], C: [14, 17, 16, 16, 16, 17, 14], D: [28, 18, 17, 17, 17, 18, 28],
  E: [31, 16, 16, 30, 16, 16, 31], F: [31, 16, 16, 30, 16, 16, 16], G: [14, 17, 16, 23, 17, 17, 15], H: [17, 17, 17, 31, 17, 17, 17],
  I: [14, 4, 4, 4, 4, 4, 14], J: [7, 2, 2, 2, 2, 18, 12], K: [17, 18, 20, 24, 20, 18, 17], L: [16, 16, 16, 16, 16, 16, 31],
  M: [17, 27, 21, 21, 17, 17, 17], N: [17, 25, 21, 19, 17, 17, 17], O: [14, 17, 17, 17, 17, 17, 14], P: [30, 17, 17, 30, 16, 16, 16],
  Q: [14, 17, 17, 17, 21, 18, 13], R: [30, 17, 17, 30, 20, 18, 17], S: [15, 16, 16, 14, 1, 1, 30], T: [31, 4, 4, 4, 4, 4, 4],
  U: [17, 17, 17, 17, 17, 17, 14], V: [17, 17, 17, 17, 17, 10, 4], W: [17, 17, 17, 21, 21, 21, 10], X: [17, 17, 10, 4, 10, 17, 17],
  Y: [17, 17, 10, 4, 4, 4, 4], Z: [31, 1, 2, 4, 8, 16, 31],
  0: [14, 17, 19, 21, 25, 17, 14], 1: [4, 12, 4, 4, 4, 4, 14], 2: [14, 17, 1, 2, 4, 8, 31], 3: [31, 2, 4, 2, 1, 17, 14], 4: [2, 6, 10, 18, 31, 2, 2],
  5: [31, 16, 30, 1, 1, 17, 14], 6: [6, 8, 16, 30, 17, 17, 14], 7: [31, 1, 2, 4, 8, 8, 8], 8: [14, 17, 17, 14, 17, 17, 14], 9: [14, 17, 17, 15, 1, 2, 12],
  a: [0, 0, 14, 1, 15, 17, 15], b: [16, 16, 22, 25, 17, 17, 30], c: [0, 0, 14, 16, 16, 17, 14], d: [1, 1, 13, 19, 17, 17, 15], e: [0, 0, 14, 17, 31, 16, 14],
  f: [6, 9, 8, 28, 8, 8, 8], g: [0, 15, 17, 17, 15, 1, 14], h: [16, 16, 22, 25, 17, 17, 17], i: [4, 0, 12, 4, 4, 4, 14], j: [2, 0, 6, 2, 2, 18, 12],
  k: [16, 16, 18, 20, 24, 20, 18], l: [12, 4, 4, 4, 4, 4, 14], m: [0, 0, 26, 21, 21, 17, 17], n: [0, 0, 22, 25, 17, 17, 17], o: [0, 0, 14, 17, 17, 17, 14],
  p: [0, 0, 30, 17, 30, 16, 16], q: [0, 0, 13, 19, 15, 1, 1], r: [0, 0, 22, 25, 16, 16, 16], s: [0, 0, 14, 16, 14, 1, 30], t: [8, 8, 28, 8, 8, 9, 6],
  u: [0, 0, 17, 17, 17, 19, 13], v: [0, 0, 17, 17, 17, 10, 4], w: [0, 0, 17, 17, 21, 21, 10], x: [0, 0, 17, 10, 4, 10, 17], y: [0, 0, 17, 17, 15, 1, 14], z: [0, 0, 31, 2, 4, 8, 31],
  ' ': [0, 0, 0, 0, 0, 0, 0], '!': [4, 4, 4, 4, 4, 0, 4], '"': [10, 10, 10, 0, 0, 0, 0], '#': [10, 10, 31, 10, 31, 10, 10], '$': [4, 15, 20, 14, 5, 30, 4],
  '%': [24, 25, 2, 4, 8, 19, 3], '&': [12, 18, 20, 8, 21, 18, 13], "'": [12, 4, 8, 0, 0, 0, 0], '(': [2, 4, 8, 8, 8, 4, 2], ')': [8, 4, 2, 2, 2, 4, 8],
  '*': [0, 4, 21, 14, 21, 4, 0], '+': [0, 4, 4, 31, 4, 4, 0], ',': [0, 0, 0, 0, 12, 4, 8], '-': [0, 0, 0, 31, 0, 0, 0], '.': [0, 0, 0, 0, 0, 12, 12],
  '/': [0, 1, 2, 4, 8, 16, 0], ':': [0, 12, 12, 0, 12, 12, 0], ';': [0, 12, 12, 0, 12, 4, 8], '<': [2, 4, 8, 16, 8, 4, 2], '=': [0, 0, 31, 0, 31, 0, 0],
  '>': [8, 4, 2, 1, 2, 4, 8], '?': [14, 17, 1, 2, 4, 0, 4], '@': [14, 17, 1, 13, 21, 21, 14], '[': [14, 8, 8, 8, 8, 8, 14], '\\': [0, 16, 8, 4, 2, 1, 0],
  ']': [14, 2, 2, 2, 2, 2, 14], '^': [4, 10, 17, 0, 0, 0, 0], '_': [0, 0, 0, 0, 0, 0, 31], '`': [8, 4, 2, 0, 0, 0, 0], '{': [2, 4, 4, 8, 4, 4, 2],
  '|': [4, 4, 4, 4, 4, 4, 4], '}': [8, 4, 4, 2, 4, 4, 8], '~': [0, 0, 8, 21, 2, 0, 0],
  '♪': [6, 5, 4, 4, 12, 28, 8], '♥': [0, 10, 31, 31, 14, 4, 0], '★': [4, 4, 31, 14, 14, 27, 17], '►': [16, 24, 28, 30, 28, 24, 16], '◄': [1, 3, 7, 15, 7, 3, 1],
  '▲': [0, 4, 4, 14, 14, 31, 0], '▼': [0, 31, 14, 14, 4, 4, 0], '•': [0, 0, 14, 14, 14, 0, 0], '…': [0, 0, 0, 0, 0, 0, 21], '☠': [14, 31, 21, 31, 14, 10, 0]
};
const FONT = { atlas: null, map: {}, cache: {} };
(function buildFont() {
  const chars = Object.keys(FONT_ROWS);
  const c = makeCanvas(chars.length * 6, 8);
  c.ctx.fillStyle = '#fff';
  chars.forEach((ch, i) => { FONT.map[ch] = i; FONT_ROWS[ch].forEach((row, y) => { for (let x = 0; x < 5; x++) if (row & (16 >> x)) c.ctx.fillRect(i * 6 + x, y, 1, 1); }); });
  FONT.atlas = c;
})();
function fontTinted(color) {
  let a = FONT.cache[color]; if (a) return a;
  a = makeCanvas(FONT.atlas.width, 8);
  a.ctx.drawImage(FONT.atlas, 0, 0); a.ctx.globalCompositeOperation = 'source-in'; a.ctx.fillStyle = color; a.ctx.fillRect(0, 0, a.width, 8);
  return FONT.cache[color] = a;
}
function textWidth(s, sc = 1) { return s.length * 6 * sc - sc; }
// text(str,x,y,{color,scale,align,shadow,outline})
function text(s, x, y, o = {}) {
  s = String(s); const sc = o.scale || 1, col = o.color || '#fff';
  let w = textWidth(s, sc);
  if (o.align === 'center') x -= w / 2 | 0; else if (o.align === 'right') x -= w;
  x = Math.round(x); y = Math.round(y);
  if (o.outline) { const oc = fontTinted(o.outline === true ? '#000' : o.outline); for (const [dx, dy] of [[-1, 0], [1, 0], [0, -1], [0, 1], [-1, -1], [1, 1], [1, -1], [-1, 1]]) drawStr(oc, s, x + dx * sc, y + dy * sc, sc, o.wave); }
  else if (o.shadow !== false) drawStr(fontTinted(o.shadow || '#000'), s, x + sc, y + sc, sc, o.wave);
  drawStr(fontTinted(col), s, x, y, sc, o.wave);
  return w;
}
function drawStr(atlas, s, x, y, sc, wave) {
  for (let i = 0; i < s.length; i++) {
    const idx = FONT.map[s[i]]; if (idx === undefined) { x += 6 * sc; continue; }
    const oy = wave ? Math.round(Math.sin(G.t * 8 + i * .6) * wave) : 0;
    ctx.drawImage(atlas, idx * 6, 0, 5, 7, x, y + oy, 5 * sc, 7 * sc); x += 6 * sc;
  }
}
function wrapText(s, maxChars) {
  const words = s.split(' '), lines = []; let cur = '';
  for (const w of words) { if ((cur + ' ' + w).trim().length > maxChars) { if (cur) lines.push(cur); cur = w; } else cur = (cur + ' ' + w).trim(); }
  if (cur) lines.push(cur); return lines;
}
// pixel panel with bevel (UI frames)
function panel(x, y, w, h, o = {}) {
  x |= 0; y |= 0; w |= 0; h |= 0;
  ctx.fillStyle = o.border || '#0b0610'; ctx.fillRect(x - 2, y - 2, w + 4, h + 4);
  ctx.fillStyle = o.rim || '#5be33c'; ctx.fillRect(x - 1, y - 1, w + 2, h + 2);
  ctx.fillStyle = o.bg || '#1b0f26'; ctx.fillRect(x, y, w, h);
  ctx.fillStyle = o.hi || 'rgba(255,255,255,.08)'; ctx.fillRect(x, y, w, 2);
  ctx.fillStyle = 'rgba(0,0,0,.25)'; ctx.fillRect(x, y + h - 2, w, 2);
}
