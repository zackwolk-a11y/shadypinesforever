// ============================================================================
// UI: HUD, toasts, banners, title, world map, menus, encyclopedia, jukebox
// ============================================================================
const HUD = {
  toasts: [], banners: [], questLabel: null, bossIntro: 0, hpShow: 0,
  reset() { this.toasts = []; this.banners = []; this.questLabel = null; },
  toast(s, col = '#fff', icon) { this.toasts.push({ s, col, icon, t: 200 }); if (this.toasts.length > 4) this.toasts.shift(); },
  banner(s, col = '#fff', sub) { this.banners = [{ s, col, sub, t: 150 }]; },
  update() { for (const t of this.toasts) t.t--; this.toasts = this.toasts.filter(t => t.t > 0); for (const b of this.banners) b.t--; this.banners = this.banners.filter(b => b.t > 0); if (this.bossIntro > 0) this.bossIntro--; },
  draw() {
    const p = Game.player; if (!p) return;
    // hearts (big, chunky)
    for (let i = 0; i < p.maxHp; i++) { const full = i < p.hp, bump = full && i === p.hp - 1 ? Math.sin(G.t * 6) * .12 : 0; spr(full ? ICON.heart : ICON.heartE, 18 + i * 20, 26, { sx: 2.4 + bump, sy: 2.4 + bump }); }
    // collectible counter
    panel(W - 84, 8, 74, 22, { rim: '#ffe14d', bg: 'rgba(26,11,34,.75)' }); spr(ICON.note, W - 72, 28, { sx: 1.8, sy: 1.8 }); text(String(Game.levelStats.notes), W - 54, 13, { color: '#ffe14d', scale: 2, outline: true });
    // current power-up
    if (p.powerT > 0 && POWERS[p.form] || p.form === 'mega') { const c = POWERS[p.form] ? POWERS[p.form].col : '#7fff3a'; panel(10, 44, 96, 26, { rim: c, bg: 'rgba(26,11,34,.75)' }); drawHero(26, 57, { face: 1, form: p.form, sx: .3, sy: .3 }); text(FORMS[p.form].name.replace(' POWER', '!'), 42, 49, { color: c, outline: true }); P.r(ctx, 42, 60, 58, 5, '#000'); P.r(ctx, 42, 60, 58 * Math.min(1, p.powerT / (p.powerMax || POWER_TIME)), 5, c); }
    // boss bar
    const b = Game.boss; if (b && !b.defeated) {
      const bw = 300, bx = W / 2 - bw / 2, by = H - 30; panel(bx, by, bw, 10, { rim: '#ff3a3a', bg: '#200' });
      const k = b.hp / b.maxHp; ctx.fillStyle = b.vulnerable === false ? '#888' : '#ff2a4a'; ctx.fillRect(bx, by, bw * k, 10); ctx.fillStyle = '#ff8a9a'; ctx.fillRect(bx, by, bw * k, 2);
      for (const ph of b.phases.slice(1)) P.r(ctx, bx + bw * ph, by, 1, 10, '#000');
      text(b.short || b.name, W / 2, by - 11, { color: '#fff', align: 'center', outline: true });
      if (this.bossIntro > 0) { const a = Math.min(1, this.bossIntro / 30); ctx.globalAlpha = a; text('BOSS', W / 2, 88, { color: '#ffe14d', align: 'center', outline: true }); text(b.name, W / 2, 100, { color: '#ff2a4a', align: 'center', scale: b.name.length > 30 ? 2 : 3, outline: true }); /* above the FIGHT! banner (y=132) */ ctx.globalAlpha = 1; }
    }
    // toasts and banners
    this.toasts.forEach((t, i) => { const a = Math.min(1, t.t / 30); ctx.globalAlpha = a; const w = textWidth(t.s) + (t.icon ? 22 : 10); panel(W / 2 - w / 2, 46 + i * 16, w, 12, { rim: t.col }); if (t.icon) ctx.drawImage(t.icon, W / 2 - w / 2 + 2, 44 + i * 16); text(t.s, W / 2 + (t.icon ? 8 : 0), 49 + i * 16, { color: t.col, align: 'center' }); ctx.globalAlpha = 1; });
    for (const bn of this.banners) { const k = bn.t / 150, a = Math.min(1, bn.t / 25, (150 - bn.t) / 10 + .2), s = bn.s.length > 26 ? 2 : 3; ctx.globalAlpha = a; text(bn.s, W / 2, 132 + (1 - ease.out(Math.min(1, (150 - bn.t) / 20))) * -30, { color: bn.col, align: 'center', scale: s, outline: true, wave: 1 }); if (bn.sub) text(bn.sub, W / 2, 162, { color: '#fff', align: 'center', outline: true }); ctx.globalAlpha = 1; }
  }
};
// ---------------------------------------------------------------- generic menu list
function drawList(items, sel, x, y, o = {}) {
  items.forEach((it, i) => {
    const s = i === sel, yy = y + i * (o.gap || 16); if (s) { P.r(ctx, x - 8, yy - 3, o.w || 220, 13, 'rgba(127,255,58,.18)'); text('►', x - 6, yy, { color: '#7fff3a' }); }
    const label = typeof it === 'string' ? it : it.label; text(label, x + 4, yy, { color: s ? '#fff' : it.dim ? '#555' : '#aaa', outline: s ? '#000' : false });
    if (it.value !== undefined) text(String(it.value), x + (o.w || 220) - 14, yy, { color: s ? '#7fff3a' : '#888', align: 'right' });
  });
}
function navList(n, cur) { if (Input.pressed.up) { AudioSys.play_sfx('menu'); return (cur + n - 1) % n; } if (Input.pressed.down) { AudioSys.play_sfx('menu'); return (cur + 1) % n; } return cur; }
// ---------------------------------------------------------------- Menus (stack)
const Menus = {
  stack: [],
  open(id, o = {}) { this.stack.push(Object.assign({ id, sel: 0, t: 0, scroll: 0 }, o)); AudioSys.play_sfx('select'); if (id === 'pause') AudioSys.setIntensity(0); },
  close() { const m = this.stack.pop(); AudioSys.play_sfx('back'); if (m && m.id === 'pause' && G.state === 'level') AudioSys.setIntensity(Game.boss ? 3 : 1); },
  get top() { return this.stack[this.stack.length - 1]; },
  update() {
    const m = this.top; if (!m) return false; m.t++;
    const H_ = this.handlers[m.id]; if (H_) H_.update(m);
    return true;
  },
  draw() { for (const m of this.stack) { const H_ = this.handlers[m.id]; if (H_) H_.draw(m); } },
  handlers: {}
};
const MH = Menus.handlers;
MH.pause = {
  items: () => ['RESUME', 'RESTART FROM CHECKPOINT', 'RESTART LEVEL', 'POWER-UPS & PALS', 'MONSTER ENCYCLOPEDIA', 'OPTIONS', 'CONTROLS', 'QUIT TO WORLD MAP'],
  update(m) { const it = this.items(); m.sel = navList(it.length, m.sel); if (Input.pressed.back || Input.pressed.pause) { Menus.close(); return; }
    if (Input.pressed.confirm) { const c = it[m.sel]; if (c === 'RESUME') Menus.close(); else if (c === 'RESTART FROM CHECKPOINT') { Menus.close(); Game.player.die(); } else if (c === 'RESTART LEVEL') { Menus.stack = []; Game.restartLevel(); } else if (c === 'POWER-UPS & PALS') Menus.open('forms'); else if (c === 'MONSTER ENCYCLOPEDIA') Menus.open('ency'); else if (c === 'OPTIONS') Menus.open('options'); else if (c === 'CONTROLS') Menus.open('controls'); else { Menus.stack = []; Save.write(); WorldMap.open(); } } },
  draw(m) { ctx.fillStyle = 'rgba(8,0,16,.78)'; ctx.fillRect(0, 0, W, H); text('PAUSED', W / 2, 50, { color: '#7fff3a', align: 'center', scale: 3, outline: true, wave: 1 }); text(Game.def.label === '333' ? 'LEVEL 333 — ' + (Game.sub.name || '') : 'LEVEL ' + Game.def.label + ' — ' + Game.def.name, W / 2, 84, { color: '#fff', align: 'center' }); panel(W / 2 - 120, 106, 240, 140); drawList(this.items(), m.sel, W / 2 - 100, 116, { w: 220 }); }
};
MH.options = {
  items() { const o = Save.data.opt; return [{ label: 'MUSIC VOLUME', value: Math.round(o.music * 10) + '/10' }, { label: 'EFFECTS VOLUME', value: Math.round(o.sfx * 10) + '/10' }, { label: 'DIFFICULTY', value: o.diff.toUpperCase() }, { label: 'SCREEN SHAKE', value: o.shake ? 'ON' : 'OFF' }, { label: 'TOUCH CONTROLS', value: (o.touch || 'auto').toUpperCase() }, { label: 'FULLSCREEN' }, { label: 'ERASE SAVE DATA' }, { label: 'BACK' }]; },
  update(m) {
    const it = this.items(), o = Save.data.opt; m.sel = navList(it.length, m.sel); const d = Input.pressed.left ? -1 : Input.pressed.right ? 1 : 0, c = it[m.sel].label;
    if (Input.pressed.back) { Save.write(); Menus.close(); return; }
    if (d || Input.pressed.confirm) {
      const dd = d || 1;
      if (c === 'MUSIC VOLUME') { o.music = clamp(Math.round(o.music * 10 + dd) / 10, 0, 1); AudioSys.musicVol = o.music; AudioSys.applyVolumes(); }
      else if (c === 'EFFECTS VOLUME') { o.sfx = clamp(Math.round(o.sfx * 10 + dd) / 10, 0, 1); AudioSys.sfxVol = o.sfx; AudioSys.applyVolumes(); AudioSys.play_sfx('note'); }
      else if (c === 'DIFFICULTY') { const L_ = ['easy', 'normal', 'hard']; o.diff = L_[(L_.indexOf(o.diff) + dd + 3) % 3]; }
      else if (c === 'SCREEN SHAKE') o.shake = !o.shake;
      else if (c === 'TOUCH CONTROLS') { const L_ = ['auto', 'on', 'off']; o.touch = L_[(L_.indexOf(o.touch || 'auto') + dd + 3) % 3]; applyTouchPref(); }
      else if (c === 'FULLSCREEN' && Input.pressed.confirm) { toggleFullscreen(); }
      else if (c === 'ERASE SAVE DATA' && Input.pressed.confirm) Menus.open('confirmErase');
      else if (c === 'BACK' && Input.pressed.confirm) { Save.write(); Menus.close(); }
      AudioSys.play_sfx('menu'); Save.write();
    }
  },
  draw(m) { ctx.fillStyle = 'rgba(8,0,16,.9)'; ctx.fillRect(0, 0, W, H); text('OPTIONS', W / 2, 40, { color: '#7fff3a', align: 'center', scale: 3, outline: true }); panel(W / 2 - 150, 90, 300, 150); drawList(this.items(), m.sel, W / 2 - 130, 102, { w: 280 }); text('◄ ► change values', W / 2, 260, { color: '#888', align: 'center' }); text('Difficulty changes hearts (8 / 5 / 3) and boss health.', W / 2, 274, { color: '#666', align: 'center' }); }
};
MH.confirmErase = { update(m) { if (Input.pressed.left || Input.pressed.right) m.sel = 1 - m.sel; if (Input.pressed.back) Menus.close(); if (Input.pressed.confirm) { if (m.sel === 1) { Save.reset(); Menus.stack = []; Title.open(); } else Menus.close(); } },
  draw(m) { ctx.fillStyle = 'rgba(0,0,0,.8)'; ctx.fillRect(0, 0, W, H); panel(W / 2 - 130, 140, 260, 70, { rim: '#ff3a3a' }); text('ERASE ALL PROGRESS?', W / 2, 152, { color: '#ff3a3a', align: 'center' }); text((m.sel === 0 ? '► ' : '  ') + 'NO', W / 2 - 50, 180, { color: m.sel === 0 ? '#fff' : '#888', align: 'center' }); text((m.sel === 1 ? '► ' : '  ') + 'YES, ERASE', W / 2 + 50, 180, { color: m.sel === 1 ? '#fff' : '#888', align: 'center' }); } };
