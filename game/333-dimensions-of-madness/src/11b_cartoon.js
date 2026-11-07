// ============================================================================
// Cartoon layer: power-up bubbles, slapstick enemy reactions, tutorial prompts,
// joke obstacles, the giant collectible, set-piece spectacles.
// ============================================================================
const POWERS = {
  pig: { col: '#ff8ab0', label: 'PIG POWER!', joke: 'OINK OINK, MOVE ASIDE!' },
  wolf: { col: '#c8c8e0', label: 'WOLF POWER!', joke: 'AWOOOO! (that means hello)' },
  cow: { col: '#ffffff', label: 'COW POWER!', joke: 'HOLY COW! LITERALLY!' },
  slime: { col: '#7fff3a', label: 'SLIME POWER!', joke: 'PTOO! PTOO! PTOO!' }
};
class PowerUp extends Ent {
  constructor(o) { super(o.x, o.y - 6, 26, 26); this.kind = o.kind || 'pig'; this.base = this.y; if (o.drop) { this.vy = -2; this.drop = true; } }
  update(L) {
    this.t++; if (this.drop) { this.vy = Math.min(this.vy + .15, 2); this.y += this.vy; if (L.solidAt(Math.floor(this.cx / TS), Math.floor((this.y + this.h + 6) / TS))) { this.drop = false; this.base = this.y; } } else this.y = this.base + Math.sin(this.t * .07) * 4;
    const p = Game.player; if (overlap(this, p) && !p.dead) {
      this.dead = true; p.setPower(this.kind); const P_ = POWERS[this.kind]; HUD.banner(P_.label, P_.col, P_.joke); AudioSys.play_sfx('power'); AudioSys.play_sfx('riff');
      FX.burst(this.cx, this.cy, 40, [P_.col, '#fff', '#ffe14d'], { speed: 5 }); FX.confetti(this.cx, this.cy - 60, 30); Cam.shake(4, 10);
      Save.data.powers = Save.data.powers || {}; Save.data.powers[this.kind] = 1; Save.achieve('firstPower'); if (Object.keys(Save.data.powers).length >= 4) Save.achieve('allPowers');
    }
  }
  draw(cx, cy) {
    const x = this.cx - cx, y = this.cy - cy, c = POWERS[this.kind].col;
    ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.fillStyle = c + '55'; ctx.beginPath(); ctx.arc(x, y, 20 + Math.sin(this.t * .2) * 2, 0, 7); ctx.fill(); ctx.restore();
    P.e(ctx, x, y, 17, 17, '#0a060e'); P.e(ctx, x, y, 15, 15, 'rgba(255,255,255,.25)');
    drawHero(x, y + 1, { face: 1, form: this.kind, sx: .36, sy: .36, rot: Math.sin(this.t * .1) * .2 });
    P.e(ctx, x - 6, y - 8, 4, 3, 'rgba(255,255,255,.8)');
    for (let i = 0; i < 4; i++) { const a = this.t * .05 + i * 1.57; P.r(ctx, x + Math.cos(a) * 22, y + Math.sin(a) * 22, 2, 2, '#fff'); }
  }
}
// slapstick enemy defeat: launched, spun, bounced, sent into the background...
const REACTIONS = ['fly', 'bg', 'tornado', 'fly', 'bg', 'bounce'];
class Ragdoll extends Ent {
  constructor(e, dir, kind) {
    super(e.x, e.y, e.w, e.h); this.img = e.kind === 'gloopkin' ? IMG.gloopkin : (SPR[e.kind] || SPR.puppet)[0]; this.kind = kind; this.dir = dir || 1; this.flipImg = e.dir > 0;
    this.vx = this.dir * (kind === 'bg' ? 3 : 6 + R(3)); this.vy = kind === 'tornado' ? -1 : -6 - R(3); this.rot = 0; this.vr = this.dir * (.3 + R(.3)); this.sc = e.sc || 1; this.bounces = 0; this.life = 140;
    if (kind === 'apart') { this.dead = true; for (let i = 0; i < 6; i++) FX.add({ x: e.cx, y: e.cy, vx: R(-4, 4), vy: R(-6, -2), type: 'junk', col: pick(['#e8c290', '#c4302b', '#5a3a1d', '#ddd']), rot: R(6), vr: R(-.4, .4), life: 60, grav: .25 }); }
    if (Math.random() < .5) FX.add({ x: e.cx, y: e.y, vx: R(-2, 2), vy: -5, type: 'hat', col: pick(['#222', '#c4302b', '#3a6ac4', '#7a3cff']), rot: 0, vr: .3, life: 70, grav: .2 });
  }
  update(L) {
    this.t++; if (--this.life <= 0) this.dead = true;
    if (this.kind === 'bg') { this.x += this.vx; this.y += this.vy; this.vy += .12; this.sc *= .955; this.rot += this.vr; if (this.sc < .08) { this.dead = true; FX.add({ x: this.cx, y: this.cy, vx: 0, vy: 0, type: 'twinkle', life: 30, grav: 0 }); AudioSys.play_sfx('ticket'); } return; }
    if (this.kind === 'tornado') { this.vr = .9; this.rot += this.vr; this.y -= 1.5; this.x += Math.sin(this.t * .4) * 3; if (this.t % 3 === 0) FX.add({ x: this.cx + R(-12, 12), y: this.y + this.h, vx: R(-1, 1), vy: -1, col: '#ddd', size: 2, life: 14, grav: 0 }); if (this.t > 70) { this.dead = true; FX.burst(this.cx, this.cy, 20, ['#fff', '#ffe14d'], { speed: 4 }); AudioSys.play_sfx('pop'); } return; }
    this.vy += .35; this.x += this.vx; this.y += this.vy; this.rot += this.vr;
    const tx = Math.floor((this.cx + sign(this.vx) * 8) / TS), ty = Math.floor(this.cy / TS);
    if (L.solidAt(tx, ty)) { this.vx = -this.vx * .8; this.bounces++; AudioSys.play_sfx('boing'); FX.ring(this.cx, this.cy, 16, '#fff', 10, 2); Cam.shake(2, 4); }
    if (L.solidAt(Math.floor(this.cx / TS), Math.floor((this.y + this.h) / TS)) && this.vy > 0) { this.vy = -this.vy * .6; this.bounces++; if (this.bounces > 3) { this.dead = true; FX.burst(this.cx, this.cy, 16, ['#fff', '#ff5bd1', '#7fff3a'], { speed: 3 }); AudioSys.play_sfx('pop'); } }
    for (const a of Game.ents) if (a instanceof BigAmp && overlap(this, a) && !a.hitT) a.boom(this);
  }
  draw(cx, cy) { const k = this.img === IMG.gloopkin ? HD : 1; spr(this.img, this.cx - cx, this.cy - cy, { ax: this.img.width / 2, ay: this.img.height / 2, rot: this.rot, sx: this.sc * k, sy: this.sc * k, flip: this.flipImg }); }
}
// tutorial prompts: a bouncing arrow + the button to press
class Prompt extends Ent {
  constructor(o) { super(o.x, o.y - 30, 30, 60); this.kind = o.kind; this.until = o.untilX; this.label = o.label; }
  update() { this.t++; const p = Game.player; if (this.until && p.x > this.until) this.gone = Math.min(1, (this.gone || 0) + .08); if (this.gone >= 1) this.dead = true; }
  draw(cx, cy) {
    const a = 1 - (this.gone || 0); if (a <= 0) return; ctx.save(); ctx.globalAlpha = a;
    const x = this.cx - cx, y = this.y - cy + Math.sin(this.t * .15) * 5, t = Input.mode === 'touch';
    const btn = this.label || { move: t ? 'STICK ►' : '► / D', jump: t ? 'JUMP' : 'SPACE', attack: t ? 'ATTACK' : 'X', collect: '♪ ♪ ♪' }[this.kind];
    const col = { move: '#ffe14d', jump: '#7fff3a', attack: '#ff5bd1', collect: '#5bd4ff' }[this.kind];
    if (this.kind === 'move') { O.poly([[x - 20, y - 8], [x + 4, y - 8], [x + 4, y - 18], [x + 26, y], [x + 4, y + 18], [x + 4, y + 8], [x - 20, y + 8]], col, 2); }
    else { O.poly([[x - 9, y - 22], [x + 9, y - 22], [x + 9, y - 4], [x + 18, y - 4], [x, y + 14], [x - 18, y - 4], [x - 9, y - 4]], col, 2); }
    const w = textWidth(btn, 1) + 12; panel(x - w / 2, y - 44, w, 13, { rim: col, bg: '#1a0a2a' }); text(btn, x, y - 41, { color: '#fff', align: 'center' });
    ctx.restore();
  }
}
// a ridiculous obstacle: jump it and it explodes into confetti
class JokeBlock extends Ent {
  constructor(o) { super(o.x, o.y - 30, 30, 30); this.solid = true; this.passed = false; }
  update() { this.t++; const p = Game.player; if (!this.passed && p.x > this.x + this.w + 2) { this.passed = true; this.dead = true; this.solid = false; FX.confetti(this.cx, this.cy - 40, 60); FX.burst(this.cx, this.cy, 30, ['#ff5bd1', '#ffe14d', '#5bd4ff', '#7fff3a'], { speed: 5 }); AudioSys.play_sfx('explode'); AudioSys.play_sfx('cheer'); Cam.shake(5, 12); FX.pop(this.cx, this.y - 10, 'TA-DAAA!', '#ffe14d'); } }
  draw(cx, cy) { const x = Math.round(this.x - cx), y = Math.round(this.y - cy), sq = Math.sin(this.t * .2) * 1.5;
    O.r(x, y + sq, 30, 30 - sq, '#ffcc33', 2); for (let i = 0; i < 3; i++) P.r(ctx, x + 2 + i * 10, y + 8 + sq, 6, 14 - sq, '#e01a2a');
    P.e(ctx, x + 9, y + 6 + sq, 5, 5, '#fff'); P.e(ctx, x + 21, y + 6 + sq, 5, 5, '#fff'); P.e(ctx, x + 10 + Math.sin(this.t * .1) * 2, y + 7 + sq, 2, 2, '#000'); P.e(ctx, x + 22 + Math.sin(this.t * .1) * 2, y + 7 + sq, 2, 2, '#000');
    P.e(ctx, x + 15, y + 22, 5, 2 + Math.abs(Math.sin(this.t * .1)) * 2, '#300'); }
}
// giant amplifier gag: enemies launched into it make it SHRED
class BigAmp extends Ent {
  constructor(o) { super(o.x, o.y - 70, 56, 70); this.hitT = 0; }
  boom(r) { this.hitT = 40; r.dead = true; AudioSys.play_sfx('riff'); AudioSys.play_sfx('stinger'); Cam.shake(6, 16); FX.notes(this.cx, this.y, 10); for (let i = 0; i < 3; i++) FX.ring(this.cx, this.cy, 60 + i * 20, '#ffe14d', 24, 3); FX.pop(this.cx, this.y - 16, 'KERRANNNG!', '#ffe14d'); Game.levelStats.kills++; }
  update() { this.t++; if (this.hitT > 0) this.hitT--; }
  draw(cx, cy) { const s = this.hitT > 0 ? 1 + Math.sin(this.hitT) * .06 : 1, x = this.cx - cx, y = this.y + this.h - cy;
    ctx.save(); ctx.translate(x, y); ctx.scale(s, s); O.r(-28, -70, 56, 70, '#1c1c22', 3); O.r(-24, -66, 48, 10, '#c9a227', 1); for (let i = 0; i < 5; i++) P.e(ctx, -18 + i * 9, -61, 2, 2, '#222');
    O.e(0, -30, 18 + (this.hitT > 0 ? 3 : 0), 18 + (this.hitT > 0 ? 3 : 0), '#33333a'); P.e(ctx, 0, -30, 7, 7, '#111'); text('MAX', 0, -12, { color: '#ff3a3a', align: 'center', shadow: false }); ctx.restore(); }
}
// the giant collectible: a golden guitar pick
class MegaNote extends Ent {
  constructor(o) { super(o.x, o.y - 30, 36, 40); this.base = this.y; }
  update() { this.t++; this.y = this.base + Math.sin(this.t * .06) * 6; const p = Game.player; if (overlap(this, p)) { this.dead = true; Game.levelStats.notes += 25; Save.data.notes += 25; AudioSys.play_sfx('riff'); AudioSys.play_sfx('shard'); FX.confetti(this.cx, this.cy - 80, 80); FX.burst(this.cx, this.cy, 40, ['#ffe14d', '#fff'], { speed: 6 }); HUD.banner('GOLDEN PICK!', '#ffe14d', '+25 NOTES. THE CROWD WEEPS WITH JOY.'); Cam.shake(4, 12); } }
  draw(cx, cy) { const x = this.cx - cx, y = this.cy - cy, s = .9 + Math.abs(Math.cos(this.t * .05)) * .2;
    ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.fillStyle = 'rgba(255,225,77,.3)'; ctx.beginPath(); ctx.arc(x, y, 30, 0, 7); ctx.fill(); ctx.restore();
    ctx.save(); ctx.translate(x, y); ctx.scale(s, 1); O.poly([[-16, -18], [16, -18], [18, -8], [0, 22], [-18, -8]], '#ffd23a', 3); P.poly(ctx, [[-10, -14], [0, -14], [-12, -4]], '#fff8c0'); text('333', 0, -8, { color: '#a05a00', align: 'center', shadow: false }); ctx.restore(); }
}
// ---------------------------------------------------------------- SET PIECES (background spectacles)
class SetPiece extends Ent {
  constructor(o) { super(o.x, 0, 16, 9999); this.kind = o.kind; this.on = false; this.k = 0; this.o = o; this.bg = true; }
  update(L) {
    const p = Game.player; if (!this.on && p.x > this.x) { this.on = true; this.start(L); }
    if (!this.on || this.finished) return; this.k++; const k = this.k;
    switch (this.kind) {
      case 'ampfall': if (k === 50) { Cam.shake(12, 30); AudioSys.play_sfx('explode'); AudioSys.play_sfx('riff'); FX.notes(this.ax, this.ay - 60, 14); for (let i = 0; i < 8; i++) Game.add(new Note(this.ax - 20 + i * 6, this.ay - 90, true)); } if (k > 160) this.finished = true; break;
      case 'cowstomp': if (k % 70 === 35 && k < 420) { Cam.shake(9, 18); AudioSys.play_sfx('rumble'); AudioSys.play_sfx('moo'); for (let i = 0; i < 3; i++) Game.add(new Note(Cam.x + R(40, VW - 40), Cam.y + 10, true)); } if (k > 460) this.finished = true; break;
      case 'stagecollapse': if (k % 40 === 10 && k < 260) { const x = p.cx + R(60, 220); Game.add(new FallingRig(x, Cam.y - 40)); } if (k > 300) this.finished = true; break;
      case 'bikejump': if (k === 1) { AudioSys.play_sfx('rev'); HUD.toast(pick(['ELECTRIC HARLEY: "COMING THROUGH, LETTUCE!"', 'ELECTRIC HARLEY: "WATCH THE HAIR!"', 'ELECTRIC HARLEY: "SICK JUMP, RIGHT?!"']), '#5bd4ff'); } if (k === 60) { AudioSys.play_sfx('land'); Cam.shake(5, 10); } if (k > 120) this.finished = true; break;
      default: if (k === 30) { Cam.shake(8, 30); AudioSys.play_sfx('rumble'); } if (k === 1) AudioSys.play_sfx(this.kind === 'moonface' ? 'scream' : this.kind === 'milkflood' ? 'splash' : 'explode', { power: 1.5 }); if (k > 300) this.finished = true;
    }
  }
  start(L) {
    const p = Game.player; this.ax = p.cx + 200; this.ay = Game.groundY(L, Math.floor(this.ax / TS)); this.px0 = p.cx; this.cam0 = Cam.x;
    const lines = { ampfall: 'A GIANT AMP FELL FROM THE SKY!', crash: 'SOMETHING HUGE JUST CRASHED THROUGH THE WALL!', cowstomp: 'THE GROUND SHAKES... IT IS A GIANT COW!', milkflood: 'MILK TSUNAMI!!!', ridebreak: 'THE FERRIS WHEEL ESCAPED!', swallow: 'THE GARBAGE MONSTER ATE A WHOLE BUILDING!', moonface: 'THE MOON IS SCREAMING. NORMAL TUESDAY.', stagecollapse: 'THE LIGHTING RIG IS COMING DOWN!', portalstorm: 'PORTAL STORM! PLEASE DO NOT LICK THE PORTALS.', strings: 'A GIANT PUPPET HAND REACHES IN...', bikejump: '' };
    if (lines[this.kind]) HUD.banner(lines[this.kind], '#ffe14d');
    if (this.kind === 'ampfall') { const a = new AmpTotem({ x: this.ax - 16, y: this.ay - 16 }); a.fallY = -260; Game.add(a); L.solidEnts.push(a); this.amp = a; }
  }
  drawBG(cx, cy) { // drawn behind the tiles, in front of the parallax
    if (!this.on || this.finished && this.kind !== 'swallow') return; const k = this.k, gy = this.ay - cy;
    switch (this.kind) {
      case 'cowstomp': { const x = this.ax - cx - 300 + k * 1.4, lift = Math.max(0, Math.sin((k % 70) / 70 * Math.PI)) * 40; ctx.save(); ctx.globalAlpha = .55; drawCow(x, gy + 30 - lift, { face: 1, t: k / 60, scale: 2.2, flash: '#3a1a5a', cape: 6 }); ctx.restore(); break; }
      case 'crash': { const x = this.px0 - cx + 120, a = Math.min(1, k / 20); ctx.save(); ctx.globalAlpha = a * .9; if (k < 30) for (let i = 0; i < 10; i++) P.r(ctx, x + R(-80, 80), gy - 120 + R(-60, 60), 10, 10, '#8a6a4a'); drawSludge(x - k * 2.2, gy + 10, { scale: 1.2, t: k / 60, wobble: 2 }); ctx.restore(); break; }
      case 'milkflood': { const x = this.px0 - cx - 400 + k * 6; ctx.fillStyle = 'rgba(244,244,255,.85)'; ctx.beginPath(); ctx.moveTo(x - 600, gy + 40); for (let i = 0; i <= 600; i += 20) ctx.lineTo(x - 600 + i, gy - 60 - Math.sin(i / 60 + k * .2) * 20 - (i > 520 ? (i - 520) * 1.2 : 0)); ctx.lineTo(x, gy + 40); ctx.fill(); for (let i = 0; i < 6; i++) { const lx = x - 80 - i * 60, ly = gy - 70 - Math.sin(k * .1 + i) * 30; P.e(ctx, lx, ly, 6, 5, '#f07ab8'); } break; }
      case 'ridebreak': { const x = this.px0 - cx - 300 + k * 3, r = 70; ctx.save(); ctx.globalAlpha = .75; ctx.translate(x, gy - r - 10); ctx.rotate(k * .05); ctx.strokeStyle = '#6a2a4a'; ctx.lineWidth = 4; ctx.beginPath(); ctx.arc(0, 0, r, 0, 7); ctx.stroke(); for (let a = 0; a < 6.283; a += .785) { ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(Math.cos(a) * r, Math.sin(a) * r); ctx.stroke(); O.r(Math.cos(a) * r - 6, Math.sin(a) * r - 5, 12, 10, hsl(a * 60, 80, 55), 1); } ctx.restore(); break; }
      case 'swallow': { const x = this.ax - cx + 80, k2 = Math.min(k, 200), bh = Math.max(0, 140 - Math.max(0, k2 - 80) * 1.4); ctx.save(); ctx.globalAlpha = .8; if (bh > 0) { O.r(x - 30, gy - bh, 60, bh, '#6a7a8a'); for (let i = 0; i < bh / 16; i++) P.r(ctx, x - 22, gy - bh + 6 + i * 16, 44, 6, '#ffe9a0'); } const mh = Math.min(1, k2 / 60); O.poly([[x - 110, gy], [x - 80, gy - 150 * mh], [x - 10, gy - 190 * mh], [x + 70, gy - 160 * mh], [x + 120, gy]], '#5a4a3a'); P.e(ctx, x - 20, gy - 130 * mh, 12, 9, '#ffd23a'); P.e(ctx, x + 30, gy - 130 * mh, 12, 9, '#ffd23a'); const jaw = k2 > 60 && k2 < 160 ? 40 : 8; O.r(x - 40, gy - 100 * mh, 90, jaw, '#200'); ctx.restore(); break; }
      case 'moonface': { const x = VW * .7, y = 60, m = Math.min(1, k / 40); P.e(ctx, x, y - cy * 0, 40, 40, '#fff8d0'); P.e(ctx, x - 14, y - 10, 6, 8 * m, '#000'); P.e(ctx, x + 14, y - 10, 6, 8 * m, '#000'); P.e(ctx, x, y + 14, 14 * m, 16 * m, '#300'); if (k % 16 < 8 && k < 200) FX.ring(x + cx, y + cy + 14, 80, '#fff8d0', 10, 2); break; }
      case 'portalstorm': { for (let i = 0; i < 6; i++) { const x = (i * 97 + k * 2) % VW, y = 40 + (i * 53) % 120; ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.strokeStyle = hsl((i * 60 + k * 5) % 360, 90, 60, .7); ctx.lineWidth = 3; ctx.beginPath(); ctx.ellipse(x, y, 14 + Math.sin(k * .1 + i) * 4, 24, 0, 0, 7); ctx.stroke(); ctx.restore(); if (k % 30 === i * 5 && k < 240) Game.add(new Note(x + cx, y + cy, true)); } break; }
      case 'strings': { const x = this.ax - cx - 40, d = Math.min(1, k / 60) * (k < 200 ? 1 : Math.max(0, 1 - (k - 200) / 60)); ctx.strokeStyle = '#eee'; for (let i = 0; i < 4; i++) { ctx.beginPath(); ctx.moveTo(x - 30 + i * 20, -10); ctx.lineTo(x - 30 + i * 20, 40 + d * 120); ctx.stroke(); } O.r(x - 40, d * 120 + 20, 80, 50, '#e8c290', 3); for (let i = 0; i < 4; i++) O.r(x - 38 + i * 20, d * 120 + 66, 14, 26, '#e8c290', 2); break; }
    }
  }
  drawFG(cx, cy) {
    if (!this.on || this.finished) return; const k = this.k;
    if (this.kind === 'bikejump') { const t = clamp(k / 60, 0, 1), x = this.px0 - cx - 140 + t * 300, y = this.ay - cy - Math.sin(t * Math.PI) * 150; drawBiker(x, y, { face: 1, t: k / 60, speed: 2, wheelie: .4 - t * .6, turbo: true }); if (k % 2 === 0) FX.smoke(x + cx - 50, y + cy - 10, -2); }
  }
}
class FallingRig extends Ent { // stage lights falling: telegraphed by a shadow
  constructor(x, y) { super(x - 20, y, 40, 16); this.vy = 0; this.wait = 45; }
  update(L) { this.t++; if (this.wait > 0) { this.wait--; return; } this.vy = Math.min(this.vy + .5, 9); this.y += this.vy; const gy = Game.groundY(L, Math.floor(this.cx / TS)); if (this.y + this.h >= gy) { this.dead = true; Cam.shake(5, 10); AudioSys.play_sfx('break'); FX.burst(this.cx, gy - 6, 20, ['#ffe9a0', '#888', '#fff'], { speed: 4 }); } if (overlap(this, Game.player)) { Game.player.hurt(1, this.cx); this.dead = true; } }
  draw(cx, cy) { const gy = Game.groundY(Game.L, Math.floor(this.cx / TS)) - cy, x = this.cx - cx; ctx.fillStyle = `rgba(0,0,0,${this.wait > 0 ? .25 + Math.sin(this.t * .5) * .1 : .35})`; ctx.beginPath(); ctx.ellipse(x, gy, 22, 5, 0, 0, 7); ctx.fill(); if (this.wait > 0) { text('!', x, gy - 30, { color: '#ff3a3a', align: 'center', outline: true, scale: 2 }); return; } const y = this.y - cy; O.r(x - 20, y, 40, 12, '#333'); for (let i = 0; i < 3; i++) P.e(ctx, x - 12 + i * 12, y + 12, 5, 4, '#ffe9a0'); }
}
// giant chaser for escape sequences (Shitman rolls in behind you)
class GiantChaser extends Ent {
  constructor(o) { super(o.x, o.y, 120, 120); this.ground = o.y; }
  update(L) { this.t++; this.x = Cam.x - 70 + Math.sin(this.t * .05) * 8; const p = Game.player; if (p.x < this.x + 110) p.hurt(1, this.x); if (this.t % 30 === 0) { Cam.shake(3, 8); AudioSys.play_sfx('gloop'); } this.ground = Game.groundY(L, Math.floor((Cam.x + 60) / TS)); }
  draw(cx, cy) { drawSludge(this.x - cx + 40, this.ground - cy + 8, { scale: .75, t: this.t / 60, wobble: 2.5, face: 1 }); }
}
