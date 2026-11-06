// ============================================================================
// Allies, summons, chase & race sequences
// ============================================================================
class UdderlyAlly extends Ent { // Captain Udderly flies alongside and assists in fights
  constructor(x, y) { super(x, y, 40, 30); this.mode = 'follow'; this.st = 0; Game.ally = this; }
  dive(tx, ty) { this.mode = 'dive'; this.st = 0; this.tx = tx; this.ty = ty; AudioSys.play_sfx('moo'); HUD.toast('CAPTAIN UDDERLY: "HOLY HEIFER, HOLD ON!"', '#fff'); }
  update(L) {
    this.t++; this.st++; const p = Game.player;
    if (this.mode === 'follow') { this.x = lerp(this.x, p.cx - p.face * 70, .04); this.y = lerp(this.y, p.cy - 90 + Math.sin(this.t * .05) * 10, .05); this.face = sign(p.cx - this.cx) || 1; }
    else if (this.mode === 'dive') { const k = Math.min(1, this.st / 30); this.x = lerp(this.x, this.tx, k * .3); this.y = lerp(this.y, this.ty, k * .3); this.face = sign(this.tx - this.cx) || 1;
      if (dist(this.cx, this.cy, this.tx, this.ty) < 30 || this.st > 60) { this.mode = 'follow'; Cam.shake(6, 14); AudioSys.play_sfx('bash'); FX.ring(this.tx, this.ty, 60, '#fff'); for (const e of Game.ents) if (e.isBoss && !e.defeated) { if (e.state !== 'dying' && e.go) { e.hit(3, { kind: 'ally' }); if (e instanceof OverlordBoss) e.go('stunned'); } } } }
  }
  draw(cx, cy) { drawCow(this.cx - cx, this.y + this.h - cy + 30, { face: this.face, t: this.t / 60, scale: .42, rot: this.mode === 'dive' ? .5 * this.face : -.12 * this.face, cape: this.mode === 'dive' ? 9 : 4, capeStretch: this.mode === 'dive' ? 8 : 0 }); }
}
// ---------------------------------------------------------------- summons (cost 50 METAL)
const SUMMONS = {
  pigs: { name: 'THREE PIG STAMPEDE', desc: 'Hamwise honks (stun), Porkington throws sticks, Trufflina charges.' },
  razz: { name: 'RAZZ ROAD RAGE', desc: 'Razz Vroomberg tears across the screen on his chopper.' },
  udderly: { name: 'UDDERLY AIR STRIKE', desc: 'Captain Udderly dive-bombs every enemy on screen.' }
};
class Summon extends Ent {
  constructor(kind) { super(Cam.x - 80, Game.player.y, 40, 40); this.kind = kind; this.dir = 1; this.ground = Game.player.y + Game.player.h; }
  update(L) {
    this.t++; const sp = this.kind === 'razz' ? 8 : 4.2; this.x += sp;
    const box = { x: this.x - 30, y: this.ground - 60, w: 100, h: 70 };
    for (const e of Game.ents) if ((e instanceof Enemy) && !e.dead && overlap(box, e)) { if (this.kind === 'pigs' && this.t % 2) e.stun(150); e.hit(this.kind === 'razz' ? 4 : 2, { dir: 1, knock: 6 }); }
    for (const e of Game.ents) if (e.isBoss && !e.defeated && overlap(box, e.hitbox()) && !this.hitBoss) { this.hitBoss = true; e.hit(4, { kind: 'ally' }); }
    if (this.kind === 'pigs' && this.t % 20 === 0) { AudioSys.play_sfx(this.t % 40 ? 'oink' : 'honk', { pitch: 1 + R(.3) }); Game.add(new StickProj(this.x + 20, this.ground - 30, 5, -3)); }
    if (this.kind === 'razz') { if (this.t % 2 === 0) FX.smoke(this.x - 50, this.ground - 12, -2); AudioSys.setEngine(true, 1); }
    if (this.kind === 'udderly' && this.t % 15 === 0) { const tg = Game.ents.find(e => e instanceof Enemy && !e.dead && e.wake && Math.abs(e.cx - this.x) < 200); if (tg) { tg.hit(3, {}); FX.ring(tg.cx, tg.cy, 30, '#fff'); AudioSys.play_sfx('bash'); } }
    if (this.x > Cam.x + W + 120) { this.dead = true; if (this.kind === 'razz') AudioSys.setEngine(false); }
  }
  draw(cx, cy) {
    const x = this.x - cx, gy = this.ground - cy;
    if (this.kind === 'pigs') { drawPig('trufflina', x + 40, gy, { face: 1, state: 'run', t: this.t / 60 }); drawPig('porkington', x, gy, { face: 1, state: 'run', t: this.t / 60 + .2 }); drawPig('hamwise', x - 36, gy, { face: 1, state: 'run', t: this.t / 60 + .4, prop: 'kazoo' }); }
    if (this.kind === 'razz') drawBiker(x, gy, { face: 1, t: this.t / 60, speed: 2, turbo: true, wheelie: .15 });
    if (this.kind === 'udderly') drawCow(x, gy - 80, { face: 1, t: this.t / 60, scale: .5, rot: -.1, cape: 8, capeStretch: 6 });
  }
}
// ---------------------------------------------------------------- chase pursuer (backstage / pig chase)
class Chaser extends Ent {
  constructor(o) { super(o.x, o.y, 100, 60); this.ground = o.y; this.rider = o.rider || 'razz'; this.lines = o.lines || []; this.li = 0; this.say = null; this.sayT = 0; }
  update(L) {
    this.t++; const p = Game.player, target = Cam.x + 50;
    this.x = lerp(this.x, Math.max(target - 40, Math.min(p.x - 70, this.x + 6)), .08);
    // follow the terrain under the front wheel
    const tx = Math.floor((this.x + 60) / TS); let gy = 0; for (let ty = 4; ty < L.h; ty++) if (L.solidAt(tx, ty) || L.onewayAt(tx, ty)) { gy = ty * TS; break; } this.ground = lerp(this.ground, gy || this.ground, .2);
    if (this.t % 3 === 0) FX.smoke(this.x - 40, this.ground - 10, -1.5);
    AudioSys.setEngine(true, .6 + Math.sin(this.t * .1) * .1);
    if (overlap({ x: this.x - 50, y: this.ground - 60, w: 110, h: 60 }, p)) p.hurt(1, this.x - 100);
    if (this.t % 260 === 120 && this.lines.length) { this.say = this.lines[this.li++ % this.lines.length]; this.sayT = 150; }
    if (this.sayT > 0) this.sayT--;
  }
  draw(cx, cy) {
    const x = this.x - cx, gy = this.ground - cy; drawBiker(x, gy, { face: 1, t: this.t / 60, speed: 1.6, wheelie: Math.sin(this.t * .05) > .7 ? .25 : 0, turbo: this.t % 60 < 20 });
    if (this.rider === 'barnaby') drawWolf(x - 16, gy - 40, { face: 1, t: this.t / 60, scale: .55, arm: -.5 + Math.sin(this.t * .2) * .3 });
    if (this.sayT > 0) { const lines = wrapText(this.say, 26); panel(x - 10, gy - 110 - lines.length * 9, lines.length ? 160 : 0, lines.length * 9 + 6, { rim: '#5bd4ff' }); lines.forEach((l, i) => text(l, x - 6, gy - 106 - lines.length * 9 + i * 9, { color: '#fff' })); }
  }
}
// ---------------------------------------------------------------- race rival (Dumpster Derby)
class RazzRacer extends Ent {
  constructor(o) { super(o.x, o.y, 80, 40); this.vx = 0; this.vy = 0; this.ground = o.y; this.finishX = o.finishX; this.won = false; this.onGround = true; this.lines = ['EAT MY EXHAUST, LETTUCE HEAD!', 'This chopper is HANDMADE, baby!', 'You call THAT a vehicle?!', 'Rainbow hair NEVER loses!']; this.say = null; this.sayT = 0; }
  update(L) {
    this.t++; const p = Game.player, gap = p.x - this.x;
    const target = 4.3 + clamp(gap / 300, -1.2, 1.6) + Math.sin(this.t * .01) * .4; this.vx = approach(this.vx, target, .05);
    this.x += this.vx;
    const tx = Math.floor((this.x + 40) / TS); let gy = null; for (let ty = 4; ty < L.h; ty++) if (L.solidAt(tx, ty)) { gy = ty * TS; break; }
    if (gy === null) { this.vy += .35; this.ground += this.vy; } else { if (this.ground < gy - 2) { this.vy += .35; this.ground = Math.min(gy, this.ground + this.vy); } else { this.ground = gy; this.vy = 0; } if (this.ground > gy) this.ground = gy; }
    if (gy !== null && this.ground >= gy && L.solidAt(tx + 2, Math.floor((gy - 20) / TS))) { this.vy = -7; this.ground -= 2; }
    if (this.ground > L.h * TS) { this.ground = 15 * TS; }
    if (this.t % 2 === 0) FX.smoke(this.x - 40, this.ground - 10, -2);
    if (this.x > this.finishX && !this.won && !Game.raceDone) { this.won = true; Game.raceLost(); }
    if (this.t % 300 === 100) { this.say = pick(this.lines); this.sayT = 140; } if (this.sayT > 0) this.sayT--;
  }
  draw(cx, cy) { const x = this.x - cx, gy = this.ground - cy; if (x < -200 || x > W + 200) { const ex = clamp(x, 10, W - 10); text(x < 0 ? '◄ RAZZ' : 'RAZZ ►', ex, 60, { color: '#5bd4ff', align: x < 0 ? 'left' : 'right', outline: true }); return; }
    drawBiker(x, gy, { face: 1, t: this.t / 60, speed: 1.8, wheelie: this.vy < 0 ? .3 : 0, turbo: this.vx > 5 });
    if (this.sayT > 0) text(this.say, x, gy - 90, { color: '#5bd4ff', align: 'center', outline: true }); }
}
// vehicle physics for the player's dumpster kart
function updateVehicle(pl, L) {
  const I = Input; pl.t++; pl.attacks = [];
  if (pl.dead) { pl.dead++; if (pl.dead > 80) Game.respawn(); return; }
  if (pl.inv > 0) pl.inv--;
  if (pl.boost === undefined) pl.boost = 100; const boost = I.held.dash && pl.boost > 0; if (boost) { pl.boost -= .9; if (pl.t % 2 === 0) FX.add({ x: pl.x, y: pl.y + pl.h - 6, vx: -3, vy: R(-.5, .5), col: pick(['#ff3a1a', '#ffa01a', '#fff36b']), size: 3, life: 14, grav: 0 }); } else if (!I.held.dash) pl.boost = Math.min(100, pl.boost + .25);
  const target = (I.held.right ? 5.2 : I.held.left ? 2.4 : 4.2) + (boost ? 2.4 : 0); pl.vx = approach(pl.vx, target, .08); pl.face = 1;
  if (I.pressed.jump && pl.onGround) { pl.vy = -7.2; AudioSys.play_sfx('jump'); }
  pl.vy = Math.min(pl.vy + PHYS.grav * (I.held.jump && pl.vy < 0 ? .7 : 1), 7);
  // tongue still works from the kart: whip obstacles
  if (I.pressed.whip && pl.whipCd <= 0) { pl.whipT = 14; pl.whipCd = 18; AudioSys.play_sfx('whip'); } if (pl.whipCd > 0) pl.whipCd--;
  if (pl.whipT > 0) { pl.whipT--; const [mx, my] = [pl.cx + 10, pl.y + 4]; const ext = (14 - pl.whipT < 5 ? (14 - pl.whipT) / 5 : pl.whipT / 9) * 60; pl.tongueTip = [mx + ext, my, mx, my]; pl.attack({ x: mx + ext - 8, y: my - 8, w: 16, h: 16, dmg: 2, kind: 'whip' }); } else pl.tongueTip = null;
  if (I.pressed.spit && pl.spitCd <= 0) { pl.spitCd = 16; Game.add(new SlimeBall(pl.cx + 10, pl.y, 8, -1, true)); AudioSys.play_sfx('spit'); } if (pl.spitCd > 0) pl.spitCd--;
  const wasG = pl.onGround; moveBody(pl, L);
  if (pl.hitWall) { if (pl.breakTiles(L, pl.x + pl.w + 2, pl.y + 2, pl.y + pl.h - 2)) { pl.vx = 2.5; Cam.shake(4, 8); } else { pl.hurt(1, pl.x + 40); pl.vx = -2; pl.vy = -3; } }
  if (!wasG && pl.onGround) { FX.dust(pl.cx, pl.y + pl.h, 6); AudioSys.play_sfx('land'); }
  if (pl.onGround && pl.groundTile === T_SPRING) { pl.vy = -10; AudioSys.play_sfx('boing'); }
  if (overlapsHazard(pl, L)) pl.hurt(1);
  if (pl.y > L.h * TS + 30) pl.fallOut();
  if (pl.t % 4 === 0 && pl.onGround) FX.dust(pl.x, pl.y + pl.h, 1);
  if (pl.onGround && !overlapsHazard(pl, L)) { const tx = Math.floor((pl.x - 40) / TS), ty = Math.floor((pl.y + pl.h + 2) / TS); if (L.solidAt(tx, ty) && ++pl.safeT > 4) pl.safe = { x: pl.x - 40, y: pl.y - 4 }; } else pl.safeT = 0;
  AudioSys.setEngine(true, .4 + pl.vx / 10);
}
function drawVehicle(pl, cx, cy) {
  if (pl.dead) return; if (pl.inv > 0 && Math.floor(pl.inv / 4) % 2) return;
  const x = pl.cx - cx, y = pl.y + pl.h - cy, rot = clamp(pl.vy * .04, -.3, .3);
  ctx.save(); ctx.translate(x, y); ctx.rotate(rot);
  if (pl.tongueTip) { const [tx, ty, mx, my] = pl.tongueTip; drawTongue(mx - pl.cx, my - pl.y - pl.h, tx - pl.cx, ty - pl.y - pl.h, 5, 3); }
  drawHero(0, -34, { face: 1, rot: Math.sin(pl.t * .3) * .05, sx: .8, sy: .8, mouth: I_mouth(pl) });
  const f = Math.floor(pl.t / 4) % 2; spr(SPR.cart[f], 0, 4, { sx: 1.2, sy: 1.1 });
  P.r(ctx, -20, -18, 40, 4, '#3a7a3a'); text('#333', 0, -10, { color: '#ffe14d', align: 'center', shadow: '#000' });
  ctx.restore();
}
function I_mouth(pl) { return Input.held.dash && pl.boost > 0 ? .8 : 0; }
