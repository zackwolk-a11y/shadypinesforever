// ============================================================================
// Graphics: supplied-art sprites, procedural pixel art (shade+outline pass),
// sprite caches (flip / flash), drawing helpers.
// ============================================================================
const IMG = {}, META = SPRITE_META;
function loadAssets() {
  return Promise.all(Object.entries(ASSET_DATA).map(([k, src]) => new Promise(res => {
    const im = new Image(); im.onload = () => { const c = makeCanvas(im.width, im.height); c.ctx.drawImage(im, 0, 0); IMG[k] = c; res(); }; im.onerror = res; im.src = src;
  })));
}
const _flipCache = new Map(), _flashCache = new Map();
function flipped(img) {
  let f = _flipCache.get(img); if (f) return f;
  f = makeCanvas(img.width, img.height); f.ctx.translate(img.width, 0); f.ctx.scale(-1, 1); f.ctx.drawImage(img, 0, 0); _flipCache.set(img, f); return f;
}
function flashOf(img, color = '#fff') {
  const key = img; let m = _flashCache.get(key); if (!m) { m = {}; _flashCache.set(key, m); }
  if (m[color]) return m[color];
  const f = makeCanvas(img.width, img.height); f.ctx.drawImage(img, 0, 0); f.ctx.globalCompositeOperation = 'source-atop'; f.ctx.fillStyle = color; f.ctx.fillRect(0, 0, img.width, img.height);
  return m[color] = f;
}
// draw sprite: (x,y) is the anchor point (default bottom-centre) in screen space
function spr(img, x, y, o = {}) {
  if (!img) return;
  const ax = o.ax !== undefined ? o.ax : img.width / 2, ay = o.ay !== undefined ? o.ay : img.height;
  let src = o.flip ? flipped(img) : img; const aax = o.flip ? img.width - ax : ax;
  if (o.flash) src = flashOf(src, o.flash === true ? '#fff' : o.flash);
  const sx = o.sx || 1, sy = o.sy || 1;
  if (!o.rot && sx === 1 && sy === 1 && !o.alpha) { ctx.drawImage(src, Math.round(x - aax), Math.round(y - ay)); return; }
  ctx.save(); if (o.alpha !== undefined) ctx.globalAlpha *= o.alpha;
  ctx.translate(Math.round(x), Math.round(y)); if (o.rot) ctx.rotate(o.rot); ctx.scale(sx, sy);
  ctx.drawImage(src, -aax, -ay); ctx.restore();
}
// strip-deformed draw (wobble/morph): fx(row01) -> {dx, sx}
function sprWarp(img, x, y, o, fx) {
  const w = img.width, h = img.height, step = o.step || 2, sy = o.sy || 1, src = o.flip ? flipped(img) : img;
  const s2 = o.flash ? flashOf(src, o.flash === true ? '#fff' : o.flash) : src;
  if (o.alpha !== undefined) { ctx.save(); ctx.globalAlpha = o.alpha; }
  for (let r = 0; r < h; r += step) {
    const d = fx(r / h, r); const ws = w * (o.sx || 1) * (d.sx || 1);
    ctx.drawImage(s2, 0, r, w, step, Math.round(x - ws / 2 + (d.dx || 0)), Math.round(y - (h - r) * sy), Math.ceil(ws), Math.ceil(step * sy) + 1);
  }
  if (o.alpha !== undefined) ctx.restore();
}
// column-deformed draw (cape flutter, hair): fx(col01) -> dy
function sprWarpX(img, x, y, o, fy) {
  const w = img.width, h = img.height, step = o.step || 2, src = o.flip ? flipped(img) : img;
  for (let c = 0; c < w; c += step) {
    const u = o.flip ? 1 - c / w : c / w; const dy = fy(u);
    ctx.drawImage(src, c, 0, step, h, Math.round(x + c), Math.round(y + dy), step, h);
  }
}

