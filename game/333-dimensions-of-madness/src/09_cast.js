// ============================================================================
// Character rigs built from the supplied artwork. Each rig animates the real
// sprite (squash/stretch, part rotation, strip warps) and adds matching
// hand-drawn pixel detail where the reference had no usable frames.
// ============================================================================
const A = n => (META[n] && META[n].anchors) || {};
function anchorPos(name, key, x, y, flip, scale = 1, ax, ay) {
  // convert sprite anchor to screen given sprite drawn with origin anchor (ax,ay) at (x,y)
  const m = META[name], a = A(name)[key]; if (!a) return [x, y];
  const dx = (a[0] - ax) * (flip ? -1 : 1) * scale, dy = (a[1] - ay) * scale; return [x + dx, y + dy];
}
// --------------------------------------------------------------------------- tongue
function drawTongue(x0, y0, x1, y1, thick = 5, sag = 6) {
  const mx = (x0 + x1) / 2, my = (y0 + y1) / 2 + sag;
  const path = () => { ctx.beginPath(); ctx.moveTo(x0, y0); ctx.quadraticCurveTo(mx, my, x1, y1); };
  ctx.lineCap = 'round';
  ctx.strokeStyle = '#1a0306'; ctx.lineWidth = thick + 3; path(); ctx.stroke();
  ctx.strokeStyle = '#e01a2a'; ctx.lineWidth = thick; path(); ctx.stroke();
  ctx.strokeStyle = '#ff7a8a'; ctx.lineWidth = Math.max(1, thick / 3); ctx.beginPath(); ctx.moveTo(x0, y0 - thick / 4); ctx.quadraticCurveTo(mx, my - thick / 3, x1, y1 - thick / 4); ctx.stroke();
  P.e(ctx, x1, y1, thick * .9 + 1.5, thick * .8 + 1.5, '#1a0306'); P.e(ctx, x1, y1, thick * .9, thick * .8, '#ff2a3a'); P.r(ctx, x1 - 1, y1 - 2, 2, 1, '#ffb0b8');
  ctx.lineCap = 'butt';
}
// --------------------------------------------------------------------------- hero
const HERO_FACE = -1; // the master art faces left
function drawHero(x, y, o = {}) {
  const mega = o.form === 'mega', img = mega ? IMG.hero_big : IMG.hero, name = mega ? 'hero_big' : 'hero';
  const sc = (o.scale || 1) * (mega ? 1.08 * HD : HD);
  const flip = (o.face || -1) !== HERO_FACE, c = A(name).center, ax = c[0], ay = c[1];
  const sx = (o.sx || 1) * sc, sy = (o.sy || 1) * sc;
  const scU = sc / HD; const ap = k => { const a = A(name)[k]; let dx = (a[0] - ax) * sx, dy = (a[1] - ay) * sy; if (flip) dx = -dx; const cs = Math.cos(o.rot || 0), sn = Math.sin(o.rot || 0); return [x + dx * cs - dy * sn, y + dx * sn + dy * cs]; };
  if (mega) { ctx.save(); ctx.globalCompositeOperation = 'lighter'; const g = ctx.createRadialGradient(x, y, 10, x, y, 80); g.addColorStop(0, 'rgba(127,255,58,.35)'); g.addColorStop(1, 'rgba(0,0,0,0)'); ctx.fillStyle = g; ctx.fillRect(x - 80, y - 80, 160, 160); ctx.restore(); }
  if (o.aura) { ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.globalAlpha = .5 + Math.sin(G.t * 20) * .2; spr(flashOf(img, '#7fff3a'), x, y, { ax, ay, flip, sx: sx * 1.12, sy: sy * 1.12, rot: o.rot }); ctx.restore(); }
  // form overlays drawn behind the head
  if (o.form === 'pig') { const [tx, ty] = ap('center'); const bx = tx + (flip ? -24 : 24) * scU; ctx.strokeStyle = '#000'; ctx.lineWidth = 4; ctx.beginPath(); ctx.arc(bx, ty + 4, 4, 0, 5); ctx.stroke(); ctx.strokeStyle = '#ff8ab0'; ctx.lineWidth = 2; ctx.stroke(); }
  if (o.form === 'clown') { const [tx, ty] = ap('top'); for (const s of [-1, 1]) for (let i = 0; i < 3; i++) { P.e(ctx, tx + s * (22 + i * 4) * scU, ty + (6 + i * 6) * scU, 8 * scU, 7 * scU, '#000'); P.e(ctx, tx + s * (22 + i * 4) * scU, ty + (6 + i * 6) * scU, 7 * scU, 6 * scU, ['#b04bff', '#ff5bd1', '#5bd4ff'][i]); } }
  if (o.form === 'bear') { const [tx, ty] = ap('top'); for (const s of [-1, 1]) { P.e(ctx, tx + s * 15 * scU, ty + 2, 8 * scU, 8 * scU, '#1a0a00'); P.e(ctx, tx + s * 15 * scU, ty + 2, 7 * scU, 7 * scU, '#7a4520'); P.e(ctx, tx + s * 15 * scU, ty + 3, 3.5 * scU, 3.5 * scU, '#d49a6a'); } }
  if (o.form === 'wolf') { const [tx, ty] = ap('top'); for (const s of [-1, 1]) { P.poly(ctx, [[tx + s * 6 * scU, ty + 8], [tx + s * 20 * scU, ty - 12 * scU], [tx + s * 24 * scU, ty + 10]], '#111'); P.poly(ctx, [[tx + s * 8 * scU, ty + 7], [tx + s * 19 * scU, ty - 9 * scU], [tx + s * 22 * scU, ty + 9]], '#9a9aa8'); P.poly(ctx, [[tx + s * 12 * scU, ty + 6], [tx + s * 18 * scU, ty - 3 * scU], [tx + s * 19 * scU, ty + 7]], '#d48b9c'); } }
  let src = img;
  spr(src, x, y, { ax, ay, flip, sx, sy, rot: o.rot, flash: o.flash, alpha: o.alpha });
  if (o.flash) return;
  // blink: green eyelid over the protruding eyeball
  if (o.blink) { const [ex, ey] = ap('eye'); P.e(ctx, ex, ey, 9 * scU, 7 * scU * o.blink, '#2a8a1a'); P.r(ctx, ex - 9 * scU, ey + 6 * scU * o.blink - 1, 18 * scU, 1, '#000'); }
  // open maw for screams / bites
  if (o.mouth > 0) { const [mx, my] = ap('mouth'); const m = o.mouth; P.e(ctx, mx, my, 15 * scU * m + 2, 11 * scU * m + 2, '#000'); P.e(ctx, mx, my, 15 * scU * m, 11 * scU * m, '#5a0010'); P.e(ctx, mx, my + 5 * m, 8 * scU * m, 4 * scU * m, '#e01a2a'); for (let i = -2; i <= 2; i++) P.poly(ctx, [[mx + i * 5 * m * scU - 2, my - 10 * m * scU], [mx + i * 5 * m * scU + 2, my - 10 * m * scU], [mx + i * 5 * m * scU, my - 5 * m * scU]], '#fff3c0'); }
  // front overlays
  if (o.form === 'pig') { const [mx, my] = ap('center'); const nx = mx + (flip ? 5 : -5) * scU; P.e(ctx, nx, my + 2, 9 * scU, 7 * scU, '#000'); P.e(ctx, nx, my + 2, 8 * scU, 6 * scU, '#ff8ab0'); P.e(ctx, nx - 3 * scU, my + 2, 1.8 * scU, 2.4 * scU, '#5a1a2a'); P.e(ctx, nx + 3 * scU, my + 2, 1.8 * scU, 2.4 * scU, '#5a1a2a'); const [tx, ty] = ap('top'); for (const s of [-1, 1]) { P.poly(ctx, [[tx + s * 8 * scU, ty + 6], [tx + s * 18 * scU, ty - 6 * scU], [tx + s * 20 * scU, ty + 10]], '#000'); P.poly(ctx, [[tx + s * 9 * scU, ty + 6], [tx + s * 17 * scU, ty - 3 * scU], [tx + s * 18 * scU, ty + 9]], '#ff8ab0'); } }
  if (o.form === 'cow') { const [tx, ty] = ap('top'); for (const s of [-1, 1]) { ctx.strokeStyle = '#000'; ctx.lineWidth = 6 * scU; ctx.beginPath(); ctx.moveTo(tx + s * 10 * scU, ty + 6); ctx.quadraticCurveTo(tx + s * 30 * scU, ty, tx + s * 26 * scU, ty - 16 * scU); ctx.stroke(); ctx.strokeStyle = '#efe2c4'; ctx.lineWidth = 4 * scU; ctx.stroke(); } const [cx2, cy2] = ap('center'); P.e(ctx, cx2 + 10 * scU, cy2 - 14 * scU, 6 * scU, 4 * scU, '#000a'); P.e(ctx, cx2 - 14 * scU, cy2 + 8 * scU, 4 * scU, 3 * scU, '#000a'); const [mx, my] = ap('mouth'); ctx.strokeStyle = '#ffd23a'; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(mx + (flip ? 10 : -10) * scU, my - 8 * scU, 4 * scU, .3, 2.8); ctx.stroke(); }
  if (o.form === 'clown') { const [mx, my] = ap('center'); P.e(ctx, mx + (flip ? 4 : -4) * scU, my - 2, 6 * scU, 6 * scU, '#000'); P.e(ctx, mx + (flip ? 4 : -4) * scU, my - 2, 5 * scU, 5 * scU, '#ff1a2a'); P.r(ctx, mx + (flip ? 2 : -6) * scU, my - 5, 2, 2, '#fff'); }
  if (o.form === 'bear') { const [bx, by] = ap('bottom'); for (const s of [-1, 1]) for (let i = 0; i < 3; i++) P.poly(ctx, [[bx + s * (10 + i * 5) * scU, by - 4], [bx + s * (12 + i * 5) * scU, by + 4], [bx + s * (14 + i * 5) * scU, by - 4]], '#fff8e0'); }
  if (o.form === 'slime') { const [mx, my] = ap('mouth'); for (let i = 0; i < 4; i++) { const dy = ((G.t * 30 + i * 9) % 20); P.e(ctx, mx - 10 * scU + i * 7 * scU, my + 4 + dy, 3 * scU, 4 * scU, '#0a2a00'); P.e(ctx, mx - 10 * scU + i * 7 * scU, my + 4 + dy, 2 * scU, 3 * scU, '#7fff3a'); } }
  if (o.form === 'wolf') { const [mx, my] = ap('mouth'); P.poly(ctx, [[mx - 8 * scU, my - 6], [mx - 5 * scU, my + 6], [mx - 2 * scU, my - 6]], '#fff'); P.poly(ctx, [[mx + 4 * scU, my - 6], [mx + 7 * scU, my + 6], [mx + 10 * scU, my - 6]], '#fff'); }
  return ap;
}
function heroMouth(x, y, face, form) { const mega = form === 'mega', name = mega ? 'hero_big' : 'hero', sc = mega ? 1.08 * HD : HD, c = A(name).center, a = A(name).mouth; const flip = face !== HERO_FACE; return [x + (a[0] - c[0]) * sc * (flip ? -1 : 1), y + (a[1] - c[1]) * sc]; }