MH.controls = { update(m) { if (Input.pressed.back || Input.pressed.confirm) Menus.close(); },
  draw() { ctx.fillStyle = 'rgba(8,0,16,.94)'; ctx.fillRect(0, 0, W, H); text('CONTROLS', W / 2, 30, { color: '#7fff3a', align: 'center', scale: 3, outline: true });
    const rows = [['MOVE', 'ARROWS / WASD', 'STICK / D-PAD', 'LEFT STICK'], ['JUMP', 'SPACE / Z', 'A', 'JUMP'], ['ATTACK', 'X / J / C / SHIFT', 'X  B  Y  RB', 'ATTACK'], ['PAUSE', 'ESC / P', 'START', 'II'], ['FULLSCREEN', 'F', '-', '-']];
    text('KEYBOARD', 250, 90, { color: '#ffe14d' }); text('GAMEPAD', 400, 90, { color: '#ffe14d' }); text('TOUCH', 530, 90, { color: '#ffe14d' });
    rows.forEach((r, i) => { text(r[0], 60, 108 + i * 24, { color: '#fff', scale: 2 }); text(r[1], 250, 112 + i * 24, { color: '#aaa' }); text(r[2], 400, 112 + i * 24, { color: '#aaa' }); text(r[3], 530, 112 + i * 24, { color: '#aaa' }); });
    ['ATTACK is smart: it whips, smashes walls, spins in the air, rolls when you run,', 'builds houses and flips switches - whatever makes sense.', 'Near a hook, ANY attack (even a power-up one) swings from it automatically.', 'Grab glowing bubbles for temporary PIG, WOLF, COW or SLIME power!'].forEach((l, i) => text(l, W / 2, 238 + i * 14, { color: '#5bd4ff', align: 'center' })); } };
