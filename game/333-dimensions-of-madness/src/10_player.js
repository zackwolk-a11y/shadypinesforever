// ============================================================================
// Player: the green monster (Moshmouth) + temporary pig heroes
// ============================================================================
const FORMS = { // transformations are now temporary power-ups collected in levels
  normal: { name: 'MOSHMOUTH', speed: 2.5, jump: 6.6, desc: 'Tongue, bones and a terrible attitude.' },
  pig: { name: 'PIG POWER', speed: 3.3, jump: 6.6, desc: 'ATTACK = unstoppable pig charge!' },
  wolf: { name: 'WOLF POWER', speed: 2.9, jump: 7.4, desc: 'ATTACK = HOWL shockwave. Double jump!' },
  cow: { name: 'COW POWER', speed: 2.4, jump: 6.6, desc: 'ATTACK = horn charge. In the air = MEGA STOMP!' },
  slime: { name: 'SLIME POWER', speed: 2.6, jump: 6.6, desc: 'ATTACK = triple slime spit!' },
  mega: { name: 'MEGA MONSTER', speed: 2.9, jump: 6.8, desc: 'Gigantic! Smash everything!' },
  bear: { name: 'BEAR', speed: 2.3, jump: 6.2, desc: '' }, clown: { name: 'CLOWN', speed: 2.6, jump: 7.0, desc: '' }
};
const POWER_TIME = 1200;
// Tongue strike: wind-up (telegraph) -> launch -> impact -> retract -> recovery. Frame counts at 60 fps.
// Launch/impact/retract follow the reference timings (0.15s / 0.1s / 0.2s); wind-up and recovery are
// trimmed for a player-controlled move (0.15s / 0.2s) so the button still feels responsive.
const TONGUE = { wind: 9, launch: 9, impact: 6, retract: 12, recover: 12, range: 96, aimCone: .9 };
const easeOutExpo = k => k >= 1 ? 1 : 1 - Math.pow(2, -10 * k);
const PIG_STATS = {
  hamwise: { w: 16, h: 20, speed: 2.5, jump: 6.0, desc: 'Glides on his straw hat. Kazoo HONK stuns.' },
  porkington: { w: 16, h: 26, speed: 2.3, jump: 6.4, desc: 'Throws sticks. BUILDS bridges at blueprints.' },
  trufflina: { w: 24, h: 30, speed: 2.1, jump: 5.7, desc: 'PUNCHES bricks. Carries bricks. Ground pound.' }
};
class Player {
  constructor(x, y) {
    this.x = x; this.y = y; this.w = 26; this.h = 30; this.vx = 0; this.vy = 0; this.face = 1; this.onGround = false; this.stepUp = true;
    this.maxHp = { easy: 8, normal: 5, hard: 3 }[Save.data.opt.diff] || 5; this.hp = this.maxHp; this.inv = 0;
    this.form = 'normal'; this.char = 'monster'; this.t = 0; this.anim = 'idle'; this.sq = 1; this.ssx = 1;
    this.coyote = 0; this.jumpBuf = 0; this.airJumps = 0; this.airDash = true;
    this.whipT = 0; this.whipCd = 0; this.whipDir = [1, 0]; this.spitCd = 0; this.bashT = 0; this.bashCd = 0; this.dashT = 0; this.dashCd = 0;
    this.scream = 0; this.screamCd = 0; this.screamT = 0; this.metal = 0; this.combo = 0; this.comboT = 0; this.bangT = 0; this.megaT = 0;
    this.grapple = null; this.tongueTip = null; this.attacks = []; this.blinkT = 120; this.dead = 0; this.safe = { x, y }; this.safeT = 0;
    this.stompT = 0; this.climb = false; this.transT = 0; this.carry = null; this.glide = false; this.stun = 0; this.frozen = false;
    this.summonSel = 0; this.grappleCount = 0; this.hitTaken = 0;
  }
  get cx() { return this.x + this.w / 2; } get cy() { return this.y + this.h / 2; }
  isPig() { return this.char !== 'monster'; }
  stats() { return this.isPig() ? PIG_STATS[this.char] : FORMS[this.form]; }
  setChar(c) {
    const bottom = this.y + this.h, mid = this.cx; this.char = c;
    const s = c === 'monster' ? (this.form === 'mega' ? { w: 40, h: 44 } : { w: 26, h: 30 }) : PIG_STATS[c];
    this.w = s.w; this.h = s.h; this.x = mid - this.w / 2; this.y = bottom - this.h;
  }
  setForm(f, silent) {
    if (this.form === f) return; const was = this.form; this.form = f; this.setChar('monster');
    if (!silent) { this.transT = 30; AudioSys.play_sfx('transform'); FX.ring(this.cx, this.cy, 60, '#7fff3a', 30); FX.burst(this.cx, this.cy, 30, ['#7fff3a', '#c8ff8a', '#fff'], { speed: 4 }); Cam.shake(3, 10); }
    if (f === 'mega') { this.megaT = 900; Save.achieve('mega'); }
  }
  hurt(dmg = 1, fromX) {
    if (this.inv > 0 || this.dead || G.cheatGod) return false;
    if (this.form === 'mega' && dmg < 3) { this.inv = 20; return false; }
    if (this.dashT > 0 && !this.isPig()) return false;
    this.hp -= dmg; this.inv = 100; this.hitTaken++; this.vy = -3.5; this.vx = (fromX !== undefined ? sign(this.cx - fromX) || -this.face : -this.face) * 3;
    this.grapple = null; AudioSys.play_sfx('hurt'); FX.stars(this.cx, this.y); Cam.shake(4, 10); G.hitstop = 4;
    if (this.isPig()) AudioSys.play_sfx('oink', { pitch: PIGS[this.char].pitch * 1.3 });
    if (this.hp <= 0) this.die();
    return true;
  }
  die() {
    if (this.dead) return; this.dead = 1; this.hp = 0; AudioSys.play_sfx('explode'); Cam.shake(6, 20); Save.data.deaths++; if (Save.data.deaths >= 50) Save.achieve('die50');
    FX.burst(this.cx, this.cy, 40, ['#7fff3a', '#2a8a1a', '#ff2a3a', '#fff'], { speed: 5 }); this.vx = this.vy = 0;
  }
  attack(box) { this.attacks.push(box); }
  // ------------------------------------------------------------------ update
  update(L) {
    this.t++; this.attacks = []; const I = Input, st = this.stats();
    if (this.dead) { this.dead++; if (this.dead > 50) Game.respawn(); return; }
    if (this.inv > 0) this.inv--; if (this.transT > 0) this.transT--; if (this.stun > 0) this.stun--;
    if (--this.blinkT < 0) this.blinkT = 90 + RI(0, 160);
    if (this.powerT > 0 && !Game.cutscene) { this.powerT--; if (this.powerT === 0) { this.setForm('normal'); HUD.toast('POWER-UP WORE OFF', '#fff'); } }
    if (this.atkCd > 0) this.atkCd--;
    if (this.comboT > 0 && --this.comboT === 0) this.combo = 0;
    const frozen = this.frozen || Game.cutscene;
    const left = !frozen && I.held.left, right = !frozen && I.held.right, up = !frozen && I.held.up, down = !frozen && I.held.down;
    const P_ = k => !frozen && I.pressed[k], H_ = k => !frozen && I.held[k];
    // timers
    ['whipCd', 'spitCd', 'bashCd', 'dashCd', 'screamCd'].forEach(k => { if (this[k] > 0) this[k]--; });
    if (this.whipT > 0) this.whipT--; if (this.bashT > 0) this.bashT--; if (this.screamT > 0) this.screamT--; if (this.bangT > 0) this.bangT--;
    if (this.jumpBuf > 0) this.jumpBuf--; if (P_('jump')) this.jumpBuf = 10;
    if (this.onGround) { this.airSpun = false; this.coyote = 9; this.airJumps = this.form === 'wolf' ? 1 : 0; this.airDash = true; } else if (this.coyote > 0) this.coyote--;
    const swim = inLiquid(this, L) && !L.liquidHazard;
    // ------------------------------------------------ grapple swinging
    if (this.grapple) { this.updateGrapple(L, left, right, up, down, P_); if (this.grapple) { this.postMove(L); return; } }
    // ------------------------------------------------ horizontal movement
    if ((left || right) && !(left && right) && this.dashT === 0) this.runT = Math.min(80, (this.runT || 0) + (this.onGround ? 1 : 0)); else this.runT = Math.max(0, (this.runT || 0) - 4);
    if (this.hitWall) this.runT = 0;
    this.sprint = this.runT > 45 && this.onGround;
    const max = st.speed * (this.stun ? .4 : 1) * (swim ? .7 : 1) * (1 + Math.min(1, this.runT / 70) * .32);
    if (this.dashT > 0) {
      this.dashT--; this.vx = this.face * (this.form === 'pig' ? 5.2 : this.form === 'cow' ? 4.8 : 6); this.vy = this.onGround ? this.vy : Math.min(this.vy, .5);
      const dmg = this.form === 'pig' || this.form === 'cow' ? 3 : 2;
      this.attack({ x: this.x - 4, y: this.y, w: this.w + 8, h: this.h, dmg, kind: 'dash', dir: this.face });
      this.breakTiles(L, this.face > 0 ? this.x + this.w + 2 : this.x - 2, this.y + 2, this.y + this.h - 2);
      if (this.t % 3 === 0) FX.dust(this.cx - this.face * 10, this.y + this.h, 2);
      if (this.hitWall) this.dashT = 0;
    } else {
      const acc = this.onGround ? .5 : .32;
      if (left && !right) { this.vx = approach(this.vx, -max, acc); this.face = -1; }
      else if (right && !left) { this.vx = approach(this.vx, max, acc); this.face = 1; }
      else this.vx = approach(this.vx, 0, this.onGround ? .4 : .12);
    }
    // conveyor / wind
    if (this.onGround && this.groundTile === T_CONVL) this.x -= 1.2; if (this.onGround && this.groundTile === T_CONVR) this.x += 1.2;
    if (L.wind) this.vx += L.wind * (this.form === 'cow' || this.char === 'trufflina' ? .3 : 1) * (this.onGround ? .5 : 1);
    // ------------------------------------------------ bear climbing
    this.climb = false;
    if (this.form === 'bear' && !this.onGround && this.hitWallLast && ((this.hitWallLast > 0 && right) || (this.hitWallLast < 0 && left))) {
      this.climb = true; this.vy = up ? -1.8 : down ? 1.8 : 0; this.airJumps = 0;
      if (this.t % 10 === 0) FX.dust(this.hitWallLast > 0 ? this.x + this.w : this.x, this.cy, 1);
    }
    // ------------------------------------------------ jumping
    const jv = st.jump;
    const gd = L.gravity < 0 ? -1 : 1;
    if (this.jumpBuf && (this.coyote > 0 || swim || this.climb)) {
      this.vy = (swim ? -3.6 : -jv) * gd; this.coyote = 0; this.jumpBuf = 0; this.sq = .7; AudioSys.play_sfx('jump'); FX.dust(this.cx, this.y + this.h, 4);
      if (this.climb) { this.vx = -this.hitWallLast * 3.2; this.face = -this.hitWallLast; }
    } else if (this.jumpBuf && this.airJumps > 0) {
      this.airJumps--; this.vy = -jv * .9 * gd; this.jumpBuf = 0; this.sq = .7; AudioSys.play_sfx('jump'); FX.ring(this.cx, this.y + this.h, 18, '#aab', 14, 2);
    }
    // gravity (variable jump height + glide + liquid)
    let g = PHYS.grav; if (this.vy * gd < 0 && H_('jump')) g *= .62; if (swim) g *= .35;
    if (this.climb) g = 0; if (this.bashT > 0 && !this.onGround) g *= .4;
    if (this.dashT > 0 && !this.onGround) g = 0;
    this.vy += g * L.gravity;
    let maxFall = swim ? 1.8 : PHYS.maxFall;
    if (this.char === 'hamwise' && H_('jump') && this.vy * gd > 0) { maxFall = 1.0; this.glide = true; } else this.glide = false;
    if (this.bashT > 0) maxFall = 1.6;
    if (this.stompT > 0) { this.vy = 8 * gd; maxFall = 8; }
    this.vy = gd > 0 ? Math.min(this.vy, maxFall) : Math.max(this.vy, -maxFall);
    // ------------------------------------------------ abilities
    if (!this.isPig()) this.monsterAbilities(L, up, down, P_, H_, I);
    else this.pigAbilities(L, up, down, P_, H_);
    this.dropThrough = down && H_('jump') && this.onGround;
    this.postMove(L);
  }
  postMove(L) {
    const wasG = this.onGround, vyBefore = this.vy;
    this.riding = null; moveBody(this, L);
    if (this.hitWall && L.solidEnts) for (const s of L.solidEnts) if (s.push && Math.abs((this.hitWall > 0 ? this.x + this.w : this.x) - (this.hitWall > 0 ? s.x : s.x + s.w)) < 3 && this.y + this.h > s.y + 4 && this.y < s.y + s.h) s.push(this.hitWall);
    this.hitWallLast = this.hitWall || (this.climb ? this.hitWallLast : 0);
    if (this.form === 'bear' && !this.hitWall && this.climb) { const probe = this.hitWallLast > 0 ? this.x + this.w + 1 : this.x - 1; if (!L.solidAt(Math.floor(probe / TS), Math.floor(this.cy / TS))) this.hitWallLast = 0; }
    if (this.riding && this.riding.dx) this.x += this.riding.dx;
    if (!wasG && this.onGround) {
      this.sq = clamp(1 + vyBefore * .06, 1, 1.45); if (vyBefore > 3) { FX.dust(this.cx, this.y + this.h, 5); AudioSys.play_sfx('land'); }
      if (this.stompT > 0) { this.stompT = 0; this.shock(L, 70, 3); }
      if (this.form === 'clown' && vyBefore > 2.5 && !Input.held.down) { this.vy = -vyBefore * .7; this.onGround = false; AudioSys.play_sfx('boing'); }
      if (this.char === 'trufflina' && this.pound) { this.pound = false; this.shock(L, 40, 2); }
    }
    // springs
    if (this.onGround && this.groundTile === T_SPRING) { this.vy = -10.5; this.onGround = false; AudioSys.play_sfx('boing'); L.springAnim = L.springAnim || {}; L.springAnim[this.groundTx + ',' + this.groundTy] = 12; this.sq = .6; }
    if (L.springAnim) for (const k in L.springAnim) if (L.springAnim[k] > 0) L.springAnim[k]--;
    // crumble blocks
    if (this.onGround && this.groundTile === T_CRUMBLE) { const k = L.idx(this.groundTx, this.groundTy); if (!L.crumbles.has(k)) L.crumbles.set(k, { t: 0 }); }
    // mega smashes blocks just by walking
    if (this.form === 'mega') this.breakTiles(L, this.face > 0 ? this.x + this.w + 2 : this.x - 2, this.y, this.y + this.h - 2);
    // hazards / pits
    if (overlapsHazard(this, L)) { if (this.hurt(1)) { this.vy = -6; } }
    if (this.y > L.h * TS + 30 || this.y < -60) { this.fallOut(); }
    if (this.onGround && !overlapsHazard(this, L) && this.groundTile !== T_CRUMBLE && this.groundTile !== T_BEATA && this.groundTile !== T_BEATB && !this.riding) { if (++this.safeT > 6) this.safe = { x: this.x, y: this.y }; } else this.safeT = 0;
    this.sq = lerp(this.sq, 1, .2);
    this.x = clamp(this.x, 0, L.w * TS - this.w);
    if (L.autoScroll) { if (this.x < Cam.x + 4) { this.x = Cam.x + 4; if (this.hitWall > 0) this.hurt(9); } }
  }
  fallOut() {
    if (this.dead) return; if (!G.cheatGod) this.hp -= 1; AudioSys.play_sfx('hurt');
    if (this.hp <= 0) { this.die(); return; }
    this.x = this.safe.x; this.y = this.safe.y - 4; this.vx = this.vy = 0; this.inv = 90; this.grapple = null; FX.ring(this.cx, this.cy, 40, '#7fff3a');
  }
  breakTiles(L, px, y0, y1) {
    const tx = Math.floor(px / TS); let broke = false;
    for (let ty = Math.floor(y0 / TS); ty <= Math.floor(y1 / TS); ty++) if (L.get(tx, ty) === T_BREAK) { L.set(tx, ty, T_EMPTY); broke = true; FX.burst(tx * TS + 8, ty * TS + 8, 10, [L.theme.g[1], L.theme.g[0], L.theme.top], { speed: 3 }); }
    if (broke) { AudioSys.play_sfx('break'); Cam.shake(2, 6); }
    return broke;
  }
  shock(L, r, dmg) {
    AudioSys.play_sfx('bash'); AudioSys.play_sfx('rumble'); Cam.shake(6, 14); FX.ring(this.cx, this.y + this.h, r, '#fff', 20, 4); FX.dust(this.cx - 20, this.y + this.h, 6); FX.dust(this.cx + 20, this.y + this.h, 6);
    this.attack({ x: this.cx - r, y: this.y + this.h - 30, w: r * 2, h: 40, dmg, kind: 'stomp' });
    for (let dx = -2; dx <= 2; dx++) { const tx = Math.floor(this.cx / TS) + dx, ty = Math.floor((this.y + this.h + 4) / TS); if (L.get(tx, ty) === T_BREAK) { L.set(tx, ty, T_EMPTY); FX.burst(tx * TS + 8, ty * TS + 8, 10, L.theme.g); } }
  }
  // ------------------------------------------------------------------ ONE BUTTON: contextual ATTACK
  setPower(kind) { this.setForm(kind); this.powerT = POWER_TIME; this.powerMax = POWER_TIME; }
  monsterAbilities(L, up, down, P_, H_) {
    if (P_('whip')) { if (this.atkCd > 0) this.atkBuf = 8; else this.contextAttack(L, up, down); }
    else if (this.atkBuf > 0 && --this.atkBuf >= 0 && this.atkCd === 0) { this.atkBuf = 0; this.contextAttack(L, up, down); }
    const f = this.form, big = f === 'mega' ? 1.6 : 1;
    this.updateTongue(L);
    if (this.bashT > 0) { const r = 30 * big; this.attack({ x: this.cx - r, y: this.cy - r, w: r * 2, h: r * 2, dmg: 2, kind: 'bash', reflect: true, knock: 6 }); if (this.bashT % 6 === 0) { AudioSys.play_sfx('whip'); for (const dx of [-r * .8, r * .8]) this.breakTiles(L, this.cx + dx, this.y + 2, this.y + this.h - 2); } }
    if (this.form === 'wolf' && this.screamT > 0 && this.screamT % 8 === 0) FX.ring(this.cx, this.cy, 150, '#fff', 20, 3);
  }
  contextAttack(L, up, down) {
    const f = this.form, G_ = Game; this.atkCd = 14; this.idleT = 0; const air = !this.onGround || Math.abs(this.vy) > 1;
    const near = (cls, r) => G_.ents.find(e => !e.dead && e instanceof cls && Math.abs(e.cx - this.cx) < r && Math.abs(e.cy - this.cy) < r + 20);
    // 0) swing: ANY attack (normal or power-up, in the air or on the ground) grabs a hook that is close enough
    { const h = G_.nearestHook(this); if (h && (air || h.y < this.cy - 24)) { this.startGrapple(h, !air); return; } }
    // 1) power-up attacks
    if (f === 'slime') { const [mx, my] = heroMouth(this.cx, this.cy, this.face, f); for (const a of [-.25, 0, .25]) G_.add(new SlimeBall(mx, my - 2, this.face * 5.5, -1.5 + a * 6, true, 2)); AudioSys.play_sfx('spit'); this.screamT = 10; return; }
    if (f === 'wolf') { this.screamT = 30; this.atkCd = 40; AudioSys.play_sfx('howl'); Cam.shake(4, 16); FX.ring(this.cx, this.cy, 150, '#fff', 30, 4); G_.stunAll(this.cx, this.cy, 150, 150); this.attack({ x: this.cx - 150, y: this.cy - 120, w: 300, h: 240, dmg: 2, kind: 'howl', circle: 150 }); G_.megaScream(this.cx, this.cy, 150); return; }
    if (f === 'pig') { this.dashT = 30; this.atkCd = 30; AudioSys.play_sfx('oink', { pitch: 1 }); FX.ring(this.cx, this.cy, 24, '#ff8ab0', 10, 2); return; }
    if (f === 'cow') { if (air) { this.stompT = 1; AudioSys.play_sfx('moo'); } else { this.dashT = 28; this.atkCd = 30; AudioSys.play_sfx('moo'); } return; }
    if (f === 'mega') { this.bashT = 26; this.atkCd = 20; AudioSys.play_sfx('bash'); Cam.shake(3, 8); return; }
    // 3) interact with things nearby
    const sw = G_.ents.find(e => !e.dead && e instanceof Switch && !e.on && Math.abs(e.cx - this.cx) < 70 && Math.abs(e.cy - this.cy) < 90); if (sw) { this.face = sign(sw.cx - this.cx) || this.face; this.startTongue({ target: sw, onReach: () => sw.activate() }); return; }
    const bp = G_.ents.find(e => !e.dead && e instanceof Blueprint && !e.built && this.cx > e.x - 40 && this.cx < e.x + e.w + 40 && Math.abs(e.y - this.y) < 80); if (bp) { bp.build(); return; }
    const site = G_.ents.find(e => !e.dead && e instanceof HouseSite && !e.built && !e.gone && Math.abs(e.cx - this.cx) < 90); if (site) { site.activate(); return; }
    const amp = near(AmpTotem, 70); if (amp) { this.bashT = 20; amp.blow(); return; }
    const crate = G_.ents.find(e => !e.dead && e instanceof Pullable && Math.abs(e.cy - this.cy) < 30 && Math.abs(e.cx - this.cx) < 140 && Math.abs(e.cx - this.cx) > 30); if (crate) { this.face = sign(crate.cx - this.cx); this.startTongue({ target: crate, onReach: () => crate.pull(sign(this.cx - crate.cx)) }); return; }
    // 4) breakable wall right in front -> bone bash
    const fx = this.face > 0 ? this.x + this.w + 10 : this.x - 10; let brk = false; for (let y = this.y + 2; y < this.y + this.h; y += 8) if (L.get(Math.floor(fx / TS), Math.floor(y / TS)) === T_BREAK) brk = true;
    if (brk) { this.bashT = 20; AudioSys.play_sfx('bash'); this.breakTiles(L, fx, this.y + 2, this.y + this.h - 2); this.breakTiles(L, fx + this.face * 16, this.y + 2, this.y + this.h - 2); return; }
    // 5) in the air -> aerial bone spin
    if (air) { if (this.airSpun) { this.startTongue({ up }); return; } this.airSpun = true; this.bashT = 22; AudioSys.play_sfx('bash'); return; }
    // 6) running fast -> rolling attack
    if (this.runT > 45 && Math.abs(this.vx) > 2.6) { this.dashT = 22; this.atkCd = 26; AudioSys.play_sfx('dash'); FX.ring(this.cx, this.cy, 24, '#fff', 10, 2); return; }
    // 7) default -> tongue whip (up if holding up)
    this.startTongue({ up });
  }
  unleashScream(L) {
    const c = this.scream / 60, mega = this.metal >= 100 || this.form === 'mega'; this.scream = 0; this.screamCd = 50; this.screamT = 36;
    let r = 50 + c * 100, dmg = 1 + Math.floor(c * 2.5);
    if (mega && c > .9) { r = 230; dmg = 5; if (this.form !== 'mega') this.metal = 0; HUD.toast('METAL SCREAM!!!', '#7fff3a'); Game.megaScream(this.cx, this.cy, r); }
    AudioSys.play_sfx('scream', { power: c + (mega ? 1 : 0) }); Cam.shake(3 + c * 6, 16 + c * 10);
    for (let i = 0; i < 3; i++) FX.ring(this.cx, this.cy, r * (1 - i * .2), i ? '#c8ff8a' : '#7fff3a', 22 + i * 6, 4 - i);
    this.attack({ x: this.cx - r, y: this.cy - r, w: r * 2, h: r * 2, dmg, kind: 'scream', circle: r, reflect: true });
    Game.stunAll(this.cx, this.cy, r, 60 + c * 60); Game.soundSwitch(this.cx, this.cy, r);
    if (c > .5) for (let a = 0; a < 6.283; a += .5) this.breakTiles(L, this.cx + Math.cos(a) * r * .6, this.cy + Math.sin(a) * r * .6, this.cy + Math.sin(a) * r * .6);
    if (!Save.data.ach.firstScream) Save.achieve('firstScream');
  }
  onBeatBonus() { if (AudioSys.onBeatWindow(.18)) { this.metal = Math.min(100, this.metal + 2); FX.notes(this.cx, this.y, 1); } }
  headbang() {
    this.bangT = 14;
    if (AudioSys.onBeatWindow(.2)) {
      this.combo++; this.comboT = 120; this.metal = Math.min(100, this.metal + 5 + Math.min(10, this.combo));
      AudioSys.play_sfx('headbang', { combo: this.combo }); FX.notes(this.cx, this.y - 6, 2); FX.ring(this.cx, this.cy, 30 + this.combo * 2, '#ffe14d', 12, 2);
      if (this.combo >= 4) this.attack({ x: this.cx - 40, y: this.cy - 30, w: 80, h: 60, dmg: 1, kind: 'bang' });
      if (this.combo >= 20) Save.achieve('combo20');
      Game.onHeadbang && Game.onHeadbang(this);
    } else { this.combo = 0; AudioSys.play_sfx('miss'); }
  }
  // ------------------------------------------------------------------ tongue strike
  startTongue(o = {}) {
    if (this.tng) { this.atkBuf = 8; return false; } // never two tongues at once
    this.tng = { ph: 'wind', t: 0, len: 0, hit: false, up: !!o.up, target: o.target, onReach: o.onReach, dir: null };
    this.atkCd = TONGUE.wind + TONGUE.launch + TONGUE.impact + TONGUE.retract + TONGUE.recover;
    AudioSys.play_sfx('charge'); return true;
  }
  tongueAim() { // aim at the nearest enemy/boss in front (or above when holding UP), else straight ahead
    const g = this.tng, [mx, my] = heroMouth(this.cx, this.cy, this.face, this.form), base = g.up ? [0, -1] : [this.face, 0];
    if (g.target) { const d = Math.hypot(g.target.cx - mx, g.target.cy - my) || 1; return [(g.target.cx - mx) / d, (g.target.cy - my) / d]; }
    let best = null, bd = TONGUE.range * (this.form === 'mega' ? 1.5 : 1) + 24;
    for (const e of Game.ents) { if (e.dead || !((e instanceof Enemy && e.wake) || e.isBoss)) continue; const hb = e.hitbox ? e.hitbox() : e, ex = hb.x + hb.w / 2, ey = hb.y + hb.h / 2, d = Math.hypot(ex - mx, ey - my); if (d > bd) continue; const dot = ((ex - mx) * base[0] + (ey - my) * base[1]) / (d || 1); if (dot < TONGUE.aimCone) continue; bd = d; best = [(ex - mx) / d, (ey - my) / d]; }
    return best || base;
  }
  tongueFrame() { // which of the 8 supplied frames to show for the current phase
    const g = this.tng, T = TONGUE; if (!g) return -1;
    switch (g.ph) { case 'wind': return g.t < 4 ? 0 : 1; case 'launch': return g.t < 3 ? 2 : 3; case 'impact': return 4; case 'retract': return g.t < T.retract / 2 ? 5 : 6; case 'recover': return 7; }
    return -1;
  }
  updateTongue(L) {
    const g = this.tng; if (!g) { if (!this.grapple) this.tongueTip = null; return; }
    g.t++; const T = TONGUE;
    if (g.ph === 'wind') { if (g.t >= T.wind) { g.dir = [this.face, 0]; g.ph = 'launch'; g.t = 0; AudioSys.play_sfx('whip'); } }
    else if (g.ph === 'launch') { if (g.t >= T.launch) { g.ph = 'impact'; g.t = 0; } }
    else if (g.ph === 'impact') { if (g.t >= T.impact) { g.ph = 'retract'; g.t = 0; AudioSys.play_sfx('slurp'); } }
    else if (g.ph === 'retract') { if (g.t >= T.retract) { g.ph = 'recover'; g.t = 0; } }
    else if (g.ph === 'recover') { if (g.t >= T.recover) { this.tng = null; this.tongueTip = null; return; } }
    const fi = this.tongueFrame(), cyy = this.y + this.h / 2 - 4 + (this.onGround ? 0 : 0);
    const tip = (g.ph === 'launch' || g.ph === 'impact' || g.ph === 'retract') ? tongueTipWorld(this.cx, cyy, this.face, fi, this.form === 'mega' ? 1.5 : 1) : null;
    const [mx, my] = heroMouth(this.cx, this.cy, this.face, this.form);
    g.len = tip ? Math.hypot(tip[0] - this.cx, tip[1] - cyy) : 0;
    this.tongueTip = tip ? [tip[0], tip[1], mx, my] : (this.grapple ? this.tongueTip : null);
    if (tip && (g.ph === 'launch' || g.ph === 'impact') && !g.hit) {
      const [tx, ty] = tip;
      // the tongue's own hitbox rides the drawn tongue tip; live only while it lashes out / at full reach; one damage event per strike
      this.attack({ x: Math.min(tx, mx) - 8, y: ty - 12, w: Math.abs(tx - mx) * .5 + 20, h: 24, dmg: 2, kind: 'whip', dir: this.face, tongue: true, knock: 6, onHit: () => this.tongueHit(tx, ty) });
      this.attack({ x: tx - 12, y: ty - 12, w: 24, h: 24, dmg: 2, kind: 'whip', dir: this.face, tongue: true, knock: 6, onHit: () => this.tongueHit(tx, ty) });
      if (L.get(Math.floor(tx / TS), Math.floor(ty / TS)) === T_BREAK || L.get(Math.floor((tx + this.face * 6) / TS), Math.floor((ty - 10) / TS)) === T_BREAK) { this.breakTiles(L, tx, ty - 12, ty + 4); this.tongueHit(tx, ty); }
      if (g.target && g.onReach && g.ph === 'impact') { g.onReach(); g.onReach = null; this.tongueHit(tx, ty); }
    }
  }
  tongueHit(tx, ty) {
    const g = this.tng; if (!g || g.hit) return; g.hit = true;
    if (g.ph === 'launch') { g.ph = 'impact'; g.t = 0; }
    FX.burst(tx, ty, 14, ['#fff', '#ffe14d', '#ff3a3a'], { speed: 3.5 }); FX.ring(tx, ty, 18, '#fff', 10, 3); FX.pop(tx, ty - 10, pick(['THWACK!', 'SHLAP!', 'SPLORT!']), '#fff'); AudioSys.play_sfx('bite'); Cam.shake(2, 5); G.hitstop = Math.max(G.hitstop, 3);
  }
  // ------------------------------------------------------------------ grapple
  startGrapple(h, fromGround) {
    this.tng = null; this.dashT = 0; this.bashT = 0;
    const dx = this.cx - h.x, dy = this.cy - h.y; const len = clamp(Math.hypot(dx, dy) - (fromGround ? 16 : 0), 30, 130);
    this.grapple = { h, len, ang: Math.atan2(dx, dy), av: 0 };
    const tang = Math.cos(this.grapple.ang) * this.vx - Math.sin(this.grapple.ang) * this.vy; this.grapple.av = tang / len;
    // from the ground: yank up off the floor and kick the swing off in the facing direction
    if (fromGround) { this.onGround = false; this.y -= 6; this.grapple.av += this.face * .05; }
    AudioSys.play_sfx('slurp'); this.grappleCount++; if (this.grappleCount >= 50) Save.achieve('allGrapple');
  }
  updateGrapple(L, left, right, up, down, P_) {
    const g = this.grapple; const acc = -PHYS.grav / g.len * Math.sin(g.ang) * 1.1;
    g.av += acc; if (left) g.av -= .0016; if (right) g.av += .0016; g.av *= .995;
    if (up) g.len = Math.max(26, g.len - 1.2); if (down) g.len = Math.min(140, g.len + 1.2);
    g.ang += g.av;
    const nx = g.h.x + Math.sin(g.ang) * g.len - this.w / 2, ny = g.h.y + Math.cos(g.ang) * g.len - this.h / 2;
    this.vx = nx - this.x; this.vy = ny - this.y; this.face = this.vx >= 0 ? 1 : -1;
    const [mx, my] = heroMouth(this.cx, this.cy, this.face, this.form); this.tongueTip = [g.h.x, g.h.y, mx, my];
    if (P_('jump') || P_('grapple') || (P_('whip'))) {
      this.grapple = null; this.vy = Math.min(this.vy, 0) - 3.4; this.vx *= 1.25; this.airDash = true; this.tongueTip = null; AudioSys.play_sfx('jump'); FX.ring(this.cx, this.cy, 16, '#ff7a8a', 10, 2);
    }
    this.attack({ x: this.x - 4, y: this.y - 4, w: this.w + 8, h: this.h + 8, dmg: 1, kind: 'swing' });
    if (this.grapple && (this.hitWall || this.hitCeil || this.onGround)) { if (this.onGround) { this.grapple = null; this.tongueTip = null; } else g.av *= -.4; }
  }
  // ------------------------------------------------------------------ pig abilities
  pigAbilities(L, up, down, P_, H_) {
    const c = this.char;
    if (P_('whip') && this.whipCd === 0) {
      if (c === 'hamwise') { this.whipT = 20; this.whipCd = 45; AudioSys.play_sfx('honk'); FX.ring(this.cx, this.cy, 70, '#ffd860', 20, 3); Game.stunAll(this.cx, this.cy, 70, 150); this.attack({ x: this.cx - 70, y: this.cy - 70, w: 140, h: 140, dmg: 0, kind: 'honk' }); Game.soundSwitch(this.cx, this.cy, 70); }
      else if (c === 'porkington') {
        const bp = Game.findEnt(e => e instanceof Blueprint && !e.built && overlap(e, this));
        if (bp) bp.build(); else { this.whipCd = 22; Game.add(new StickProj(this.cx, this.y + 6, this.face * 4.5, -2.5)); AudioSys.play_sfx('throw'); }
      }
      else if (c === 'trufflina') {
        this.whipT = 14; this.whipCd = 22; AudioSys.play_sfx('bash');
        const slot = this.carry && Game.findEnt(e => e instanceof BrickSlot && !e.filled && Math.abs(e.x + 8 - this.cx) < 40 && Math.abs(e.y - this.y) < 60);
        if (slot) { slot.fill(); this.carry = null; }
      }
    }
    if (c === 'trufflina' && this.whipT > 4) { this.attack({ x: this.face > 0 ? this.x + this.w - 4 : this.x - 22, y: this.y, w: 26, h: this.h, dmg: 2, kind: 'punch', knock: 6 }); if (this.whipT === 10) this.breakTiles(L, this.face > 0 ? this.x + this.w + 6 : this.x - 6, this.y, this.y + this.h - 2); }
    if (c === 'trufflina' && down && P_('jump') && !this.onGround) { this.pound = true; this.vy = 7; }
    if (P_('spit') || P_('dash')) { if (c === 'hamwise' && this.onGround) { this.vx = this.face * 4; } }
  }
  // ------------------------------------------------------------------ draw
  draw(cx, cy) {
    if (this.dead) {
      const k = this.dead; if (k < 30) drawHero(this.cx - cx, this.cy - cy + k * .3, { face: this.face, sy: 1 - k / 40, sx: 1 + k / 60, flash: k % 4 < 2 ? '#fff' : false });
      else if (k < 70) { spr(ICON.skull, this.cx - cx, this.cy - cy - (k - 30) * .8, { sx: 2, sy: 2, ay: 6, alpha: 1 - (k - 30) / 40 }); if (k % 5 === 0) FX.smoke(this.cx, this.cy, 0); }
      return;
    }
    if (this.inv > 0 && Math.floor(this.inv / 4) % 2 && this.inv < 90) return;
    const x = this.cx - cx, y = this.y + this.h - cy;
    if (this.isPig()) {
      const st = !this.onGround ? 'jump' : Math.abs(this.vx) > .3 ? (Math.abs(this.vx) > 2.2 ? 'run' : 'walk') : this.whipT > 0 ? 'attack' : 'idle';
      drawPig(this.char, x, y + 1, { face: this.face, state: this.inv > 80 ? 'hurt' : this.whipT > 0 ? 'attack' : st, sq: this.sq, t: this.t / 60 });
      if (this.glide) { P.e(ctx, x, y - 44, 18, 4, '#000'); P.e(ctx, x, y - 44, 17, 3, '#ffd860'); }
      if (this.carry) spr(ICON.brick, x, y - this.h - 18, { sx: 1, sy: 1 });
      if (this.char === 'hamwise' && this.whipT > 0) P.r(ctx, x + this.face * 10, y - 26, 8, 3, '#ff3a6a');
      return;
    }
    // squash/stretch, roll, headbang tilt, bounce
    let sx = 1 / this.sq, sy = this.sq, rot = 0;
    const moving = Math.abs(this.vx) > .4 && this.onGround;
    if (moving) { const b = Math.abs(Math.sin(this.t * .25)); sy *= 1 - b * .07; sx *= 1 + b * .05; }
    if (!this.onGround && !this.grapple) { sy *= this.vy < 0 ? 1.08 : .96; sx *= this.vy < 0 ? .94 : 1.04; }
    if (this.dashT > 0) rot = this.t * .55 * this.face;                       // Mosh Dash = rolling
    else if (this.sprint && Math.abs(this.vx) > 3) { rot = this.t * .35 * this.face; if (this.t % 4 === 0) FX.dust(this.cx - this.face * 12, this.y + this.h, 1); }
    else if (Math.abs(this.vx) > 2.4 && this.onGround) rot = Math.sin(this.t * .3) * .12;
    if (this.bangT > 0) rot = Math.sin((14 - this.bangT) / 14 * Math.PI) * .5 * this.face;
    if (this.grapple) rot = -this.grapple.ang * .6;
    if (this.climb) rot = this.hitWallLast * -.3;
    if (this.stompT > 0) { sy *= 1.2; sx *= .85; }
    const bob = this.onGround && !moving ? Math.round(Math.sin(this.t * .07) * 1.5) : moving ? -Math.round(Math.abs(Math.sin(this.t * .25)) * 4) : 0;
    const cyy = y - this.h / 2 - 4 + bob;
    // tongue behind face when whipping/grappling
    const tg = this.tng, tk = tg ? tg.t / (TONGUE[tg.ph] || 1) : 0;
    let px2 = 0; if (tg && tg.ph === 'wind') px2 = -this.face * 2 * tk; else if (tg && (tg.ph === 'launch' || tg.ph === 'impact')) px2 = this.face * 2;
    if (this.grapple && this.tongueTip) { const [tx, ty, mx, my] = this.tongueTip; drawTongue(mx - cx, my - cy + bob, tx - cx, ty - cy, this.form === 'mega' ? 9 : 7, 2); }
    // bone bash spin trail
    if (this.bashT > 0) { ctx.save(); ctx.globalAlpha = .5; ctx.strokeStyle = '#fff6d0'; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(x, cyy, 30 * (this.form === 'mega' ? 1.6 : 1), 0, 7); ctx.stroke(); ctx.restore(); rot = (26 - this.bashT) * .5; }
    // shadow
    if (this.onGround) { ctx.fillStyle = 'rgba(0,0,0,.3)'; ctx.beginPath(); ctx.ellipse(x, y, 14 * (this.form === 'mega' ? 1.6 : 1), 3, 0, 0, 7); ctx.fill(); }
    const blink = this.blinkT < 6 ? 1 - Math.abs(this.blinkT - 3) / 3 : 0;
    let mouth = this.screamT > 0 ? Math.min(1, this.screamT / 10) : 0;
    if (tg) mouth = tg.ph === 'wind' ? .45 + .5 * ease.out(tk) : tg.ph === 'recover' ? .9 * (1 - tk) : .95;
    if (this.gdir < 0) { sy = -sy; }
    if (tg && !this.isPig() && IMG.hero_tongue && IMG.hero_tongue.length) { drawTongueFrame(this.cx - cx + px2, this.y + this.h / 2 - 4 - cy, this.face, this.tongueFrame(), { scale: this.form === 'mega' ? 1.5 : 1, flash: this.inv > 88 ? '#ff3a3a' : false }); }
    else drawHero(x + px2, this.gdir < 0 ? this.y + this.h / 2 - cy : cyy, { closed: true, face: this.face, sx, sy, rot, blink, mouth, form: this.form, aura: this.transT > 0 || this.scream > 40 || this.metal >= 100 && this.t % 30 < 15, flash: this.inv > 88 ? '#ff3a3a' : false });
    if (this.scream > 10) { ctx.strokeStyle = `rgba(127,255,58,${this.scream / 60})`; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(x, cyy, 40 - (this.t % 10) * 2, 0, 7); ctx.stroke(); }
    if (this.stun) text('?!', x, cyy - 40, { color: '#ffe14d', align: 'center' });
    if (this.megaT > 0 && this.megaT < 180 && this.t % 20 < 10) text(Math.ceil(this.megaT / 60) + '', x, cyy - 60, { color: '#7fff3a', align: 'center', scale: 2 });
  }
}
// party follower (inactive pigs follow the active hero)
class PigFollower {
  constructor(id, x, y) { this.id = id; this.x = x; this.y = y; this.w = 16; this.h = 20; this.vx = 0; this.vy = 0; this.face = 1; this.onGround = false; this.t = 0; this.stepUp = true; }
  update(L, target, slot) {
    this.t++; this.cool = (this.cool || 0) - 1;
    if (this.cool <= 0 && Game.boss && !Game.boss.defeated && Math.abs(Game.boss.cx - this.x) < 220 && this.t % 360 === 0) { this.cool = 90; const bz = Game.boss; FX.pop(this.x, this.y - 30, { hamwise: 'HONK!!', porkington: 'STICK ATTACK!', trufflina: 'PIG PUNCH!' }[this.id], '#ff8ab0'); AudioSys.play_sfx(this.id === 'hamwise' ? 'honk' : 'bash'); bz.inv = 0; bz.hit(1, { kind: 'ally' }); }
    if (this.cool <= 0) { const e = Game.ents.find(e => e instanceof Enemy && !e.dead && e.wake && Math.abs(e.cx - this.x) < 90 && Math.abs(e.cy - this.y) < 50); if (e) { this.cool = 70; if (this.id === 'hamwise') { e.stun(120); AudioSys.play_sfx('honk'); FX.ring(this.x + 8, this.y + 10, 50, '#ffd860', 16, 2); FX.pop(this.x, this.y - 30, 'HONK!', '#ffd860'); } else if (this.id === 'porkington') { Game.add(new StickProj(this.x + 8, this.y + 4, sign(e.cx - this.x) * 4.5, -2.5)); AudioSys.play_sfx('throw'); } else { e.hit(2, { dir: sign(e.cx - this.x), knock: 7 }); AudioSys.play_sfx('bash'); FX.pop(this.x, this.y - 30, 'KAPOW!', '#ff3a4a'); } } } const tx = target.cx - target.face * (28 + slot * 22), d = tx - (this.x + this.w / 2);
    this.vx = approach(this.vx, clamp(d * .08, -2.6, 2.6), .3); if (Math.abs(d) > 4) this.face = sign(d);
    if (this.onGround && (this.hitWall || (target.y + target.h < this.y - 20 && Math.abs(d) < 60))) this.vy = -6;
    this.vy = Math.min(this.vy + PHYS.grav, 6); moveBody(this, L);
    if (Math.abs(d) > 260 || this.y > L.h * TS) { this.x = target.x; this.y = target.y - 10; this.vx = this.vy = 0; FX.ring(this.x + 8, this.y + 10, 20, '#ff8ab0'); }
  }
  draw(cx, cy) { drawPig(this.id, this.x + this.w / 2 - cx, this.y + this.h - cy + 1, { face: this.face, state: !this.onGround ? 'jump' : Math.abs(this.vx) > .3 ? 'walk' : 'idle', t: this.t / 60 + this.id.length, alpha: .92 }); }
}