// --------------------------------------------------------------------------- pigs
const PIGS = {
  hamwise: { name: 'Hamwise', color: '#ff8ab0', belly: '#ffc0d4', bw: 22, bh: 14, head: 'pig_hamwise', hat: 'straw', pitch: 1.25 },
  porkington: { name: 'Porkington', color: '#f77aa6', belly: '#ffb8cf', bw: 18, bh: 15, head: 'pig_porkington', hat: 'hard', pitch: 1 },
  trufflina: { name: 'Trufflina', color: '#ef6a9a', belly: '#ffaac4', bw: 28, bh: 18, head: 'pig_trufflina', hat: 'band', pitch: .8 }
};
const PIG_BODIES = {};
function buildPigBodies() {
  for (const k in PIGS) {
    const p = PIGS[k], w = p.bw + 8, h = p.bh + 10;
    PIG_BODIES[k] = makeSprite(w, h, 5, (c, f) => {
      const leg = f === 4 ? 2 : [0, 2, 0, -2][f], cx = w / 2, cy = p.bh / 2 + 2;
      const lh = 6;
      // back legs
      P.r(c, cx - p.bw / 2 + 3 - leg, cy + p.bh / 2 - 2, 4, lh + (f === 4 ? -2 : 0), '#c8587e'); P.r(c, cx + p.bw / 2 - 7 + leg, cy + p.bh / 2 - 2, 4, lh, '#c8587e');
      P.e(c, cx, cy, p.bw / 2, p.bh / 2, p.color); P.e(c, cx + 1, cy + 3, p.bw / 2 - 4, p.bh / 2 - 4, p.belly);
      // front legs (hooves)
      P.r(c, cx - p.bw / 2 + 6 + leg, cy + p.bh / 2 - 1, 4, lh, p.color); P.r(c, cx + p.bw / 2 - 10 - leg, cy + p.bh / 2 - 1, 4, lh, p.color);
      P.r(c, cx - p.bw / 2 + 6 + leg, cy + p.bh / 2 + lh - 2, 4, 2, '#4a1a2a'); P.r(c, cx + p.bw / 2 - 10 - leg, cy + p.bh / 2 + lh - 2, 4, 2, '#4a1a2a');
      // tail
      P.e(c, cx - p.bw / 2 - 1, cy - 2, 2.5, 2.5, p.color); P.e(c, cx - p.bw / 2 - 1, cy - 2, 1, 1, 'rgba(0,0,0,0)');
      if (k === 'porkington') { P.r(c, cx - p.bw / 2 + 2, cy + 1, p.bw - 4, 3, '#8a5a2a'); P.r(c, cx - 2, cy + 1, 3, 5, '#999'); P.r(c, cx + 3, cy, 2, 6, '#c8a040'); }
      if (k === 'trufflina') { P.r(c, cx - p.bw / 2 + 3, cy - 4, p.bw - 6, 5, '#2a2a30'); P.r(c, cx + 2, cy - 4, 3, 5, '#5a5a65'); P.e(c, cx + p.bw / 2 - 3, cy - 1, 4, 4, p.color); P.e(c, cx - p.bw / 2 + 4, cy - 1, 4, 4, p.color); }
      if (k === 'hamwise') { P.r(c, cx - 4, cy - 3, 8, 2, '#ffd860'); }
    });
  }
}
function drawPig(id, x, y, o = {}) {
  const p = PIGS[id], body = PIG_BODIES[id], head = IMG[p.head]; if (!body || !head) return;
  const flip = (o.face || 1) < 0, st = o.state || 'idle', t = o.t || G.t;
  let f = 0; if (st === 'walk' || st === 'run') f = Math.floor(t * (st === 'run' ? 16 : 10)) % 4; else if (st === 'jump') f = 4;
  const bob = st === 'idle' ? Math.round(Math.sin(t * 4) * 1) : st === 'walk' || st === 'run' ? (f % 2) : 0;
  const sq = o.sq || 1, sc = o.scale || 1;
  const b = body[f]; spr(b, x, y, { flip, sx: sc / sq, sy: sc * sq, flash: o.flash, alpha: o.alpha });
  const hs = sc * HD; const hx = x + (flip ? -1 : 1) * (p.bw / 2 - 2) * sc, hy = y - (b.height - 4) * sc - bob + (st === 'attack' ? 2 : 0);
  const rot = (st === 'attack' ? .25 : st === 'hurt' ? -.3 : st === 'dance' ? Math.sin(t * 10) * .25 : 0) * (flip ? -1 : 1);
  spr(head, hx, hy + 6 * sc, { flip, rot, sx: hs, sy: hs, flash: o.flash, alpha: o.alpha, ay: head.height - 9 });
  if (o.flash) return;
  // accessories
  const tx = hx + (flip ? 2 : -2), ty = hy - head.height * hs + 10;
  ctx.save(); ctx.translate(tx, ty); ctx.rotate(rot); ctx.scale(sc, sc);
  if (p.hat === 'straw') { P.e(ctx, 0, 0, 14, 4, '#000'); P.e(ctx, 0, 0, 13, 3, '#ffd860'); P.r(ctx, -7, -8, 14, 8, '#000'); P.r(ctx, -6, -7, 12, 7, '#f0c040'); P.r(ctx, -6, -3, 12, 2, '#c03030'); }
  if (p.hat === 'hard') { P.e(ctx, 0, -2, 11, 8, '#000'); P.e(ctx, 0, -2, 10, 7, '#ffcc22'); P.r(ctx, -12, 2, 24, 3, '#000'); P.r(ctx, -11, 2, 22, 2, '#ffcc22'); P.r(ctx, -1, -8, 2, 8, '#e0a010'); }
  if (p.hat === 'band') { P.r(ctx, -12, 2, 24, 5, '#000'); P.r(ctx, -11, 3, 22, 3, '#e01a2a'); P.poly(ctx, [[-11, 4], [-18, 1 + Math.sin(t * 9) * 2], [-17, 8 + Math.sin(t * 9) * 2]], '#e01a2a'); P.r(ctx, (flip ? -9 : -3), 9, 13, 4, '#000'); P.r(ctx, (flip ? -8 : -2), 10, 5, 2, '#3a3a50'); P.r(ctx, (flip ? -2 : 4), 10, 5, 2, '#3a3a50'); }
  ctx.restore();
  if (o.prop === 'kazoo') P.r(ctx, hx + (flip ? -16 : 10), hy - 6, 8, 3, '#ff3a6a');
}
// --------------------------------------------------------------------------- biker + motorcycle
function drawBiker(x, y, o = {}) {
  const flip = (o.face || 1) < 0, t = o.t || G.t, bike = IMG.biker_bike, rider = IMG.biker_rider, full = IMG.biker; if (!bike) return;
  const W2 = full.width, H2 = full.height, an = A('biker');
  const rw = an.rearWheel, piv = [rw[0], H2 - 2]; // pivot at rear tyre contact
  ctx.save(); ctx.translate(Math.round(x), Math.round(y)); if (flip) ctx.scale(-1, 1);
  ctx.rotate(-(o.wheelie || 0) + (o.tilt || 0)); ctx.scale(HD * (o.scale || 1), HD * (o.scale || 1));
  ctx.translate(-piv[0], -piv[1]);
  const spd = o.speed === undefined ? 1 : o.speed, vib = spd > .05 ? (Math.floor(t * 30) % 2) : 0;
  if (o.flash) { ctx.drawImage(flashOf(full), 0, 0); ctx.restore(); return; }
  // turbo flame
  if (o.turbo) { const ex = an.exhaust; for (let i = 0; i < 3; i++) { const L = 14 + Math.random() * 14; P.poly(ctx, [[ex[0], ex[1] - 4], [ex[0] - L - i * 4, ex[1] + (i - 1) * 3], [ex[0], ex[1] + 4]], ['#ff3a1a', '#ffa01a', '#fff36b'][i]); } }
  ctx.drawImage(bike, 0, H2 - bike.height);
  // spinning wheel spokes + tyre tread
  for (const k of ['rearWheel', 'frontWheel']) {
    const [wx, wy] = an[k], rad = 22, ang = t * 18 * spd * (k === 'rearWheel' ? 1 : 1.03);
    ctx.strokeStyle = '#e8ecf4'; ctx.lineWidth = 1;
    for (let i = 0; i < 4; i++) { const a = ang + i * Math.PI / 4; ctx.beginPath(); ctx.moveTo(wx + Math.cos(a) * rad * .3, wy + Math.sin(a) * rad * .3); ctx.lineTo(wx + Math.cos(a) * rad * .8, wy + Math.sin(a) * rad * .8); ctx.stroke(); }
    ctx.fillStyle = '#fff'; for (let i = 0; i < 3; i++) { const a = -ang * 1 + i * 2.09; ctx.fillRect(Math.round(wx + Math.cos(a) * (rad + 1)), Math.round(wy + Math.sin(a) * (rad + 1)), 2, 2); }
  }
  // rider with suspension bob and flowing rainbow hair (column warp, stronger toward the trailing hair)
  const ry = -vib - (o.bounce || 0);
  for (let c = 0; c < rider.width; c += 2) {
    const u = c / rider.width, amp = u < .55 ? (1 - u / .55) * (2 + spd * 3) : 0;
    const dy = Math.sin(t * 16 - u * 9) * amp;
    ctx.drawImage(rider, c, 0, 2, rider.height, c, ry + dy, 2, rider.height);
  }
  ctx.restore();
}
// --------------------------------------------------------------------------- werewolf
function drawWolf(x, y, o = {}) {
  const flip = (o.face || 1) < 0, t = o.t || G.t, body = IMG.wolf_body, arm = IMG.wolf_arm; if (!body) return;
  const an = A('wolf_body'), sh = an.shoulder, br = 1 + Math.sin(t * 3) * .02 * (o.breath === undefined ? 1 : o.breath);
  const sc = o.scale || 1;
  ctx.save(); ctx.translate(Math.round(x), Math.round(y)); if (flip) ctx.scale(-1, 1); ctx.scale(sc * HD, sc * HD);
  ctx.rotate(o.rot || 0);
  const sy = br * (o.sy || 1), sx = (2 - br) * (o.sx || 1);
  ctx.scale(sx, sy); ctx.translate(-body.width / 2, -body.height);
  const b = o.flash ? flashOf(body, o.flash === true ? '#fff' : o.flash) : body, a = o.flash ? flashOf(arm, o.flash === true ? '#fff' : o.flash) : arm;
  // arm swings from the shoulder; default pose is raised (as in the art)
  const ang = o.arm || 0, aa = A('wolf_arm').shoulder;
  ctx.drawImage(b, 0, 0);
  ctx.save(); ctx.translate(sh[0], sh[1]); ctx.rotate(ang); ctx.drawImage(a, -aa[0], -aa[1]); ctx.restore();
  if (o.claw) { ctx.strokeStyle = `rgba(255,255,255,${o.claw})`; ctx.lineWidth = 2; for (let i = 0; i < 3; i++) { ctx.beginPath(); ctx.arc(sh[0] - 10, sh[1] + 10, 40 + i * 5, -1.2, .9); ctx.stroke(); } }
  if (o.eyes) { const e = an.eye; ctx.fillStyle = '#ff2'; ctx.globalCompositeOperation = 'lighter'; ctx.fillRect(e[0] - 2, e[1] - 2, 5, 3); ctx.fillRect(e[0] + 8, e[1] - 1, 4, 3); ctx.globalCompositeOperation = 'source-over'; }
  ctx.restore();
}
// --------------------------------------------------------------------------- superhero cow
function drawCow(x, y, o = {}) {
  const flip = (o.face || 1) < 0, t = o.t || G.t, body = IMG.cow_body, cape = IMG.cow_cape; if (!body) return;
  const an = A('cow_body'), can = A('cow_cape'), sc = o.scale || 1;
  ctx.save(); ctx.translate(Math.round(x), Math.round(y)); if (flip) ctx.scale(-1, 1); ctx.scale(sc * HD * (o.sx || 1), sc * HD * (o.sy || 1)); ctx.rotate(o.rot || 0);
  ctx.translate(-body.width / 2, -body.height);
  // cape: column-warped flutter, free (left) end waves hardest
  const amp = o.cape === undefined ? 3 : o.cape, neck = an.neck, cn = can.neck, cx0 = neck[0] - cn[0], cy0 = neck[1] - cn[1];
  const capeImg = o.flash ? flashOf(cape) : cape;
  for (let c = 0; c < cape.width; c += 2) { const u = c / cape.width; const dy = Math.sin(t * 12 + u * 7) * amp * (1 - u) + (1 - u) * (o.capeLift || 0); ctx.drawImage(capeImg, c, 0, 2, cape.height, cx0 + c - (1 - u) * (o.capeStretch || 0), cy0 + dy, 2, cape.height); }
  ctx.drawImage(o.flash ? flashOf(body, o.flash === true ? '#fff' : o.flash) : body, 0, 0);
  if (o.glow) { ctx.globalCompositeOperation = 'lighter'; ctx.globalAlpha = .4 + Math.sin(t * 10) * .2; ctx.drawImage(flashOf(body, o.glow), 0, 0); ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over'; }
  if (o.hypno) { const h = an.head; ctx.strokeStyle = '#ff2aff'; ctx.lineWidth = 1; for (let i = 0; i < 3; i++) { ctx.beginPath(); ctx.arc(h[0] - 12, h[1] - 14, 3 + i * 3 + (t * 8) % 3, 0, 7); ctx.stroke(); ctx.beginPath(); ctx.arc(h[0] + 10, h[1] - 14, 3 + i * 3 + (t * 8) % 3, 0, 7); ctx.stroke(); } }
  ctx.restore();
}
// --------------------------------------------------------------------------- golden sludge
function drawSludge(x, y, o = {}) {
  const img = o.small ? IMG.gloopkin : IMG.sludge; if (!img) return;
  const t = o.t || G.t, wob = o.wobble === undefined ? 1 : o.wobble, flip = (o.face || -1) > 0;
  const sy = (o.sy || 1) * (o.scale || 1) * HD, sx = (o.sx || 1) * (o.scale || 1) * HD;
  sprWarp(img, x, y, { flip, sy, sx, flash: o.flash, alpha: o.alpha, step: o.small ? 1 : 2 }, (v, r) => ({ dx: Math.sin(t * 3 + v * 7 + (o.phase || 0)) * wob * (1 - v) * (o.small ? 2 : 6), sx: 1 + Math.sin(t * 4 + v * 5) * .04 * wob + (o.bulge || 0) * Math.sin(v * Math.PI) }));
}
function drawGloopkin(x, y, o = {}) { drawSludge(x, y, Object.assign({ small: true }, o)); }