MH.forms = { update(m) { if (Input.pressed.back || Input.pressed.confirm) Menus.close(); },
  draw(m) { ctx.fillStyle = 'rgba(8,0,16,.94)'; ctx.fillRect(0, 0, W, H); text('POWER-UPS & PALS', W / 2, 20, { color: '#7fff3a', align: 'center', scale: 2, outline: true });
    ['pig', 'wolf', 'cow', 'slime'].forEach((f, i) => { const y = 60 + i * 52, P_ = POWERS[f]; drawHero(60, y + 18, { face: 1, form: f, sx: .6, sy: .6 }); text(P_.label, 100, y + 4, { color: P_.col, scale: 2 }); text(FORMS[f].desc, 100, y + 24, { color: '#ddd' }); });
    text('PALS (they help automatically)', 430, 50, { color: '#5bd4ff' }); [['THE THREE LITTLE PIGS', 'Honk, throw sticks, punch.'], ['COWGOD', 'Delivers COW POWER from the sky.'], ['ELECTRIC HARLEY', 'Jumps his chopper over you. Show-off.']].forEach((r, i) => { text(r[0], 430, 70 + i * 36, { color: '#fff' }); text(r[1], 430, 82 + i * 36, { color: '#999' }); }); } };
MH.ency = {
  keys: () => Object.keys(ENCY),
  update(m) { const ks = this.keys(), cols = 6; if (m.detail) { if (Input.pressed.back || Input.pressed.confirm) { m.detail = false; AudioSys.play_sfx('back'); } return; }
    if (Input.pressed.left) m.sel = Math.max(0, m.sel - 1); if (Input.pressed.right) m.sel = Math.min(ks.length - 1, m.sel + 1); if (Input.pressed.up) m.sel = Math.max(0, m.sel - cols); if (Input.pressed.down) m.sel = Math.min(ks.length - 1, m.sel + cols);
    if (Input.pressed.left || Input.pressed.right || Input.pressed.up || Input.pressed.down) AudioSys.play_sfx('menu');
    if (Input.pressed.back) { Menus.close(); return; } if (Input.pressed.confirm && Save.data.seen[ks[m.sel]]) { m.detail = true; AudioSys.play_sfx('select'); }
    const row = Math.floor(m.sel / cols); if (row < m.scroll) m.scroll = row; if (row > m.scroll + 3) m.scroll = row - 3; },
  draw(m) {
    ctx.fillStyle = '#0d0618'; ctx.fillRect(0, 0, W, H); const ks = this.keys(), seen = ks.filter(k => Save.data.seen[k]).length;
    text('MONSTER ENCYCLOPEDIA', W / 2, 12, { color: '#5bd4ff', align: 'center', scale: 2, outline: true }); text(seen + ' / ' + ks.length + ' DISCOVERED', W / 2, 34, { color: '#aaa', align: 'center' });
    const cols = 6, cw = 96, ch = 74, x0 = (W - cols * cw) / 2;
    ks.forEach((k, i) => { const r = Math.floor(i / cols) - m.scroll, c = i % cols; if (r < 0 || r > 3) return; const x = x0 + c * cw, y = 50 + r * ch, s = i === m.sel, e = ENCY[k], got = Save.data.seen[k];
      panel(x + 4, y, cw - 8, ch - 8, { rim: s ? '#5bd4ff' : e.cat === 'CAST' ? '#7a5aa0' : e.cat === 'BOSS' ? '#a03a3a' : '#3a3a4a', bg: s ? '#1f1a3a' : '#150f24' });
      ctx.save(); ctx.beginPath(); ctx.rect(x + 4, y, cw - 8, ch - 20); ctx.clip(); if (got) e.draw(x + cw / 2, y + ch - 24); else { ctx.globalAlpha = .9; text('?', x + cw / 2, y + 18, { color: '#333', align: 'center', scale: 3, shadow: false }); ctx.globalAlpha = 1; } ctx.restore();
      text(got ? (e.name.length > 15 ? e.name.slice(0, 14) + '.' : e.name) : '???', x + cw / 2, y + ch - 19, { color: got ? '#fff' : '#555', align: 'center' }); });
    if (m.detail) { const e = ENCY[ks[m.sel]]; ctx.fillStyle = 'rgba(0,0,0,.85)'; ctx.fillRect(0, 0, W, H); panel(40, 40, W - 80, H - 80, { rim: '#5bd4ff' });
      ctx.save(); ctx.beginPath(); ctx.rect(46, 50, 200, 230); ctx.clip(); ctx.translate(146, 230); ctx.scale(1.6, 1.6); e.draw(0, 0); ctx.restore();
      text(e.name, 260, 60, { color: '#5bd4ff', scale: 2 }); text(e.cat, 260, 82, { color: e.cat === 'BOSS' ? '#ff3a3a' : e.cat === 'CAST' ? '#ff5bd1' : '#aaa' }); wrapText(e.desc, 52).forEach((l, i) => text(l, 260, 104 + i * 12, { color: '#ddd' })); }
  }
};
MH.ach = { update(m) { const n = Object.keys(ACHIEVEMENTS).length; m.sel = navList(n, m.sel); if (Input.pressed.back || Input.pressed.confirm) Menus.close(); if (m.sel < m.scroll) m.scroll = m.sel; if (m.sel > m.scroll + 12) m.scroll = m.sel - 12; },
  draw(m) { ctx.fillStyle = '#0d0618'; ctx.fillRect(0, 0, W, H); const ks = Object.keys(ACHIEVEMENTS), got = ks.filter(k => Save.data.ach[k]).length; text('ACHIEVEMENTS ' + got + '/' + ks.length, W / 2, 12, { color: '#ffcc33', align: 'center', scale: 2, outline: true });
    ks.slice(m.scroll, m.scroll + 13).forEach((k, i) => { const idx = i + m.scroll, y = 44 + i * 23, g = Save.data.ach[k]; if (idx === m.sel) P.r(ctx, 30, y - 4, W - 60, 22, 'rgba(255,204,51,.12)'); ctx.globalAlpha = g ? 1 : .3; ctx.drawImage(ICON.ach, 40, y - 2); ctx.globalAlpha = 1; text(ACHIEVEMENTS[k][0], 64, y, { color: g ? '#ffcc33' : '#666' }); text(ACHIEVEMENTS[k][1], 64, y + 10, { color: g ? '#ccc' : '#444' }); }); } };