// ---------------------------------------------------------------- procedural pixel-art pipeline
function shadeOutline(c, o = {}) {
  const w = c.width, h = c.height, x = c.ctx, id = x.getImageData(0, 0, w, h), d = id.data;
  const op = (i, j) => i >= 0 && j >= 0 && i < w && j < h && d[(j * w + i) * 4 + 3] > 0;
  const out = new Uint8ClampedArray(d);
  for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) {
    const k = (j * w + i) * 4;
    if (d[k + 3] > 0) {
      d[k + 3] = 255; out[k + 3] = 255;
      if (o.shade !== false) {
        let f = 1;
        if (!op(i, j - 1) || !op(i - 1, j)) f = 1.28; else if (!op(i, j + 1) || !op(i + 1, j)) f = .7;
        else if (!op(i, j + 2) || !op(i + 2, j)) f = .86;
        out[k] = Math.min(255, d[k] * f); out[k + 1] = Math.min(255, d[k + 1] * f); out[k + 2] = Math.min(255, d[k + 2] * f);
      }
    } else if (op(i - 1, j) || op(i + 1, j) || op(i, j - 1) || op(i, j + 1)) { out[k] = 10; out[k + 1] = 6; out[k + 2] = 14; out[k + 3] = 255; }
  }
  id.data.set(out); x.putImageData(id, 0, 0); return c;
}
// build an animated procedural sprite: frames = [canvas]
function makeSprite(w, h, frames, draw, o) {
  const arr = []; for (let f = 0; f < frames; f++) { const c = makeCanvas(w + 2, h + 2); c.ctx.translate(1, 1); draw(c.ctx, f, w, h); c.ctx.setTransform(1, 0, 0, 1, 0, 0); arr.push(shadeOutline(c, o)); } return arr;
}
// primitive helpers for procedural art (integer-snapped)
const P = {
  r(c, x, y, w, h, col) { c.fillStyle = col; c.fillRect(Math.round(x), Math.round(y), Math.round(w), Math.round(h)); },
  e(c, x, y, rx, ry, col) { c.fillStyle = col; c.beginPath(); c.ellipse(Math.round(x), Math.round(y), Math.max(.5, rx), Math.max(.5, ry), 0, 0, 7); c.fill(); },
  poly(c, pts, col) { c.fillStyle = col; c.beginPath(); pts.forEach((p, i) => i ? c.lineTo(p[0], p[1]) : c.moveTo(p[0], p[1])); c.closePath(); c.fill(); },
  l(c, x0, y0, x1, y1, col, w = 1) { c.strokeStyle = col; c.lineWidth = w; c.beginPath(); c.moveTo(x0, y0); c.lineTo(x1, y1); c.stroke(); },
  eye(c, x, y, r, look = 0, col = '#fff') { P.e(c, x, y, r, r, col); P.r(c, x - 1 + look, y - 1, 2, 2, '#000'); },
  teeth(c, x, y, w, n, col = '#fff6c0') { const tw = w / n; for (let i = 0; i < n; i++) P.poly(c, [[x + i * tw, y], [x + i * tw + tw, y], [x + i * tw + tw / 2, y + 3]], col); }
};

