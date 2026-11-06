// ============================================================================
// Concerts (rhythm game) and the ending celebration
// ============================================================================
const LANES = [{ act: 'jump', alt: 'left', col: '#7fff3a', label: 'JUMP' }, { act: 'whip', alt: 'down', col: '#ff3a6a', label: 'WHIP' }, { act: 'spit', alt: 'up', col: '#5bd4ff', label: 'SPIT' }, { act: 'bash', alt: 'right', col: '#ffe14d', label: 'BASH' }];
const Concert = {
  start(song, final) {
    this.song = song; this.final = final; G.state = 'concert'; AudioSys.play(song, true); AudioSys.setIntensity(2);
    this.notes = []; this.t = 0; this.score = 0; this.combo = 0; this.maxCombo = 0; this.hits = 0; this.total = 0; this.crowd = .5; this.judge = null; this.started = false; this.lastBeat = -1; this.done = false; this.fx = [];
    this.len = final ? 96 : 72; this.r = mulberry(hashStr(song + 'chart')); this.startBeat = null;
    this.band = final ? ['hamwise', 'porkington', 'trufflina', 'razz', 'udderly', 'barnaby', 'gloop'] : ['hamwise', 'porkington', 'trufflina'];
  },
  pos() { const b = AudioSys.beat(); return b.beat + b.phase; },
  update() {
    this.t++; const pos = this.pos();
    if (this.startBeat === null) { this.startBeat = Math.floor(pos) + 4; for (let i = 0; i < this.len; i++) { const beat = this.startBeat + 4 + i; const dens = i > this.len * .5 ? .85 : .65; if (this.r() < dens) this.notes.push({ b: beat, lane: Math.floor(this.r() * 4), hit: false, miss: false }); if (i > this.len * .4 && this.r() < .3) this.notes.push({ b: beat + .5, lane: Math.floor(this.r() * 4), hit: false, miss: false }); if (this.final && i % 16 === 15) this.notes.push({ b: beat, lane: (Math.floor(this.r() * 4) + 2) % 4, hit: false, miss: false }); } this.total = this.notes.length; }
    for (let l = 0; l < 4; l++) {
      if (Input.pressed[LANES[l].act] || Input.pressed[LANES[l].alt]) {
        let best = null, bd = .3; for (const n of this.notes) if (!n.hit && !n.miss && n.lane === l) { const d = Math.abs(n.b - pos); if (d < bd) { bd = d; best = n; } }
        if (best) { best.hit = true; this.hits++; const perfect = bd < .1; this.combo++; this.maxCombo = Math.max(this.maxCombo, this.combo); this.score += (perfect ? 300 : 120) * (1 + Math.floor(this.combo / 10)); this.crowd = Math.min(1, this.crowd + .03); this.judge = { s: perfect ? 'PERFECT!' : 'GOOD', col: perfect ? '#ff5bd1' : '#7fff3a', t: 30 }; AudioSys.play_sfx('headbang', { combo: this.combo + l }); this.fx.push({ lane: l, t: 14 }); }
        else { this.combo = 0; this.crowd = Math.max(0, this.crowd - .02); AudioSys.play_sfx('miss'); }
      }
    }
    for (const n of this.notes) if (!n.hit && !n.miss && pos - n.b > .3) { n.miss = true; this.combo = 0; this.crowd = Math.max(0, this.crowd - .04); this.judge = { s: 'MISS', col: '#ff3a3a', t: 30 }; }
    if (this.judge && --this.judge.t <= 0) this.judge = null; for (const f of this.fx) f.t--; this.fx = this.fx.filter(f => f.t > 0);
    if (Math.floor(pos) !== this.lastBeat) { this.lastBeat = Math.floor(pos); if (this.crowd > .6 && this.lastBeat % 2 === 0) FX.notes(R(80, W - 80), 200, 1); }
    FX.update();
    if (!this.done && this.notes.length && pos > this.notes[this.notes.length - 1].b + 2) this.finish();
    if (Input.pressed.pause && !this.done) this.finish();
  },
  finish() {
    this.done = true; const acc = this.total ? this.hits / this.total : 0, rank = acc > .95 ? 'S' : acc > .85 ? 'A' : acc > .7 ? 'B' : acc > .5 ? 'C' : 'D';
    if (rank === 'S' || rank === 'A') Save.achieve('concert'); AudioSys.play_sfx('cheer'); AudioSys.play_sfx('stinger');
    this.rank = rank; this.acc = acc; this.endT = 0;
  },
  updateEnd() { this.endT++; FX.update(); if (this.endT > 60 && Input.pressed.confirm) { if (this.final) { Game.finishLevel(); } else { G.state = 'level'; Game.finishing = false; Game.finishLevel(); } } },
  draw() {
    const t = G.t, pos = this.pos(), b = AudioSys.beat(), kick = b.phase < .15;
    // stage
    const g = ctx.createLinearGradient(0, 0, 0, H); g.addColorStop(0, '#0a0014'); g.addColorStop(1, '#2a0030'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    ctx.save(); ctx.globalCompositeOperation = 'lighter'; for (let i = 0; i < 6; i++) { const x = 60 + i * 104, a = Math.sin(t * 1.2 + i) * .5; const gg = ctx.createLinearGradient(x, 0, x, 220); gg.addColorStop(0, hsl((i * 60 + t * 40) % 360, 90, 60, .3)); gg.addColorStop(1, 'rgba(0,0,0,0)'); ctx.fillStyle = gg; ctx.beginPath(); ctx.moveTo(x - 4, 0); ctx.lineTo(x + 4, 0); ctx.lineTo(x + a * 160 + 50, 220); ctx.lineTo(x + a * 160 - 50, 220); ctx.fill(); } ctx.restore();
    for (let x = 0; x < W; x += 40) { O.r(x + 2, 110, 36, 36, '#111', 1); P.e(ctx, x + 20, 128, 12 + (kick ? 2 : 0), 12 + (kick ? 2 : 0), '#2a2a30'); }
    P.r(ctx, 0, 214, W, 8, '#3a2a40'); P.r(ctx, 0, 214, W, 2, '#c9a227');
    // band
    const xs = this.final ? [70, 140, 210, 400, 470, 540, 600] : [180, 250, 460];
    this.band.forEach((who, i) => { const x = xs[i], bounce = kick ? -3 : 0; const anim = who === 'razz' ? (Math.floor(pos / 8) % 2 ? 'wheelie' : 'go') : 'dance'; drawActor(who, x, 214 + bounce, { face: x < W / 2 ? 1 : -1, t: t + i, anim, scale: who === 'barnaby' ? .5 : who === 'udderly' ? .42 : who === 'gloop' ? .25 : undefined }); });
    drawHero(W / 2, 170 + (kick ? 4 : 0), { face: 1, mouth: kick ? .9 : .3, rot: Math.sin(pos * Math.PI) * .25, aura: this.combo > 10 });
    if (this.combo > 10 && kick) FX.ring(W / 2, 170, 80, '#7fff3a', 12, 2);
    // crowd
    for (let i = 0; i < 46; i++) { const x = i * 14 + 4, jump = (this.crowd > .4 && (i + Math.floor(pos)) % 3 === 0 && kick) ? 4 : 0; ctx.fillStyle = hsl(i * 37 % 360, 30, 20); ctx.beginPath(); ctx.arc(x, 232 - jump, 6, 0, 7); ctx.fill(); ctx.fillRect(x - 6, 232 - jump, 12, 20); if (this.crowd > .7 && i % 4 === 0) { ctx.fillRect(x - 1, 216 - jump, 2, 10); ctx.fillRect(x - 3, 214 - jump, 2, 4); ctx.fillRect(x + 1, 214 - jump, 2, 4); } }
    // highway
    const hx = W / 2 - 100, hitY = 330; ctx.fillStyle = 'rgba(0,0,0,.6)'; ctx.fillRect(hx, 240, 200, 120);
    for (let l = 0; l < 4; l++) { const lx = hx + 25 + l * 50; P.r(ctx, lx - 1, 240, 2, 120, '#333'); const lit = this.fx.find(f => f.lane === l); O.e(lx, hitY, 14, 6, lit ? LANES[l].col : '#222'); text(Input.mode === 'touch' || Input.mode === 'pad' ? LANES[l].label : ['Z/←', 'X/↓', 'C/↑', 'V/→'][l].replace('↓', 'v').replace('↑', '^').replace('←', '<').replace('→', '>'), lx, 344, { color: LANES[l].col, align: 'center' }); }
    for (const n of this.notes) { if (n.hit) continue; const y = hitY - (n.b - pos) * 40; if (y < 236 || y > 360) continue; const lx = hx + 25 + n.lane * 50; O.e(lx, y, 11, 5, n.miss ? '#444' : LANES[n.lane].col); P.r(ctx, lx - 5, y - 2, 4, 1, '#fff8'); }
    // HUD
    text('SCORE ' + this.score, 10, 10, { color: '#fff', outline: true }); text('COMBO x' + this.combo, 10, 22, { color: '#ffe14d', outline: true });
    text('CROWD', W - 110, 10, { color: '#fff' }); P.r(ctx, W - 110, 22, 100, 6, '#300'); P.r(ctx, W - 110, 22, 100 * this.crowd, 6, this.crowd > .6 ? '#7fff3a' : this.crowd > .3 ? '#ffe14d' : '#ff3a3a');
    if (this.judge) text(this.judge.s, W / 2, 270, { color: this.judge.col, align: 'center', scale: 2, outline: true });
    if (this.startBeat !== null && pos < this.startBeat + 4) text(['4', '3', '2', '1'][clamp(Math.floor(pos - this.startBeat + 4) - 4 + 4, 0, 3)] || 'GO', W / 2, 60, { color: '#fff', align: 'center', scale: 4, outline: true });
    text(this.final ? 'THE FINAL SONG — ENCORE!' : 'THE THREE PIG PUNK PARTY', W / 2, 6, { color: '#ff5bd1', align: 'center', outline: true });
    FX.draw(0, 0);
    if (this.done) { ctx.fillStyle = 'rgba(0,0,0,.7)'; ctx.fillRect(0, 0, W, H); text('SHOW OVER!', W / 2, 80, { color: '#7fff3a', align: 'center', scale: 3, outline: true }); text('ACCURACY ' + Math.round(this.acc * 100) + '%   MAX COMBO ' + this.maxCombo, W / 2, 130, { color: '#fff', align: 'center' }); text('RANK ' + this.rank, W / 2, 160, { color: '#ff5bd1', align: 'center', scale: 4, outline: true }); if (this.endT > 60 && Math.floor(t * 2) % 2) text('PRESS CONFIRM', W / 2, 240, { color: '#fff', align: 'center' }); }
  }
};
// ---------------------------------------------------------------- ending celebration + credits
const Ending = {
  start() { G.state = 'ending'; this.t = 0; AudioSys.play('ending', true); AudioSys.setIntensity(2); Save.data.cleared = true; Save.write(); FX.clear(); },
  credits: ['THE 333 DIMENSIONS OF MADNESS', '', 'STARRING', 'MOSHMOUTH — the screaming head', '', 'THE THREE LITTLE PIGS', 'HAMWISE — kazoo & naps', 'PORKINGTON — drums & structural engineering', 'TRUFFLINA — bass & punching', '', 'RAZZ VROOMBERG — rhythm guitar & hair', 'BIG BAD BARNABY — backing howls', 'CAPTAIN UDDERLY — cowbell & justice', 'THE GOLDEN GLOOP — light show & ooze', '', 'WITH', 'Grizelda the Bear, the Puppet King, the MOO-9000,', 'the Dimension Devourer, the Carnival Colossus,', 'every Gloopkin, and one very tired narrator', '', 'MUSIC', 'Procedurally composed original hard rock, thrash,', 'punk, industrial, psychedelic & circus metal', '', 'NO DIMENSIONS WERE PERMANENTLY HARMED', '', 'THANK YOU FOR PLAYING', '', 'STAY HEAVY. STAY ABSURD.', '', 'THE END...?'],
  update() { this.t++; FX.update(); if (this.t % 20 === 0) FX.confetti(W / 2, -10, 10); if ((this.t > 300 && Input.pressed.confirm) || this.t > 3600) { Title.open(); } },
  draw() {
    const t = G.t, b = AudioSys.beat(), kick = b.phase < .15, k = this.t;
    const g = ctx.createLinearGradient(0, 0, 0, H); g.addColorStop(0, '#1a0030'); g.addColorStop(1, '#ff5bd122'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = '#ffffe0'; ctx.beginPath(); ctx.arc(560, 60, 30, 0, 7); ctx.fill();
    P.r(ctx, 0, 300, W, 60, '#2a1a30'); P.r(ctx, 0, 300, W, 3, '#c9a227');
    // each cast member celebrates in their own way
    drawHero(W / 2, 250 + (kick ? 4 : 0), { face: 1, mouth: kick ? 1 : .2, rot: Math.sin(t * 6) * .3 }); if (kick && k % 2 === 0) FX.ring(W / 2, 250, 70, '#7fff3a', 14, 2);
    drawPig('hamwise', 110, 300, { face: 1, state: 'dance', t, prop: 'kazoo' }); if (k % 30 === 0) FX.notes(110, 260, 2);
    drawPig('porkington', 160, 300 - Math.abs(Math.sin(t * 6)) * 6, { face: 1, state: 'idle', t }); if (kick) { FX.debris(160, 262, 'stick', 1); }
    drawPig('trufflina', 216, 300, { face: 1, state: Math.floor(t * 2) % 2 ? 'attack' : 'idle', t, sq: 1 + Math.sin(t * 8) * .06 });
    const rx = W / 2 + Math.cos(t * .8) * 220, dir = -Math.sin(t * .8); drawBiker(rx, 302, { face: dir > 0 ? 1 : -1, t, speed: 1.4, wheelie: .3 + Math.sin(t * 3) * .1, turbo: true }); if (k % 3 === 0) FX.smoke(rx - (dir > 0 ? 60 : -60), 292, -dir * 2);
    drawWolf(540, 302, { face: -1, t, scale: .5, rot: -.35, arm: -.4 + Math.sin(t * 3) * .2 }); if (k % 90 === 0) { AudioSys.play_sfx('howl'); FX.ring(530, 220, 60, '#fff', 30, 2); }
    drawCow(W / 2 + Math.cos(t * 1.4) * 160, 120 + Math.sin(t * 2.8) * 40, { face: Math.sin(t * 1.4) < 0 ? 1 : -1, t, scale: .38, rot: Math.sin(t * 1.4) * .3, cape: 8, capeStretch: 6 });
    const gm = Math.floor(t / 2) % 3; if (gm === 0) drawSludge(420, 302, { t, scale: .3, sy: 1 + Math.sin(t * 4) * .4, wobble: 2 }); else if (gm === 1) { for (const s of [-1, 0, 1]) drawSludge(420 + s * 26, 302, { t: t + s, scale: .14, sy: 1 + Math.abs(Math.sin(t * 6 + s)) * .5 }); } else drawSludge(420, 302, { t, scale: .3, sx: 1.6, sy: .6, wobble: 3, bulge: .2 });
    FX.draw(0, 0);
    // credits roll
    const y0 = H - k * .45; ctx.fillStyle = 'rgba(0,0,0,.35)'; ctx.fillRect(W / 2 - 170, 0, 340, 200);
    this.credits.forEach((c, i) => { const y = y0 + i * 14; if (y > -10 && y < 200) text(c, W / 2, y, { color: i === 0 ? '#7fff3a' : c === c.toUpperCase() && c.length < 22 ? '#ff5bd1' : '#fff', align: 'center', outline: true, scale: i === 0 ? 2 : 1 }); });
    if (k > 300) text('PRESS CONFIRM', W / 2, H - 14, { color: '#aaa', align: 'center' });
  }
};