MH.jukebox = {
  list: () => SONG_SPECS.map(s => s[0]).filter(id => Save.data.jukebox[id] || G.unlockAll),
  update(m) { const l = this.list(); m.sel = navList(l.length, m.sel); if (Input.pressed.back) { Menus.close(); AudioSys.play(G.state === 'title' ? 'title' : 'map'); return; } if (Input.pressed.confirm) { AudioSys.play(l[m.sel], true); AudioSys.setIntensity(1); } if (Input.pressed.left) AudioSys.setIntensity(Math.max(0, AudioSys.targetIntensity - 1)); if (Input.pressed.right) AudioSys.setIntensity(Math.min(3, AudioSys.targetIntensity + 1)); if (m.sel < m.scroll) m.scroll = m.sel; if (m.sel > m.scroll + 14) m.scroll = m.sel - 14; },
  draw(m) { ctx.fillStyle = '#0a0612'; ctx.fillRect(0, 0, W, H); const l = this.list(); text('MONSTER JUKEBOX', W / 2, 12, { color: '#ff5bd1', align: 'center', scale: 2, outline: true }); text(l.length + ' / ' + SONG_SPECS.length + ' TRACKS UNLOCKED', W / 2, 32, { color: '#888', align: 'center' });
    l.slice(m.scroll, m.scroll + 15).forEach((id, i) => { const idx = i + m.scroll, s = SONGS[id], y = 52 + i * 17, sel = idx === m.sel, playing = AudioSys.song && AudioSys.song.id === id; if (sel) P.r(ctx, 26, y - 4, 360, 15, 'rgba(255,91,209,.15)'); text((playing ? '♪ ' : '  ') + s.name, 32, y, { color: playing ? '#ff5bd1' : sel ? '#fff' : '#999' }); text(s.style.toUpperCase() + ' ' + s.bpm, 380, y, { color: '#666', align: 'right' }); });
    panel(410, 60, 200, 220, { rim: '#ff5bd1' }); const b = AudioSys.beat(); for (let i = 0; i < 16; i++) { const h = (Math.abs(Math.sin(G.t * (3 + i * .7) + i)) * .6 + (b.phase < .2 ? .4 : 0)) * 120 * (AudioSys.song ? 1 : .1); P.r(ctx, 420 + i * 11, 250 - h, 8, h, hsl(300 + i * 6, 90, 55)); }
    text(AudioSys.song ? AudioSys.song.name : '-', 510, 70, { color: '#fff', align: 'center' }); text('INTENSITY ◄ ' + ['CALM', 'EXPLORE', 'COMBAT', 'BOSS'][AudioSys.targetIntensity] + ' ►', 510, 84, { color: '#ffe14d', align: 'center' });
    drawHero(510, 160 + (b.phase < .15 ? 3 : 0), { face: 1, sx: .9, sy: .9, rot: Math.sin(b.phase * Math.PI * 2) * .15, mouth: b.phase < .3 ? .6 : 0 }); }
};
MH.mapmenu = {
  items: ['CONTINUE', 'POWER-UPS & PALS', 'MONSTER ENCYCLOPEDIA', 'MONSTER JUKEBOX', 'ACHIEVEMENTS', 'OPTIONS', 'CONTROLS', 'TITLE SCREEN'],
  update(m) { m.sel = navList(this.items.length, m.sel); if (Input.pressed.back || Input.pressed.pause) { Menus.close(); return; }
    if (Input.pressed.confirm) { const c = this.items[m.sel]; ({ 'CONTINUE': () => Menus.close(), 'POWER-UPS & PALS': () => Menus.open('forms'), 'MONSTER ENCYCLOPEDIA': () => Menus.open('ency'), 'MONSTER JUKEBOX': () => Menus.open('jukebox'), 'ACHIEVEMENTS': () => Menus.open('ach'), 'OPTIONS': () => Menus.open('options'), 'CONTROLS': () => Menus.open('controls'), 'TITLE SCREEN': () => { Menus.stack = []; Title.open(); } })[c](); } },
  draw(m) { ctx.fillStyle = 'rgba(8,0,16,.8)'; ctx.fillRect(0, 0, W, H); text('MENU', W / 2, 60, { color: '#7fff3a', align: 'center', scale: 3, outline: true }); panel(W / 2 - 120, 106, 240, 140); drawList(this.items, m.sel, W / 2 - 100, 116); }
};
MH.resume333 = { update(m) { if (Input.pressed.up || Input.pressed.down) m.sel = 1 - m.sel; if (Input.pressed.back) { Menus.close(); return; } if (Input.pressed.confirm) { const ch = m.sel === 0 ? Save.data.ch333 : 0; Menus.stack = []; Game.loadLevel(LEVEL_BY_ID.L3, ch); } },
  draw(m) { ctx.fillStyle = 'rgba(0,0,0,.8)'; ctx.fillRect(0, 0, W, H); panel(W / 2 - 150, 130, 300, 80, { rim: '#ff8ab0' }); text('LEVEL 333 IN PROGRESS', W / 2, 140, { color: '#ff8ab0', align: 'center' }); drawList(['RESUME: ' + LEVEL_BY_ID.L3.chapters[Save.data.ch333].name.split(':')[0], 'START FROM CHAPTER 1'], m.sel, W / 2 - 120, 164, { w: 260 }); } };