// ---------------------------------------------------------------- enemy & prop sprite library
const SPR = {};
function buildProceduralSprites() {
  // --- World 1
  SPR.puppet = makeSprite(20, 30, 4, (c, f) => {
    const sw = [0, 2, 0, -2][f];
    P.l(c, 4, 0, 6, 12, '#ddd'); P.l(c, 16, 0, 14, 12, '#ddd'); P.l(c, 10, 0, 10, 4, '#ddd');
    P.r(c, 6, 14, 8, 9, '#c4302b'); P.r(c, 6, 18, 8, 2, '#f2c14e');
    P.r(c, 3 + sw, 14, 3, 8, '#e0b88a'); P.r(c, 14 - sw, 14, 3, 8, '#e0b88a');
    P.r(c, 7 - sw, 23, 2, 6, '#5a3a1d'); P.r(c, 11 + sw, 23, 2, 6, '#5a3a1d');
    P.e(c, 10, 8, 6, 6, '#e8c290'); P.r(c, 7, 6, 2, 2, '#000'); P.r(c, 11, 6, 2, 2, '#000'); P.r(c, 6, 10, 8, 2, '#8b1a1a'); P.r(c, 9, 12, 2, 3, '#e8c290');
    P.e(c, 5, 9, 1.5, 1, '#ff7b7b'); P.e(c, 15, 9, 1.5, 1, '#ff7b7b'); P.r(c, 5, 1, 10, 3, '#3b2a1a');
  });
  SPR.amp = makeSprite(24, 26, 4, (c, f) => {
    const st = [0, 1, 0, -1][f];
    P.r(c, 4 - st, 21, 4, 5, '#333'); P.r(c, 16 + st, 21, 4, 5, '#333');
    P.r(c, 1, 2, 22, 20, '#2a2a2e'); P.r(c, 3, 4, 18, 13, '#4b4b52');
    for (let i = 0; i < 6; i++) P.r(c, 4, 5 + i * 2, 16, 1, '#323238');
    P.r(c, 2, 18, 20, 3, '#c9a227'); for (let i = 0; i < 4; i++) P.e(c, 5 + i * 5, 19.5, 1, 1, '#222');
    P.poly(c, [[5, 7], [10, 9], [5, 10]], '#ff3b1f'); P.poly(c, [[19, 7], [14, 9], [19, 10]], '#ff3b1f');
    P.r(c, 7, 12 + (f % 2), 10, 3, '#100'); P.teeth(c, 7, 12 + (f % 2), 10, 4);
  });
  SPR.cable = makeSprite(26, 14, 4, (c, f) => {
    for (let i = 0; i < 6; i++) { const y = 8 + Math.sin(f * 1.5 + i * 1.1) * 3; P.e(c, 3 + i * 3.4, y, 3, 3, '#1d1d22'); }
    P.r(c, 20, 3 + Math.sin(f * 1.5 + 6.6) * 3, 6, 6, '#9a9aa3'); P.r(c, 25, 4 + Math.sin(f * 1.5 + 6.6) * 3, 2, 1, '#ddd'); P.r(c, 25, 7 + Math.sin(f * 1.5 + 6.6) * 3, 2, 1, '#ddd');
    if (f % 2) P.r(c, 24, 1, 2, 2, '#fff36b');
  });
  SPR.bookbat = makeSprite(26, 18, 4, (c, f) => {
    const wing = [0, 4, 7, 4][f];
    P.poly(c, [[13, 9], [1, 3 + wing], [3, 15], [13, 15]], '#6b2fa0'); P.poly(c, [[13, 9], [25, 3 + wing], [23, 15], [13, 15]], '#6b2fa0');
    P.poly(c, [[13, 10], [4, 6 + wing], [5, 13], [13, 13]], '#f2e6c8'); P.poly(c, [[13, 10], [22, 6 + wing], [21, 13], [13, 13]], '#f2e6c8');
    P.r(c, 6, 9, 5, 1, '#999'); P.r(c, 15, 9, 5, 1, '#999');
    P.e(c, 13, 12, 3, 3, '#300'); P.teeth(c, 10, 10, 6, 3); P.r(c, 10, 6, 2, 2, '#ff2'); P.r(c, 15, 6, 2, 2, '#ff2');
  });
  SPR.candle = makeSprite(16, 28, 4, (c, f) => {
    const fl = [0, 1, 0, -1][f];
    P.poly(c, [[8 + fl, 0], [12, 7], [8, 11], [4, 7]], '#ffb21f'); P.e(c, 8, 7, 2, 3, '#fff3a0');
    P.r(c, 3, 11, 10, 15, '#efe7d2'); P.r(c, 3, 11, 3, 6, '#fffaf0'); P.r(c, 10, 14, 3, 8, '#d9ccb0');
    P.r(c, 5, 15, 2, 3, '#000'); P.r(c, 9, 15, 2, 3, '#000'); P.e(c, 8, 21, 2, 1.5 + (f % 2), '#300');
    P.r(c, 1, 26, 14, 2, '#8a6a2a');
  });
  SPR.soldier = makeSprite(18, 30, 4, (c, f) => {
    const sw = [0, 2, 0, -2][f];
    P.r(c, 5, 0, 8, 7, '#1b1b6a'); P.r(c, 4, 6, 10, 2, '#000'); P.e(c, 9, 10, 4, 3.5, '#f0c8a0'); P.r(c, 7, 9, 1, 2, '#000'); P.r(c, 10, 9, 1, 2, '#000');
    P.r(c, 4, 13, 10, 9, '#c0262d'); P.l(c, 4, 13, 14, 22, '#fff', 1); P.r(c, 4, 22, 10, 2, '#000');
    P.r(c, 5 + sw, 24, 3, 6, '#1b1b6a'); P.r(c, 10 - sw, 24, 3, 6, '#1b1b6a');
    P.r(c, 15, 2, 1, 26, '#8a6a3a'); P.poly(c, [[13, 3], [15.5, -1], [18, 3]], '#ccc');
  });
  // --- World 2
  SPR.loop = makeSprite(22, 22, 4, (c, f) => {
    const sq = [0, 1, 2, 1][f];
    P.e(c, 11, 12 + sq / 2, 10, 9 - sq / 2, '#f07ab8'); P.e(c, 11, 12 + sq / 2, 4, 3, 'rgba(0,0,0,0)');
    c.globalCompositeOperation = 'destination-out'; P.e(c, 11, 13, 3, 2.5, '#000'); c.globalCompositeOperation = 'source-over';
    [[5, 7, '#ffef5b'], [15, 6, '#5bd4ff'], [17, 14, '#7dff5b'], [6, 16, '#fff']].forEach(([x, y, cl]) => P.r(c, x, y, 2, 1, cl));
    P.eye(c, 7, 8, 2.4); P.eye(c, 15, 8, 2.4); P.r(c, 7, 17, 8, 2, '#600');
  });
  SPR.toaster = makeSprite(24, 22, 2, (c, f) => {
    P.r(c, 2, 6, 20, 15, '#c7ccd4'); P.r(c, 2, 6, 20, 3, '#eef1f5'); P.r(c, 5, 4, 5, 3, '#222'); P.r(c, 14, 4, 5, 3, '#222');
    if (f) { P.r(c, 6, 0, 3, 5, '#d49a4a'); P.r(c, 15, -1, 3, 6, '#d49a4a'); }
    P.r(c, 21, 10, 3, 2, '#555'); P.eye(c, 8, 12, 2.5); P.eye(c, 16, 12, 2.5); P.r(c, 6, 9, 5, 1, '#000'); P.r(c, 13, 9, 5, 1, '#000');
    P.r(c, 8, 16, 8, 3, '#300'); P.r(c, 3, 21, 3, 1, '#444'); P.r(c, 18, 21, 3, 1, '#444');
  });
  SPR.carton = makeSprite(18, 28, 4, (c, f) => {
    const sw = [0, 2, 0, -2][f];
    P.poly(c, [[2, 6], [9, 0], [16, 6]], '#e8e8f0'); P.r(c, 2, 6, 14, 16, '#f4f4fa'); P.r(c, 2, 10, 14, 5, '#3a8de0');
    P.r(c, 4, 11, 10, 1, '#fff'); P.eye(c, 6, 17, 2); P.eye(c, 12, 17, 2); P.r(c, 6, 20, 6, 1, '#600');
    P.r(c, 4 + sw, 22, 3, 6, '#ccc'); P.r(c, 11 - sw, 22, 3, 6, '#ccc'); if (f % 2) P.e(c, 16, 4, 2, 2, '#fff');
  });
  SPR.bacon = makeSprite(30, 12, 4, (c, f) => {
    for (let i = 0; i < 10; i++) { const y = 5 + Math.sin(f * 1.6 + i * .8) * 2.5; P.r(c, i * 2.8, y, 3.4, 6, i % 3 === 1 ? '#f5c6a5' : '#b8352b'); }
    const hy = 5 + Math.sin(f * 1.6 + 8) * 2.5; P.eye(c, 27, hy + 1, 1.8); P.r(c, 25, hy + 4, 4, 1, '#300');
  });
  SPR.cultcow = makeSprite(20, 30, 4, (c, f) => {
    const sw = [0, 1, 0, -1][f];
    P.poly(c, [[10, 2], [19, 30], [1, 30]], '#5b2a86'); P.poly(c, [[10, 2], [16, 14], [4, 14]], '#43206a');
    P.e(c, 10, 11, 4.5, 4, '#f4f4f4'); P.e(c, 10, 14, 3.5, 2, '#f5a0b0'); P.r(c, 8, 13, 1, 1, '#000'); P.r(c, 11, 13, 1, 1, '#000');
    P.r(c, 7, 9, 2, 2, '#ff2'); P.r(c, 11, 9, 2, 2, '#ff2'); P.r(c, 4 + sw, 18, 3, 3, '#f4f4f4'); P.r(c, 13 - sw, 18, 3, 3, '#f4f4f4');
    P.r(c, 15, 10 - sw, 1, 14, '#ccb070'); P.e(c, 15.5, 9 - sw, 2, 2, '#ffd84a');
  });
  // --- World 3
  SPR.shroom = makeSprite(22, 24, 2, (c, f) => {
    P.r(c, 8, 12, 6, 12, '#efe2c4'); P.e(c, 11, 10, 11, 8, '#d23be0'); [[5, 7], [15, 5], [17, 11], [8, 12]].forEach(([x, y]) => P.e(c, x, y, 1.6, 1.6, '#ffe8ff'));
    P.e(c, 11, 9, 4.5, 4.5, '#fff'); P.e(c, 11 + (f ? 1 : -1), 9, 2.4, 2.4, '#1db954'); P.r(c, 10 + (f ? 1 : -1), 8, 2, 2, '#000');
    P.l(c, 8, 7, 9, 8, '#c00'); P.l(c, 14, 11, 13, 10, '#c00');
  });
  SPR.lava = makeSprite(18, 22, 4, (c, f) => {
    const s = [0, 1, 2, 1][f]; P.e(c, 9, 11, 8 - s / 2, 10 + s / 2, '#ff6a2a'); P.e(c, 7, 7, 3, 4, '#ffd04a'); P.e(c, 12, 15, 2, 3, '#ffb03a');
    P.eye(c, 6, 11, 2); P.eye(c, 12, 11, 2); P.e(c, 9, 16, 2, 1 + f % 2, '#600');
  });
  SPR.spark = makeSprite(22, 24, 4, (c, f) => {
    P.e(c, 11, 10, 8, 9, '#7fe7ff'); P.poly(c, [[3, 12], [6, 23], [9, 18], [11, 24], [14, 18], [17, 23], [19, 12]], '#7fe7ff');
    P.e(c, 8, 9, 2, 3, '#003'); P.e(c, 14, 9, 2, 3, '#003'); P.e(c, 11, 15, 3, 1 + f % 2, '#003');
    if (f % 2) { P.l(c, 0, 4, 4, 8, '#fff36b', 1); P.l(c, 21, 2, 18, 7, '#fff36b', 1); }
  });
  SPR.hand = makeSprite(22, 20, 2, (c, f) => {
    const g = f ? 3 : 0; P.r(c, 6, 9, 11, 9, '#9be07a'); for (let i = 0; i < 4; i++) P.r(c, 6 + i * 3, 2 + g + (i % 2), 2, 8 - g, '#9be07a');
    P.r(c, 16, 10, 5, 3, '#9be07a'); P.r(c, 7, 15, 9, 1, '#6aa050'); P.e(c, 11, 13, 2, 2, '#fff'); P.r(c, 10, 12, 2, 2, '#c00'); P.r(c, 3, 17, 4, 3, '#55306a');
  });
  SPR.felt = makeSprite(20, 26, 4, (c, f) => {
    const m = [0, 1, 2, 1][f]; P.e(c, 10, 13 + m, 9, 11 - m, '#47b5ff'); P.r(c, 2, 20 + m, 16, 6 - m, '#47b5ff');
    P.e(c, 6, 9, 3, 3.5, '#fff'); P.e(c, 14, 9 + m, 3, 3.5, '#fff'); P.r(c, 5, 9, 2, 2, '#000'); P.r(c, 13, 10 + m, 2, 2, '#000');
    P.e(c, 10, 17 + m, 4, 2, '#d42d5a'); for (let i = 0; i < 5; i++) P.r(c, 2 + i * 4, 24, 2, 2 + (i + f) % 3, '#47b5ff');
  });
  // --- World 4
  SPR.clown = makeSprite(22, 32, 4, (c, f) => {
    const sw = [0, 2, 0, -2][f], arm = f === 3 ? -5 : 0;
    P.e(c, 4, 7, 4, 4, '#ff4d2e'); P.e(c, 18, 7, 4, 4, '#ff4d2e'); P.e(c, 11, 9, 6, 6.5, '#fbf3ea');
    P.r(c, 8, 6, 2, 2, '#000'); P.r(c, 12, 6, 2, 2, '#000'); P.l(c, 7, 4, 10, 5, '#000'); P.l(c, 15, 4, 12, 5, '#000'); P.e(c, 11, 10, 2, 2, '#e8102a');
    P.r(c, 7, 13, 8, 2, '#a00'); P.teeth(c, 7, 13, 8, 4);
    P.r(c, 5, 16, 12, 9, '#7a3cff'); P.e(c, 11, 18, 1.5, 1.5, '#ffe14d'); P.e(c, 11, 22, 1.5, 1.5, '#ffe14d');
    P.r(c, 3 + sw, 25, 5, 5, '#3dd16a'); P.r(c, 14 - sw, 25, 5, 5, '#3dd16a'); P.r(c, 1 + sw, 29, 8, 3, '#e8102a'); P.r(c, 13 - sw, 29, 8, 3, '#e8102a');
    P.r(c, 17, 16 + arm, 3, 6, '#7a3cff'); P.r(c, 18, 11 + arm, 2, 6, '#ddd');
  });
  SPR.balloon = makeSprite(16, 28, 2, (c, f) => {
    P.e(c, 8, 8, 7, 8, f ? '#ff5bd1' : '#ff3d6a'); P.r(c, 5, 4, 2, 3, '#fff'); P.poly(c, [[7, 16], [9, 16], [8, 18]], '#c02050');
    P.l(c, 8, 18, 6 + f * 3, 27, '#ddd'); P.r(c, 5, 8, 2, 2, '#000'); P.r(c, 10, 8, 2, 2, '#000'); P.r(c, 6, 12, 5, 1, '#000');
  });
  SPR.fish = makeSprite(26, 22, 4, (c, f) => {
    const sw = [0, 2, 0, -2][f];
    P.poly(c, [[0, 4], [6, 10], [0, 16]], '#4ec27a'); P.e(c, 13, 10, 10, 7, '#5ee08a'); P.e(c, 14, 13, 7, 3, '#c9ffd9');
    P.e(c, 19, 7, 3.5, 3.5, '#fff'); P.r(c, 19, 6, 2, 2, '#c00'); P.r(c, 17, 13, 7, 2, '#300'); P.teeth(c, 17, 13, 7, 3);
    P.poly(c, [[10, 3], [14, 0], [16, 4]], '#2f9a58'); P.r(c, 9 + sw, 16, 2, 6, '#f2a35a'); P.r(c, 15 - sw, 16, 2, 6, '#f2a35a');
  });
  SPR.teddy = makeSprite(22, 28, 4, (c, f) => {
    const sw = [0, 2, 0, -2][f];
    P.e(c, 5, 4, 3, 3, '#a06a3a'); P.e(c, 17, 4, 3, 3, '#a06a3a'); P.e(c, 11, 8, 7, 6, '#b67a44'); P.e(c, 11, 10, 3, 2, '#e0b080');
    P.r(c, 7, 6, 2, 2, '#000'); P.l(c, 13, 5, 16, 8, '#000'); P.l(c, 16, 5, 13, 8, '#000');
    P.r(c, 4, 14, 14, 10, '#f0f0f0'); for (let i = 0; i < 3; i++) P.r(c, 4, 15 + i * 3, 14, 1.5, '#222');
    P.r(c, 5 + sw, 24, 4, 4, '#b67a44'); P.r(c, 13 - sw, 24, 4, 4, '#b67a44'); P.l(c, 11, 2, 11, 8, '#ff5555');
  });
  SPR.ticket = makeSprite(18, 18, 4, (c, f) => {
    P.r(c, 1, 3 + (f % 2), 16, 11, '#ffcc33'); P.r(c, 1, 3 + (f % 2), 2, 11, '#e09a1a'); P.r(c, 15, 3 + (f % 2), 2, 11, '#e09a1a');
    P.eye(c, 6, 7 + (f % 2), 2); P.eye(c, 12, 7 + (f % 2), 2); P.r(c, 5, 11 + (f % 2), 8, 1, '#600');
    P.r(c, 3 + [0, 2, 0, -2][f], 14, 2, 4, '#600'); P.r(c, 13 - [0, 2, 0, -2][f], 14, 2, 4, '#600');
  });
  // --- World 5
  SPR.rat = makeSprite(26, 16, 4, (c, f) => {
    const sw = [0, 2, 0, -2][f]; P.l(c, 0, 9, 7, 10 + (f % 2), '#d48b9c', 2);
    P.e(c, 12, 9, 7, 5, '#77707a'); P.e(c, 20, 8, 5, 4, '#8b848e'); P.e(c, 17, 3, 2.5, 2.5, '#d48b9c'); P.r(c, 24, 8, 2, 2, '#f06');
    P.r(c, 20, 6, 2, 2, '#ff2'); P.r(c, 21, 11, 3, 2, '#fff'); P.r(c, 8 + sw, 13, 2, 3, '#555'); P.r(c, 15 - sw, 13, 2, 3, '#555');
  });
  SPR.can = makeSprite(24, 20, 4, (c, f) => {
    const cl = f % 2 ? 3 : 0; P.r(c, 6, 4, 12, 11, '#c8312e'); P.r(c, 6, 4, 12, 2, '#ddd'); P.r(c, 6, 13, 12, 2, '#ddd'); P.r(c, 9, 8, 6, 3, '#fff');
    P.poly(c, [[6, 8], [0, 4 - cl], [1, 9], [6, 10]], '#ff6a3a'); P.poly(c, [[18, 8], [24, 4 - cl], [23, 9], [18, 10]], '#ff6a3a');
    P.r(c, 9, 1, 2, 3, '#000'); P.r(c, 13, 1, 2, 3, '#000'); for (let i = 0; i < 3; i++) { P.r(c, 6 + i * 2 + [0, 1, 0, -1][f], 15, 1, 5, '#a33'); P.r(c, 17 - i * 2 - [0, 1, 0, -1][f], 15, 1, 5, '#a33'); }
  });
  SPR.toy = makeSprite(18, 28, 4, (c, f) => {
    const sw = [0, 1, 0, -1][f]; P.e(c, 9, 7, 6, 6, '#f6d2b8'); P.r(c, 3, 1, 12, 4, '#ffe14d'); P.r(c, 6, 6, 2, 2, '#38f'); P.r(c, 10, 6, 2, 2, '#38f');
    P.l(c, 6, 10, 12, 11, '#c00'); P.r(c, 4, 13, 10, 10, '#ff7ab8'); P.r(c, 4, 18, 10, 2, '#fff'); P.r(c, 5 + sw, 23, 3, 5, '#f6d2b8'); P.r(c, 10 - sw, 23, 3, 5, '#f6d2b8');
    P.r(c, 14, 15, 3, 2, '#aaa'); P.r(c, 16, 13 + (f % 2) * 2, 2, 6, '#ccc');
  });
  SPR.bag = makeSprite(24, 26, 4, (c, f) => {
    const s = [0, 1, 2, 1][f]; P.e(c, 12, 15 + s / 2, 11, 10 - s / 2, '#2c2c34'); P.poly(c, [[9, 5], [12, 0], [15, 5]], '#2c2c34'); P.r(c, 10, 5, 4, 2, '#ffe14d');
    P.e(c, 8, 13, 2.5, 2.5, '#9f9'); P.e(c, 16, 13, 2.5, 2.5, '#9f9'); P.r(c, 7, 19, 10, 2, '#000'); P.teeth(c, 7, 19, 10, 4, '#9f9');
    P.r(c, 3, 9, 3, 2, '#4a4a55'); P.r(c, 19, 21, 3, 2, '#4a4a55');
  });
  // --- World 6
  SPR.roadie = makeSprite(20, 32, 4, (c, f) => {
    const sw = [0, 2, 0, -2][f]; P.e(c, 10, 7, 6, 6, '#8fbf7a'); P.r(c, 4, 1, 12, 3, '#222'); P.r(c, 6, 6, 3, 2, '#ff0'); P.r(c, 11, 6, 3, 2, '#ff0');
    P.r(c, 7, 10, 6, 2, '#300'); P.r(c, 3, 13, 14, 11, '#1a1a1a'); P.r(c, 6, 15, 8, 4, '#d33'); P.r(c, 0, 14 + sw, 3, 8, '#8fbf7a'); P.r(c, 17, 14 - sw, 3, 8, '#8fbf7a');
    P.r(c, 5 + sw, 24, 4, 8, '#2a3a6a'); P.r(c, 11 - sw, 24, 4, 8, '#2a3a6a');
  });
  SPR.speaker = makeSprite(22, 30, 2, (c, f) => {
    P.r(c, 1, 1, 20, 28, '#1c1c20'); const r = f ? 7 : 6; P.e(c, 11, 9, r, r, '#3b3b44'); P.e(c, 11, 9, 3, 3, '#111'); P.e(c, 11, 22, r - 2, r - 2, '#3b3b44'); P.e(c, 11, 22, 2, 2, '#111');
    P.r(c, 3, 3, 3, 2, '#f22'); P.r(c, 16, 3, 3, 2, '#f22');
  });
  // --- bosses / big procedural creatures
  SPR.bear = makeSprite(60, 56, 2, (c, f) => {
    const b = f; P.e(c, 14, 10, 7, 7, '#6b3d1c'); P.e(c, 46, 10, 7, 7, '#6b3d1c'); P.e(c, 14, 10, 3, 3, '#d49a6a'); P.e(c, 46, 10, 3, 3, '#d49a6a');
    P.e(c, 30, 36, 26, 20, '#7a4520'); P.e(c, 30, 22, 18, 15, '#8a5028'); P.e(c, 30, 28, 9, 6, '#e0b080'); P.e(c, 30, 25, 3, 2, '#111');
    P.e(c, 22, 18, 3, 3, '#fff'); P.e(c, 38, 18, 3, 3, '#fff'); P.r(c, 21, 17 + b, 2, 2, '#000'); P.r(c, 37, 17 + b, 2, 2, '#000');
    P.r(c, 25, 31, 10, 2, '#5a2010'); P.e(c, 30, 44, 12, 9, '#c08050'); P.r(c, 6, 46, 12, 8, '#6b3d1c'); P.r(c, 42, 46, 12, 8, '#6b3d1c');
    for (let i = 0; i < 3; i++) { P.r(c, 7 + i * 4, 52, 2, 3, '#ffe'); P.r(c, 43 + i * 4, 52, 2, 3, '#ffe'); }
    P.e(c, 30, 4, 4, 3, '#ff5bd1'); P.r(c, 27, 3, 6, 1, '#fff');
  });
  SPR.cart = makeSprite(40, 26, 2, (c, f) => {
    P.r(c, 2, 2, 34, 14, '#9aa3ad'); for (let i = 0; i < 7; i++) P.r(c, 4 + i * 5, 3, 1, 12, '#5a6470'); P.r(c, 2, 8, 34, 1, '#5a6470');
    P.r(c, 34, 0, 6, 3, '#e33'); P.r(c, 4, 16, 30, 3, '#6a7480');
    for (const x of [8, 30]) { P.e(c, x, 22, 4, 4, '#222'); P.r(c, x - 1 + (f ? 1 : 0), 20, 2, 2, '#aaa'); }
  });
}
// small icons (pixel maps)
function pixmap(rows, pal, sc = 1) {
  const h = rows.length, w = rows[0].length, c = makeCanvas(w * sc, h * sc);
  rows.forEach((r, y) => [...r].forEach((ch, x) => { if (ch !== '.' && pal[ch]) { c.ctx.fillStyle = pal[ch]; c.ctx.fillRect(x * sc, y * sc, sc, sc); } }));
  return c;
}
const ICON = {};
function buildIcons() {
  ICON.note = pixmap(['....kkk.', '...kyyyk', '...kyykk', '...kyk..', '...kyk..', '.kkkyk..', 'kyyyyk..', 'kyyyyk..', '.kkkk...'], { k: '#120a00', y: '#ffd23a' });
  ICON.heart = pixmap(['.kk.kk.', 'krrkrrk', 'krwrrrk', 'krrrrrk', '.krrrk.', '..krk..', '...k...'], { k: '#000', r: '#ff2244', w: '#ffaabb' });
  ICON.heartE = pixmap(['.kk.kk.', 'k..k..k', 'k.....k', 'k.....k', '.k...k.', '..k.k..', '...k...'], { k: '#552233' });
  ICON.shard = pixmap(['...k...', '..kck..', '.kcwck.', 'kccwcck', '.kcpck.', '..kpk..', '...k...'], { k: '#000', c: '#b04bff', w: '#fff', p: '#ff5bd1' }, 2);
  ICON.skull = pixmap(['.kkkkk.', 'kwwwwwk', 'kwkwkwk', 'kwwwwwk', '.kwkwk.', '..kkk..'], { k: '#000', w: '#eee' }, 2);
  ICON.metal = pixmap(['k.....k', 'kk...kk', '.kk.kk.', '..kkk..', '.kgggk.', 'kgggggk', '.kgggk.'], { k: '#000', g: '#7fff3a' });
  ICON.hook = pixmap(['.kkkk.', 'kmmmmk', 'km..mk', 'km..mk', 'kmmmmk', '.kkkk.'], { k: '#111', m: '#c8c8d8' }, 2);
  ICON.lock = pixmap(['.kkk.', 'k...k', 'kkkkk', 'kyyyk', 'kykyk', 'kkkkk'], { k: '#000', y: '#ffcc33' }, 2);
  ICON.star = pixmap(['...k...', '..kyk..', 'kkyyykk', '.kyyyk.', '.kykyk.', 'kk...kk'], { k: '#000', y: '#ffe14d' }, 2);
  ICON.ach = pixmap(['kkkkkkk', 'kyyyyyk', '.kyyyk.', '..kyk..', '..kyk..', '.kkkkk.'], { k: '#000', y: '#ffcc33' }, 2);
  ICON.straw = pixmap(['..kkkk..', '.kyyyyk.', 'kyoyyoyk', 'kyyyyyyk', 'kyoyyoyk', '.kyyyyk.', '..kkkk..'], { k: '#3a2a00', y: '#ffd860', o: '#c09020' }, 2);
  ICON.stick = pixmap(['......kk', '.....kbk', '....kbk.', '...kbk..', '..kbk...', '.kbk....', 'kbk.....', 'kk......'], { k: '#2a1500', b: '#a0662a' }, 2);
  ICON.brick = pixmap(['kkkkkkkkk', 'krrrkrrrk', 'kkkkkkkkk', 'krkrrrkrk', 'kkkkkkkkk'], { k: '#2a0a00', r: '#c24a2a' }, 2);
  ICON.ticket = pixmap(['kkkkkkk', 'kyyyyyk', 'kyykyyk', 'kyyyyyk', 'kkkkkkk'], { k: '#000', y: '#ffcc33' }, 2);
  ICON.roadie = pixmap(['.kkk.', 'kgggk', 'kgkgk', 'kgggk', '.kbk.', 'kbbbk', '.k.k.'], { k: '#000', g: '#9fff8a', b: '#3a3aff' }, 2);
}
