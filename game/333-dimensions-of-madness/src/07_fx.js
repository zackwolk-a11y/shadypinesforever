// ============================================================================
// Particles, screen shake, camera, lighting
// ============================================================================
const FX = {
  list: [], rings: [], texts: [],
  add(p) { if (this.list.length > 900) this.list.shift(); p.life = p.life || 30; p.max = p.life; this.list.push(p); return p; },
  burst(x, y, n, col, o = {}) { for (let i = 0; i < n; i++) { const a = R(6.283), s = R(o.min || .5, o.speed || 3); this.add({ x, y, vx: Math.cos(a) * s, vy: Math.sin(a) * s - (o.up || 1), col: Array.isArray(col) ? pick(col) : col, size: o.size || RI(1, 3), grav: o.grav === undefined ? .15 : o.grav, life: RI(18, o.life || 40) }); } },
  slime(x, y, n = 10, col = ['#7fff3a', '#3aa01a', '#c8ff8a']) { this.burst(x, y, n, col, { speed: 3.5, size: 3, life: 35 }); },
  dust(x, y, n = 6) { for (let i = 0; i < n; i++) this.add({ x: x + R(-8, 8), y, vx: R(-1, 1), vy: R(-.8, -.1), col: '#c8b8a8', size: RI(2, 4), grav: -.01, life: RI(14, 26), fade: true }); },
  stars(x, y) { for (let i = 0; i < 5; i++) this.add({ x, y, vx: Math.cos(i * 1.256) * 2, vy: Math.sin(i * 1.256) * 2 - 1, type: 'star', life: 30, grav: .05 }); },
  ring(x, y, r1, col = '#7fff3a', life = 24, w = 3) { this.rings.push({ x, y, r: 2, r1, col, life, max: life, w }); },
  pop(x, y, s, col = '#ffe14d') { this.texts.push({ x, y, s, col, life: 50 }); },
  smoke(x, y, vx = -1) { this.add({ x, y, vx: vx + R(-.3, .3), vy: R(-.6, -.1), type: 'smoke', life: RI(24, 40), grav: -.01, s: R(.5, 1) }); },
  debris(x, y, kind, n = 8) { for (let i = 0; i < n; i++) this.add({ x: x + R(-8, 8), y: y + R(-8, 8), vx: R(-3, 3), vy: R(-5, -1), type: kind, rot: R(6), vr: R(-.3, .3), life: RI(40, 70), grav: .2 }); },
  notes(x, y, n = 3) { for (let i = 0; i < n; i++) this.add({ x: x + R(-10, 10), y, vx: R(-.6, .6), vy: R(-1.4, -.6), type: 'note', life: 50, grav: 0, col: pick(['#7fff3a', '#ffe14d', '#ff5bd1', '#5bd4ff']) }); },
  confetti(x, y, n = 40) { for (let i = 0; i < n; i++) this.add({ x: x + R(-W / 2, W / 2), y: y + R(-40, 0), vx: R(-1, 1), vy: R(-1, 1), col: hsl(R(360), 90, 60), size: 2, grav: .03, life: RI(80, 160), flut: true }); },
  update() {
    for (const p of this.list) { p.x += p.vx; p.y += p.vy; p.vy += p.grav; p.life--; if (p.vr) p.rot += p.vr; if (p.flut) p.vx = Math.sin(p.life * .1) * .8; }
    this.list = this.list.filter(p => p.life > 0);
    for (const r of this.rings) { r.life--; r.r = lerp(r.r, r.r1, .18); } this.rings = this.rings.filter(r => r.life > 0);
    for (const t of this.texts) { t.life--; t.y -= .5; } this.texts = this.texts.filter(t => t.life > 0);
  },
  draw(cx, cy) {
    for (const p of this.list) {
      const x = Math.round(p.x - cx), y = Math.round(p.y - cy); if (x < -20 || x > VW + 20 || y < -20 || y > VH + 20) continue;
      const a = p.fade || p.type === 'smoke' ? p.life / p.max : 1;
      switch (p.type) {
        case 'star': ctx.drawImage(ICON.star, x - 7, y - 6); break;
        case 'smoke': spr(IMG.smoke, x, y, { ax: 12, ay: 12, sx: p.s * (1.6 - a * .6), sy: p.s * (1.6 - a * .6), alpha: a * .85 }); break;
        case 'note': text('♪', x, y, { color: p.col }); break;
        case 'straw': ctx.save(); ctx.translate(x, y); ctx.rotate(p.rot); P.r(ctx, -4, -1, 8, 2, '#ffd860'); ctx.restore(); break;
        case 'stick': ctx.save(); ctx.translate(x, y); ctx.rotate(p.rot); P.r(ctx, -6, -1, 12, 2, '#8a5a2a'); ctx.restore(); break;
        case 'brick': ctx.save(); ctx.translate(x, y); ctx.rotate(p.rot); P.r(ctx, -4, -2, 8, 4, '#c24a2a'); P.r(ctx, -4, -2, 8, 1, '#e87a5a'); ctx.restore(); break;
        case 'hat': ctx.save(); ctx.translate(x, y); ctx.rotate(p.rot); P.r(ctx, -6, -1, 12, 3, '#0a060e'); P.r(ctx, -4, -7, 8, 7, '#0a060e'); P.r(ctx, -5, -1, 10, 2, p.col); P.r(ctx, -3, -6, 6, 5, p.col); ctx.restore(); break;
        case 'twinkle': { const s2 = Math.sin(p.life / p.max * Math.PI) * 6; PP.star(ctx, x, y, s2 + 1, '#ffe14d'); break; }
        case 'junk': ctx.save(); ctx.translate(x, y); ctx.rotate(p.rot); P.r(ctx, -3, -3, 6, 6, p.col || '#8a8a8a'); ctx.restore(); break;
        default: ctx.globalAlpha = a; ctx.fillStyle = p.col; ctx.fillRect(x, y, p.size, p.size); ctx.globalAlpha = 1;
      }
    }
    for (const r of this.rings) { ctx.globalAlpha = r.life / r.max; ctx.strokeStyle = r.col; ctx.lineWidth = r.w; ctx.beginPath(); ctx.arc(Math.round(r.x - cx), Math.round(r.y - cy), r.r, 0, 7); ctx.stroke(); ctx.globalAlpha = 1; }
    for (const t of this.texts) text(t.s, t.x - cx, t.y - cy, { color: t.col, align: 'center', outline: true });
  },
  clear() { this.list = []; this.rings = []; this.texts = []; }
};
const Cam = {
  x: 0, y: 0, shakeT: 0, shakeA: 0, zoom: 1, tx: 0, ty: 0,
  shake(a = 3, t = 12) { if (Save.data && Save.data.opt && Save.data.opt.shake === false) return; this.shakeA = Math.max(this.shakeA, a); this.shakeT = Math.max(this.shakeT, t); },
  follow(L, px, py, facing, instant) {
    // hero sits centre-left with a smoothed look-ahead; vertical deadzone avoids bobbing
    this.look = lerp(this.look || 0, facing * VW * .12, instant ? 1 : .025);
    let tx = px - VW / 2 + this.look, ty = this.ty0 === undefined ? py - VH * .56 : this.ty0;
    const want = py - VH * .56; if (instant || Math.abs(want - ty) > 18) ty = lerp(ty, want, instant ? 1 : .08); this.ty0 = ty;
    if (L.camLock) { tx = clamp(tx, L.camLock.x0, L.camLock.x1 - VW); if (L.camLock.gy) ty = L.camLock.gy - VH * .86; } // gy: arena floor low on screen (room for big flying bosses)
    tx = clamp(tx, 0, L.w * TS - VW); ty = clamp(ty, 0, L.h * TS - VH);
    if (L.autoScroll) tx = Math.max(this.x, L.scrollX);
    if (instant) { this.x = tx; this.y = ty; } else { this.x = lerp(this.x, tx, L.autoScroll ? 1 : .1); this.y = lerp(this.y, ty, .1); }
    if (this.shakeT > 0) { this.shakeT--; } else this.shakeA *= .8;
  },
  ox() { return this.shakeT > 0 ? R(-this.shakeA, this.shakeA) : 0; }, oy() { return this.shakeT > 0 ? R(-this.shakeA, this.shakeA) : 0; }
};
// lighting overlays per theme
function drawLighting(L, cx) {
  const th = L.theme, t = G.t;
  switch (th.light) {
    case 'spot': ctx.save(); ctx.globalCompositeOperation = 'lighter';
      for (let i = 0; i < 3; i++) { const x = ((i * 260 - cx * .4) % 900 + 900) % 900 - 130, a = Math.sin(t * .7 + i * 2) * .5; const g = ctx.createLinearGradient(x, 0, x + Math.sin(a) * 300, H); const col = ['255,80,200', '80,255,120', '255,220,80'][i]; g.addColorStop(0, `rgba(${col},.22)`); g.addColorStop(1, `rgba(${col},0)`); ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(x - 6, 0); ctx.lineTo(x + 6, 0); ctx.lineTo(x + Math.sin(a) * 300 + 70, H); ctx.lineTo(x + Math.sin(a) * 300 - 70, H); ctx.fill(); }
      ctx.restore(); break;
    case 'disco': ctx.save(); ctx.globalCompositeOperation = 'lighter'; for (let i = 0; i < 5; i++) { const x = W / 2 + Math.sin(t * (.6 + i * .17) + i) * 300, y = 80 + Math.cos(t * .5 + i) * 60; const g = ctx.createRadialGradient(x, y, 0, x, y, 120); g.addColorStop(0, hsl((t * 60 + i * 70) % 360, 90, 55, .18)); g.addColorStop(1, 'rgba(0,0,0,0)'); ctx.fillStyle = g; ctx.fillRect(x - 120, y - 120, 240, 240); } ctx.restore(); break;
    case 'lightning': if ((Math.floor(t * 10) % 53) === 0 || (Math.floor(t * 10) % 53) === 2) { ctx.fillStyle = 'rgba(200,220,255,.25)'; ctx.fillRect(0, 0, W, H); } break;
    case 'psy': ctx.save(); ctx.globalCompositeOperation = 'overlay'; ctx.fillStyle = hsl((t * 30) % 360, 80, 50, .07); ctx.fillRect(0, 0, W, H); ctx.restore(); break;
    case 'flicker': break;
    case 'alarm': ctx.fillStyle = `rgba(255,30,0,${(Math.sin(t * 4) * .5 + .5) * .1})`; ctx.fillRect(0, 0, W, H); break;
    case 'search': { const x = W / 2 + Math.sin(t * .8) * 260; const g = ctx.createRadialGradient(x, H - 80, 0, x, H - 80, 90); g.addColorStop(0, 'rgba(255,255,200,.18)'); g.addColorStop(1, 'rgba(0,0,0,0)'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H); break; }
    case 'moon': break;
  }
  // vignette
  const v = ctx.createRadialGradient(W / 2, H / 2, H * .35, W / 2, H / 2, H * .85); v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(20,0,40,.22)'); ctx.fillStyle = v; ctx.fillRect(0, 0, W, H);
}
