// ============================================================================
// Bosses — multi-phase battles with telegraphed, animated attacks
// ============================================================================
const O = { // outlined primitives for big hand-drawn bosses
  e(x, y, rx, ry, col, ol = 2) { P.e(ctx, x, y, rx + ol, ry + ol, '#0a060e'); P.e(ctx, x, y, rx, ry, col); },
  r(x, y, w, h, col, ol = 2) { P.r(ctx, x - ol, y - ol, w + ol * 2, h + ol * 2, '#0a060e'); P.r(ctx, x, y, w, h, col); },
  poly(pts, col, ol = 2) { ctx.lineJoin = 'round'; ctx.strokeStyle = '#0a060e'; ctx.lineWidth = ol * 2; ctx.beginPath(); pts.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])); ctx.closePath(); ctx.stroke(); ctx.fillStyle = col; ctx.fill(); },
  line(x0, y0, x1, y1, col, w = 3) { ctx.lineCap = 'round'; ctx.strokeStyle = '#0a060e'; ctx.lineWidth = w + 3; ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke(); ctx.strokeStyle = col; ctx.lineWidth = w; ctx.stroke(); ctx.lineCap = 'butt'; }
};
class Boss extends Ent {
  constructor(x, y, w, h, o) { super(x, y, w, h); this.isBoss = true; this.o = o || {}; this.phase = 1; this.state = 'intro'; this.st = 0; this.flash = 0; this.inv = 0; this.dir = -1; this.phases = [1, .66, .33]; this.defeated = false; this.vulnerable = true; }
  setHp(n) { this.maxHp = this.hp = Math.round(n * ({ easy: .7, normal: 1, hard: 1.3 }[Save.data.opt.diff] || 1)); }
  hitbox() { return this; }
  go(s) { this.state = s; this.st = 0; }
  hit(dmg, a) {
    if (this.defeated || this.inv > 0 || !this.vulnerable || dmg <= 0) { if (dmg > 0 && !this.vulnerable && this.inv <= 0) { FX.pop(this.cx, this.y, 'BLOCKED', '#aaa'); this.inv = 10; } return false; }
    this.hp -= dmg; this.flash = 8; this.inv = 12; AudioSys.play_sfx('enemyHit'); FX.burst(a && a.x !== undefined ? a.x : this.cx, this.cy, 8, '#fff'); G.hitstop = 3;
    if (AudioSys.onBeatWindow(.18)) Game.player.metal = Math.min(100, Game.player.metal + 4);
    const f = this.hp / this.maxHp;
    if (this.phase < this.phases.length && f <= this.phases[this.phase]) { this.phase++; this.onPhase(this.phase); AudioSys.setIntensity(3); AudioSys.setBossPhase(this.phase); HUD.banner('PHASE ' + this.phase, '#ff5bd1'); Cam.shake(6, 20); AudioSys.play_sfx('stinger'); }
    if (this.hp <= 0) this.defeat();
    return true;
  }
  onPhase(p) { }
  defeat() { this.defeated = true; this.hp = 0; this.go('dying'); AudioSys.play_sfx('bossDie'); Cam.shake(8, 60); Game.bossDefeated(this); }
  contactDmg() { const p = Game.player; if (!this.defeated && this.state !== 'intro' && this.state !== 'stunned' && overlap(this.hitbox(), p)) { if (p.dashT > 0 && p.form === 'mega') this.hit(2, {}); else p.hurt(1, this.cx); } }
  commonUpdate() { this.t++; this.st++; if (this.flash > 0) this.flash--; if (this.inv > 0) this.inv--; if (this.state === 'dying') { if (this.st % 6 === 0) FX.burst(this.cx + R(-this.w / 2, this.w / 2), this.cy + R(-this.h / 2, this.h / 2), 14, ['#fff', '#ffe14d', '#ff5bd1'], { speed: 4 }); if (this.st > 120) this.dead = true; return false; } return true; }
}
// ---------------------------------------------------------------------------- BIG BAD BARNABY (werewolf)
class WolfBoss extends Boss {
  constructor(x, y, o) {
    super(x, y - 100, 64, 100, o); this.name = 'BIG BAD BARNABY'; this.ver = o.ver || 1; this.setHp([0, 30, 36, 44][this.ver]); this.face = -1; this.arm = 0; this.armV = 0; this.bike = null;
    this.phases = this.ver === 1 ? [1, .66, .33] : this.ver === 2 ? [1, .5] : [1, .66, .33]; this.ground = y; this.claw = 0; this.sxx = 1; this.syy = 1; this.rot = 0; this.enraged = false;
  }
  hitbox() { return { x: this.x + 8, y: this.y + 20, w: this.w - 16, h: this.h - 20 }; }
  onPhase(p) { if (p === this.phases.length) { this.enraged = true; this.go('howl'); } }
  update(L) {
    if (!this.commonUpdate()) return; const p = Game.player, dx = p.cx - this.cx, spd = this.enraged ? 1.5 : 1;
    this.arm = lerp(this.arm, this.armT || 0, .25); this.claw = Math.max(0, this.claw - .05); this.sxx = lerp(this.sxx, 1, .15); this.syy = lerp(this.syy, 1, .15); this.rot = lerp(this.rot, 0, .1);
    const onG = this.y + this.h >= this.ground - 1;
    if (this.state !== 'bike' && this.state !== 'leap') { this.vy += .4; this.y = Math.min(this.y + this.vy, this.ground - this.h); if (this.y + this.h >= this.ground) this.vy = 0; }
    switch (this.state) {
      case 'intro': if (this.st > 60) this.go('think'); break;
      case 'think': this.armT = 0; this.face = sign(dx) || -1; this.x += this.face * .6 * spd;
        if (this.st > 70 / spd) { const r = R(), far = Math.abs(dx) > 150, third = this.ver === 2 ? 'treeLeap' : 'huff'; this.go(far ? (r < .5 ? third : 'leap0') : r < .6 ? 'claw' : 'leap0'); }
        break;
      case 'claw': this.armT = -.6; this.face = sign(dx) || this.face; if (this.st === 18) { this.armT = 2.2; this.claw = 1; AudioSys.play_sfx('whip'); AudioSys.play_sfx('growl'); this.vx = this.face * 4; }
        if (this.st > 18 && this.st < 30) { this.x += this.face * 3; Game.bossAttack({ x: this.face > 0 ? this.x + this.w - 10 : this.x - 40, y: this.y + 20, w: 50, h: 70 }); }
        if (this.st > 44) { if (this.enraged && !this.combo) { this.combo = 1; this.go('claw'); } else { this.combo = 0; this.go('think'); } }
        break;
      case 'leap0': this.syy = .8; this.sxx = 1.15; if (this.st > 20) { this.vy = -9; this.vx = clamp(dx / 40, -5, 5); this.go('leap'); AudioSys.play_sfx('growl'); } break;
      case 'leap': this.vy += .4; this.x += this.vx; this.y += this.vy; this.rot = this.vx * .03; this.armT = -.4;
        if (this.y + this.h >= this.ground && this.vy > 0) { this.y = this.ground - this.h; this.vy = 0; this.syy = .7; this.sxx = 1.3; Cam.shake(6, 14); AudioSys.play_sfx('bash'); FX.dust(this.cx, this.ground, 12); FX.ring(this.cx, this.ground, 80, '#c8b8a8', 18, 3);
          Game.bossAttack({ x: this.cx - 70, y: this.ground - 16, w: 140, h: 16 }); Game.add(new EnemyShot(this.cx, this.ground - 8, -3, 0, 'wave')); Game.add(new EnemyShot(this.cx, this.ground - 8, 3, 0, 'wave')); this.go('think'); }
        break;
      case 'huff': this.sxx = 1 + Math.min(this.st, 50) / 200; this.face = sign(dx) || this.face;
        if (this.st === 50) { AudioSys.play_sfx('dash'); AudioSys.play_sfx('growl'); }
        if (this.st > 50 && this.st < 150) { Game.L.wind = this.face * (this.enraged ? .32 : .24); if (this.st % 3 === 0) FX.add({ x: this.cx + this.face * 30, y: this.y + 40 + R(-20, 30), vx: this.face * R(4, 7), vy: R(-.5, .5), col: '#fff8', size: 2, life: 40, grav: 0 });
          if (this.st % 22 === 0) Game.add(new EnemyShot(this.cx + this.face * 30, this.y + 30 + R(40), this.face * 4, R(-1, 1), this.ver === 1 ? pick(['brick', 'glob']) : 'spore')); }
        if (this.st >= 150) { Game.L.wind = 0; this.go('think'); }
        break;
      case 'howl': this.rot = -.35; this.armT = -.5; if (this.st === 10) { AudioSys.play_sfx('howl'); Cam.shake(5, 50); } if (this.st % 12 === 0 && this.st < 60) FX.ring(this.cx, this.y + 20, 140, '#fff', 20, 3);
        if (this.st > 70) this.go('think'); break;
      case 'callBike': // Barnaby whistles; Razz's motorcycle roars in and the werewolf rides it
        this.vulnerable = false; if (this.st === 1) { AudioSys.play_sfx('rev'); HUD.banner('RAZZ ROLLS IN!', '#5bd4ff'); }
        if (this.st > 50) { this.bike = { x: Game.L.camLock ? Game.L.camLock.x0 - 120 : Cam.x - 120, dir: 1, passes: 0, spd: 0 }; this.go('bike'); } break;
      case 'bike': { const b = this.bike, a = Game.L.camLock || { x0: Cam.x, x1: Cam.x + W };
        AudioSys.setEngine(true, .7); b.spd = approach(b.spd, 5.5 * (this.enraged ? 1.2 : 1), .15); b.x += b.dir * b.spd; this.x = b.x - this.w / 2; this.y = this.ground - this.h - 26; this.face = b.dir;
        if (this.t % 3 === 0) FX.smoke(b.x - b.dir * 60, this.ground - 14, -b.dir);
        Game.bossAttack({ x: b.x - 55, y: this.ground - 44, w: 110, h: 44 });
        if ((b.dir > 0 && b.x > a.x1 + 100) || (b.dir < 0 && b.x < a.x0 - 100)) { b.dir *= -1; b.passes++; b.spd = 0; AudioSys.play_sfx('rev'); if (this.t % 2 === 0) for (let i = 0; i < 3; i++) Game.add(new EnemyShot(a.x0 + R(W), Cam.y - 10, 0, 2.5, 'brick')); }
        if (b.passes >= 3 && Math.abs(b.x - (a.x0 + a.x1) / 2) < 30) { this.go('crash'); AudioSys.setEngine(false); AudioSys.play_sfx('explode'); Cam.shake(10, 30); FX.burst(b.x, this.ground - 20, 40, ['#ccc', '#ff3a1a', '#fff36b'], { speed: 5 }); this.crashX = b.x; }
        break; }
      case 'crash': this.vulnerable = true; this.y = this.ground - this.h; this.rot = .5 * this.face; if (this.st > 220) { this.bike = null; this.go('think'); } break;
      case 'treeLeap': // version 2: springs between trees, drops from above
        if (this.st === 1) { this.vy = -12; AudioSys.play_sfx('growl'); } this.y += this.vy; this.vy += .25;
        if (this.st > 30 && this.st < 70) { this.y = Cam.y - 160; this.x = lerp(this.x, p.cx - this.w / 2, .1); }
        if (this.st === 70) { this.vy = 8; } if (this.st > 70 && this.y + this.h >= this.ground) { this.y = this.ground - this.h; this.syy = .7; Cam.shake(6, 12); FX.ring(this.cx, this.ground, 90, '#c8b8a8', 18, 3); Game.bossAttack({ x: this.cx - 50, y: this.ground - 30, w: 100, h: 30 }); this.go('think'); }
        break;
      case 'dying': break;
    }
    if (this.state !== 'bike') { const a = Game.L.camLock; if (a) this.x = clamp(this.x, a.x0 + 10, a.x1 - this.w - 10); }
    if (this.state !== 'bike' && this.state !== 'crash') this.contactDmg();
  }
  draw(cx, cy) {
    const x = this.cx - cx, y = this.y + this.h - cy, flash = this.flash > 0 ? '#fff' : this.enraged && this.t % 20 < 3 ? '#ff3a3a' : false;
    if (this.state === 'bike' || (this.state === 'crash' && this.st < 40)) {
      const bx = (this.state === 'bike' ? this.bike.x : this.crashX) - cx; const gy = this.ground - cy;
      drawBiker(bx, gy, { face: this.face, t: this.t / 60, speed: this.state === 'bike' ? 1.5 : 0, wheelie: this.state === 'bike' && this.bike.spd < 3 ? .3 : 0, turbo: this.state === 'bike' && this.bike.spd > 5, tilt: this.state === 'crash' ? this.st * .05 : 0 });
      drawWolf(bx - this.face * 14, gy - 40, { face: this.face, t: this.t / 60, scale: .6, arm: -.4, flash, rot: this.state === 'crash' ? this.st * .1 : 0 });
      return;
    }
    if (this.state === 'crash') { drawBiker(this.crashX - cx + 60, this.ground - cy, { face: -this.face, t: 0, speed: 0, tilt: 1.4 }); }
    drawWolf(x, y, { face: this.face, t: this.t / 60, arm: this.arm, claw: this.claw, sx: this.sxx, sy: this.syy, rot: this.rot * this.face, flash, eyes: this.enraged, scale: this.ver === 3 ? .78 : .72 });
    if (this.state === 'crash') for (let i = 0; i < 3; i++) { const a = this.t * .12 + i * 2.1; ctx.drawImage(ICON.star, x + Math.cos(a) * 18 - 7, y - this.h - 10 + Math.sin(a) * 4); }
    if (this.state === 'huff' && this.st < 50) text('HUFF...', x, y - this.h - 20, { color: '#fff', align: 'center', outline: true });
    if (this.state === 'huff' && this.st >= 50 && this.st < 70) text('PUFF!!', x, y - this.h - 20, { color: '#ff3a3a', align: 'center', outline: true, scale: 2 });
  }
}
// ---------------------------------------------------------------------------- CAPTAIN UDDERLY (hypnotized)
class CowBoss extends Boss {
  constructor(x, y, o) { super(x, y - 90, 80, 70, o); this.name = 'CAPTAIN UDDERLY (HYPNOTIZED)'; this.setHp(30); this.ground = y; this.face = -1; this.rot = 0; this.cape = 3; this.capeStretch = 0; this.sxx = 1; this.syy = 1; this.hx = x; }
  hitbox() { return { x: this.x + 10, y: this.y + 8, w: this.w - 20, h: this.h - 10 }; }
  update(L) {
    if (!this.commonUpdate()) return; const p = Game.player, a = L.camLock || { x0: Cam.x, x1: Cam.x + W }, mid = (a.x0 + a.x1) / 2, spd = 1 + (this.phase - 1) * .25;
    this.rot = lerp(this.rot, 0, .08); this.cape = lerp(this.cape, 3, .05); this.capeStretch = lerp(this.capeStretch, 0, .1); this.sxx = lerp(this.sxx, 1, .15); this.syy = lerp(this.syy, 1, .15);
    switch (this.state) {
      case 'intro': this.y = this.ground - 160 + Math.sin(this.t * .05) * 8; if (this.st > 60) this.go('hover'); break;
      case 'hover': this.face = sign(p.cx - this.cx) || -1; this.x = lerp(this.x, p.cx - this.w / 2 - this.face * 120, .02); this.y = lerp(this.y, this.ground - 170 + Math.sin(this.t * .06) * 14, .05);
        if (this.st > 80 / spd) this.go(pick(this.phase === 1 ? ['swoop', 'charge'] : ['swoop', 'stomp', 'charge'])); break;
      case 'swoop': { if (this.st === 1) { this.sx0 = this.x; this.tx = p.cx; AudioSys.play_sfx('flap'); AudioSys.play_sfx('moo'); }
        const k = this.st / (70 / spd); this.x = lerp(this.sx0, this.tx - this.w / 2 + this.face * 220, k); this.y = this.ground - 170 + Math.sin(k * Math.PI) * 130; this.rot = .3 * this.face * Math.cos(k * Math.PI); this.cape = 7; this.capeStretch = 6;
        if (this.st % 4 === 0) FX.add({ x: this.cx - this.face * 30, y: this.cy, vx: -this.face, vy: 0, col: '#ff3a3a', size: 2, life: 20, grav: 0 });
        Game.bossAttack(this.hitbox()); if (k >= 1) this.go('hover'); break; }
      case 'charge': if (this.st < 30) { this.y = lerp(this.y, this.ground - this.h, .2); this.syy = .9; this.face = sign(p.cx - this.cx) || -1; } else { if (this.st === 30) AudioSys.play_sfx('moo'); this.x += this.face * 6.5 * spd; this.cape = 8; this.capeStretch = 10; this.rot = .1 * this.face; if (this.st % 2 === 0) FX.dust(this.cx - this.face * 30, this.ground, 1); Game.bossAttack(this.hitbox()); if (this.x < a.x0 - 20 || this.x + this.w > a.x1 + 20) { this.x = clamp(this.x, a.x0 - 20, a.x1 - this.w + 20); Cam.shake(6, 12); AudioSys.play_sfx('bash'); this.go('dizzy'); } } break;
      case 'dizzy': this.y = this.ground - this.h; if (this.st > 90 - this.phase * 15) this.go('hover'); break;
      case 'stomp': if (this.st < 50) { this.x = lerp(this.x, p.cx - this.w / 2, .08); this.y = lerp(this.y, this.ground - 230, .1); } else if (this.st === 50) { this.vy = 2; } else { this.vy += .8; this.y += this.vy; this.syy = 1.2; this.sxx = .85; if (this.y + this.h >= this.ground) { this.y = this.ground - this.h; this.syy = .65; this.sxx = 1.35; Cam.shake(8, 16); AudioSys.play_sfx('bash'); AudioSys.play_sfx('rumble'); FX.ring(this.cx, this.ground, 120, '#fff', 20, 4); FX.dust(this.cx, this.ground, 16); Game.bossAttack({ x: this.cx - 90, y: this.ground - 16, w: 180, h: 16 }); Game.add(new EnemyShot(this.cx, this.ground - 8, -3.2, 0, 'wave')); Game.add(new EnemyShot(this.cx, this.ground - 8, 3.2, 0, 'wave')); this.go('dizzy'); } } break;
      case 'cape': this.cape = 14; this.rot = Math.sin(this.st * .4) * .2; if (this.st % 10 === 0) { AudioSys.play_sfx('flap'); Game.add(new EnemyShot(this.cx, this.cy, R(-4, 4), R(-3, -1), 'spore')); } Game.L.wind = this.face * -.15; if (this.st > 80) { Game.L.wind = 0; this.go('hover'); } break;
      case 'dying': this.y = Math.min(this.y + 1, this.ground - this.h); break;
    }
    if (this.state !== 'swoop' && this.state !== 'charge' && this.state !== 'dying' && this.state !== 'intro') this.contactDmg();
  }
  draw(cx, cy) { const x = this.cx - cx, y = this.y + this.h - cy + 10; drawCow(x, y, { face: this.face, t: this.t / 60, scale: .62 * this.sxx, sy: this.syy / this.sxx, rot: this.rot, cape: this.cape, capeStretch: this.capeStretch, hypno: !this.defeated, flash: this.flash > 0 ? '#fff' : false });
    if (this.state === 'dizzy') for (let i = 0; i < 3; i++) { const a = this.t * .12 + i * 2.1; ctx.drawImage(ICON.star, x + Math.cos(a) * 20 - 7, y - 90 + Math.sin(a) * 4); } }
}
// ---------------------------------------------------------------------------- BOVINE OVERLORD (mech cow)
class OverlordBoss extends Boss {
  constructor(x, y, o) { super(x - 60, y - 170, 150, 170, o); this.name = 'THE BOVINE OVERLORD'; this.setHp(42); this.ground = y; this.legT = 0; this.laser = 0; this.mouthOpen = 0; this.assistT = 200; }
  hitbox() { return this.phase < 3 ? { x: this.x + 90, y: this.y + 10, w: 60, h: 60 } : { x: this.x + 40, y: this.y + 90, w: 50, h: 40 }; }
  onPhase(p) { if (p === 3) { HUD.banner('UDDER REACTOR EXPOSED!', '#ff5bd1'); FX.burst(this.x + 65, this.y + 110, 40, ['#fff', '#ccc', '#ff3a1a'], { speed: 5 }); } }
  update(L) {
    if (!this.commonUpdate()) return; const p = Game.player, spd = 1 + (this.phase - 1) * .3; this.legT += .05 * spd; this.mouthOpen = Math.max(0, this.mouthOpen - .05);
    // Captain Udderly assists: dives in and stuns the mech periodically
    if (--this.assistT <= 0 && Game.ally) { this.assistT = 420; Game.ally.dive(this.cx, this.y + 40); }
    switch (this.state) {
      case 'intro': if (this.st > 80) this.go('walk'); break;
      case 'walk': this.x += Math.sin(this.legT * .5) * 1.2; if (this.st > 90 / spd) this.go(pick(this.phase === 1 ? ['cannon', 'stomp'] : ['cannon', 'laser', 'stomp'])); break;
      case 'cannon': this.mouthOpen = 1; if (this.st % 16 === 0 && this.st < 80) { const a = Math.atan2(p.cy - (this.y + 50), p.cx - (this.x + 120)); Game.add(new EnemyShot(this.x + 130, this.y + 50, Math.cos(a) * 3.5, Math.sin(a) * 3.5 - 2, 'glob')); AudioSys.play_sfx('spit'); } if (this.st > 100) this.go('walk'); break;
      case 'laser': if (this.st < 40) { this.laser = this.st / 40 * .3; } else if (this.st < 120) { this.laser = 1; this.lAng = lerp(.2, 1.1, (this.st - 40) / 80); AudioSys.play_sfx(this.st % 8 === 0 ? 'laser' : ''); const ex = this.x + 130, ey = this.y + 35; for (let d = 30; d < 500; d += 16) Game.bossAttack({ x: ex + Math.cos(Math.PI - this.lAng) * d - 6, y: ey + Math.sin(this.lAng) * d - 6, w: 12, h: 12 }); } else { this.laser = 0; this.go('walk'); } break;
      case 'stomp': if (this.st === 30 || this.st === 70) { Cam.shake(7, 14); AudioSys.play_sfx('rumble'); FX.ring(this.x + 40, this.ground, 140, '#fff', 20, 4); Game.bossAttack({ x: this.x - 100, y: this.ground - 14, w: 300, h: 14 }); for (let i = 0; i < 2; i++) Game.add(new EnemyShot(Cam.x + R(W), Cam.y - 10, 0, 2.2, 'glob')); } if (this.st > 100) this.go('walk'); break;
      case 'summon': if (this.st === 20) { for (let i = 0; i < 2; i++) { const e = new Enemy({ kind: 'cultcow', x: this.x - 40 - i * 40, y: this.ground - 40 }); e.wake = true; Game.add(e); } AudioSys.play_sfx('moo'); } if (this.st > 60) this.go('walk'); break;
      case 'stunned': if (this.st > 160) this.go('walk'); break;
    }
    const a = L.camLock; if (a) this.x = clamp(this.x, a.x0 + W * .45, a.x1 - this.w - 10);
    this.contactDmg();
  }
  contactDmg() { const p = Game.player, body = { x: this.x + 10, y: this.y + 60, w: 130, h: 110 }; if (!this.defeated && this.state !== 'intro' && overlap(body, p)) p.hurt(1, this.cx); }
  draw(cx, cy) {
    const x = Math.round(this.x - cx), y = Math.round(this.y - cy), fl = this.flash > 0, t = this.legT;
    const metal = fl ? '#fff' : '#8a8a95', dark = fl ? '#fff' : '#4a4a55', spots = fl ? '#fff' : '#1a1a22';
    for (let i = 0; i < 4; i++) { const lx = x + 20 + i * 32, lift = Math.max(0, Math.sin(t * 2 + i * 1.6)) * 8; O.r(lx, y + 120 - lift, 14, 50 + lift - 8, dark); O.r(lx - 3, y + 160, 20, 10, '#222'); P.r(ctx, lx + 3, y + 126 - lift, 8, 4, '#ffcc33'); }
    O.r(x, y + 50, 140, 80, metal, 3); for (const [sx, sy, r] of [[25, 70, 14], [80, 95, 18], [110, 65, 10]]) P.e(ctx, x + sx, y + sy, r, r * .7, spots);
    for (let i = 0; i < 6; i++) P.e(ctx, x + 10 + i * 24, y + 56, 2, 2, '#ccc');
    // udder reactor
    const pulse = Math.sin(this.t * .2) * .5 + .5; O.e(x + 65, y + 132, 26, 14, this.phase >= 3 ? `rgb(255,${90 + pulse * 120},${200})` : '#c8a0b0'); for (let i = -1; i <= 1; i++) O.r(x + 60 + i * 14, y + 140, 6, 10, '#c8a0b0', 1);
    if (this.phase >= 3) { ctx.save(); ctx.globalCompositeOperation = 'lighter'; P.e(ctx, x + 65, y + 132, 34 + pulse * 6, 20, 'rgba(255,90,209,.35)'); ctx.restore(); }
    // head
    const hy = y + 10 + Math.sin(this.t * .05) * 3; O.r(x + 100, hy, 56, 56, metal, 3); O.poly([[x + 104, hy], [x + 88, hy - 26], [x + 112, hy - 4]], '#efe2c4'); O.poly([[x + 150, hy], [x + 168, hy - 26], [x + 146, hy - 4]], '#efe2c4');
    O.r(x + 108, hy + 34, 46, 22, '#f5a0b0'); P.e(ctx, x + 120, hy + 44, 4, 3, '#5a1a2a'); P.e(ctx, x + 142, hy + 44, 4, 3, '#5a1a2a');
    const eyeC = this.laser > 0 ? '#ff2a2a' : '#ffcc33'; P.e(ctx, x + 116, hy + 18, 7, 6, '#000'); P.e(ctx, x + 116, hy + 18, 5, 4, eyeC); P.e(ctx, x + 142, hy + 18, 7, 6, '#000'); P.e(ctx, x + 142, hy + 18, 5, 4, eyeC);
    if (this.mouthOpen > 0) P.r(ctx, x + 112, hy + 52, 38, 6 * this.mouthOpen, '#300');
    P.r(ctx, x + 104, hy + 4, 48, 3, '#c22'); text('MOO-9000', x + 128, hy - 10, { color: '#ffcc33', align: 'center', shadow: '#000' });
    if (this.laser >= 1) { const ex = x + 130, ey = y + 35; ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.strokeStyle = '#ff2a2a'; ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(ex, ey); ctx.lineTo(ex + Math.cos(Math.PI - this.lAng) * 520, ey + Math.sin(this.lAng) * 520); ctx.stroke(); ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.stroke(); ctx.restore(); }
    else if (this.laser > 0) { ctx.strokeStyle = 'rgba(255,40,40,.5)'; ctx.setLineDash([4, 4]); ctx.beginPath(); ctx.moveTo(x + 130, y + 35); ctx.lineTo(x + 130 - 400, y + 35 + 80); ctx.stroke(); ctx.setLineDash([]); }
    if (this.state === 'stunned') for (let i = 0; i < 3; i++) { const a = this.t * .12 + i * 2.1; ctx.drawImage(ICON.star, x + 128 + Math.cos(a) * 24 - 7, y - 10 + Math.sin(a) * 5); }
    for (let i = 0; i < 3; i++) if (this.t % 30 > 15) FX.smoke(this.x + 20 + i * 50, this.y + 50, 0);
  }
}
// ---------------------------------------------------------------------------- PUPPET KING
class PuppetKing extends Boss {
  constructor(x, y, o) { super(x - 70, y - 300, 140, 120, o); this.name = 'THE PUPPET KING'; this.setHp(36); this.ground = y; this.hands = [{ x: -90, y: 0, hp: 6, vy: 0, st: 'hover', t: 0 }, { x: 90, y: 0, hp: 6, vy: 0, st: 'hover', t: 60 }]; this.headY = y - 300; this.cx0 = x; }
  hitbox() { return this.phase >= 2 ? { x: this.cx0 - 50, y: this.headY + 20, w: 100, h: 104 } : { x: -999, y: -999, w: 0, h: 0 }; }
  handBox(h) { return { x: this.cx0 + h.x - 24, y: this.ground - 48 - h.y, w: 48, h: 48 }; }
  update(L) {
    if (!this.commonUpdate()) return; const p = Game.player;
    this.vulnerable = this.phase >= 2 || this.hands.every(h => h.hp <= 0);
    if (this.phase === 1 && this.hands.every(h => h.hp <= 0)) { this.phase = 2; this.onPhaseVis(); }
    this.headY = lerp(this.headY, this.phase >= 2 ? this.ground - 124 + Math.sin(this.t * .03) * 8 : this.ground - 290, .02);
    for (const h of this.hands) {
      if (h.hp <= 0 && this.phase < 3) { h.y = lerp(h.y, -40, .05); continue; }
      h.t++;
      if (h.st === 'hover') { h.y = lerp(h.y, 140 + Math.sin(h.t * .05) * 10, .05); h.x = lerp(h.x, p.cx - this.cx0 + (h === this.hands[0] ? -30 : 30), .02); if (h.t % (this.phase >= 3 ? 70 : 110) === 0) h.st = 'slam'; }
      else if (h.st === 'slam') { h.vy += .7; h.y -= h.vy; if (h.y <= 0) { h.y = 0; h.vy = 0; h.st = 'down'; h.dt = 0; Cam.shake(5, 10); AudioSys.play_sfx('bash'); FX.dust(this.cx0 + h.x, this.ground, 8); Game.bossAttack({ x: this.cx0 + h.x - 30, y: this.ground - 24, w: 60, h: 24 }); } else Game.bossAttack(this.handBox(h)); }
      else if (h.st === 'down') { if (++h.dt > 90) h.st = 'hover'; }
      // hands can be hit while resting on the floor
      for (const a of p.attacks) if (h.st === 'down' && h.hp > 0 && overlap(a, this.handBox(h)) && !h.inv) { h.hp -= a.dmg || 1; h.inv = 12; AudioSys.play_sfx('enemyHit'); FX.burst(this.cx0 + h.x, this.ground - 40, 8, '#e8c290'); if (h.hp <= 0) { AudioSys.play_sfx('break'); FX.debris(this.cx0 + h.x, this.ground - 40, 'stick', 12); HUD.toast('STRING SNAPPED!', '#ffcc33'); } }
      if (h.inv) h.inv--;
    }
    if (this.phase >= 2 && this.t % (this.phase >= 3 ? 90 : 140) === 0) { const e = new Enemy({ kind: 'soldier', x: this.cx0 - 10, y: this.headY + 100 }); e.y = this.headY + 90; e.wake = true; Game.add(e); AudioSys.play_sfx('pop'); }
    if (this.phase >= 2 && this.t % 60 === 0) Game.add(new EnemyShot(this.cx0, this.headY + 90, (p.cx - this.cx0) / 60, -2, 'knife'));
    this.x = this.cx0 - 70; this.y = this.headY;
  }
  onPhase(p) { if (p === 3) { for (const h of this.hands) { h.hp = 4; h.st = 'hover'; } HUD.toast('HE GOT NEW STRINGS!', '#ff3a3a'); } }
  onPhaseVis() { HUD.banner('THE KING DESCENDS!', '#ffcc33'); AudioSys.setIntensity(3); AudioSys.play_sfx('stinger'); }
  draw(cx, cy) {
    const x = this.cx0 - cx, hy = this.headY - cy, fl = this.flash > 0;
    // strings from the rafters
    ctx.strokeStyle = '#eee'; ctx.lineWidth = 1; for (const s of [-40, 0, 40]) { ctx.beginPath(); ctx.moveTo(x + s, -cy); ctx.lineTo(x + s * .6, hy + 10); ctx.stroke(); }
    for (const h of this.hands) { if (h.hp <= 0 && this.phase < 3) continue; ctx.beginPath(); ctx.moveTo(x + h.x, -cy); ctx.lineTo(x + h.x, this.ground - 80 - h.y - cy); ctx.stroke(); }
    // crown + wooden head
    O.e(x, hy + 60, 60, 52, fl ? '#fff' : '#d8a870', 3); O.poly([[x - 50, hy + 16], [x - 40, hy - 24], [x - 20, hy + 4], [x, hy - 34], [x + 20, hy + 4], [x + 40, hy - 24], [x + 50, hy + 16]], '#ffcc33', 3);
    for (const gx of [-30, 0, 30]) P.e(ctx, x + gx, hy + 4, 4, 4, '#e01a2a');
    P.e(ctx, x - 22, hy + 48, 11, 13, '#fff'); P.e(ctx, x + 22, hy + 48, 11, 13, '#fff'); const lk = clamp((Game.player.cx - this.cx0) / 80, -4, 4); P.e(ctx, x - 22 + lk, hy + 50, 5, 6, '#000'); P.e(ctx, x + 22 + lk, hy + 50, 5, 6, '#000');
    P.l(ctx, x - 36, hy + 30, x - 10, hy + 38, '#000', 3); P.l(ctx, x + 36, hy + 30, x + 10, hy + 38, '#000', 3);
    P.e(ctx, x - 44, hy + 74, 8, 5, '#ff7b7b'); P.e(ctx, x + 44, hy + 74, 8, 5, '#ff7b7b');
    const jaw = this.phase >= 2 ? 6 + Math.abs(Math.sin(this.t * .1)) * 10 : 4; O.r(x - 30, hy + 82, 60, jaw, '#300', 2); P.teeth(ctx, x - 28, hy + 82, 56, 7); P.r(ctx, x - 1, hy + 60, 2, 20, '#8a5a2a'); P.r(ctx, x - 40, hy + 84 + jaw, 80, 18, fl ? '#fff' : '#d8a870'); P.l(ctx, x - 34, hy + 84, x - 34, hy + 102 + jaw, '#5a3a1a', 2); P.l(ctx, x + 34, hy + 84, x + 34, hy + 102 + jaw, '#5a3a1a', 2);
    for (const h of this.hands) { if (h.hp <= 0 && this.phase < 3) continue; const hx = x + h.x, hy2 = this.ground - 60 - h.y - cy; const f2 = h.inv > 0; O.r(hx - 20, hy2 - 18, 40, 32, f2 ? '#fff' : '#e8c290'); for (let i = 0; i < 4; i++) O.r(hx - 18 + i * 10, hy2 + 12, 7, 12, f2 ? '#fff' : '#e8c290', 1); O.r(hx - 24, hy2 - 26, 48, 10, '#c4302b'); if (h.st === 'down') text('HIT!', hx, hy2 - 40, { color: '#ffe14d', align: 'center', outline: true, wave: 1 }); }
  }
}
// ---------------------------------------------------------------------------- DIMENSION DEVOURER
class DevourerBoss extends Boss {
  constructor(x, y, o) { super(x - 80, y - 200, 160, 160, o); this.name = 'THE DIMENSION DEVOURER'; this.setHp(45); this.ground = y; this.cx0 = x; this.mouth = 0; this.portal = null; this.eyes = [0, 1, 2, 3, 4].map(i => ({ a: i * 1.25, r: 50 + (i % 2) * 14 })); }
  hitbox() { return this.state === 'emerge' || this.state === 'hover' || this.state === 'suck' || this.state === 'spit' ? { x: this.x + 30, y: this.y + 30, w: this.w - 60, h: this.h - 60 } : { x: -999, y: 0, w: 0, h: 0 }; }
  onPhase(p) { if (p === 3) { this.invT = 0; } }
  update(L) {
    if (!this.commonUpdate()) return; const p = Game.player; this.mouth = lerp(this.mouth, this.mouthT || 0, .1); for (const e of this.eyes) e.a += .01 * this.phase;
    switch (this.state) {
      case 'intro': this.y = lerp(this.y, this.ground - 240, .03); if (this.st > 80) this.go('hover'); break;
      case 'hover': this.mouthT = .2; this.x = lerp(this.x, p.cx - this.w / 2, .015); this.y = lerp(this.y, this.ground - 240 + Math.sin(this.t * .04) * 20, .05); if (this.st > 90) this.go(pick(this.phase === 1 ? ['suck', 'spit'] : ['suck', 'spit', 'portal', 'portal'])); break;
      case 'suck': this.mouthT = 1; L.wind = sign(this.cx - p.cx) * .22 * (this.st > 20 ? 1 : 0); if (this.st % 3 === 0) FX.add({ x: this.cx + R(-200, 200), y: this.cy + R(-100, 140), vx: 0, vy: 0, col: '#b04bff', size: 2, life: 20, grav: 0, fade: true }); if (dist(p.cx, p.cy, this.cx, this.cy + 30) < 60) p.hurt(1, this.cx); if (this.st > 130) { L.wind = 0; this.go('hover'); } break;
      case 'spit': this.mouthT = .8; if (this.st % 14 === 0 && this.st < 80) { const a = Math.atan2(p.cy - this.cy, p.cx - this.cx) + R(-.3, .3); Game.add(new EnemyShot(this.cx, this.cy + 20, Math.cos(a) * 3, Math.sin(a) * 3, 'spore')); AudioSys.play_sfx('pop'); } if (this.st > 100) this.go('hover'); break;
      case 'portal': if (this.st === 1) { this.portal = { x: p.cx + pick([-1, 1]) * 120, y: this.ground - 80 }; AudioSys.play_sfx('zap'); } this.y = Cam.y - 300; if (this.st > 60) { this.x = this.portal.x - this.w / 2; this.y = this.portal.y - this.h / 2; this.go('emerge'); AudioSys.play_sfx('bite'); Cam.shake(6, 14); } break;
      case 'emerge': this.mouthT = 1; Game.bossAttack({ x: this.x + 40, y: this.y + 40, w: this.w - 80, h: this.h - 80 }); if (this.st > 70) { this.portal = null; this.go('hover'); } break;
    }

  }
  draw(cx, cy) {
    const x = this.cx - cx, y = this.cy - cy, t = this.t, fl = this.flash > 0;
    if (this.portal) { const px = this.portal.x - cx, py = this.portal.y - cy; ctx.save(); ctx.globalCompositeOperation = 'lighter'; for (let i = 0; i < 4; i++) { ctx.strokeStyle = hsl(270 + i * 20, 90, 60, .7); ctx.lineWidth = 3; ctx.beginPath(); ctx.ellipse(px, py, 60 - i * 10 + Math.sin(t * .2) * 4, 80 - i * 12, 0, 0, 7); ctx.stroke(); } ctx.restore(); }
    if (this.state === 'portal') return;
    // tentacles
    for (let i = 0; i < 8; i++) { const a = i / 8 * 6.283 + Math.sin(t * .03) * .3; let px = x, py = y; ctx.strokeStyle = '#0a060e'; ctx.lineWidth = 9; ctx.beginPath(); ctx.moveTo(px, py); for (let k = 1; k < 6; k++) { px = x + Math.cos(a + Math.sin(t * .05 + k + i) * .4) * k * 22; py = y + Math.sin(a + Math.sin(t * .05 + k + i) * .4) * k * 22; ctx.lineTo(px, py); } ctx.stroke(); ctx.strokeStyle = fl ? '#fff' : '#5a1a8a'; ctx.lineWidth = 6; ctx.stroke(); }
    O.e(x, y, 72, 70, fl ? '#fff' : '#2a0a4a', 3); O.e(x, y, 62, 60, '#3a1060', 0);
    for (const e of this.eyes) { const ex = x + Math.cos(e.a) * e.r, ey = y + Math.sin(e.a) * e.r * .8 - 10; O.e(ex, ey, 8, 8, '#fff'); P.e(ctx, ex + (Game.player.cx - this.cx) / 80, ey, 4, 4, '#b04bff'); P.e(ctx, ex + (Game.player.cx - this.cx) / 80, ey, 2, 2, '#000'); }
    const m = this.mouth; O.e(x, y + 14, 46, 8 + 30 * m, '#000'); for (let i = -4; i <= 4; i++) { P.poly(ctx, [[x + i * 10 - 5, y + 14 - (8 + 30 * m) + 2], [x + i * 10 + 5, y + 14 - (8 + 30 * m) + 2], [x + i * 10, y + 14 - (8 + 30 * m) + 14]], '#e8e0c8'); P.poly(ctx, [[x + i * 10 - 5, y + 14 + (8 + 30 * m) - 2], [x + i * 10 + 5, y + 14 + (8 + 30 * m) - 2], [x + i * 10, y + 14 + (8 + 30 * m) - 14]], '#e8e0c8'); }
    if (m > .5) { ctx.save(); ctx.globalCompositeOperation = 'lighter'; P.e(ctx, x, y + 14, 20, 20 * m, hsl(t * 5 % 360, 90, 50, .5)); ctx.restore(); }
  }
}
// ---------------------------------------------------------------------------- CARNIVAL COLOSSUS (mech clown)
class ClownBoss extends Boss {
  constructor(x, y, o) { super(x - 70, y - 220, 140, 220, o); this.name = 'THE CARNIVAL COLOSSUS'; this.setHp(45); this.ground = y; this.cx0 = x; this.spring = 0; this.arms = 0; this.headOff = null; }
  hitbox() { return this.headOff ? { x: this.headOff.x - 40, y: this.headOff.y - 40, w: 80, h: 80 } : { x: this.cx0 - 50, y: this.y - 10 - this.spring, w: 100, h: this.ground - this.y + 10 + this.spring }; }
  onPhase(p) { if (p === 3) { this.headOff = { x: this.cx0, y: this.y + 30, vx: 3, vy: -6 }; HUD.banner('HIS HEAD CAME OFF!', '#ff3a3a'); AudioSys.play_sfx('boing'); } }
  update(L) {
    if (!this.commonUpdate()) return; const p = Game.player; this.spring = Math.sin(this.t * .06) * 20; this.arms += .02 * this.phase;
    if (this.headOff) { const h = this.headOff, a = L.camLock || { x0: Cam.x, x1: Cam.x + W }; h.vy += .3; h.x += h.vx; h.y += h.vy; if (h.y > this.ground - 40) { h.y = this.ground - 40; h.vy = -5 - R(2); AudioSys.play_sfx('boing'); Cam.shake(3, 6); } if (h.x < a.x0 + 40 || h.x > a.x1 - 40) h.vx *= -1; Game.bossAttack(this.hitbox()); }
    switch (this.state) {
      case 'intro': if (this.st > 70) this.go('idle'); break;
      case 'idle': if (this.st > 70) this.go(pick(['knives', 'balloons', this.phase >= 2 ? 'spin' : 'knives'])); break;
      case 'knives': if (this.st % 12 === 0 && this.st < 72) { const sx = this.cx0 + (this.st % 24 ? -60 : 60), sy = this.y + 60, a = Math.atan2(p.cy - sy, p.cx - sx); Game.add(new EnemyShot(sx, sy, Math.cos(a) * 4, Math.sin(a) * 4, 'knife')); AudioSys.play_sfx('throw'); } if (this.st > 90) this.go('idle'); break;
      case 'balloons': if (this.st % 30 === 0 && this.st < 90) { const e = new Enemy({ kind: 'balloon', x: this.cx0 + R(-80, 80), y: this.y + 40 }); e.home.y = this.ground - 80 - R(60); e.wake = true; Game.add(e); AudioSys.play_sfx('pop'); } if (this.st > 110) this.go('idle'); break;
      case 'spin': this.arms += .15; for (const s of [0, Math.PI]) { const ax = this.cx0 + Math.cos(this.arms + s) * 130, ay = this.y + 120 + Math.sin(this.arms + s) * 90; Game.bossAttack({ x: ax - 16, y: ay - 16, w: 32, h: 32 }); } if (this.st > 160) this.go('idle'); break;
    }
    const body = { x: this.cx0 - 34, y: this.y + 90, w: 68, h: 130 }; if (overlap(body, p) && this.state !== 'intro' && this.t % 30 === 0) p.hurt(1, this.cx0);
  }
  draw(cx, cy) {
    const x = this.cx0 - cx, y = this.y - cy, fl = this.flash > 0, t = this.t;
    // tent-striped torso on a giant spring
    for (let i = 0; i < 6; i++) O.e(x, y + 120 + i * 14 - (this.spring * i / 6), 40, 6, '#888', 2);
    O.poly([[x - 60, y + 220], [x - 40, y + 110], [x + 40, y + 110], [x + 60, y + 220]], fl ? '#fff' : '#7a3cff', 3); for (let i = 0; i < 4; i++) P.e(ctx, x, y + 130 + i * 22, 5, 5, '#ffe14d');
    // arms
    for (const s of [0, Math.PI]) { const ax = x + Math.cos(this.arms + s) * (this.state === 'spin' ? 130 : 80), ay = y + 120 + Math.sin(this.arms + s) * (this.state === 'spin' ? 90 : 30); O.line(x, y + 120, ax, ay, '#3dd16a', 8); O.e(ax, ay, 14, 14, '#fff'); }
    // head
    const hx = this.headOff ? this.headOff.x - cx : x, hy = this.headOff ? this.headOff.y - cy : y + 30 - this.spring; const rot = this.headOff ? t * .2 : Math.sin(t * .05) * .1;
    ctx.save(); ctx.translate(hx, hy); ctx.rotate(rot);
    for (const s of [-1, 1]) { O.e(s * 46, -10, 22, 22, '#ff4d2e'); O.e(s * 58, 8, 16, 16, '#ff4d2e'); }
    O.e(0, 0, 42, 44, fl ? '#fff' : '#fbf3ea', 3); P.e(ctx, -15, -10, 8, 10, '#3a8aff'); P.e(ctx, 15, -10, 8, 10, '#3a8aff'); P.e(ctx, -15, -8, 4, 5, '#000'); P.e(ctx, 15, -8, 4, 5, '#000');
    P.l(ctx, -26, -26, -6, -20, '#000', 3); P.l(ctx, 26, -26, 6, -20, '#000', 3); O.e(0, 6, 9, 9, '#e8102a'); P.r(ctx, -3, 2, 3, 3, '#fff8');
    O.r(-26, 18, 52, 10 + Math.abs(Math.sin(t * .1)) * 6, '#a00'); P.teeth(ctx, -24, 18, 48, 8); O.poly([[-12, -40], [0, -78], [12, -40]], '#3dd16a'); P.e(ctx, 0, -80, 6, 6, '#ffe14d');
    ctx.restore();
  }
}
// ---------------------------------------------------------------------------- KING OF THE GARBAGE HEAP + Golden Gloop core
class HeapBoss extends Boss {
  constructor(x, y, o) {
    super(x - 100, y - 190, 200, 190, o); this.name = 'KING OF THE GARBAGE HEAP'; this.setHp(52); this.ground = y; this.cx0 = x;
    this.junk = []; for (let i = 0; i < 14; i++) this.junk.push({ a: i / 14 * 6.283, r: 70 + (i % 3) * 16, col: hsl(R(360), 30, 35), w: RI(14, 26), h: RI(10, 20), alive: true, regen: 0 });
    this.blobs = null; this.stretch = 0; this.armor = true;
  }
  hitbox() { if (this.blobs) return { x: -999, y: 0, w: 0, h: 0 }; return { x: this.cx0 - 70, y: this.ground - 140 - this.stretch, w: 140, h: 140 + this.stretch }; }
  get vulnerableNow() { return !this.armor || this.junk.filter(j => j.alive).length <= 4; }
  hit(dmg, a) { if (this.armor && !this.vulnerableNow && !this.blobs && dmg > 0 && this.inv <= 0) { this.inv = 10; let n = 0; for (const j of this.junk) if (j.alive && n < 3) { j.alive = false; j.regen = 900; n++; FX.debris(this.cx0 + Math.cos(j.a) * j.r, this.ground - 90 + Math.sin(j.a) * j.r * .6, 'junk', 4); } AudioSys.play_sfx('break'); FX.pop(this.cx0, this.ground - 160, 'CLANG! ARMOUR OFF!', '#ffd23a'); return true; } return super.hit(dmg, a); }
  onPhase(p) {
    if (p === 2) { this.armor = false; HUD.banner('THE GOLDEN GLOOP EMERGES!', '#ffd23a'); for (const j of this.junk) if (j.alive) { j.alive = false; FX.debris(this.cx0 + Math.cos(j.a) * j.r, this.ground - 90 + Math.sin(j.a) * j.r * .6, 'junk', 3); } Save.see('gloop'); }
    if (p === 3) this.go('split');
  }
  update(L) {
    if (!this.commonUpdate()) return; const p = Game.player; this.vulnerable = this.vulnerableNow && !this.blobs;
    // junk armour orbits and REGENERATES unless kept smashed
    for (const j of this.junk) {
      j.a += .008; const jx = this.cx0 + Math.cos(j.a) * j.r, jy = this.ground - 90 + Math.sin(j.a) * j.r * .6;
      if (this.armor) { if (j.alive) { for (const a of p.attacks) if (overlap(a, { x: jx - j.w / 2, y: jy - j.h / 2, w: j.w, h: j.h })) { j.alive = false; j.regen = 900; AudioSys.play_sfx('break'); FX.debris(jx, jy, 'junk', 5); } if (dist(jx, jy, p.cx, p.cy) < 16) p.hurt(1, jx); }
        else if (--j.regen <= 0) { j.alive = true; FX.ring(jx, jy, 16, '#ffd23a'); AudioSys.play_sfx('gloop'); } }
    }
    switch (this.state) {
      case 'intro': if (this.st > 80) this.go('idle'); break;
      case 'idle': this.stretch = lerp(this.stretch, 0, .1); if (this.st > 70) this.go(pick(['throw', 'slam'])); break;
      case 'throw': if (this.st % 18 === 0 && this.st < 70) { const a = Math.atan2(p.cy - (this.ground - 150), p.cx - this.cx0); Game.add(new EnemyShot(this.cx0, this.ground - 150, Math.cos(a) * 4, Math.sin(a) * 4 - 2, this.armor ? 'brick' : 'glob')); AudioSys.play_sfx('throw'); } if (this.st > 90) this.go('idle'); break;
      case 'slam': if (this.st < 40) this.stretch = this.st * 2.5; else if (this.st === 40) { this.stretch = -30; Cam.shake(8, 16); AudioSys.play_sfx('gloop'); AudioSys.play_sfx('rumble'); FX.ring(this.cx0, this.ground, 150, '#ffd23a', 20, 4); Game.bossAttack({ x: this.cx0 - 200, y: this.ground - 14, w: 400, h: 14 }); for (const s of [-1, 1]) Game.add(new EnemyShot(this.cx0 + s * 80, this.ground - 10, s * 3.5, 0, 'wave')); } else this.stretch = lerp(this.stretch, 0, .1); if (this.st > 80) this.go('idle'); break;
      case 'stretch': { // sludge arm stretches across the arena
        const k = Math.min(1, this.st / 40), dir = sign(p.cx - this.cx0) || -1; this.armX = this.cx0 + dir * k * 260; if (this.st > 20 && this.st < 70) Game.bossAttack({ x: Math.min(this.cx0, this.armX) - 10, y: this.ground - 50, w: Math.abs(this.armX - this.cx0) + 20, h: 30 }); if (this.st > 70) { this.armX = null; this.go('idle'); } break; }
      case 'wave': if (this.st % 25 === 0 && this.st < 80) Game.add(new EnemyShot(this.cx0, this.ground - 12, (sign(p.cx - this.cx0) || 1) * 3, 0, 'wave')); if (this.st > 100) this.go('idle'); break;
      case 'split': // splits into three gloops which must each be hit, then reforms
        if (this.st === 1) { AudioSys.play_sfx('squish'); this.blobs = [-1, 0, 1].map(s => ({ x: this.cx0 + s * 40, y: this.ground, vx: s * 3 + R(-1, 1), vy: -6, hp: 3, flash: 0 })); HUD.toast('IT SPLIT! HIT ALL THREE!', '#ffd23a'); }
        for (const b of this.blobs) { if (b.hp <= 0) continue; b.vy += .3; b.x += b.vx; b.y += b.vy; if (b.y > this.ground) { b.y = this.ground; b.vy = -3.5 - R(2); b.vx = sign(p.cx - b.x) * R(1, 3); AudioSys.play_sfx('gloop'); } const a = L.camLock; if (a) b.x = clamp(b.x, a.x0 + 30, a.x1 - 30); if (b.flash) b.flash--;
          const box = { x: b.x - 24, y: b.y - 40, w: 48, h: 40 }; if (overlap(box, p)) p.hurt(1, b.x);
          for (const at of p.attacks) if (overlap(at, box) && !b.flash) { b.hp--; b.flash = 12; AudioSys.play_sfx('squish'); FX.slime(b.x, b.y - 20, 10, ['#ffd23a', '#c8902a']); if (b.hp <= 0) { this.hp -= 4; FX.pop(b.x, b.y - 50, 'SPLAT!', '#ffd23a'); } }
          for (const e of Game.ents) if (e instanceof SlimeBall && e.friendly && overlap(e, box) && !b.flash) { b.hp--; b.flash = 12; e.splat(); if (b.hp <= 0) this.hp -= 4; } }
        if (this.blobs.every(b => b.hp <= 0) || this.st > 900) { this.blobs = null; this.go('idle'); AudioSys.play_sfx('gloop'); HUD.toast('...AND REFORMED!', '#ffd23a'); FX.ring(this.cx0, this.ground - 60, 80, '#ffd23a'); if (this.hp <= 0) this.defeat(); else this.timerSplit = 600; }
        break;
    }
    if (this.phase >= 3 && !this.blobs && this.state === 'idle' && (this.timerSplit = (this.timerSplit || 600) - 1) <= 0) this.go('split');
    const body = { x: this.cx0 - 60, y: this.ground - 100, w: 120, h: 100 }; if (!this.blobs && overlap(body, p) && this.state !== 'intro') p.hurt(1, this.cx0);
  }
  draw(cx, cy) {
    const x = this.cx0 - cx, gy = this.ground - cy, fl = this.flash > 0;
    if (this.blobs) { for (const b of this.blobs) if (b.hp > 0) drawSludge(b.x - cx, b.y - cy, { scale: .28, t: this.t / 60 + b.x, flash: b.flash > 0 ? '#fff' : false, sy: b.vy < 0 ? 1.2 : .9 }); return; }
    if (this.armor) { // trash mountain body
      O.poly([[x - 100, gy], [x - 70, gy - 120], [x - 20, gy - 160], [x + 40, gy - 150], [x + 90, gy - 100], [x + 110, gy]], fl ? '#fff' : '#5a4a3a', 3);
      for (let i = 0; i < 18; i++) { const r = mulberry(i * 99); P.r(ctx, x - 80 + r() * 160, gy - 20 - r() * 120, 10 + r() * 16, 6 + r() * 10, hsl(r() * 360, 30, 30)); }
      O.poly([[x - 40, gy - 150], [x - 30, gy - 190], [x - 10, gy - 168], [x, gy - 200], [x + 10, gy - 168], [x + 30, gy - 190], [x + 40, gy - 150]], '#ffd23a');
      P.e(ctx, x - 18, gy - 120, 8, 6, '#ffd23a'); P.e(ctx, x + 18, gy - 120, 8, 6, '#ffd23a'); P.e(ctx, x - 18, gy - 120, 3, 3, '#000'); P.e(ctx, x + 18, gy - 120, 3, 3, '#000'); O.r(x - 24, gy - 100, 48, 10, '#300'); P.teeth(ctx, x - 22, gy - 100, 44, 6);
      const glow = Math.sin(this.t * .1) * .5 + .5; ctx.save(); ctx.globalCompositeOperation = 'lighter'; P.e(ctx, x, gy - 60, 26 + glow * 4, 20, 'rgba(255,210,58,.3)'); ctx.restore();
    } else {
      drawSludge(x + 20, gy + 4, { scale: .9, sy: 1 + this.stretch / 150, t: this.t / 60, wobble: 1.5, flash: fl ? '#fff' : false, bulge: this.state === 'slam' && this.st < 40 ? .1 : 0 });
      O.poly([[x - 10, gy - 160 - this.stretch], [x - 2, gy - 190 - this.stretch], [x + 8, gy - 168 - this.stretch], [x + 16, gy - 196 - this.stretch], [x + 24, gy - 168 - this.stretch], [x + 34, gy - 190 - this.stretch], [x + 40, gy - 160 - this.stretch]], '#ffd23a');
      if (this.armX) { const ax = this.armX - cx; ctx.strokeStyle = '#3a2000'; ctx.lineWidth = 26; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(x, gy - 40); ctx.quadraticCurveTo((x + ax) / 2, gy - 80, ax, gy - 36); ctx.stroke(); ctx.strokeStyle = '#d4a02a'; ctx.lineWidth = 20; ctx.stroke(); ctx.lineCap = 'butt'; P.e(ctx, ax, gy - 36, 16, 14, '#ffd23a'); }
    }
    for (const j of this.junk) if (j.alive && this.armor) { const jx = x + Math.cos(j.a) * j.r, jy = gy - 90 + Math.sin(j.a) * j.r * .6; O.r(jx - j.w / 2, jy - j.h / 2, j.w, j.h, j.col, 1); }
    if (this.armor && this.vulnerableNow) text('CORE EXPOSED!', x, gy - 210, { color: '#ffd23a', align: 'center', outline: true, wave: 1 });
  }
}
// ---------------------------------------------------------------------------- THE ETERNAL FEEDBACK (final)
class FeedbackBoss extends Boss {
  constructor(x, y, o) { super(x - 110, y - 250, 220, 200, o); this.name = 'THE ETERNAL FEEDBACK'; this.setHp(60); this.ground = y; this.cx0 = x; this.static = 0; this.echo = null; this.phases = [1, .7, .4]; this.shield = 0; }
  hitbox() { return { x: this.cx0 - 80, y: this.y + 60, w: 160, h: 136 }; }
  onPhase(p) { if (p === 2) HUD.banner('ECHO CHAMBER', '#b04bff'); if (p === 3) { HUD.banner('THE FINAL SONG — PLAY ON THE BEAT!', '#7fff3a'); this.shield = 1; Game.flag('finalPhase'); } }
  hit(dmg, a) {
    if (this.phase >= 3 && a && a.kind !== 'ally' && this.shield > 0) { if (!this.msgT || this.t - this.msgT > 40) { FX.pop(this.cx, this.y, 'WAIT FOR YOUR BAND!', '#7fff3a'); this.msgT = this.t; } return false; }
    return super.hit(dmg, a);
  }
  update(L) {
    if (!this.commonUpdate()) return; const p = Game.player; this.static = (this.static + 1) % 1000; this.y = this.ground - 196 + Math.sin(this.t * .02) * 6;
    switch (this.state) {
      case 'intro': if (this.st > 90) this.go('idle'); break;
      case 'idle': if (this.st > 70) this.go(this.phase === 1 ? pick(['wall', 'rings']) : pick(['wall', 'rings', 'echoWolf'])); break;
      case 'wall': if (this.st % 50 === 1 && this.st < 150) { const gap = RI(0, 2); for (let i = 0; i < 4; i++) if (i !== gap) Game.add(new EnemyShot(this.cx0 - 60, this.ground - 16 - i * 34, -2.6, 0, 'wave')); AudioSys.play_sfx('laser'); } if (this.st > 170) this.go('idle'); break;
      case 'rings': if (this.st % 10 === 0 && this.st < 60) for (let a = 0; a < 6.283; a += .785) Game.add(new EnemyShot(this.cx0, this.y + 100, Math.cos(a + this.st) * 2.2, Math.sin(a + this.st) * 2.2, 'ring')); if (this.st > 90) this.go('idle'); break;
      case 'echoWolf': if (this.st === 1) { this.echo = { kind: 'wolf', x: Cam.x - 60, dir: 1 }; AudioSys.play_sfx('howl'); } this.echo.x += 6; Game.bossAttack({ x: this.echo.x - 30, y: this.ground - 80, w: 60, h: 80 }); if (this.echo.x > Cam.x + W + 60) { this.echo = null; this.go('idle'); } break;
      case 'echoCow': if (this.st === 1) { this.echo = { kind: 'cow', x: p.cx, y: Cam.y - 80 }; AudioSys.play_sfx('moo'); } if (this.st < 40) this.echo.x = lerp(this.echo.x, p.cx, .1); else { this.echo.y += 9; if (this.echo.y > this.ground - 40) { Cam.shake(6, 12); FX.ring(this.echo.x, this.ground, 90, '#fff'); Game.bossAttack({ x: this.echo.x - 60, y: this.ground - 20, w: 120, h: 20 }); this.echo = null; this.go('idle'); break; } Game.bossAttack({ x: this.echo.x - 30, y: this.echo.y - 30, w: 60, h: 60 }); } break;
      case 'echoGloop': if (this.st === 1) { this.echo = { kind: 'gloop', x: p.cx, t: 0 }; AudioSys.play_sfx('gloop'); } this.echo.t++; if (this.echo.t > 40 && this.echo.t < 100) Game.bossAttack({ x: this.echo.x - 50, y: this.ground - 30, w: 100, h: 30 }); if (this.echo.t > 110) { this.echo = null; this.go('idle'); } break;
    }
    if (this.phase >= 3) {
      this.shield = this.shieldDown > 0 ? 0 : 1; if (this.shieldDown > 0) this.shieldDown--;
      this.allyT = (this.allyT || 0) + 1;
      if (this.allyT % 300 === 40) { const a = ['pigs', 'razz', 'udderly', 'barnaby', 'gloop'][Math.floor(this.allyT / 300) % 5]; this.allyEvent = { k: a, t: 0 }; }
      if (this.allyEvent) { const e = this.allyEvent; e.t++;
        if (e.t === 1) { HUD.banner({ pigs: 'THE PIGS STAMPEDE!', razz: 'RAZZ RAMS THE AMP!', udderly: 'UDDERLY DIVE-BOMBS!', barnaby: 'BARNABY HOWLS THE SHIELD DOWN!', gloop: 'THE GLOOP HOLDS IT STILL!' }[e.k], '#7fff3a', 'SHIELD DOWN - ATTACK!!'); AudioSys.play_sfx({ pigs: 'oink', razz: 'rev', udderly: 'moo', barnaby: 'howl', gloop: 'gloop' }[e.k], { pitch: 1 }); this.shieldDown = 220; }
        if (e.k === 'gloop' && e.t < 200) this.y = this.ground - 250;
        if (e.t === 40) { Cam.shake(8, 20); FX.ring(this.cx0, this.y + 100, 120, '#7fff3a'); super.hit(2, { kind: 'ally' }); }
        if (e.t > 220) this.allyEvent = null; }
    }
    if (overlap({ x: this.cx0 - 60, y: this.y + 120, w: 120, h: 60 }, p) && this.t % 30 === 0) p.hurt(1, this.cx0);
  }
  draw(cx, cy) {
    const x = this.cx0 - cx, y = this.y - cy, t = this.t, fl = this.flash > 0;
    // static aura
    ctx.save(); ctx.globalCompositeOperation = 'lighter'; for (let i = 0; i < 60; i++) { ctx.fillStyle = hsl(R(360), 80, 60, .5); ctx.fillRect(x + R(-140, 140), y + R(-20, 220), R(1, 6), 1); } ctx.restore();
    // cables like tentacles
    for (let i = 0; i < 6; i++) { const s = i < 3 ? -1 : 1, k = i % 3; ctx.strokeStyle = '#0a060e'; ctx.lineWidth = 8; ctx.beginPath(); ctx.moveTo(x + s * 80, y + 120 + k * 30); ctx.bezierCurveTo(x + s * 160, y + 80 + k * 40 + Math.sin(t * .05 + i) * 30, x + s * 200, y + 200, x + s * (220 + k * 30), this.ground - cy); ctx.stroke(); ctx.strokeStyle = '#2a2a30'; ctx.lineWidth = 5; ctx.stroke(); }
    // amp-face
    O.r(x - 110, y, 220, 190, fl ? '#fff' : '#18181c', 3); O.r(x - 100, y + 10, 200, 14, '#c9a227', 1); for (let i = 0; i < 10; i++) P.e(ctx, x - 90 + i * 20, y + 17, 4, 4, '#222');
    for (let gy2 = y + 34; gy2 < y + 180; gy2 += 5) P.r(ctx, x - 100, gy2, 200, 2, '#24242a');
    const ang = this.phase >= 3 ? '#7fff3a' : '#ff2a4a', pulse = Math.sin(t * .15) * .5 + .5;
    for (const s of [-1, 1]) { O.e(x + s * 50, y + 80, 30 + pulse * 3, 30 + pulse * 3, '#000'); P.e(ctx, x + s * 50, y + 80, 22, 22, ang); P.e(ctx, x + s * 50, y + 80, 8, 8, '#fff'); }
    O.r(x - 70, y + 130, 140, 30 + pulse * 10, '#000'); for (let i = 0; i < 20; i++) { const h = Math.abs(Math.sin(t * .3 + i * .7)) * (24 + pulse * 10); P.r(ctx, x - 66 + i * 7, y + 145 - h / 2, 5, h, ang); }
    if (this.shield > 0) { ctx.strokeStyle = `rgba(127,255,58,${.4 + pulse * .3})`; ctx.lineWidth = 3; ctx.beginPath(); ctx.ellipse(x, y + 95, 130, 120, 0, 0, 7); ctx.stroke(); }
    if (this.allyEvent) { const e = this.allyEvent, k = e.t / 60, gy = this.ground - cy;
      if (e.k === 'pigs') { const px = -60 + e.t * 5; drawPig('trufflina', px + 40, gy, { face: 1, state: 'run', t: k }); drawPig('porkington', px, gy, { face: 1, state: 'run', t: k + .2 }); drawPig('hamwise', px - 36, gy, { face: 1, state: 'run', t: k + .4, prop: 'kazoo' }); }
      if (e.k === 'razz') drawBiker(-80 + e.t * 7, gy, { face: 1, t: k, speed: 2, turbo: true, wheelie: .25 });
      if (e.k === 'udderly') drawCow(x - 200 + e.t * 4, y - 60 + Math.min(e.t, 40) * 3, { face: 1, t: k, scale: .5, rot: .5, cape: 10, capeStretch: 8 });
      if (e.k === 'barnaby') { drawWolf(60, gy, { face: 1, t: k, scale: .55, rot: -.35, arm: -.4 }); if (e.t % 10 === 0) FX.ring(60 + cx, this.ground - 90, 160, '#fff', 20, 2); }
      if (e.k === 'gloop') { drawSludge(x + 30, gy + 4, { t: k, scale: .7, sx: 1.8, sy: .5, wobble: 2 }); }
    }
    if (this.echo) { const e = this.echo; ctx.save(); ctx.globalAlpha = .7; if (e.kind === 'wolf') drawWolf(e.x - cx, this.ground - cy, { face: 1, t: t / 60, scale: .6, arm: 1.5, flash: '#b04bff' }); if (e.kind === 'cow') drawCow(e.x - cx, e.y - cy + 50, { face: 1, t: t / 60, scale: .5, flash: '#b04bff', rot: .8 }); if (e.kind === 'gloop') { if (e.t < 40) { ctx.fillStyle = '#b04bff'; ctx.fillRect(e.x - cx - 50, this.ground - cy - 4, 100, 4); } else drawSludge(e.x - cx + 20, this.ground - cy, { scale: .35, sy: Math.min(1, (e.t - 40) / 15), flash: '#b04bff', t: t / 60 }); } ctx.restore(); }
  }
}
const BOSS_CLASSES = { wolf: WolfBoss, cow: CowBoss, overlord: OverlordBoss, puppetking: PuppetKing, devourer: DevourerBoss, clown: ClownBoss, heap: HeapBoss, feedback: FeedbackBoss };
