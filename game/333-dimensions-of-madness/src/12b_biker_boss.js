// ============================================================================
// LEVEL 2 BOSS: ELECTRIC HARLEY HOUSE (OF LOVE)
// Frame-based animations baked from the supplied biker art into fixed-size,
// fixed-anchor, transparent frames (nearest-neighbour, no smoothing), an
// explicit boss state machine and a single encounter controller.
// ============================================================================
const BIKER_FRAME = { w: 470, h: 260, ax: 192, ay: 226 }; // HD pixels; anchor = rear tyre contact
const BIKER_ANIMS = {};
const BIKER_FPS = { idle: 8, drive: 14, tongue: 0, hit: 16, charge: 14, defeat: 7 };
const BIKER_TONGUE_EXT = [0, 0, .35, .75, 1, 1, .45, 0]; // tongue extension per TONGUE frame
function bakeBikerFrames() {
  if (!IMG.biker_bike) return;
  const F = BIKER_FRAME, an = A('biker'), period = Math.PI * 2 / 16; // hair wave period
  const mk = (n, fn) => Array.from({ length: n }, (_, i) => { const c = makeCanvas(F.w, F.h); c.ctx.imageSmoothingEnabled = false; withCtx(c, () => fn(i, n)); return c; });
  const at = (o, dx = 0, dy = 0) => drawBiker(F.ax + dx, F.ay + dy, Object.assign({ face: 1, scale: ZOOM }, o));
  const ex = [F.ax - an.rearWheel[0] + an.exhaust[0], F.ay - (IMG.biker.height - 2) + an.exhaust[1]];
  const puff = (x, y, r, a) => { r *= 1.5; ctx.save(); ctx.globalAlpha = a; PP.ell(ctx, x, y, r, r * .8, '#d8d8e8', 2); ctx.fillStyle = '#fff8'; ctx.beginPath(); ctx.arc(x - r * .3, y - r * .3, r * .3, 0, 7); ctx.fill(); ctx.restore(); };
  BIKER_ANIMS.idle = mk(4, (i, n) => { const t = i * period / n; puff(ex[0] - 10 - i * 4, ex[1] - i * 2, 6 + i, .8 - i * .15); at({ t, speed: .25, bounce: i % 2 }); });
  BIKER_ANIMS.drive = mk(8, (i, n) => { const t = i * period / n * 2; for (let k = 0; k < 3; k++) puff(ex[0] - 14 - k * 16 - (i % 4) * 4, ex[1] - k * 3, 6 + k * 3, .75 - k * .2); at({ t, speed: 1, bounce: (i % 4 === 1) ? 2 : (i % 4 === 3 ? 1 : 0) }); });
  BIKER_ANIMS.tongue = mk(8, (i) => { const lean = [-.1, -.16, .06, .1, .1, .08, 0, -.04][i], mouth = [.6, 1, 1, 1, 1, 1, .7, .3][i]; at({ t: i * .05, speed: .3, riderRot: lean, mouthOpen: mouth, bounce: i < 2 ? 1 : 0 }); });
  BIKER_ANIMS.hit = mk(4, (i) => { at({ t: i * .05, speed: .3, riderRot: [-.05, -.24, -.14, -.05][i], riderDX: [-2, -6, -3, -1][i], tilt: [0, -.06, -.03, 0][i], flash: i === 0 ? '#fff' : false, riderFlash: i === 1 ? '#ffb0b0' : false, mouthOpen: i === 1 ? .8 : 0 }); if (i === 1) { PP.star(ctx, F.ax + 90, F.ay - 150, 10, '#ffe14d'); PP.star(ctx, F.ax + 110, F.ay - 120, 6, '#fff'); } });
  BIKER_ANIMS.charge = mk(6, (i, n) => { const t = i * period / n * 2; for (let k = 0; k < 4; k++) { ctx.fillStyle = '#ffffffaa'; ctx.fillRect(F.ax - 120 - k * 14 - (i * 9) % 30, F.ay - 40 - k * 22, 46 - k * 6, 3); } at({ t, speed: 2.2, wheelie: .14 + (i % 2) * .04, turbo: true, hairBoost: 4, bounce: i % 2 }); });
  BIKER_ANIMS.defeat = mk(12, (i) => {
    // 0-2 loses control (wobble), 3-5 skids nose-up, 6-8 tips onto its side and the rider is thrown, 9-11 smoke + dazed final pose
    if (i <= 2) { const w = [.05, -.06, .07][i]; at({ t: i * .07, speed: 1.4, tilt: w, riderRot: -w * 3, riderDX: [0, -3, 3][i], mouthOpen: 1 }); return; }
    if (i <= 5) { const k = (i - 2) / 3; for (let d = 0; d < 4; d++) puff(F.ax - 10 - d * 20, F.ay - 8 - d * 3, 8 + d * 3, .75); at({ t: i * .04, speed: 1, tilt: -(.08 + k * .22), riderRot: -.2 - k * .3, riderDX: -k * 10, riderDY: -k * 12, mouthOpen: 1 }); return; }
    const k = Math.min(1, (i - 5) / 3), lie = i >= 8;
    ctx.save(); ctx.translate(F.ax + 40, F.ay); ctx.rotate(-.1 * k); ctx.scale(1, 1 - .32 * k); ctx.translate(-F.ax - 40, -F.ay);
    drawBiker(F.ax, F.ay, { face: 1, scale: ZOOM, t: 0, speed: 0, riderDX: 30 + 45 * k, riderDY: 34 * k, riderRot: 1.35 * k, dizzy: lie, mouthOpen: lie ? .2 : 1 });
    ctx.restore();
    for (let d = 0; d < 3 + (i >= 9 ? 2 : 0); d++) puff(F.ax - 40 + d * 36 + (i * 7) % 12, F.ay - 26 - d * 6 - (i - 6) * 3, 11 + d * 3 + (i - 6), .7 - d * .08);
    if (i >= 9) { PP.star(ctx, F.ax + 150, F.ay - 40 - (i % 2) * 4, 7, '#ffe14d'); PP.star(ctx, F.ax + 175, F.ay - 30, 5, '#fff'); }
  });
  BIKER_ANIMS.ready = true;
}
const BIKER_STATES = ['INACTIVE', 'ENTERING', 'INTRO', 'FIGHTING', 'DEFEATED', 'EXITING', 'COMPLETE'];
class BikerBoss extends Boss {
  constructor(enc) {
    const gy = enc.gyPx; super(enc.x0 + enc.w + 140, gy - 70, 120, 70, {}); this.enc = enc; this.name = 'ELECTRIC HARLEY HOUSE (OF LOVE)'; this.short = 'ELECTRIC HARLEY'; /* full name on the intro card, short name on the health bar */ this.setHp(24);
    this.ground = gy; this.face = -1; this.st = 'ENTERING'; this.sub = null; this.stT = 0; this.subT = 0; this.anim = 'drive'; this.af = 0; this.aT = 0; this.hitT = 0; this.tongue = null; this.charge = null; this.vulnerable = false; this.phases = [1, .5];
    this.home = enc.x0 + enc.w * .72; this.attacks = 0; AudioSys.setEngine(true, .8); AudioSys.play_sfx('rev');
  }
  get state() { return this.st; } set state(v) { } // Boss base uses .state for intro checks
  hitbox() { return { x: this.x + 14, y: this.ground - 66, w: this.w - 28, h: 62 }; }
  setState(s) { if (this.st === s) return; this.st = s; this.stT = 0; }
  setSub(s) { this.sub = s; this.subT = 0; }
  play(name, restart) { if (this.anim !== name || restart) { this.anim = name; this.af = 0; this.aT = 0; } }
  stepAnim() { const fps = BIKER_FPS[this.anim]; if (!fps) return; const n = (BIKER_ANIMS[this.anim] || []).length || 1; this.aT += fps / 60; if (this.aT >= 1) { this.aT -= 1; this.af = this.anim === 'defeat' ? Math.min(n - 1, this.af + 1) : (this.af + 1) % n; } }
  mouthWorld() { const an = A('biker'), dx = (an.mouth[0] - an.rearWheel[0]) * HD, dy = (an.mouth[1] - (IMG.biker.height - 2)) * HD; return [this.wheelX() + dx * this.face, this.ground + dy]; }
  wheelX() { return this.face > 0 ? this.x + 20 : this.x + this.w - 20; }
  arena() { return { a: this.enc.x0 + 30, b: this.enc.x0 + this.enc.w - 30 }; }
  hit(dmg, a) {
    if (this.st !== 'FIGHTING') return false;
    if (this.sub === 'ATTACK' && this.charge) { if (this.inv <= 0) { FX.pop(this.cx, this.ground - 80, 'TOO FAST! JUMP IT!', '#aaa'); this.inv = 20; } return false; }
    const ok = super.hit(dmg, a); if (ok) { this.hitT = 14; this.play('hit', true); Cam.shake(3, 6); if (this.sub === 'RECOVERY') this.subT = Math.max(0, this.subT - 6); } return ok;
  }
  onPhase(p) { HUD.toast('ELECTRIC HARLEY: "YOU SCRATCHED MY CHROME!!"', '#5bd4ff'); }
  defeat() { // single authoritative end: health hit zero -> DEFEATED sequence (never despawns early)
    this.defeated = true; this.hp = 0; this.tongue = null; this.charge = null; this.setState('DEFEATED'); this.play('defeat', true); this.vulnerable = false;
    AudioSys.setEngine(false); AudioSys.play_sfx('bossDie'); AudioSys.play_sfx('explode'); Cam.shake(8, 40); HUD.banner('ELECTRIC HARLEY WIPES OUT!', '#5bd4ff');
    for (const e of Game.ents) if (e instanceof EnemyShot) e.dead = true;
  }
  update(L) {
    this.t++; this.stT++; this.subT++; if (this.flash > 0) this.flash--; if (this.inv > 0) this.inv--; if (this.hitT > 0) this.hitT--;
    const p = Game.player, ar = this.arena();
    switch (this.st) {
      case 'ENTERING': { this.play('drive'); this.face = -1; this.x = approach(this.x, this.home - this.w / 2, 4); if (this.t % 3 === 0) FX.smoke(this.x + this.w + 10, this.ground - 10, 2); if (Math.abs(this.x - (this.home - this.w / 2)) < 1) { this.setState('INTRO'); AudioSys.play_sfx('rev'); } break; }
      case 'INTRO': { this.play('idle'); if (this.stT === 1) { HUD.toast('ELECTRIC HARLEY: "TIME TO TASTE MY SECRET WEAPON: TONGUE!"', '#5bd4ff'); HUD.banner('FIGHT!', '#ff3a3a'); HUD.bossIntro = 90; AudioSys.setIntensity(3); AudioSys.setBossPhase(1); } if (this.stT > 50) { this.setState('FIGHTING'); this.setSub('IDLE'); this.vulnerable = true; } break; }
      case 'FIGHTING': this.fight(L, p, ar); break;
      case 'DEFEATED': { if (this.stT % 10 === 0 && this.stT < 100) FX.smoke(this.cx + R(-30, 30), this.ground - 20, R(-1, 1)); if (this.af >= BIKER_ANIMS.defeat.length - 1 && this.stT > 120) { this.setState('EXITING'); HUD.toast('ELECTRIC HARLEY: "OW. MY HAIR. OKAY... YOU WIN. THIS TIME."', '#5bd4ff'); } break; }
      case 'EXITING': { if (this.stT > 90) this.setState('COMPLETE'); break; }
      case 'COMPLETE': break;
    }
    if (this.hitT === 0 && this.anim === 'hit') this.play(this.st === 'FIGHTING' && this.sub === 'IDLE' ? 'drive' : 'idle');
    this.stepAnim();
    this.x = clamp(this.x, this.enc.x0 - 200, this.enc.x0 + this.enc.w + 200);
  }
  fight(L, p, ar) {
    const dx = p.cx - this.cx;
    switch (this.sub) {
      case 'IDLE': { // reposition toward a spot facing the player
        const want = clamp(p.cx + (dx > 0 ? -150 : 150), ar.a + 60, ar.b - 60);
        this.face = sign(dx) || this.face; const mv = clamp(want - this.cx, -2, 2); this.x += mv; if (this.hitT === 0) this.play(Math.abs(mv) > .3 ? 'drive' : 'idle');
        AudioSys.setEngine(true, .5 + Math.abs(mv) * .1);
        if (this.subT > 70 - (this.phase - 1) * 15) { this.kind = Math.abs(dx) < 175 && this.attacks % 3 !== 2 ? 'tongue' : 'charge'; this.attacks++; this.setSub('TELEGRAPH'); this.face = sign(dx) || this.face; AudioSys.play_sfx('rev'); }
        break; }
      case 'TELEGRAPH': {
        if (this.kind === 'tongue') { this.play('tongue'); this.af = this.subT < 18 ? 0 : 1; if (this.subT === 1) FX.pop(this.cx, this.ground - 110, '!', '#ff3a3a');
          if (this.subT >= 34) { const [mx, my] = this.mouthWorld(), tx = p.cx, ty = clamp(p.cy, this.ground - 120, this.ground - 8), d = Math.hypot(tx - mx, ty - my) || 1; this.tongue = { dir: [(tx - mx) / d, (ty - my) / d], len: 0, hit: false, max: 168 }; if (sign(this.tongue.dir[0]) !== this.face) this.tongue.dir = [this.face, 0]; this.setSub('ATTACK'); AudioSys.play_sfx('whip'); } }
        else { this.play('charge'); if (this.subT === 1) { HUD.toast('WARNING: CHOPPER CHARGE - JUMP!', '#ff3a3a'); AudioSys.play_sfx('rev'); } this.x -= this.face * .6; if (this.t % 4 === 0) FX.smoke(this.wheelX() - this.face * 20, this.ground - 8, -this.face * 2);
          if (this.subT >= 50) { this.charge = { dir: this.face, spd: 0 }; this.setSub('ATTACK'); AudioSys.play_sfx('dash'); } }
        break; }
      case 'ATTACK': {
        if (this.kind === 'tongue' && this.tongue) { // frames 2..5 extend/strike: locked direction, live hitbox on the tongue tip
          const k = this.subT / 20, g = this.tongue; this.play('tongue'); this.af = clamp(2 + Math.floor(k * 4), 2, 5); g.len = g.max * BIKER_TONGUE_EXT[this.af] * (this.af === 3 ? .95 : 1);
          if (this.af >= 4) g.len = g.max;
          const [mx, my] = this.mouthWorld(), tx = mx + g.dir[0] * g.len, ty = my + g.dir[1] * g.len; g.tip = [tx, ty, mx, my];
          if (!g.hit && g.len > 10) { const box = { x: tx - 12, y: ty - 12, w: 24, h: 24 }; if (overlap(box, p) && p.hurt(1, mx)) { g.hit = true; p.vx = this.face * 5; p.vy = -4; FX.burst(tx, ty, 16, ['#ff6aa8', '#fff', '#ffe14d'], { speed: 4 }); FX.pop(tx, ty - 14, 'SLURP-SMACK!', '#ff6aa8'); AudioSys.play_sfx('bite'); } }
          if (this.subT >= 20) this.setSub('RECOVERY');
        } else if (this.charge) { const c = this.charge; c.spd = approach(c.spd, 6.2, .35); this.x += c.dir * c.spd; this.play('charge'); AudioSys.setEngine(true, 1);
          if (this.t % 2 === 0) FX.smoke(this.wheelX() - c.dir * 30, this.ground - 10, -c.dir * 2);
          if (overlap(this.hitbox(), p)) p.hurt(1, this.cx);
          if ((c.dir > 0 && this.x + this.w > ar.b) || (c.dir < 0 && this.x < ar.a)) { this.charge = null; this.setSub('RECOVERY'); Cam.shake(6, 12); AudioSys.play_sfx('bash'); FX.dust(this.cx, this.ground, 14); FX.pop(this.cx, this.ground - 100, 'SKRRRT!', '#fff'); } }
        else this.setSub('RECOVERY');
        break; }
      case 'RECOVERY': {
        if (this.kind === 'tongue') { this.play('tongue'); const k = this.subT / 14; this.af = k < .5 ? 6 : 7; if (this.tongue) { const g = this.tongue; g.len = g.max * (this.af === 6 ? BIKER_TONGUE_EXT[6] * (1 - (k - 0) * .5) : 0); const [mx, my] = this.mouthWorld(); g.tip = [mx + g.dir[0] * g.len, my + g.dir[1] * g.len, mx, my]; if (g.len <= 0) this.tongue = null; } if (this.subT >= 14 + 30) { this.tongue = null; this.setSub('IDLE'); } }
        else { if (this.hitT === 0) this.play('idle'); this.dizzy = this.subT < 70; if (this.subT >= 80) { this.dizzy = false; this.face = sign(Game.player.cx - this.cx) || -this.face; this.setSub('IDLE'); } }
        break; }
    }
  }
  draw(cx, cy) {
    if (!BIKER_ANIMS.ready) return;
    const frames = BIKER_ANIMS[this.hitT > 0 ? 'hit' : this.anim] || BIKER_ANIMS.idle, fi = this.hitT > 0 ? Math.min(3, Math.floor((14 - this.hitT) / 4)) : this.af, img = frames[clamp(fi, 0, frames.length - 1)];
    const F = BIKER_FRAME, an = A('biker');
    // the frame anchor is the rear tyre contact; place it where the rear wheel is in world space
    const ax = F.ax - an.rearWheel[0] + an.rearWheel[0], X = this.wheelX() - cx, Y = this.ground - cy;
    if (this.st === 'FIGHTING' && this.sub === 'TELEGRAPH' && this.kind === 'charge' && this.t % 10 < 6) { for (let i = 0; i < 3; i++) O.poly([[X + this.face * (60 + i * 30), Y - 6], [X + this.face * (76 + i * 30), Y - 12], [X + this.face * (60 + i * 30), Y - 18]], '#ff3a3a', 1.5); }
    if (this.tongue && this.tongue.tip) { const [tx, ty, mx, my] = this.tongue.tip; drawTongue(mx - cx, my - cy, tx - cx, ty - cy, 6, 4, ['#3a0018', '#ff6aa8', '#ffc0dc']); }
    spr(img, X, Y + 1, { ax: F.ax, ay: F.ay, sx: HD, sy: HD, flip: this.face < 0, flash: this.flash > 4 ? '#fff' : false });
    if (this.dizzy) for (let i = 0; i < 3; i++) { const a2 = this.t * .15 + i * 2.1; ctx.drawImage(ICON.star, X + this.face * 55 + Math.cos(a2) * 16 - 7, Y - 100 + Math.sin(a2) * 4); }
    if (this.st === 'FIGHTING' && this.sub === 'TELEGRAPH' && this.kind === 'tongue') text('!', X + this.face * 60, Y - 112 + Math.sin(this.t * .5) * 2, { color: '#ff3a3a', align: 'center', outline: true, scale: 2 });
  }
}
// ---------------------------------------------------------------- the single encounter controller
class BikerEncounter extends Ent {
  constructor(o) { super(o.x0, 0, o.w, 9999); this.x0 = o.x0; this.w = o.w; this.o = o; this.gyPx = o.gy * TS; this.phase = 'INACTIVE'; this.boss = null; this.watch = 0; this.lastBossState = null; }
  update(L) {
    const p = Game.player;
    if (this.phase === 'INACTIVE') { if (p.x > this.x0 + 48 && !Game.cutscene && !p.dead) this.begin(L); return; }
    if (this.phase !== 'ACTIVE') return;
    const b = this.boss;
    // watchdog: the boss can never silently vanish mid-fight, and no state can hang forever
    if (!b || (b.dead && b.st !== 'COMPLETE') || !Game.ents.includes(b)) { this.boss = null; this.spawnBoss(true); return; }
    if (b.st === this.lastBossState && b.st !== 'FIGHTING') { if (++this.watch > 900) { b.setState(b.st === 'DEFEATED' ? 'EXITING' : b.st === 'EXITING' ? 'COMPLETE' : 'FIGHTING'); if (b.st === 'FIGHTING') { b.setSub('IDLE'); b.vulnerable = true; } this.watch = 0; } } else { this.watch = 0; this.lastBossState = b.st; }
    if (b.st === 'COMPLETE') this.complete(L);
  }
  begin(L) {
    this.phase = 'ACTIVE'; this.walls(L, true); L.camLock = { x0: this.x0 - 16, x1: this.x0 + this.w + 16 }; this.spawnBoss(false);
    AudioSys.setIntensity(2); Save.see('razz');
  }
  spawnBoss(resume) {
    const b = new BikerBoss(this); if (resume) { b.x = b.home - b.w / 2; b.setState('FIGHTING'); b.setSub('IDLE'); b.vulnerable = true; b.hp = this.lastHp || b.hp; }
    this.boss = b; Game.add(b); Game.boss = b; Game.bossHits = Game.player.hitTaken;
  }
  walls(L, on) { const a = Math.floor(this.x0 / TS) - 1, bx = Math.floor((this.x0 + this.w) / TS); for (let ty = 0; ty < this.o.gy; ty++) for (const tx of [a, bx]) { const t = L.get(tx, ty); if (t === T_EMPTY || t === T_WALL) L.tiles[L.idx(tx, ty)] = on ? T_WALL : T_EMPTY; } }
  complete(L) {
    this.phase = 'COMPLETE'; this.walls(L, false); L.camLock = null; Game.boss = null; AudioSys.setEngine(false); AudioSys.setIntensity(1); AudioSys.setBossPhase(1);
    for (const e of Game.ents) if (e instanceof EnemyShot || e === this.boss) e.dead = true;
    Save.achieve('biker'); if (Game.player.hitTaken === Game.bossHits) Save.achieve('noHit');
    Game.finishLevel();
  }
  onPlayerRespawn(L) { // player died mid-fight: reset the encounter cleanly so it can start again exactly once
    if (this.phase !== 'ACTIVE') return; if (this.boss) { this.lastHp = null; this.boss.dead = true; } this.boss = null; this.phase = 'INACTIVE'; this.walls(L, false); L.camLock = null; Game.boss = null; AudioSys.setEngine(false); AudioSys.setIntensity(1);
    for (const e of Game.ents) if (e instanceof EnemyShot) e.dead = true;
  }
}
