// ============================================================================
// Environment art (cartoon overhaul): bright painted parallax scenes, chunky
// outlined 24px tile materials, oversized props — each world has its own look.
// Everything here is baked once per level into canvases (the asset pipeline
// for environments), then composited at runtime.
// ============================================================================
const HTS = TS * ZOOM; // tile art resolution (24px)
const INK = '#1a0b22';
const THEMES = {
  stage:     { sky: ['#5a1a8a', '#ff5bb0'], g: ['#c8742a', '#f0a050', '#7a3a10'], top: '#ffcc33', pat: 'planks', edge: 'trim', hz: 'electric', light: 'spot', scene: 'stage', props: ['amp', 'mic', 'drum', 'speaker'] },
  backstage: { sky: ['#1a6a8a', '#ffb070'], g: ['#3a3a48', '#6a6a7a', '#1a1a24'], top: '#c8c8d8', pat: 'cases', edge: 'trim', hz: 'electric', light: 'spot', scene: 'backstage', props: ['case', 'amp', 'puppet', 'poster'] },
  meadow:    { sky: ['#3aa0ff', '#c8f0ff'], g: ['#8a4a1a', '#b86a2a', '#5a2a08'], top: '#5ae03a', pat: 'dirt', edge: 'grass', hz: 'spikes', light: 'sun', scene: 'meadow', props: ['flower', 'sunflower', 'fence', 'hay', 'mushroom'] },
  castle:    { sky: ['#5a3aa0', '#ffa0d0'], g: ['#6a4aa0', '#9a7ad0', '#3a2a60'], top: '#7ad04a', pat: 'bricks', edge: 'moss', hz: 'spikes', light: 'none', scene: 'castle', props: ['candle', 'books', 'potion', 'mushroom'] },
  theater:   { sky: ['#8a0a2a', '#ff6a4a'], g: ['#a0602a', '#d89050', '#5a2a08'], top: '#ffcc33', pat: 'planks', edge: 'trim', hz: 'spikes', light: 'spot', scene: 'theater', props: ['puppet', 'mask', 'drum'] },
  factory:   { sky: ['#ff9a2a', '#fff07a'], g: ['#e04a8a', '#ff8ac0', '#902a5a'], top: '#ffe14d', pat: 'metal', edge: 'goo', goo: '#fff4f8', hz: 'acid', light: 'none', scene: 'factory', props: ['cereal', 'bottle', 'donut'] },
  market:    { sky: ['#2ad0c0', '#fff0a0'], g: ['#ff8ab0', '#ffffff', '#c04a7a'], top: '#2ad0c0', pat: 'checker', edge: 'trim', hz: 'acid', light: 'none', scene: 'market', props: ['cereal', 'cart', 'sign', 'donut'] },
  farm:      { sky: ['#ff6a2a', '#ffe07a'], g: ['#9a5a2a', '#c8823a', '#5a2a10'], top: '#ffd860', pat: 'dirt', edge: 'hay', hz: 'spikes', light: 'sun', scene: 'farm', props: ['hay', 'fence', 'sunflower', 'candle'] },
  canal:     { sky: ['#4ab0ff', '#e0f8ff'], g: ['#3a6ad0', '#6a9aff', '#1a3a8a'], top: '#ffffff', pat: 'bricks', edge: 'goo', goo: '#ffffff', hz: 'milk', light: 'none', scene: 'canal', props: ['bottle', 'cereal', 'flower'] },
  mech:      { sky: ['#c02a2a', '#ffb04a'], g: ['#8a9ab0', '#c8d8e8', '#4a5a70'], top: '#ffcc33', pat: 'metal', edge: 'hazard', hz: 'milk', light: 'alarm', scene: 'mech', props: ['bottle', 'gear', 'pipe'] },
  forest:    { sky: ['#ff4ad0', '#ffd0f0'], g: ['#6a2a9a', '#9a5ad0', '#3a1060'], top: '#2affd0', pat: 'candy', edge: 'grass', grass: '#2affd0', hz: 'spikes', light: 'psy', scene: 'forest', props: ['mushroom', 'eyeplant', 'flower'] },
  mansion:   { sky: ['#2a2a8a', '#7a5aff'], g: ['#8a3a3a', '#c86a5a', '#4a1a1a'], top: '#ffd23a', pat: 'checker', edge: 'trim', hz: 'electric', light: 'lightning', scene: 'mansion', props: ['candle', 'coil', 'portrait'] },
  void:      { sky: ['#1a0a5a', '#ff3ad0'], g: ['#2a1a6a', '#5a3ad0', '#100430'], top: '#3affff', pat: 'checker', edge: 'neon', hz: 'void', light: 'psy', scene: 'void', props: ['door', 'eyeplant'] },
  felt:      { sky: ['#4ad0ff', '#fff07a'], g: ['#ff6aa0', '#ffa0c8', '#c03a70'], top: '#6aff6a', pat: 'felt', edge: 'stitch', hz: 'spikes', light: 'sun', scene: 'felt', props: ['button', 'yarn', 'flower'] },
  devourer:  { sky: ['#2a0050', '#ff3a8a'], g: ['#4a1a6a', '#8a3ab0', '#200a30'], top: '#ff5bd1', pat: 'candy', edge: 'neon', hz: 'void', light: 'psy', scene: 'devourer', props: ['eyeplant', 'door'] },
  circus:    { sky: ['#2a1a7a', '#ff7ad0'], g: ['#e02a3a', '#ffffff', '#8a0a1a'], top: '#ffcc33', pat: 'stripes', edge: 'trim', hz: 'spikes', light: 'spot', scene: 'circus', props: ['balloon', 'barrel', 'popcorn', 'sign'] },
  park:      { sky: ['#ff7a3a', '#ffe0a0'], g: ['#b0703a', '#e0a060', '#6a3a10'], top: '#ff3a7a', pat: 'planks', edge: 'bulbs', hz: 'spikes', light: 'sun', scene: 'park', props: ['balloon', 'popcorn', 'sign'] },
  fishery:   { sky: ['#0a8a9a', '#a0fff0'], g: ['#2a9aa0', '#6ad8d0', '#0a5a60'], top: '#ffe14d', pat: 'metal', edge: 'goo', goo: '#a0ff6a', hz: 'acid', light: 'none', scene: 'fishery', props: ['barrel', 'fishsign', 'pipe'] },
  prison:    { sky: ['#4a5a8a', '#c8b0ff'], g: ['#8a8aa0', '#c0c0d8', '#4a4a60'], top: '#ffcc33', pat: 'stone', edge: 'hazard', hz: 'electric', light: 'search', scene: 'prison', props: ['sign', 'barrel', 'poster'] },
  bigtop:    { sky: ['#c01a3a', '#ffd23a'], g: ['#ffcc33', '#fff07a', '#b07a10'], top: '#e02a3a', pat: 'stripes', edge: 'trim', hz: 'spikes', light: 'spot', scene: 'bigtop', props: ['barrel', 'balloon', 'popcorn'] },
  junk:      { sky: ['#5ac0a0', '#fff0a0'], g: ['#7a6a5a', '#a89a8a', '#3a3028'], top: '#9ae05a', pat: 'junk', edge: 'grass', grass: '#9ae05a', hz: 'acid', light: 'sun', scene: 'junk', props: ['tire', 'fridge', 'tv', 'bag'] },
  derby:     { sky: ['#ff9a2a', '#fff0a0'], g: ['#6a5a4a', '#9a8a7a', '#2a2018'], top: '#ffcc33', pat: 'junk', edge: 'hazard', hz: 'spikes', light: 'sun', scene: 'derby', props: ['tire', 'sign', 'tv'] },
  assembly:  { sky: ['#2a8a4a', '#c8ffa0'], g: ['#5a6a7a', '#8a9aaa', '#2a3a4a'], top: '#7fff3a', pat: 'metal', edge: 'neon', hz: 'electric', light: 'alarm', scene: 'assembly', props: ['gear', 'pipe', 'tv'] },
  heap:      { sky: ['#a05ac0', '#ffd07a'], g: ['#7a6a4a', '#a89a6a', '#3a3020'], top: '#ffd23a', pat: 'junk', edge: 'goo', goo: '#ffd23a', hz: 'acid', light: 'none', scene: 'junk', props: ['tire', 'fridge', 'tv'] },
  rock:      { sky: ['#1a0a5a', '#c03aff'], g: ['#2a2a3a', '#4a4a60', '#10101a'], top: '#7fff3a', pat: 'grille', edge: 'neon', hz: 'electric', light: 'disco', scene: 'rock', props: ['amp', 'mic', 'drum', 'speaker'] },
  final:     { sky: ['#3a0040', '#ff3a6a'], g: ['#5a1a4a', '#9a3a7a', '#2a0a20'], top: '#ff3a6a', pat: 'grille', edge: 'neon', hz: 'void', light: 'disco', scene: 'rock', props: ['amp', 'speaker', 'eyeplant'] }
};
const HZCOL = { acid: ['#9aff3a', '#3ab01a'], milk: ['#ffffff', '#dce4ff'], void: ['#ff5bff', '#6a1aa0'], electric: ['#9affff', '#2a7ad0'], spikes: ['#7ad8ff', '#2a8ad0'], lava: ['#ffb02a', '#e03a0a'] };
// ---------------------------------------------------------------- painter helpers (outlined, shaded, cartoon)
const PP = {
  path(c, pts) { c.beginPath(); pts.forEach((p, i) => i ? c.lineTo(p[0], p[1]) : c.moveTo(p[0], p[1])); c.closePath(); },
  fillOut(c, fill, ol = 3) { if (ol) { c.lineJoin = 'round'; c.strokeStyle = INK; c.lineWidth = ol * 2; c.stroke(); } c.fillStyle = fill; c.fill(); },
  poly(c, pts, fill, ol = 3) { PP.path(c, pts); PP.fillOut(c, fill, ol); },
  ell(c, x, y, rx, ry, fill, ol = 3) { c.beginPath(); c.ellipse(x, y, Math.max(1, rx), Math.max(1, ry), 0, 0, 7); PP.fillOut(c, fill, ol); },
  rect(c, x, y, w, h, fill, ol = 3, r = 0) { c.beginPath(); if (r && c.roundRect) c.roundRect(x, y, w, h, r); else c.rect(x, y, w, h); PP.fillOut(c, fill, ol); },
  grad(c, x0, y0, x1, y1, stops) { const g = c.createLinearGradient(x0, y0, x1, y1); stops.forEach((s, i) => g.addColorStop(i / (stops.length - 1), s)); return g; },
  hill(c, w, base, amp, freq, phase, fill, ol = 3, rough = 0, r) { c.beginPath(); c.moveTo(-10, H + 10); for (let x = -10; x <= w + 10; x += 8) c.lineTo(x, base - Math.abs(Math.sin((x / w) * Math.PI * 2 * freq + phase)) * amp - (rough ? Math.sin(x * .3) * rough : 0)); c.lineTo(w + 10, H + 10); c.closePath(); PP.fillOut(c, fill, ol); },
  cloud(c, x, y, s, col = '#ffffff') { const blobs = [[0, 0, 26], [24, -10, 22], [46, 2, 24], [20, 8, 22]]; c.beginPath(); for (const [bx, by, br] of blobs) { c.moveTo(x + bx * s + br * s, y + by * s); c.arc(x + bx * s, y + by * s, br * s, 0, 7); } c.lineWidth = 6; c.strokeStyle = INK; c.stroke(); c.fillStyle = col; c.fill(); c.fillStyle = 'rgba(160,190,255,.45)'; c.beginPath(); c.ellipse(x + 24 * s, y + 16 * s, 44 * s, 8 * s, 0, 0, 7); c.fill(); c.fillStyle = 'rgba(255,255,255,.9)'; c.beginPath(); c.ellipse(x - 6 * s, y - 10 * s, 9 * s, 5 * s, -.4, 0, 7); c.fill(); },
  star(c, x, y, r, col) { const pts = []; for (let i = 0; i < 10; i++) { const a = i / 10 * Math.PI * 2 - Math.PI / 2, rr = i % 2 ? r * .45 : r; pts.push([x + Math.cos(a) * rr, y + Math.sin(a) * rr]); } PP.poly(c, pts, col, 2); },
  wobblyHouse(c, x, y, w, h, wall, roof, r) { const lean = (r() - .5) * 10; PP.poly(c, [[x, y], [x + lean, y - h], [x + w + lean, y - h], [x + w, y]], wall); PP.poly(c, [[x - 8 + lean, y - h + 4], [x + w / 2 + lean * 1.6, y - h - w * .7], [x + w + 8 + lean, y - h + 4]], roof); for (let i = 0; i < 2; i++) PP.rect(c, x + 8 + i * (w - 28) + lean * .5, y - h * .7, 12, 14, '#ffe9a0', 2); PP.rect(c, x + w / 2 - 7 + lean * .2, y - 22, 14, 22, '#6a3a1a', 2); },
  dots(c, x, y, w, h, n, cols, r) { for (let i = 0; i < n; i++) { c.fillStyle = cols[i % cols.length]; c.beginPath(); c.arc(x + r() * w, y + r() * h, 1 + r() * 2.5, 0, 7); c.fill(); } },
  sun(c, x, y, r, col) { c.save(); c.globalAlpha = .35; c.fillStyle = col; for (let i = 0; i < 12; i++) { c.beginPath(); c.moveTo(x, y); c.arc(x, y, r * 2.4, i * .52, i * .52 + .22); c.fill(); } c.restore(); PP.ell(c, x, y, r, r, col, 3); c.fillStyle = 'rgba(255,255,255,.6)'; c.beginPath(); c.ellipse(x - r * .35, y - r * .35, r * .3, r * .2, -.6, 0, 7); c.fill(); }
};
// ---------------------------------------------------------------- tiles (24px, baked)
function buildTileset(th, seed) {
  const r = mulberry(seed), T = {}, [base, light, dark] = th.g, S = HTS;
  const tile = (draw) => { const c = makeCanvas(S, S); c.ctx.imageSmoothingEnabled = false; draw(c.ctx); return c; };
  const shadeDot = (c, x, y) => { c.fillStyle = 'rgba(255,255,255,.35)'; c.fillRect(x, y, 2, 2); };
  const tex = (c, v) => {
    c.fillStyle = PP.grad(c, 0, 0, 0, S, [light, base, base, dark]); c.fillRect(0, 0, S, S);
    switch (th.pat) {
      case 'dirt': for (let i = 0; i < 7; i++) { const x = r() * S, y = r() * S; c.fillStyle = dark; c.beginPath(); c.ellipse(x, y, 2 + r() * 2, 1.5 + r(), 0, 0, 7); c.fill(); } if (r() < .45) { const x = 4 + r() * 14, y = 6 + r() * 12; PP.ell(c, x, y, 3.5, 2.5, '#c8a888', 1); shadeDot(c, x - 2, y - 2); } if (v === 1 && r() < .3) { c.strokeStyle = '#ff8aa0'; c.lineWidth = 2; c.beginPath(); c.moveTo(6, 16); c.quadraticCurveTo(10, 12, 14, 16); c.stroke(); } break;
      case 'planks': for (let y = 0; y < S; y += 8) { c.fillStyle = PP.grad(c, 0, y, 0, y + 8, [light, base, dark]); c.fillRect(0, y, S, 8); c.fillStyle = INK; c.fillRect(0, y + 7, S, 1); c.fillStyle = 'rgba(0,0,0,.2)'; c.fillRect(4 + r() * 10, y + 3, 7, 1); c.fillStyle = '#ffe9a0'; c.fillRect((y / 8) % 2 ? 3 : 19, y + 3, 2, 2); } break;
      case 'bricks': for (let y = 0; y < S; y += 8) for (let x = (y / 8 % 2) * -6; x < S; x += 12) { c.fillStyle = PP.grad(c, 0, y, 0, y + 8, [light, base]); c.fillRect(x + 1, y + 1, 10, 6); c.fillStyle = 'rgba(255,255,255,.3)'; c.fillRect(x + 2, y + 2, 4, 1); } c.fillStyle = 'rgba(0,0,0,.35)'; for (let y = 7; y < S; y += 8) c.fillRect(0, y, S, 1); break;
      case 'metal': c.fillStyle = 'rgba(255,255,255,.35)'; c.beginPath(); c.moveTo(0, S); c.lineTo(S * .4, 0); c.lineTo(S * .6, 0); c.lineTo(S * .2, S); c.fill(); for (const [x, y] of [[3, 3], [S - 5, 3], [3, S - 5], [S - 5, S - 5]]) { PP.ell(c, x + 1, y + 1, 1.8, 1.8, '#e8e8f0', 1); } c.strokeStyle = INK; c.lineWidth = 1; c.strokeRect(.5, .5, S - 1, S - 1); break;
      case 'checker': { const a = v % 2 ? light : base, b = v % 2 ? base : light; c.fillStyle = a; c.fillRect(0, 0, S, S); c.fillStyle = b; c.fillRect(0, 0, S / 2, S / 2); c.fillRect(S / 2, S / 2, S / 2, S / 2); c.fillStyle = 'rgba(255,255,255,.35)'; c.fillRect(2, 2, 6, 2); c.fillStyle = 'rgba(0,0,0,.15)'; c.fillRect(0, S - 3, S, 3); break; }
      case 'stripes': for (let x = 0; x < S; x += 12) { c.fillStyle = PP.grad(c, x, 0, x + 6, 0, [light, '#fff', light]); c.fillRect(x, 0, 6, S); } c.fillStyle = 'rgba(0,0,0,.18)'; c.fillRect(0, S - 4, S, 4); break;
      case 'felt': c.strokeStyle = 'rgba(255,255,255,.6)'; c.setLineDash([3, 3]); c.lineWidth = 1.5; c.strokeRect(3, 3, S - 6, S - 6); c.setLineDash([]); c.fillStyle = 'rgba(0,0,0,.08)'; for (let i = 0; i < 10; i++) c.fillRect(r() * S, r() * S, 2, 1); break;
      case 'candy': for (let i = 0; i < 4; i++) { const x = r() * S, y = r() * S; c.fillStyle = pick(['#ff5bd1', '#5bd4ff', '#ffe14d', '#7fff3a']); c.beginPath(); c.arc(x, y, 2.4, 0, 7); c.fill(); shadeDot(c, x - 1, y - 1); } break;
      case 'stone': for (let i = 0; i < 4; i++) { const x = (i % 2) * 12 + 1, y = Math.floor(i / 2) * 12 + 1; PP.rect(c, x, y, 10, 10, (i + v) % 2 ? light : base, 1, 3); shadeDot(c, x + 2, y + 2); } break;
      case 'cases': PP.rect(c, 1, 1, S - 2, S - 2, base, 1, 2); for (const [x, y] of [[1, 1], [S - 7, 1], [1, S - 7], [S - 7, S - 7]]) PP.rect(c, x, y, 6, 6, '#d8d8e8', 1, 1); if (v === 2) PP.rect(c, 6, 8, 12, 8, pick(['#ff5bd1', '#ffe14d', '#5bd4ff']), 1, 2); break;
      case 'junk': { const cols = ['#e04a3a', '#3a8ae0', '#e0c02a', '#8a8a9a', '#a04ae0', '#3ae08a', '#ff8a2a']; for (let i = 0; i < 5; i++) PP.rect(c, r() * 14, r() * 14, 6 + r() * 9, 4 + r() * 7, cols[(r() * cols.length) | 0], 1, 1); if (r() < .4) PP.ell(c, 6 + r() * 12, 6 + r() * 12, 4, 4, '#222', 1); break; }
      case 'grille': PP.rect(c, 1, 1, S - 2, S - 2, base, 1, 2); c.fillStyle = dark; for (let y = 4; y < S - 3; y += 3) c.fillRect(4, y, S - 8, 1); PP.ell(c, S / 2, S / 2, 5, 5, light, 1); break;
    }
  };
  T.solid = [0, 1, 2].map(v => tile(c => tex(c, v)));
  const topCol = th.top;
  // overhanging cap (drawn above the tile's top edge into the empty cell above)
  T.capH = 12;
  T.caps = [0, 1, 2].map(v => { const c = makeCanvas(S, S + T.capH); const x = c.ctx; x.translate(0, T.capH);
    switch (th.edge) {
      case 'grass': { const gc = th.grass || topCol; x.fillStyle = INK; x.fillRect(0, -2, S, 8); x.fillStyle = gc; x.fillRect(0, -1, S, 6); for (let i = 0; i < 7; i++) { const bx = i * 4 - 1 + r() * 2, h = 3 + r() * 6; PP.poly(x, [[bx, 2], [bx + 2, -h], [bx + 5, 2]], gc, 1); } x.fillStyle = 'rgba(255,255,255,.4)'; x.fillRect(0, 0, S, 1); if (r() < .35) { const fx = 4 + r() * 16; x.strokeStyle = '#2a8a1a'; x.lineWidth = 1; x.beginPath(); x.moveTo(fx, 0); x.lineTo(fx, -7); x.stroke(); PP.ell(x, fx, -8, 2.5, 2.5, pick(['#fff', '#ff5bd1', '#ffe14d', '#ff3a3a']), 1); } break; }
      case 'hay': x.fillStyle = INK; x.fillRect(0, -2, S, 7); x.fillStyle = topCol; x.fillRect(0, -1, S, 5); for (let i = 0; i < 9; i++) { x.strokeStyle = i % 2 ? '#c09020' : '#fff0a0'; x.lineWidth = 1.5; const bx = r() * S; x.beginPath(); x.moveTo(bx, 2); x.lineTo(bx + (r() - .5) * 8, -4 - r() * 5); x.stroke(); } break;
      case 'moss': x.fillStyle = INK; x.fillRect(0, -2, S, 6); x.fillStyle = topCol; x.fillRect(0, -1, S, 4); for (let i = 0; i < 4; i++) PP.ell(x, r() * S, 2, 3 + r() * 2, 2 + r() * 2, topCol, 1); break;
      case 'goo': { const gc = th.goo || topCol; x.fillStyle = INK; x.fillRect(0, -2, S, 7); x.fillStyle = gc; x.fillRect(0, -1, S, 5); for (let i = 0; i < 2; i++) { const dx = 3 + r() * 16, dl = 4 + r() * 8; x.fillStyle = INK; x.beginPath(); x.ellipse(dx, 3 + dl / 2, 3.5, dl / 2 + 1, 0, 0, 7); x.fill(); x.fillStyle = gc; x.beginPath(); x.ellipse(dx, 3 + dl / 2, 2.5, dl / 2, 0, 0, 7); x.fill(); } x.fillStyle = 'rgba(255,255,255,.7)'; x.fillRect(2, 0, 6, 1); break; }
      case 'neon': x.fillStyle = INK; x.fillRect(0, -2, S, 6); x.fillStyle = topCol; x.fillRect(0, -1, S, 3); x.save(); x.globalAlpha = .35; x.fillStyle = topCol; x.fillRect(0, -6, S, 4); x.restore(); x.fillStyle = '#fff'; x.fillRect(0, 0, S, 1); break;
      case 'stitch': x.fillStyle = INK; x.fillRect(0, -2, S, 7); x.fillStyle = topCol; x.fillRect(0, -1, S, 5); x.strokeStyle = '#fff'; x.setLineDash([3, 3]); x.beginPath(); x.moveTo(0, 2); x.lineTo(S, 2); x.stroke(); x.setLineDash([]); break;
      case 'hazard': x.fillStyle = INK; x.fillRect(0, -2, S, 7); for (let i = -1; i < 5; i++) { x.fillStyle = i % 2 ? '#222' : '#ffcc33'; x.beginPath(); x.moveTo(i * 6, 4); x.lineTo(i * 6 + 6, -1); x.lineTo(i * 6 + 12, -1); x.lineTo(i * 6 + 6, 4); x.fill(); } break;
      case 'bulbs': x.fillStyle = INK; x.fillRect(0, -2, S, 7); x.fillStyle = topCol; x.fillRect(0, -1, S, 5); for (let i = 0; i < 3; i++) PP.ell(x, 4 + i * 8, 1.5, 2, 2, ['#fff36b', '#7fff3a', '#5bd4ff'][(i + v) % 3], 1); break;
      default: x.fillStyle = INK; x.fillRect(0, -2, S, 7); x.fillStyle = PP.grad(x, 0, -1, 0, 4, ['#fff6c0', topCol, '#a07010']); x.fillRect(0, -1, S, 5); for (let i = 0; i < 2; i++) PP.ell(x, 6 + i * 12, 1.5, 1.5, 1.5, '#fff6c0', 1);
    } return c; });
  T.oneway = tile(c => { PP.rect(c, 0, 2, S, 9, light, 0); c.fillStyle = PP.grad(c, 0, 2, 0, 11, ['#fff8', light, dark]); c.fillRect(0, 2, S, 9); c.fillStyle = INK; c.fillRect(0, 1, S, 2); c.fillRect(0, 11, S, 2); c.fillStyle = topCol; c.fillRect(0, 3, S, 2); PP.poly(c, [[4, 12], [8, 12], [6, 18]], dark, 1); PP.poly(c, [[16, 12], [20, 12], [18, 18]], dark, 1); });
  T.brk = tile(c => { tex(c, 1); c.fillStyle = 'rgba(255,240,200,.35)'; c.fillRect(0, 0, S, S); c.strokeStyle = INK; c.lineWidth = 2; c.beginPath(); c.moveTo(5, 2); c.lineTo(12, 11); c.lineTo(9, 21); c.moveTo(12, 11); c.lineTo(20, 7); c.moveTo(12, 11); c.lineTo(19, 18); c.stroke(); c.strokeRect(1, 1, S - 2, S - 2); PP.star(c, 18, 5, 3.5, '#ffe14d'); });
  T.crumble = tile(c => { PP.rect(c, 1, 1, S - 2, 11, '#d0aa6a', 2, 2); c.fillStyle = '#f0d090'; c.fillRect(3, 3, S - 6, 2); c.strokeStyle = INK; c.lineWidth = 1.5; c.beginPath(); c.moveTo(7, 1); c.lineTo(9, 12); c.moveTo(16, 1); c.lineTo(14, 12); c.stroke(); });
  T.spike = tile(c => { for (let i = 0; i < 3; i++) { PP.poly(c, [[i * 8, S], [i * 8 + 4, 6], [i * 8 + 8, S]], '#f0f0ff', 1.5); c.fillStyle = '#a0a0c0'; c.beginPath(); c.moveTo(i * 8 + 4, 6); c.lineTo(i * 8 + 8, S); c.lineTo(i * 8 + 4, S); c.fill(); } c.fillStyle = '#ff3a3a'; for (let i = 0; i < 3; i++) c.fillRect(i * 8 + 3, 7, 2, 2); });
  T.spring = [0, 1].map(f => tile(c => { PP.rect(c, 2, 18, 20, 6, '#555', 2, 2); for (let i = 0; i < 3; i++) PP.rect(c, 5, 9 + i * 3 + f * 3, 14, 2, '#ddd', 1); PP.rect(c, 1, 4 + f * 6, 22, 6, '#ff3a5a', 2, 3); c.fillStyle = '#fff'; c.fillRect(4, 5 + f * 6, 8, 1); }));
  T.conv = [0, 1, 2, 3].map(f => tile(c => { PP.rect(c, 0, 1, S, S - 2, '#3a3a48', 1, 3); for (let x = -6; x < S; x += 6) { c.fillStyle = '#ffcc33'; c.beginPath(); c.moveTo(x + f * 1.5, 3); c.lineTo(x + 3 + f * 1.5, 3); c.lineTo(x + 6 + f * 1.5, 6); c.lineTo(x + 3 + f * 1.5, 6); c.fill(); } PP.ell(c, 6, 15, 4, 4, '#8a8a9a', 1); PP.ell(c, 18, 15, 4, 4, '#8a8a9a', 1); }));
  const beat = (on, col) => tile(c => { if (on) { PP.rect(c, 1, 1, S - 2, S - 2, col, 2, 4); c.fillStyle = 'rgba(255,255,255,.5)'; c.fillRect(4, 3, 10, 2); text && 0; c.fillStyle = INK; c.fillRect(10, 6, 3, 10); c.beginPath(); c.ellipse(9, 16, 4, 3, 0, 0, 7); c.fill(); c.fillRect(10, 6, 6, 3); } else { c.globalAlpha = .55; c.strokeStyle = col; c.setLineDash([3, 3]); c.lineWidth = 2; c.strokeRect(2, 2, S - 4, S - 4); } });
  T.beatOn = beat(true, '#7fff3a'); T.beatOff = beat(false, '#7fff3a'); T.beatOnB = beat(true, '#ff5bd1'); T.beatOffB = beat(false, '#ff5bd1');
  const hc = HZCOL[th.hz] || HZCOL.acid;
  T.liquid = [0, 1, 2, 3].map(f => tile(c => { c.fillStyle = hc[1]; c.fillRect(0, 5, S, S - 5); c.fillStyle = hc[0]; c.beginPath(); c.moveTo(0, S); for (let x = 0; x <= S; x += 2) c.lineTo(x, 4 + Math.sin((x + f * 6) / S * 6.283) * 2.5); c.lineTo(S, S); c.fill(); c.fillStyle = hc[1]; c.fillRect(0, 10, S, S); c.fillStyle = 'rgba(255,255,255,.7)'; c.fillRect((f * 6) % S, 5, 5, 1); PP.ell(c, (f * 7 + 5) % S, 15, 2, 2, 'rgba(255,255,255,.5)', 0); }));
  T.liquidFill = tile(c => { c.fillStyle = hc[1]; c.fillRect(0, 0, S, S); c.fillStyle = 'rgba(255,255,255,.18)'; c.fillRect(r() * 20, r() * 20, 3, 3); });
  T.zap = [0, 1, 2, 3].map(f => tile(c => { PP.rect(c, 0, 16, S, 8, '#3a3a5a', 1, 2); PP.rect(c, 2, 12, 4, 5, '#c8c8e0', 1); PP.rect(c, 18, 12, 4, 5, '#c8c8e0', 1); c.strokeStyle = hc[0]; c.lineWidth = 2; c.beginPath(); let y = 12; c.moveTo(4, 12); for (let x = 6; x <= 20; x += 3) { y = 4 + ((x * 7 + f * 13) % 9); c.lineTo(x, y); } c.stroke(); c.strokeStyle = '#fff'; c.lineWidth = 1; c.stroke(); }));
  return T;
}
// ---------------------------------------------------------------- props (oversized cartoon scenery, baked at 1.5x)
function buildProps(th, seed) {
  const r = mulberry(seed + 7), out = [];
  const mk = (w, h, d) => { const c = makeCanvas((w + 8) * ZOOM, (h + 8) * ZOOM); const x = c.ctx; x.scale(ZOOM, ZOOM); x.translate(4, 4); d(x, w, h); c.hd = true; return c; };
  const lib = {
    amp: () => mk(44, 50, c => { PP.rect(c, 0, 0, 44, 50, '#24242c', 2.5, 4); PP.rect(c, 3, 3, 38, 8, '#ffcc33', 1.5, 2); for (let i = 0; i < 4; i++) PP.ell(c, 9 + i * 9, 7, 2, 2, '#222', 1); PP.ell(c, 22, 31, 14, 14, '#3a3a48', 2); PP.ell(c, 22, 31, 5, 5, '#111', 1); c.fillStyle = 'rgba(255,255,255,.25)'; c.fillRect(4, 14, 3, 32); }),
    speaker: () => mk(36, 72, c => { PP.rect(c, 0, 0, 36, 72, '#1c1c24', 2.5, 4); for (const y of [18, 50]) { PP.ell(c, 18, y, 13, 13, '#3a3a4a', 2); PP.ell(c, 18, y, 5, 5, '#7fff3a', 1); } }),
    mic: () => mk(16, 56, c => { PP.rect(c, 6, 10, 4, 44, '#b0b0c0', 1.5); PP.ell(c, 8, 54, 9, 3, '#555', 1.5); PP.ell(c, 8, 7, 6, 8, '#444', 2); c.fillStyle = '#888'; for (let i = 0; i < 3; i++) c.fillRect(4, 3 + i * 3, 8, 1); }),
    drum: () => mk(46, 36, c => { PP.ell(c, 23, 24, 21, 12, '#e02a3a', 2.5); PP.ell(c, 23, 17, 21, 7, '#f4f4ff', 2); c.fillStyle = '#ffe14d'; for (let i = 0; i < 6; i++) c.fillRect(6 + i * 7, 22, 2, 12); PP.rect(c, 38, -6, 2, 18, '#aaa', 1); PP.ell(c, 39, -6, 9, 2.5, '#ffd23a', 1.5); }),
    case: () => mk(46, 32, c => { PP.rect(c, 0, 0, 46, 32, '#2a2a38', 2.5, 3); for (const [x, y] of [[0, 0], [40, 0], [0, 26], [40, 26]]) PP.rect(c, x, y, 6, 6, '#d8d8e8', 1); PP.rect(c, 8, 9, 30, 12, pick(['#ff5bd1', '#ffe14d', '#5bd4ff']), 1.5, 3); c.fillStyle = INK; c.font = 'bold 8px monospace'; c.fillText('FRAGILE', 9, 18); }),
    poster: () => mk(30, 40, c => { PP.rect(c, 0, 0, 30, 40, pick(['#ff5bd1', '#5bd4ff', '#ffe14d', '#7fff3a']), 2, 2); PP.ell(c, 15, 16, 9, 9, '#5ae03a', 1.5); PP.ell(c, 12, 14, 2.5, 2.5, '#fff', 1); c.fillStyle = INK; c.fillRect(6, 30, 18, 3); c.fillRect(9, 35, 12, 2); }),
    puppet: () => mk(22, 50, c => { c.strokeStyle = '#ddd'; c.lineWidth = 1; c.beginPath(); c.moveTo(11, -4); c.lineTo(11, 16); c.stroke(); PP.ell(c, 11, 20, 8, 8, '#e8c290', 2); PP.ell(c, 8, 18, 1.5, 1.5, INK, 0); PP.ell(c, 14, 18, 1.5, 1.5, INK, 0); PP.rect(c, 4, 28, 14, 14, '#3a6ac4', 2); PP.rect(c, 5, 42, 4, 8, '#5a3a1d', 1.5); PP.rect(c, 13, 42, 4, 8, '#5a3a1d', 1.5); }),
    flower: () => { const col = pick(['#ff4a8a', '#ffe14d', '#ffffff', '#b04bff', '#ff7a2a']); return mk(18, 28, c => { c.strokeStyle = '#2a8a1a'; c.lineWidth = 3; c.beginPath(); c.moveTo(9, 28); c.quadraticCurveTo(6, 18, 9, 10); c.stroke(); PP.ell(c, 14, 20, 4, 2, '#3ac02a', 1); for (let a = 0; a < 5; a++) PP.ell(c, 9 + Math.cos(a * 1.26) * 5, 8 + Math.sin(a * 1.26) * 5, 4, 4, col, 1.5); PP.ell(c, 9, 8, 3, 3, '#6a3a00', 1); }); },
    sunflower: () => mk(30, 70, c => { c.strokeStyle = INK; c.lineWidth = 6; c.beginPath(); c.moveTo(15, 70); c.lineTo(15, 20); c.stroke(); c.strokeStyle = '#3ac02a'; c.lineWidth = 4; c.stroke(); PP.ell(c, 22, 44, 7, 3, '#3ac02a', 1.5); for (let a = 0; a < 10; a++) PP.ell(c, 15 + Math.cos(a * .63) * 10, 16 + Math.sin(a * .63) * 10, 5, 5, '#ffd23a', 1.5); PP.ell(c, 15, 16, 7, 7, '#7a4a10', 2); PP.ell(c, 12, 14, 1.8, 1.8, '#fff', 0); PP.ell(c, 18, 14, 1.8, 1.8, '#fff', 0); c.strokeStyle = '#fff'; c.lineWidth = 1.5; c.beginPath(); c.arc(15, 17, 3, .2, 2.9); c.stroke(); }),
    fence: () => mk(52, 30, c => { for (let x = 0; x < 52; x += 13) PP.poly(c, [[x, 30], [x, 6], [x + 4.5, 0], [x + 9, 6], [x + 9, 30]], '#f4e0c0', 2); PP.rect(c, -2, 10, 56, 5, '#e0c8a0', 2); PP.rect(c, -2, 20, 56, 5, '#e0c8a0', 2); }),
    hay: () => mk(40, 28, c => { PP.rect(c, 0, 0, 40, 28, '#ffd860', 2.5, 6); for (let i = 0; i < 10; i++) { c.strokeStyle = '#c09020'; c.lineWidth = 1; const x = r() * 36 + 2; c.beginPath(); c.moveTo(x, 3 + r() * 6); c.lineTo(x + 4, 6 + r() * 6); c.stroke(); } PP.rect(c, 0, 8, 40, 4, '#c0302a', 1); PP.rect(c, 0, 18, 40, 4, '#c0302a', 1); }),
    mushroom: () => { const col = pick(['#ff3a5a', '#ff5bd1', '#5bd4ff', '#ffe14d']); return mk(36, 40, c => { PP.rect(c, 12, 18, 12, 22, '#fff0d8', 2, 4); PP.ell(c, 18, 16, 18, 13, col, 2.5); for (let i = 0; i < 4; i++) PP.ell(c, 7 + i * 7, 10 + (i % 2) * 6, 2.6, 2.6, '#fff', 1); PP.ell(c, 15, 27, 1.5, 2, INK, 0); PP.ell(c, 21, 27, 1.5, 2, INK, 0); }); },
    candle: () => mk(14, 36, c => { PP.rect(c, 3, 12, 8, 24, '#fff4e0', 2, 2); c.fillStyle = '#ffd8a0'; c.fillRect(4, 14, 2, 18); PP.poly(c, [[7, 0], [11, 8], [7, 12], [3, 8]], '#ffb21f', 1.5); PP.ell(c, 7, 8, 1.5, 2.5, '#fff8a0', 0); }),
    books: () => mk(36, 30, c => { const cols = ['#e03a3a', '#3a8ae0', '#3ae08a', '#e0c03a', '#a03ae0']; let x = 0; for (let i = 0; i < 5; i++) { const w = 6 + r() * 3, h = 18 + r() * 12; PP.rect(c, x, 30 - h, w, h, cols[i], 1.5, 1); c.fillStyle = '#fff8'; c.fillRect(x + 1, 30 - h + 4, w - 2, 1); x += w + .5; } }),
    potion: () => mk(20, 28, c => { PP.ell(c, 10, 19, 9, 9, pick(['#7fff3a', '#ff5bd1', '#5bd4ff']), 2); PP.rect(c, 7, 2, 6, 9, '#c8e0ff', 1.5); PP.rect(c, 6, 0, 8, 3, '#8a5a2a', 1); PP.ell(c, 7, 16, 2, 2, '#fff', 0); }),
    mask: () => mk(28, 22, c => { PP.ell(c, 14, 11, 13, 10, '#ffffff', 2); PP.ell(c, 9, 9, 3, 3, INK, 0); PP.ell(c, 19, 9, 3, 3, INK, 0); c.strokeStyle = INK; c.lineWidth = 2; c.beginPath(); c.arc(14, 13, 5, .2, 2.9); c.stroke(); }),
    cereal: () => { const col = pick(['#ff3a5a', '#3a8aff', '#ffcc33', '#a03aff', '#3ad08a']); return mk(34, 48, c => { PP.rect(c, 0, 4, 34, 44, col, 2.5, 2); PP.rect(c, 3, 8, 28, 12, '#fff', 1.5, 2); c.fillStyle = INK; c.font = 'bold 8px monospace'; c.fillText('LOOPS', 5, 17); PP.ell(c, 17, 32, 9, 9, '#ff8ab0', 2); PP.ell(c, 17, 32, 3, 3, col, 1); PP.ell(c, 13, 29, 1.5, 1.5, INK, 0); PP.ell(c, 21, 29, 1.5, 1.5, INK, 0); }); },
    bottle: () => mk(20, 44, c => { PP.rect(c, 1, 16, 18, 28, '#ffffff', 2, 3); PP.rect(c, 5, 4, 10, 13, '#ffffff', 2, 2); PP.rect(c, 5, 0, 10, 5, '#3a8de0', 1.5, 1); PP.rect(c, 1, 24, 18, 8, '#3a8de0', 1.5); c.fillStyle = '#fff'; c.font = 'bold 6px monospace'; c.fillText('MOO', 4, 30); }),
    donut: () => mk(32, 32, c => { PP.ell(c, 16, 16, 15, 15, '#e0a060', 2.5); PP.ell(c, 16, 15, 13, 12, '#ff8ac0', 0); c.fillStyle = INK; c.beginPath(); c.arc(16, 16, 5, 0, 7); c.fill(); c.fillStyle = '#ffeedd'; c.beginPath(); c.arc(16, 16, 4, 0, 7); c.fill(); for (let i = 0; i < 8; i++) { c.fillStyle = pick(['#fff', '#5bd4ff', '#ffe14d', '#7fff3a']); c.save(); c.translate(16 + Math.cos(i) * 9, 16 + Math.sin(i) * 9); c.rotate(i); c.fillRect(-2, -.7, 4, 1.4); c.restore(); } }),
    cart: () => SPR.cart[0],
    sign: () => mk(44, 40, c => { PP.rect(c, 19, 18, 6, 22, '#8a5a2a', 2); PP.rect(c, 0, 0, 44, 22, '#ffe14d', 2.5, 4); PP.rect(c, 3, 3, 38, 16, '#e02a3a', 1.5, 3); c.fillStyle = '#fff'; c.font = 'bold 9px monospace'; c.fillText(pick(['SALE!', 'NO!', 'YES', 'MOSH', 'WOW']), 7, 15); }),
    gear: () => mk(40, 40, c => { const pts = []; for (let i = 0; i < 20; i++) { const a = i / 20 * Math.PI * 2, rr = i % 2 ? 19 : 15; pts.push([20 + Math.cos(a) * rr, 20 + Math.sin(a) * rr]); } PP.poly(c, pts, '#c8a040', 2); PP.ell(c, 20, 20, 6, 6, '#6a4a10', 1.5); }),
    pipe: () => mk(22, 64, c => { PP.rect(c, 4, 0, 14, 64, '#a0a8b8', 2); PP.rect(c, 1, 12, 20, 6, '#c8d0e0', 2); PP.rect(c, 1, 44, 20, 6, '#c8d0e0', 2); c.fillStyle = 'rgba(255,255,255,.5)'; c.fillRect(7, 0, 3, 64); }),
    eyeplant: () => mk(28, 48, c => { c.strokeStyle = INK; c.lineWidth = 5; c.beginPath(); c.moveTo(14, 48); c.quadraticCurveTo(4, 30, 14, 16); c.stroke(); c.strokeStyle = '#3ae08a'; c.lineWidth = 3; c.stroke(); PP.ell(c, 14, 12, 11, 10, '#fff', 2.5); PP.ell(c, 14, 12, 5, 5, pick(['#b04bff', '#ff3a3a', '#1db954']), 1); PP.ell(c, 14, 12, 2, 2, INK, 0); c.strokeStyle = '#ff3a3a'; c.lineWidth = 1; c.beginPath(); c.moveTo(4, 12); c.lineTo(8, 10); c.stroke(); }),
    door: () => mk(30, 50, c => { PP.rect(c, 0, 0, 30, 50, pick(['#ff5bd1', '#5bd4ff', '#ffe14d']), 2.5, 6); PP.rect(c, 5, 5, 20, 40, '#1a0a3a', 1.5, 4); PP.ell(c, 21, 26, 2, 2, '#ffe14d', 1); }),
    coil: () => mk(20, 54, c => { PP.rect(c, 6, 8, 8, 46, '#555', 2); for (let y = 12; y < 50; y += 4) PP.rect(c, 2, y, 16, 2.5, '#e08a2a', 1); PP.ell(c, 10, 6, 9, 6, '#c8c8e0', 2); }),
    portrait: () => mk(36, 44, c => { PP.rect(c, 0, 0, 36, 44, '#ffcc33', 2.5, 2); PP.rect(c, 4, 4, 28, 36, '#3a2a5a', 1.5); PP.ell(c, 18, 20, 9, 10, '#5ae03a', 1.5); PP.ell(c, 15, 18, 2, 2, '#fff', 0); PP.ell(c, 21, 18, 2, 2, '#fff', 0); c.strokeStyle = INK; c.lineWidth = 1.5; c.beginPath(); c.moveTo(14, 25); c.lineTo(22, 25); c.stroke(); }),
    button: () => { const col = pick(['#ff3a3a', '#3a8aff', '#ffe14d', '#7fff3a']); return mk(26, 26, c => { PP.ell(c, 13, 13, 12, 12, col, 2.5); for (const [x, y] of [[9, 9], [17, 9], [9, 17], [17, 17]]) PP.ell(c, x, y, 2, 2, 'rgba(0,0,0,.4)', 0); }); },
    yarn: () => mk(30, 30, c => { const col = pick(['#ff5bd1', '#5bd4ff', '#ffe14d']); PP.ell(c, 15, 15, 14, 14, col, 2.5); c.strokeStyle = 'rgba(255,255,255,.6)'; c.lineWidth = 1.5; for (let i = 0; i < 4; i++) { c.beginPath(); c.arc(15, 15, 10 - i * 2, i, i + 2.5); c.stroke(); } }),
    balloon: () => SPR.balloon[0],
    barrel: () => mk(30, 36, c => { PP.ell(c, 15, 18, 15, 18, '#c0702a', 2.5); PP.rect(c, 0, 7, 30, 3, '#555', 1); PP.rect(c, 0, 26, 30, 3, '#555', 1); c.fillStyle = 'rgba(255,255,255,.3)'; c.fillRect(6, 3, 3, 30); }),
    popcorn: () => mk(28, 40, c => { PP.poly(c, [[2, 12], [26, 12], [22, 40], [6, 40]], '#fff', 2.5); for (let x = 4; x < 26; x += 6) { c.fillStyle = '#e02a3a'; c.fillRect(x + 1, 14, 3, 25); } for (let i = 0; i < 7; i++) PP.ell(c, 4 + i * 3.5, 8 + (i % 2) * 3, 4, 4, '#fff8c0', 1.5); }),
    fishsign: () => mk(40, 26, c => { PP.ell(c, 18, 13, 16, 10, '#5ee08a', 2.5); PP.poly(c, [[30, 13], [40, 3], [40, 23]], '#5ee08a', 2.5); PP.ell(c, 10, 10, 4, 4, '#fff', 1.5); PP.ell(c, 10, 10, 1.5, 1.5, INK, 0); }),
    tire: () => mk(36, 36, c => { PP.ell(c, 18, 18, 17, 17, '#2a2a2a', 2.5); PP.ell(c, 18, 18, 8, 8, '#8a8a9a', 2); PP.ell(c, 18, 18, 3, 3, '#333', 1); }),
    fridge: () => mk(30, 54, c => { PP.rect(c, 0, 0, 30, 54, '#f0f0e8', 2.5, 4); c.fillStyle = INK; c.fillRect(0, 18, 30, 2); PP.rect(c, 23, 6, 3, 8, '#888', 1); PP.rect(c, 23, 24, 3, 14, '#888', 1); PP.rect(c, 4, 28, 10, 8, pick(['#ff5bd1', '#ffe14d']), 1); }),
    tv: () => mk(36, 34, c => { PP.rect(c, 0, 4, 36, 28, '#8a5a3a', 2.5, 4); PP.rect(c, 4, 8, 24, 20, '#5bd4ff', 1.5, 3); c.strokeStyle = INK; c.lineWidth = 1.5; c.beginPath(); c.moveTo(10, 4); c.lineTo(4, -4); c.moveTo(22, 4); c.lineTo(28, -4); c.stroke(); PP.ell(c, 32, 14, 2, 2, '#ffe14d', 1); c.fillStyle = 'rgba(255,255,255,.5)'; c.fillRect(6, 10, 8, 2); }),
    bag: () => mk(30, 28, c => { PP.ell(c, 15, 17, 14, 11, '#2c2c3a', 2.5); PP.poly(c, [[11, 6], [15, 0], [19, 6]], '#2c2c3a', 2); PP.rect(c, 12, 6, 6, 3, '#ffe14d', 1); c.fillStyle = 'rgba(255,255,255,.25)'; c.fillRect(6, 12, 3, 8); })
  };
  for (const k of th.props) if (lib[k]) for (let i = 0; i < 3; i++) out.push(lib[k]());
  return out;
}
// ---------------------------------------------------------------- painted parallax backgrounds (screen-space, 640x360)
const BGW = 960;
function buildBackground(th, seed) {
  const r = mulberry(seed + 99), far = makeCanvas(BGW, H), mid = makeCanvas(BGW, H), sky = makeCanvas(W, H), f = far.ctx, m = mid.ctx, s = sky.ctx;
  const [s0, s1] = th.sky;
  s.fillStyle = PP.grad(s, 0, 0, 0, H, [s0, s1]); s.fillRect(0, 0, W, H);
  // dithered horizon glow
  s.fillStyle = 'rgba(255,255,255,.12)'; for (let y = 150; y < 260; y += 3) for (let x = (y / 3 % 2) * 2; x < W; x += 4) if (r() < (y - 150) / 160) s.fillRect(x, y, 1, 1);
  const wrap = (fn) => { fn(0); fn(BGW); fn(-BGW); };
  const each = (n, fn) => { for (let i = 0; i < n; i++) { const x = r() * BGW; const rr = r; wrap(o => fn(x + o, i, rr)); } };
  const anim = [], animF = []; // live animated elements: (ctx, t, ox) with ox = parallax offset
  const scene = th.scene;
  const night = ['stage', 'castle', 'mansion', 'void', 'devourer', 'circus', 'rock', 'backstage'].includes(scene);
  // celestial
  if (night) { for (let i = 0; i < 90; i++) { s.fillStyle = r() < .2 ? hsl(r() * 360, 90, 75) : '#fff'; const sz = r() < .1 ? 2 : 1; s.fillRect(r() * W, r() * 200, sz, sz); } PP.ell(s, 520, 64, 30, 30, '#fff8d0', 3); s.fillStyle = 'rgba(200,190,150,.5)'; s.beginPath(); s.arc(510, 56, 6, 0, 7); s.arc(530, 76, 4, 0, 7); s.fill(); }
  else { PP.sun(s, 520, 70, 28, scene === 'farm' || scene === 'park' ? '#fff07a' : '#fff6a0'); }
  if (!night || scene === 'circus') anim.push((c, t) => { for (let i = 0; i < 5; i++) { const x = ((i * 210 + t * (6 + i * 2)) % (W + 200)) - 100, y = 40 + (i * 37) % 90; PP.cloud(c, x, y, .55 + (i % 3) * .15); } });
  switch (scene) {
    case 'stage': case 'rock': {
      // giant amp towers + truss + cheering crowd
      each(5, (x, i) => { const h = 150 + (i % 3) * 40; PP.rect(f, x, H - 90 - h, 70, h, '#1c1424', 3, 6); for (let y = H - 80 - h; y < H - 100; y += 34) { PP.ell(f, x + 35, y + 14, 15, 15, '#2c2440', 2); PP.ell(f, x + 35, y + 14, 6, 6, th.top, 2); } PP.rect(f, x + 4, H - 88 - h, 62, 8, '#ffcc33', 2, 2); });
      f.fillStyle = 'rgba(255,90,200,.25)'; f.fillRect(0, 40, BGW, 16); f.strokeStyle = INK; f.lineWidth = 3; f.strokeRect(-2, 40, BGW + 4, 16); for (let x = 0; x < BGW; x += 20) { f.beginPath(); f.moveTo(x, 40); f.lineTo(x + 20, 56); f.stroke(); }
      for (let x = 30; x < BGW; x += 80) { PP.rect(f, x, 56, 16, 14, '#333', 2, 3); f.fillStyle = hsl(x * 3 % 360, 90, 65); f.fillRect(x + 3, 66, 10, 4); }
      PP.rect(m, -4, H - 72, BGW + 8, 80, scene === 'rock' ? '#4a2a7a' : '#6a2a6a', 0);
      animF.push((c, t, ox) => { const b = AudioSys.beat(), kick = b.phase < .15 ? 4 : 0; for (let i = 0; i < 46; i++) { const x = ((i * 23 - ox * 1.0) % (W + 40) + W + 40) % (W + 40) - 20, j = ((i + b.beat) % 3 === 0 ? kick : 0) + Math.sin(t * 6 + i) * 1.5, col = hsl((i * 47) % 360, 70, 55), y = H - 54 - j + (i % 2) * 10; PP.ell(c, x, y, 9, 10, col, 2.5); PP.ell(c, x - 3, y - 2, 2, 2, '#fff', 0); PP.ell(c, x + 3, y - 2, 2, 2, '#fff', 0); if (i % 3 === 0) { c.strokeStyle = INK; c.lineWidth = 4; c.beginPath(); c.moveTo(x + 6, y - 6); c.lineTo(x + 10, y - 22 - j); c.stroke(); c.strokeStyle = col; c.lineWidth = 2; c.stroke(); PP.ell(c, x + 10, y - 24 - j, 3, 3, col, 1.5); } } });
      break; }
    case 'backstage': {
      PP.rect(f, -4, 0, BGW + 8, H, '#c86a3a', 0); for (let y = 0; y < H; y += 14) for (let x = (y / 14 % 2) * 14; x < BGW; x += 28) { f.fillStyle = (x + y) % 3 ? '#d87a4a' : '#b85a2a'; f.fillRect(x + 1, y + 1, 26, 12); }
      each(10, (x, i) => { const w = 40 + (i % 3) * 10; f.save(); f.translate(x, 80 + (i % 4) * 30); f.rotate((r() - .5) * .3); PP.rect(f, 0, 0, w, w * 1.3, ['#ff5bd1', '#5bd4ff', '#ffe14d', '#7fff3a'][i % 4], 2.5, 2); PP.ell(f, w / 2, w * .5, w * .25, w * .25, '#1a0b22', 0); f.fillStyle = '#fff'; f.font = 'bold 9px monospace'; f.fillText(['LIVE!', 'MOSH', '333', 'ROCK'][i % 4], 6, w * 1.15); f.restore(); });
      each(8, (x, i) => { PP.rect(m, x, H - 110 - (i % 3) * 28, 70, 50, '#2a2a38', 3, 3); PP.rect(m, x + 10, H - 98 - (i % 3) * 28, 50, 16, ['#ff5bd1', '#ffe14d', '#5bd4ff'][i % 3], 2, 3); });
      m.strokeStyle = INK; m.lineWidth = 6; for (let i = 0; i < 5; i++) { m.beginPath(); m.moveTo(0, 30 + i * 12); for (let x = 0; x <= BGW; x += 40) m.quadraticCurveTo(x + 20, 50 + i * 12 + 20, x + 40, 30 + i * 12); m.stroke(); }
      animF.push((c, t) => { for (let i = 0; i < 3; i++) { const x = (i * 260 + t * 10) % (W + 60) - 30, sw = Math.sin(t * 2 + i) * 8; c.strokeStyle = '#ddd'; c.lineWidth = 1; c.beginPath(); c.moveTo(x, 0); c.lineTo(x + sw, 70); c.stroke(); PP.ell(c, x + sw, 78, 9, 9, '#e8c290', 2); PP.rect(c, x + sw - 7, 86, 14, 18, '#c4302b', 2); } });
      break; }
    case 'meadow': case 'farm': {
      const hills = scene === 'farm' ? ['#e0a040', '#c87a2a', '#a05a1a'] : ['#7ae05a', '#4ac03a', '#2a9a2a'];
      PP.hill(f, BGW, H - 120, 60, 1.5, .3, hills[0], 3); each(4, (x, i) => PP.wobblyHouse(f, x, H - 140 - (i % 2) * 10, 44, 36, ['#ff5a4a', '#fff0d0', '#5ab0ff'][i % 3], ['#8a2a1a', '#ff8a2a', '#3a3a8a'][i % 3], r));
      each(3, (x, i) => { PP.rect(f, x, H - 200, 10, 70, '#fff', 2.5); anim.push((c, t, ox) => { const X = ((x - ox * .15) % BGW + BGW) % BGW - 60; if (X < -40 || X > W + 40) return; c.save(); c.translate(X + 5, H - 200); c.rotate(t * 1.5 + i); for (let k = 0; k < 4; k++) { c.rotate(Math.PI / 2); PP.rect(c, -3, 0, 6, 34, '#ff5a4a', 2); } c.restore(); PP.ell(c, X + 5, H - 200, 4, 4, '#ffcc33', 2); }); });
      PP.hill(m, BGW, H - 80, 46, 2, 1.1, hills[1], 3); PP.hill(m, BGW, H - 46, 30, 3, 2.2, hills[2], 3);
      each(14, (x) => { m.fillStyle = pick(['#fff', '#ff5bd1', '#ffe14d']); m.beginPath(); m.arc(x, H - 40 + r() * 30, 2.5, 0, 7); m.fill(); });
      if (scene === 'farm') each(2, (x) => { PP.rect(m, x, H - 170, 60, 100, '#5a2a6a', 3, 6); PP.ell(m, x + 30, H - 175, 40, 26, '#7a4a8a', 3); PP.poly(m, [[x - 2, H - 190], [x - 18, H - 220], [x + 14, H - 196]], '#efe2c4', 2); PP.poly(m, [[x + 62, H - 190], [x + 78, H - 220], [x + 46, H - 196]], '#efe2c4', 2); PP.ell(m, x + 18, H - 178, 5, 4, '#ffe14d', 2); PP.ell(m, x + 42, H - 178, 5, 4, '#ffe14d', 2); });
      break; }
    case 'castle': case 'mansion': {
      PP.hill(f, BGW, H - 90, 30, 1, 0, scene === 'castle' ? '#8a5ad0' : '#3a3a8a', 3);
      each(4, (x, i) => { const h = 140 + (i % 3) * 50, w = 46; const lean = (i % 2 ? 1 : -1) * 8; PP.poly(f, [[x, H - 80], [x + lean, H - 80 - h], [x + w + lean, H - 80 - h], [x + w, H - 80]], scene === 'castle' ? '#b090e0' : '#5a4a8a'); PP.poly(f, [[x - 8 + lean, H - 76 - h], [x + w / 2 + lean * 2, H - 80 - h - 70], [x + w + 8 + lean, H - 76 - h]], ['#ff5bd1', '#5bd4ff', '#ffe14d'][i % 3]); for (let y = H - 70 - h; y < H - 100; y += 36) PP.rect(f, x + 15 + lean * .5, y + 20, 14, 18, '#ffe9a0', 2, 7); });
      each(6, (x, i) => { PP.rect(m, x, H - 70 - 40 - (i % 2) * 20, 22, 60, ['#e03a3a', '#3a8ae0', '#3ae08a', '#e0c03a'][i % 4], 2.5, 2); });
      if (scene === 'mansion') anim.push((c, t) => { if ((Math.floor(t * 4) % 23) < 1) { c.strokeStyle = '#fff'; c.lineWidth = 3; c.beginPath(); let x = 100 + (Math.floor(t) * 137) % 400, y = 0; c.moveTo(x, y); while (y < 200) { x += R(-20, 20); y += 20; c.lineTo(x, y); } c.stroke(); c.fillStyle = 'rgba(255,255,255,.2)'; c.fillRect(0, 0, W, H); } });
      break; }
    case 'theater': case 'bigtop': {
      for (let x = 0; x < BGW; x += 40) { f.fillStyle = PP.grad(f, x, 0, x + 40, 0, scene === 'theater' ? ['#6a0a1a', '#e02a3a', '#6a0a1a'] : ['#ffcc33', '#fff07a', '#e02a3a', '#fff07a', '#ffcc33']); f.fillRect(x, 0, 40, H); }
      f.strokeStyle = INK; f.lineWidth = 3; for (let x = 0; x < BGW; x += 80) { f.beginPath(); f.arc(x + 40, -6, 44, 0, Math.PI); f.fillStyle = '#ffcc33'; f.fill(); f.stroke(); }
      PP.rect(m, -4, H - 90, BGW + 8, 100, scene === 'theater' ? '#8a4a1a' : '#e02a3a', 3); for (let x = 0; x < BGW; x += 30) PP.ell(m, x, H - 90, 6, 6, '#ffe14d', 2);
      anim.push((c, t) => { for (let i = 0; i < 2; i++) { const x = W / 2 + Math.sin(t * .7 + i * 3) * 220; c.save(); c.globalCompositeOperation = 'lighter'; const g = c.createRadialGradient(x, H - 90, 0, x, H - 90, 90); g.addColorStop(0, 'rgba(255,255,200,.35)'); g.addColorStop(1, 'rgba(0,0,0,0)'); c.fillStyle = g; c.fillRect(x - 90, H - 180, 180, 180); c.restore(); } });
      break; }
    case 'factory': case 'mech': case 'assembly': {
      const pipeCol = scene === 'factory' ? ['#ff5bd1', '#5bd4ff', '#7fff3a'] : scene === 'mech' ? ['#c8d0e0', '#ff6a2a', '#ffcc33'] : ['#7fff3a', '#3a8a4a', '#c8d0e0'];
      each(5, (x, i) => { const h = 130 + (i % 3) * 40; PP.rect(f, x, H - 80 - h, 40, h, '#e0e0f0', 3, 4); PP.rect(f, x - 4, H - 80 - h, 48, 12, pipeCol[i % 3], 2.5, 3); anim.push((c, t, ox) => { const X = ((x - ox * .15) % BGW + BGW) % BGW - 60 + 20; if (X < -60 || X > W + 60) return; for (let k = 0; k < 3; k++) { const p = (t * .4 + k / 3 + i * .2) % 1; c.globalAlpha = 1 - p; PP.cloud(c, X - 10 + p * 30, H - 100 - h - p * 80, .25 + p * .3, scene === 'factory' ? '#ffe0f0' : '#e0e0e0'); c.globalAlpha = 1; } }); });
      for (let i = 0; i < 4; i++) { const y = 90 + i * 40; PP.rect(f, -4, y, BGW + 8, 12, pipeCol[i % 3], 2.5); }
      if (scene === 'factory') each(6, (x, i) => { PP.rect(m, x, H - 150, 50, 72, ['#ff3a5a', '#3a8aff', '#ffcc33'][i % 3], 3, 3); PP.rect(m, x + 5, H - 142, 40, 16, '#fff', 2, 2); PP.ell(m, x + 25, H - 104, 15, 15, '#ff8ab0', 2.5); PP.ell(m, x + 25, H - 104, 5, 5, '#ffcc33', 2); });
      else each(5, (x) => { const pts = []; for (let i = 0; i < 24; i++) { const a = i / 24 * 6.283, rr = i % 2 ? 34 : 27; pts.push([x + Math.cos(a) * rr, H - 120 + Math.sin(a) * rr]); } PP.poly(m, pts, scene === 'mech' ? '#c0a050' : '#6aa07a'); PP.ell(m, x, H - 120, 9, 9, '#3a2a10', 2); });
      if (scene === 'assembly') anim.push((c, t) => { for (let i = 0; i < 3; i++) { const x = 120 + i * 200, a = Math.sin(t * 1.5 + i) * .6; c.save(); c.translate(x, 0); c.rotate(a); PP.rect(c, -8, 0, 16, 90, '#5a6a7a', 3); PP.rect(c, -14, 86, 28, 12, '#7fff3a', 2.5); c.restore(); } });
      break; }
    case 'market': {
      each(5, (x, i) => { PP.rect(f, x, 60, 150, H - 120, '#2ad0c0', 3, 4); for (let y = 80; y < H - 80; y += 46) { PP.rect(f, x + 4, y + 36, 142, 6, '#fff', 2); for (let b = x + 8; b < x + 140; b += 18) PP.rect(f, b, y + 6, 14, 30, hsl(r() * 360, 80, 60), 2, 2); } });
      each(3, (x, i) => { PP.rect(f, x, 20, 90, 24, '#ff3a6a', 3, 6); f.fillStyle = '#fff'; f.font = 'bold 16px monospace'; f.fillText(['SALE!', 'MILK', 'LOOPS'][i % 3], x + 12, 38); });
      PP.rect(m, -4, H - 60, BGW + 8, 60, '#ffffff', 0); for (let x = 0; x < BGW; x += 30) PP.rect(m, x, H - 60, 15, 15, '#ff8ab0', 0);
      break; }
    case 'canal': {
      PP.hill(f, BGW, H - 120, 40, 1.5, 0, '#a0d0ff', 3); each(4, (x, i) => PP.wobblyHouse(f, x, H - 130, 50, 50, ['#ff8ab0', '#ffe14d', '#fff'][i % 3], '#3a6ad0', r));
      each(3, (x) => { m.beginPath(); m.arc(x + 80, H - 40, 80, Math.PI, 0); m.lineTo(x + 170, H - 130); m.lineTo(x - 10, H - 130); m.closePath(); PP.fillOut(m, '#d06a5a', 3); m.fillStyle = '#fff'; m.beginPath(); m.arc(x + 80, H - 40, 56, Math.PI, 0); m.fill(); });
      each(3, (x) => { PP.rect(m, x, H - 200, 40, 90, '#ffffff', 3, 6); PP.rect(m, x + 8, H - 226, 24, 28, '#ffffff', 3, 4); PP.rect(m, x, H - 170, 40, 20, '#3a8de0', 2); });
      break; }
    case 'forest': case 'felt': {
      if (scene === 'felt') { PP.hill(f, BGW, H - 140, 60, 1.2, 0, '#ff8ab0', 3); PP.hill(m, BGW, H - 90, 40, 2, 1, '#8aff8a', 3); PP.hill(m, BGW, H - 50, 30, 3, 2, '#ffb05a', 3); each(10, (x) => { m.strokeStyle = 'rgba(255,255,255,.8)'; m.setLineDash([4, 4]); m.lineWidth = 2; m.beginPath(); m.arc(x, H - 80, 30, Math.PI, 0); m.stroke(); m.setLineDash([]); }); }
      else { each(10, (x, i) => { const h = 140 + (i % 4) * 30; PP.rect(f, x - 7, H - 80 - h, 14, h, '#8a3aa0', 3); const col = ['#ff3a8a', '#3affd0', '#ffe14d', '#5bd4ff'][i % 4]; PP.ell(f, x, H - 80 - h, 40, 28, col, 3); for (let k = 0; k < 4; k++) PP.ell(f, x - 24 + k * 16, H - 86 - h + (k % 2) * 8, 4, 4, '#fff', 1.5); }); each(8, (x, i) => { const h = 50 + (i % 3) * 20; PP.rect(m, x - 6, H - 50 - h, 12, h, '#fff0d8', 3); PP.ell(m, x, H - 50 - h, 26, 16, ['#ff5bd1', '#ffe14d', '#7fff3a'][i % 3], 3); PP.ell(m, x - 6, H - 30 - h, 2, 3, INK, 0); PP.ell(m, x + 6, H - 30 - h, 2, 3, INK, 0); }); anim.push((c, t) => { for (let i = 0; i < 18; i++) { const x = (i * 71 + Math.sin(t + i) * 20) % W, y = H - ((t * 20 + i * 40) % H); c.fillStyle = hsl((i * 40 + t * 50) % 360, 90, 70); c.beginPath(); c.arc(x, y, 2, 0, 7); c.fill(); } }); }
      break; }
    case 'void': case 'devourer': {
      anim.push((c, t) => { c.strokeStyle = th.top + '66'; c.lineWidth = 1; for (let i = 0; i < 12; i++) { const y = H - 120 + i * i * 1.4; c.beginPath(); c.moveTo(0, y); c.lineTo(W, y); c.stroke(); } for (let i = -10; i <= 10; i++) { c.beginPath(); c.moveTo(W / 2 + i * 20, H - 120); c.lineTo(W / 2 + i * 120, H + 40); c.stroke(); } });
      each(10, (x, i) => { f.save(); f.translate(x, 50 + (i * 31) % 160); f.rotate((r() - .5) * 1.2); PP.rect(f, -14, -22, 28, 44, ['#ff5bd1', '#3affff', '#ffe14d', '#7a5aff'][i % 4], 3, 4); PP.rect(f, -9, -17, 18, 34, '#1a0a3a', 2, 3); f.restore(); });
      if (scene === 'devourer') { for (let x = 0; x < BGW; x += 30) { PP.poly(m, [[x, -4], [x + 15, 40 + r() * 30], [x + 30, -4]], '#fff0e0'); } }
      break; }
    case 'circus': case 'park': {
      if (scene === 'circus') each(3, (x, i) => { const w = 180; for (let k = 0; k < 8; k++) PP.poly(f, [[x + w / 2, H - 260], [x + k * w / 8, H - 90], [x + (k + 1) * w / 8, H - 90]], k % 2 ? '#e02a3a' : '#fff', 2); PP.rect(f, x + w / 2 - 2, H - 290, 4, 32, '#ffe14d', 1.5); PP.poly(f, [[x + w / 2 + 2, H - 290], [x + w / 2 + 26, H - 282], [x + w / 2 + 2, H - 274]], '#7fff3a', 1.5); });
      else { f.strokeStyle = INK; f.lineWidth = 7; f.beginPath(); for (let x = 0; x <= BGW; x += 6) f.lineTo(x, 150 + Math.sin(x / BGW * Math.PI * 4) * 60); f.stroke(); f.strokeStyle = '#ff3a7a'; f.lineWidth = 4; f.stroke(); for (let x = 0; x <= BGW; x += 30) { f.strokeStyle = INK; f.lineWidth = 5; f.beginPath(); f.moveTo(x, 150 + Math.sin(x / BGW * Math.PI * 4) * 60); f.lineTo(x, H); f.stroke(); f.strokeStyle = '#ffe0a0'; f.lineWidth = 2; f.stroke(); }
        anim.push((c, t, ox) => { const X = ((700 - ox * .15) % BGW + BGW) % BGW - 100, Y = 150, rr = 90; c.save(); c.translate(X, Y); c.rotate(t * .3); c.strokeStyle = INK; c.lineWidth = 5; c.beginPath(); c.arc(0, 0, rr, 0, 7); c.stroke(); c.strokeStyle = '#ff5bd1'; c.lineWidth = 3; c.stroke(); for (let a = 0; a < 6.283; a += .785) { c.strokeStyle = '#fff'; c.lineWidth = 2; c.beginPath(); c.moveTo(0, 0); c.lineTo(Math.cos(a) * rr, Math.sin(a) * rr); c.stroke(); } c.restore(); for (let a = 0; a < 6.283; a += .785) { const ax = X + Math.cos(a + t * .3) * rr, ay = Y + Math.sin(a + t * .3) * rr; PP.rect(c, ax - 8, ay, 16, 12, hsl(a * 50, 90, 60), 2, 3); } }); }
      for (let x = 0; x < BGW; x += 12) { const y = 30 + Math.sin(x / 70) * 14; m.fillStyle = INK; m.beginPath(); m.arc(x, y, 3.5, 0, 7); m.fill(); m.fillStyle = ['#ff3a3a', '#ffe14d', '#3aff8a', '#3a8aff'][(x / 12) % 4]; m.beginPath(); m.arc(x, y, 2.5, 0, 7); m.fill(); }
      each(5, (x, i) => { PP.rect(m, x, H - 110, 70, 50, '#fff', 3, 4); for (let k = 0; k < 5; k++) m.fillStyle = k % 2 ? '#e02a3a' : '#fff', m.fillRect(x + k * 14, H - 118, 14, 10); PP.rect(m, x - 2, H - 120, 74, 12, '#e02a3a', 3, 4); m.fillStyle = INK; m.font = 'bold 10px monospace'; m.fillText(['POPCORN', 'TICKETS', 'PRIZES', 'FREAKS', 'CANDY'][i % 5], x + 6, H - 82); });
      break; }
    case 'fishery': {
      each(5, (x, i) => { PP.rect(f, x, 60, 110, 210, '#0a5a6a', 3, 10); PP.rect(f, x + 8, 70, 94, 190, '#3ad0d0', 2, 8); anim.push((c, t, ox) => { const X = ((x - ox * .15) % BGW + BGW) % BGW - 60; if (X < -120 || X > W + 20) return; for (let k = 0; k < 2; k++) { const fx = X + 30 + Math.sin(t * .8 + k * 2 + i) * 30, fy = 120 + k * 60 + Math.sin(t * 1.3 + k) * 10; PP.ell(c, fx, fy, 12, 7, '#ffcc33', 2); PP.poly(c, [[fx - 12, fy], [fx - 20, fy - 6], [fx - 20, fy + 6]], '#ffcc33', 2); PP.ell(c, fx + 5, fy - 2, 2, 2, INK, 0); } for (let k = 0; k < 4; k++) { const by = 250 - ((t * 30 + k * 50 + i * 20) % 180); c.strokeStyle = '#fff'; c.lineWidth = 1.5; c.beginPath(); c.arc(X + 20 + k * 18, by, 3, 0, 7); c.stroke(); } }); });
      for (let i = 0; i < 3; i++) PP.rect(m, -4, 70 + i * 60, BGW + 8, 12, ['#ffe14d', '#ff5bd1', '#c8d0e0'][i], 2.5);
      break; }
    case 'prison': {
      PP.rect(f, -4, H - 220, BGW + 8, 160, '#8a8ab0', 3); for (let x = 0; x < BGW; x += 40) PP.rect(f, x, H - 220, 20, 160, '#9a9ac8', 0); each(5, (x, i) => { f.save(); f.translate(x, H - 180); f.rotate(-.1); f.fillStyle = ['#ff5bd1', '#7fff3a', '#ffe14d'][i % 3]; f.font = 'bold 20px monospace'; f.lineWidth = 4; f.strokeStyle = INK; f.strokeText(['FREE!', 'LOL', 'MOSH', '333'][i % 4], 0, 0); f.fillText(['FREE!', 'LOL', 'MOSH', '333'][i % 4], 0, 0); f.restore(); });
      each(3, (x) => { PP.rect(f, x, H - 300, 40, 90, '#6a6a90', 3); PP.poly(f, [[x - 10, H - 300], [x + 20, H - 330], [x + 50, H - 300]], '#e02a3a'); });
      for (let x = 0; x < BGW; x += 16) PP.rect(m, x, H - 140, 5, 80, '#4a4a6a', 2);
      break; }
    case 'junk': case 'derby': {
      PP.hill(f, BGW, H - 110, 80, 1.3, .5, '#a08a6a', 3, 3);
      each(26, (x, i) => { const y = H - 120 - r() * 70; PP.rect(f, x, y, 14 + r() * 20, 10 + r() * 14, ['#e04a3a', '#3a8ae0', '#e0c02a', '#8a8a9a', '#a04ae0', '#3ae08a', '#ff8a2a'][i % 7], 2.5, 2); });
      if (scene === 'derby') { for (let y = 0; y < 5; y++) PP.rect(m, -4, H - 170 + y * 18, BGW + 8, 8, '#8a4a2a', 2.5); animF.push((c, t, ox) => { const b = AudioSys.beat(); for (let i = 0; i < 60; i++) { const x = ((i * 16 - ox * .4) % (W + 20) + W + 20) % (W + 20) - 10, y = H - 176 + (i % 5) * 18 - (b.phase < .2 && i % 2 ? 3 : 0); PP.ell(c, x, y, 5, 5, hsl(i * 37 % 360, 70, 55), 1.5); } }); }
      else { PP.hill(m, BGW, H - 60, 50, 2, 1, '#7a9a4a', 3); each(8, (x) => { PP.ell(m, x, H - 70 - r() * 30, 14, 14, '#222', 3); PP.ell(m, x, H - 70 - r() * 30, 6, 6, '#888', 2); }); }
      break; }
  }
  return { far, mid, sky: [s0, s1], skyC: sky, anim, animF };
}
