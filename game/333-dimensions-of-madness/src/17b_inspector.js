// ============================================================================
// DEVELOPER SPRITE INSPECTOR (not reachable from the normal menus)
// Open: press F9 anywhere, or load the game with #inspector in the URL. Esc / F9 to leave.
//   UP / DOWN ........ character (all six groups; the Three Little Pigs are three entries)
//   LEFT / RIGHT ..... animation
//   SPACE ............ play / pause          , / . ..... step one frame back / forward
//   - / + ............ playback speed        B ......... background: light / dark checker / black / white
//   O ................ overlays on/off (frame bounds, opaque bounds, pivot, collision box, attack hitbox)
//   G ................ zoom 1x / 2x          V ......... run validation for every character
// ============================================================================
const Inspector = {
  ids: [], ci: 0, ai: 0, f: 0, acc: 0, playing: true, speed: 1, bg: 0, overlays: true, zoom: 1, report: null, prev: null,
  BGS: [['#eeeeee', '#c4c4c4', 'LIGHT CHECKER'], ['#2a2a2a', '#111111', 'DARK CHECKER'], ['#000000', '#000000', 'BLACK'], ['#ffffff', '#ffffff', 'WHITE']],
  open() {
    if (G.state === 'inspector') return;
    this.prev = G.state; this.ids = CHAR_GROUPS.flatMap(([, ids]) => ids); CharAnim.bakeAll(); this.report = null;
    AudioSys.stop && AudioSys.stop(); G.state = 'inspector'; this.f = 0; this.acc = 0;
  },
  close() { G.state = this.prev && this.prev !== 'inspector' && this.prev !== 'boot' ? this.prev : 'title'; if (G.state === 'title') Title.open(); },
  cur() { const id = this.ids[this.ci], m = CharAnim.atlas[id], names = Object.keys(m.anims); this.ai = clamp(this.ai, 0, names.length - 1); return { id, m, name: names[this.ai], a: m.anims[names[this.ai]], names }; },
  key(code) {
    const c = this.cur();
    switch (code) {
      case 'Escape': case 'F9': this.close(); return;
      case 'ArrowUp': case 'KeyW': this.ci = (this.ci + this.ids.length - 1) % this.ids.length; this.ai = 0; this.f = 0; break;
      case 'ArrowDown': case 'KeyS': this.ci = (this.ci + 1) % this.ids.length; this.ai = 0; this.f = 0; break;
      case 'ArrowLeft': case 'KeyA': this.ai = (this.ai + c.names.length - 1) % c.names.length; this.f = 0; break;
      case 'ArrowRight': case 'KeyD': this.ai = (this.ai + 1) % c.names.length; this.f = 0; break;
      case 'Space': this.playing = !this.playing; break;
      case 'Comma': this.playing = false; this.f = (this.f + c.a.count - 1) % c.a.count; break;
      case 'Period': this.playing = false; this.f = (this.f + 1) % c.a.count; break;
      case 'Minus': case 'NumpadSubtract': this.speed = Math.max(.125, this.speed / 2); break;
      case 'Equal': case 'NumpadAdd': this.speed = Math.min(4, this.speed * 2); break;
      case 'KeyB': this.bg = (this.bg + 1) % this.BGS.length; break;
      case 'KeyO': this.overlays = !this.overlays; break;
      case 'KeyG': this.zoom = this.zoom === 1 ? 2 : 1; break;
      case 'KeyV': this.report = CharAnim.validate(); break;
    }
  },
  update() {
    const { a } = this.cur(); if (!this.playing) return;
    this.acc += a.fps * this.speed / 60;
    while (this.acc >= 1) { this.acc -= 1; this.f++; if (this.f >= a.count) this.f = a.loop ? 0 : a.count - 1; if (!a.loop && this.f === a.count - 1) { this.hold = (this.hold || 0) + 1; if (this.hold > 20) { this.hold = 0; this.f = 0; } } }
  },
  checker(x, y, w, h, s = 8) { const [c1, c2] = this.BGS[this.bg]; ctx.fillStyle = c1; ctx.fillRect(x, y, w, h); if (c1 === c2) return; ctx.fillStyle = c2; for (let yy = 0; yy < h; yy += s) for (let xx = (yy / s) % 2 ? s : 0; xx < w; xx += s * 2) ctx.fillRect(x + xx, y + yy, Math.min(s, w - xx), Math.min(s, h - yy)); },
  draw() {
    ctx.fillStyle = '#140a1e'; ctx.fillRect(0, 0, W, H);
    const { id, m, name, a, names } = this.cur(), fr = CharAnim.frame(id, name, this.f);
    text('SPRITE INSPECTOR (DEV)', 8, 6, { color: '#7fff3a' }); text('F9/ESC EXIT', W - 8, 6, { color: '#666', align: 'right' });
    // character list (grouped)
    let y = 22; for (const [g, ids] of CHAR_GROUPS) { const short = g.length > 24 ? g.slice(0, 23) + '.' : g; if (ids.length === 1) { const sel = ids[0] === id; text((sel ? '► ' : '') + short, 8, y, { color: sel ? '#fff' : '#5bd4ff' }); y += 10; } else { text(short, 8, y, { color: '#5bd4ff' }); y += 10; for (const cid of ids) { const sel = cid === id; text((sel ? '► ' : '  ') + CharAnim.atlas[cid].label, 12, y, { color: sel ? '#fff' : '#888' }); y += 10; } } y += 2; }
    // animation list
    y += 4; text('ANIMATIONS', 8, y, { color: '#ffe14d' }); y += 10;
    names.forEach((n, i) => { const an = m.anims[n], bad = an.bounds.some(b => !b); text((i === this.ai ? '► ' : '  ') + n + ' (' + an.count + ')' + (bad ? ' !' : ''), 12, y + i * 9, { color: i === this.ai ? '#fff' : bad ? '#ff3a3a' : '#999' }); });
    // stage: checkerboard + frame
    const sx = 170, sy = 22, sw = W - sx - 8, sh = 252;
    this.checker(sx, sy, sw, sh);
    const sc = Math.min(this.zoom, (sw - 8) / m.frameW, (sh - 8) / m.frameH), fx = sx + (sw - m.frameW * sc) / 2, fy = sy + (sh - m.frameH * sc) / 2;
    ctx.save(); ctx.beginPath(); ctx.rect(sx, sy, sw, sh); ctx.clip(); ctx.imageSmoothingEnabled = false;
    if (fr) ctx.drawImage(fr.sheet, fr.rect[0], fr.rect[1], fr.rect[2], fr.rect[3], fx, fy, m.frameW * sc, m.frameH * sc);
    if (this.overlays && fr) {
      const px = fx + m.pivot[0] * sc, py = fy + m.pivot[1] * sc, R = (x, y2, w, h, c) => { ctx.strokeStyle = c; ctx.lineWidth = 1; ctx.strokeRect(Math.round(x) + .5, Math.round(y2) + .5, Math.round(w), Math.round(h)); };
      R(fx, fy, m.frameW * sc, m.frameH * sc, '#00e5ff');                                       // frame boundary
      if (fr.bounds) R(fx + fr.bounds.x * sc, fy + fr.bounds.y * sc, fr.bounds.w * sc, fr.bounds.h * sc, '#ffe14d'); // opaque pixels
      const bx = m.box; R(px + bx[0] * sc, py + bx[1] * sc, bx[2] * sc, bx[3] * sc, '#3aff6a'); // collision box (frame px)
      if (a.hit && a.hit.frames.includes(fr.index)) { const hb = a.hit.box; ctx.fillStyle = 'rgba(255,40,60,.25)'; ctx.fillRect(px + hb[0] * sc, py + hb[1] * sc, hb[2] * sc, hb[3] * sc); R(px + hb[0] * sc, py + hb[1] * sc, hb[2] * sc, hb[3] * sc, '#ff2840'); }
      ctx.strokeStyle = '#ff3aff'; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(px - 8, py + .5); ctx.lineTo(px + 8, py + .5); ctx.moveTo(px + .5, py - 8); ctx.lineTo(px + .5, py + 8); ctx.stroke(); // pivot
    }
    ctx.restore();
    // filmstrip
    const n = a.count, tw = Math.min(46, (sw - 4) / n), th = tw * m.frameH / m.frameW, ty = sy + sh + 4;
    for (let i = 0; i < n; i++) { const x = sx + 2 + i * tw; this.checker(x, ty, tw - 2, th, 4); const r = a.rects[i]; ctx.drawImage(m.sheet, r[0], r[1], r[2], r[3], x, ty, tw - 2, th); if (i === (fr ? fr.index : -1)) { ctx.strokeStyle = '#fff'; ctx.strokeRect(x - .5, ty - .5, tw - 1, th + 1); } if (!a.bounds[i]) { ctx.fillStyle = 'rgba(255,0,0,.5)'; ctx.fillRect(x, ty, tw - 2, th); } }
    // info + diagnostics
    const b = fr && fr.bounds, iy = H - 34, blank = a.bounds.filter(v => !v).length, clipped = a.bounds.filter(v => v && (v.x <= 0 || v.y <= 0 || v.x + v.w >= m.frameW || v.y + v.h >= m.frameH)).length;
    text(m.label + ' / ' + name + '   FRAME ' + ((fr ? fr.index : 0) + 1) + '/' + n + '   ' + a.fps + ' FPS x' + this.speed + '   ' + (a.loop ? 'LOOP' : 'ONCE') + '   ' + (this.playing ? 'PLAYING' : 'PAUSED'), 8, iy, { color: '#fff' });
    text('FRAME ' + m.frameW + 'x' + m.frameH + '  PIVOT ' + m.pivot.join(',') + '  OPAQUE ' + (b ? b.w + 'x' + b.h + ' @' + b.x + ',' + b.y + ' (' + b.px + 'px)' : 'NONE') + '  BG ' + this.BGS[this.bg][2] + (a.hit ? '  HITBOX FRAMES ' + a.hit.frames.join(',') : ''), 8, iy + 10, { color: '#aaa' });
    text('DIAGNOSTICS: ' + (blank ? blank + ' BLANK  ' : '') + (clipped ? clipped + ' CLIPPED  ' : '') + (m.problems.length ? m.problems.length + ' ERRORS' : '') + (!blank && !clipped && !m.problems.length ? 'OK - every frame valid' : '') + '   [SPACE , . - + B O G V]', 8, iy + 20, { color: blank || clipped || m.problems.length ? '#ff3a3a' : '#7fff3a' });
    if (this.report) { const bad = this.report.filter(r => r.blank || r.clipped || r.outOfBounds || r.missing.length || r.problems.length); panel(W / 2 - 150, 120, 300, 40, { rim: bad.length ? '#ff3a3a' : '#7fff3a' }); text(bad.length ? bad.length + ' CHARACTER(S) WITH PROBLEMS: ' + bad.map(r => r.id).join(', ') : 'VALIDATION OK: ' + this.report.reduce((s, r) => s + r.frames, 0) + ' FRAMES, ' + this.report.length + ' CHARACTERS', W / 2, 136, { color: '#fff', align: 'center' }); }
  }
};
window.addEventListener('keydown', e => {
  if (e.code === 'F9') { e.preventDefault(); if (G.state === 'inspector') Inspector.close(); else if (G.state !== 'boot') Inspector.open(); return; }
  if (G.state === 'inspector') { e.preventDefault(); Inspector.key(e.code); }
});