// ---------------------------------------------------------------- Results
const Results = {
  show(def, st, cb) { this.def = def; this.st = st; this.cb = cb; this.t = 0; G.state = 'results'; AudioSys.setIntensity(1); },
  update() { this.t++; if (this.t > 40 && Input.pressed.confirm) { AudioSys.play_sfx('select'); G.state = 'level'; this.cb(); } },
  draw() {
    if (Game.L) Game.draw(); ctx.fillStyle = 'rgba(5,0,12,.82)'; ctx.fillRect(0, 0, W, H); const st = this.st, d = this.def;
    text(d.label === '333' ? 'LEVEL 333 COMPLETE!' : 'LEVEL ' + d.label + ' COMPLETE!', W / 2, 40, { color: '#7fff3a', align: 'center', scale: 3, outline: true, wave: 1 }); text(d.name, W / 2, 74, { color: '#fff', align: 'center' });
    panel(W / 2 - 140, 96, 280, 160, { rim: '#7fff3a' }); const sh = st.shards.filter(Boolean).length, tm = Math.floor(st.time / 60);
    const rows = [['NOTES', st.notes], ['DIMENSIONAL SHARDS', sh + ' / 3'], ['MONSTERS BONKED', st.kills], ['ROADIES RESCUED', st.rescued || 0], ['TIME', Math.floor(tm / 60) + ':' + String(tm % 60).padStart(2, '0')]];
    rows.forEach((r, i) => { if (this.t > 10 + i * 10) { text(r[0], W / 2 - 120, 108 + i * 18, { color: '#aaa' }); text(String(r[1]), W / 2 + 120, 108 + i * 18, { color: '#ffe14d', align: 'right' }); } });
    const score = st.notes + sh * 50 + st.kills * 2, rank = score > 260 ? 'S' : score > 180 ? 'A' : score > 110 ? 'B' : score > 50 ? 'C' : 'D';
    if (this.t > 70) text('RANK ' + rank, W / 2, 210, { color: rank === 'S' ? '#ff5bd1' : '#7fff3a', align: 'center', scale: 3, outline: true });
    drawHero(W / 2 + 160, 200, { face: -1, rot: Math.sin(G.t * 8) * .2, mouth: .4 + Math.sin(G.t * 10) * .3 });
    if (this.t > 40 && Math.floor(G.t * 2) % 2) text('PRESS CONFIRM', W / 2, 280, { color: '#fff', align: 'center' });
  }
};
// ---------------------------------------------------------------- World map
const WorldMap = {
  sel: 0, t: 0,
  nodes: null,
  layout() { if (this.nodes) return; this.nodes = LEVELS.map((l, i) => { const w = l.world, k = i % 5; const bx = 40 + w * 100, x = bx + [10, 50, 30, 70, 40][k], y = 276 - k * 37 + (w % 2 ? -6 : 0); return { x, y, l }; }); },
  open(focus) { this.layout(); G.state = 'map'; AudioSys.play('map'); this.sel = clamp((focus || Save.data.unlocked) - 1, 0, Math.min(Save.data.unlocked, 30) - 1); this.t = 0; Game.L = null; Save.write(); },
  update() {
    this.t++; if (Menus.update()) return; const max = Math.min(Save.data.unlocked, 30) - 1;
    if (Input.pressed.right || Input.pressed.up) { if (this.sel < max) { this.sel++; AudioSys.play_sfx('menu'); } else if (this.sel === max && max < 29) AudioSys.play_sfx('miss'); }
    if (Input.pressed.left || Input.pressed.down) { if (this.sel > 0) { this.sel--; AudioSys.play_sfx('menu'); } }
    if (Input.pressed.pause || Input.pressed.back) Menus.open('mapmenu');
    if (Input.pressed.confirm && this.t > 15) { const l = LEVELS[this.sel]; AudioSys.play_sfx('select'); if (l.id === 'L3' && Save.data.ch333 > 0) Menus.open('resume333'); else Game.loadLevel(l, 0); }
  },
  draw() {
    this.layout(); const t = G.t;
    const g = ctx.createLinearGradient(0, 0, W, H); g.addColorStop(0, '#12051f'); g.addColorStop(1, '#2a0a2a'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    for (let i = 0; i < 60; i++) { const r = mulberry(i); ctx.fillStyle = `rgba(255,255,255,${.3 + .3 * Math.sin(t * 2 + i)})`; ctx.fillRect(r() * W, r() * H, 1, 1); }
    WORLDS.forEach((w, i) => { const x = 30 + i * 100, unlocked = Save.data.unlocked > i * 5; ctx.fillStyle = unlocked ? w.col + '22' : '#ffffff08'; ctx.fillRect(x, 70, 96, 220); ctx.strokeStyle = unlocked ? w.col + '88' : '#333'; ctx.strokeRect(x + .5, 70.5, 95, 219); wrapText(w.name, 13).forEach((s, j) => text(s, x + 48, 76 + j * 9, { color: unlocked ? w.col : '#444', align: 'center' })); });
    // path
    ctx.strokeStyle = '#555'; ctx.lineWidth = 2; ctx.setLineDash([3, 3]); ctx.beginPath(); this.nodes.forEach((n, i) => i ? ctx.lineTo(n.x, n.y) : ctx.moveTo(n.x, n.y)); ctx.stroke(); ctx.setLineDash([]);
    this.nodes.forEach((n, i) => { const un = i < Save.data.unlocked, d = Save.data.done[n.l.id], s = i === this.sel, is333 = n.l.id === 'L3';
      const r = is333 ? 9 : 6; O.e(n.x, n.y, r + (s ? Math.sin(t * 8) + 1 : 0), r, !un ? '#222' : d && d.clear ? WORLDS[n.l.world].col : '#fff');
      text(n.l.label, n.x, n.y - 3, { color: un ? '#000' : '#555', align: 'center', shadow: false }); if (d) for (let k = 0; k < 3; k++) if (d.shards && d.shards[k]) P.r(ctx, n.x - 5 + k * 4, n.y + r + 3, 3, 3, '#b04bff'); });
    const n = this.nodes[this.sel]; drawHero(n.x, n.y - 26 + Math.sin(t * 5) * 3, { face: 1, sx: .5, sy: .5 });
    const l = n.l, d = Save.data.done[l.id]; panel(20, 300, W - 40, 50, { rim: WORLDS[l.world].col });
    text((l.label === '333' ? 'LEVEL 333' : 'LEVEL ' + l.label) + ': ' + l.name.toUpperCase(), 32, 308, { color: WORLDS[l.world].col, scale: 1 });
    text('WORLD ' + (l.world + 1) + ' — ' + WORLDS[l.world].name, 32, 322, { color: '#aaa' });
    text(d ? 'CLEARED  •  NOTES ' + d.notes + '  •  SHARDS ' + (d.shards || []).filter(Boolean).length + '/3' : (l.big ? 'A COMPLETE SEVEN-CHAPTER ADVENTURE' : 'NOT YET CLEARED'), 32, 336, { color: d ? '#7fff3a' : '#888' });
    text('MAP: THE 333 DIMENSIONS', W / 2, 10, { color: '#7fff3a', align: 'center', scale: 2, outline: true });
    const tot = Object.values(Save.data.done).reduce((a, d) => a + (d.shards || []).filter(Boolean).length, 0); text('SHARDS ' + tot + '/90   NOTES ' + Save.data.notes, W / 2, 32, { color: '#b04bff', align: 'center' });
    text((Input.mode === 'touch' ? 'II' : 'ESC') + ': MENU', W - 10, 48, { color: '#666', align: 'right' });
    Menus.draw();
  }
};
// ---------------------------------------------------------------- Title screen
const Title = {
  sel: 0, t: 0, pressed: false,
  items() { return [Save.data.unlocked > 1 || Object.keys(Save.data.done).length ? 'CONTINUE' : null, 'NEW GAME', 'MONSTER ENCYCLOPEDIA', 'MONSTER JUKEBOX', 'ACHIEVEMENTS', 'OPTIONS', 'CONTROLS'].filter(Boolean); },
  open() { G.state = 'title'; this.t = 0; AudioSys.play('title'); Game.L = null; },
  update() {
    this.t++; if (Menus.update()) return;
    if (!this.pressed) { if (Input.anyPressed && this.t > 20) { this.pressed = true; AudioSys.unlock(); AudioSys.play_sfx('scream', { power: 1 }); Cam.shake(4, 12); } return; }
    const it = this.items(); this.sel = navList(it.length, this.sel);
    if (Input.pressed.confirm) { const c = it[this.sel]; AudioSys.play_sfx('select');
      if (c === 'CONTINUE') WorldMap.open(); else if (c === 'NEW GAME') { if (Object.keys(Save.data.done).length) Menus.open('confirmNew'); else { Game.loadLevel(LEVELS[0]); } }
      else if (c === 'MONSTER ENCYCLOPEDIA') Menus.open('ency'); else if (c === 'MONSTER JUKEBOX') Menus.open('jukebox'); else if (c === 'ACHIEVEMENTS') Menus.open('ach'); else if (c === 'OPTIONS') Menus.open('options'); else if (c === 'CONTROLS') Menus.open('controls'); }
  },
  draw() {
    const t = G.t, b = AudioSys.beat(), kick = b.phase < .12 ? 1 : 0;
    const g = ctx.createRadialGradient(W / 2, 150, 20, W / 2, 150, 420); g.addColorStop(0, '#3a0d4a'); g.addColorStop(1, '#07020c'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    // dimensional rift rays
    ctx.save(); ctx.translate(W / 2, 140); ctx.globalCompositeOperation = 'lighter'; for (let i = 0; i < 18; i++) { const a = i / 18 * 6.283 + t * .1; ctx.fillStyle = hsl((i * 20 + t * 40) % 360, 90, 50, .08); ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(Math.cos(a) * 500, Math.sin(a) * 500); ctx.lineTo(Math.cos(a + .12) * 500, Math.sin(a + .12) * 500); ctx.fill(); } ctx.restore();
    for (let i = 0; i < 3; i++) { ctx.strokeStyle = hsl((t * 60 + i * 120) % 360, 90, 60, .4); ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(W / 2, 140, 110 + i * 30 + ((t * 40) % 30), 0, 7); ctx.stroke(); }
    const hy = 150 + Math.sin(t * 2) * 6 - kick * 4;
    spr(IMG.hero_title, W / 2, hy + 110, { sx: 1 + kick * .03, sy: 1 - kick * .03, rot: Math.sin(t * 1.3) * .05 });
    // title logo
    const title1 = 'THE 333 DIMENSIONS', title2 = 'OF MADNESS';
    text(title1, W / 2, 16, { color: '#7fff3a', align: 'center', scale: 3, outline: '#1a0030', wave: 1.5 });
    text(title2, W / 2, 44, { color: '#ff2a4a', align: 'center', scale: 4, outline: '#1a0030', wave: 2 });
    // cast parade
    const px = (t * 40) % (W + 600) - 300;
    drawPig('hamwise', px, 352, { face: 1, state: 'walk', t }); drawPig('porkington', px - 30, 352, { face: 1, state: 'walk', t: t + .2 }); drawPig('trufflina', px - 66, 352, { face: 1, state: 'walk', t: t + .4 });
    drawBiker(px - 160, 354, { face: 1, t, speed: 1, wheelie: Math.sin(t) > .6 ? .25 : 0 });
    drawWolf(W + 300 - ((t * 32) % (W + 600)), 356, { face: -1, t, scale: .42, arm: Math.sin(t * 4) * .6 });
    drawCow(W + 380 - ((t * 32) % (W + 600)), 300, { face: -1, t, scale: .55, rot: -.1 * Math.sin(t) });
    drawSludge(W + 470 - ((t * 32) % (W + 600)), 358, { face: -1, t, scale: .2 });
    if (!this.pressed) { if (Math.floor(t * 2) % 2) text(Input.mode === 'touch' ? 'TAP TO ROCK' : 'PRESS ANY BUTTON', W / 2, 300, { color: '#fff', align: 'center', scale: 2, outline: true }); }
    else { panel(W / 2 - 100, 236, 200, this.items().length * 14 + 8, { rim: '#7fff3a', bg: 'rgba(20,8,30,.9)' }); drawList(this.items(), this.sel, W / 2 - 84, 242, { gap: 14, w: 190 }); }
    text('AN ORIGINAL GROTESQUE HEAVY METAL ADVENTURE', W / 2, 352 - 12, { color: '#555', align: 'center', shadow: false });
    Menus.draw();
  }
};
MH.confirmNew = { update(m) { if (Input.pressed.left || Input.pressed.right) m.sel = 1 - m.sel; if (Input.pressed.back) Menus.close(); if (Input.pressed.confirm) { if (m.sel === 1) { Save.reset(); Menus.stack = []; Game.loadLevel(LEVELS[0]); } else Menus.close(); } },
  draw(m) { ctx.fillStyle = 'rgba(0,0,0,.8)'; ctx.fillRect(0, 0, W, H); panel(W / 2 - 150, 140, 300, 70, { rim: '#ff3a3a' }); text('START OVER? THIS ERASES YOUR SAVE.', W / 2, 152, { color: '#ff3a3a', align: 'center' }); text((m.sel === 0 ? '► ' : '  ') + 'NO', W / 2 - 60, 180, { color: m.sel === 0 ? '#fff' : '#888', align: 'center' }); text((m.sel === 1 ? '► ' : '  ') + 'YES', W / 2 + 60, 180, { color: m.sel === 1 ? '#fff' : '#888', align: 'center' }); } };
function applyTouchPref() { const o = Save.data.opt.touch || 'auto', el = document.getElementById('touch'); if (o === 'on') { Touch.on = true; el.classList.add('on'); } else if (o === 'off') { Touch.on = false; el.classList.remove('on'); } }
