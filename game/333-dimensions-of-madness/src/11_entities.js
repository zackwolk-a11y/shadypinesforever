// ============================================================================
// Entities: enemies, projectiles, pickups, interactive objects, allies
// ============================================================================
class Ent {
  constructor(x, y, w, h) { this.x = x; this.y = y; this.w = w; this.h = h; this.vx = 0; this.vy = 0; this.dead = false; this.t = 0; this.face = -1; }
  get cx() { return this.x + this.w / 2; } get cy() { return this.y + this.h / 2; }
  update(L) { this.t++; } draw(cx, cy) { }
}
const ENEMY_DEFS = {
  puppet: { name: 'Runaway Marionette', hp: 2, beh: 'walk', spd: .7, desc: 'Cut its own strings to join a punk band. Still can\'t play anything.' },
  amp: { name: 'Feral Amplifier', hp: 3, beh: 'shoot', spd: .4, proj: 'ring', desc: 'Turned up to 11 and never turned back down. Fires feedback rings.' },
  cable: { name: 'Patch Cable Viper', hp: 1, beh: 'walk', spd: 1.3, desc: 'Coils under the stage waiting to trip roadies. Bites with 9 volts.' },
  bookbat: { name: 'Bedtime Bookbat', hp: 1, beh: 'fly', spd: 1.1, desc: 'A storybook that ate its own ending. Flaps its pages angrily.' },
  candle: { name: 'Wick Wraith', hp: 2, beh: 'float', spd: .5, desc: 'Haunted candle. Drips hot wax gossip about everyone it ever lit.' },
  soldier: { name: 'Toy Grenadier', hp: 3, beh: 'charge', spd: 1.6, desc: 'Wind-up soldier from the Puppet King\'s guard. Lowers spear, charges.' },
  loop: { name: 'Frosted Loop Fiend', hp: 2, beh: 'hop', spd: 1.2, desc: 'Escaped cereal ring with sugar fangs. Part of a balanced breakfast nightmare.' },
  toaster: { name: 'Toast Cannon', hp: 3, beh: 'shoot', spd: 0, proj: 'toast', desc: 'Launches burnt toast at 80 mph. Ding.' },
  carton: { name: 'Expired Milk Carton', hp: 2, beh: 'walk', spd: .9, desc: 'Best before: three dimensions ago. Smells like a threat.' },
  bacon: { name: 'Bacon Serpent', hp: 2, beh: 'walk', spd: 1.5, desc: 'Sizzles when angry. Always angry.' },
  cultcow: { name: 'Udder Cultist', hp: 3, beh: 'walk', spd: .8, desc: 'Hooded farmhand devoted to the Holy Moo. Chants in 7/8 time.' },
  gloopkin: { name: 'Shitkin', hp: 2, beh: 'hop', spd: 1, split: true, desc: 'Spawn of Shitman. Splits in two when struck. Smells like honey and regret.' },
  shroom: { name: 'Eyecap Mushroom', hp: 2, beh: 'shoot', spd: 0, proj: 'spore', desc: 'Watches you. Judges you. Sneezes hallucinogenic spores.' },
  lava: { name: 'Lava Lamp Blob', hp: 2, beh: 'float', spd: .7, desc: 'Groovy, warm and burns on contact. Peace and love, mostly burns.' },
  spark: { name: 'Voltergeist', hp: 2, beh: 'fly', spd: 1.3, desc: 'An electric ghost living in the mansion wiring. Zaps on touch.' },
  hand: { name: 'Grabby Hand', hp: 2, beh: 'fly', spd: 1.6, desc: 'Nobody knows whose hand this is. Not even the hand.' },
  felt: { name: 'Melted Felt Puppet', hp: 3, beh: 'hop', spd: .9, desc: 'A children\'s show puppet left too close to a dimensional rift.' },
  clown: { name: 'Knife-Juggling Clown', hp: 3, beh: 'shoot', spd: .6, proj: 'knife', desc: 'Trained for decades. Still drops knives on purpose. At you.' },
  balloon: { name: 'Balloon Bomb', hp: 1, beh: 'float', spd: .6, explode: true, desc: 'Floats closer, pops, explodes. A party favour from hell.' },
  fish: { name: 'Leggy Mutant Fish', hp: 2, beh: 'hop', spd: 1.4, desc: 'Grew legs in the factory runoff. Now insists on walking everywhere.' },
  teddy: { name: 'Convict Teddy', hp: 3, beh: 'charge', spd: 1.7, desc: 'Serving life for excessive cuddling. Breaks out every Tuesday.' },
  ticket: { name: 'Ticket Gremlin', hp: 1, beh: 'hop', spd: 1.6, desc: 'Admit one. Bite many.' },
  rat: { name: 'Trashopolis Rat', hp: 2, beh: 'walk', spd: 1.8, desc: 'Mayor of a very small alley. Very fast. Very rude.' },
  can: { name: 'Can Crab', hp: 2, beh: 'walk', spd: 1.1, desc: 'Lives in a soda can. Claims it is vintage.' },
  toy: { name: 'Wind-Up Waif', hp: 3, beh: 'charge', spd: 1.5, desc: 'A garbage child\'s toy that kept winding itself. Forever.' },
  bag: { name: 'Bag Ghoul', hp: 3, beh: 'hop', spd: .8, desc: 'What lives at the bottom of the bin. Oozes slime when hit.' },
  roadie: { name: 'Undead Roadie', hp: 4, beh: 'walk', spd: 1.0, desc: 'Still hauling gear after the universe ended. Union rules.' },
  speaker: { name: 'Sonic Stack', hp: 5, beh: 'shoot', spd: 0, proj: 'ring', desc: 'A speaker tower cranked into sentience. Bass drops are its attacks.' }
};
const FLYING = { bookbat: 1, spark: 1, hand: 1, candle: 1, lava: 1, balloon: 1 };
class Enemy extends Ent {
  constructor(o) {
    const d = ENEMY_DEFS[o.kind] || ENEMY_DEFS.puppet, img = o.kind === 'gloopkin' ? IMG.gloopkin : (SPR[o.kind] || SPR.puppet)[0];
    const sc = (o.small ? .65 : 1) * (o.kind === 'gloopkin' ? 1.2 : 1.4);
    const isz = o.kind === 'gloopkin' ? HD : 1; super(o.x, o.y, Math.max(12, (img.width * isz - 4) * .8 * sc), (img.height * isz - 2) * sc);
    this.kind = o.kind; this.def = d; this.hp = Math.min(3, Math.ceil(d.hp * (o.small ? .5 : 1) * .7)); this.stunT = 0; this.flash = 0; this.dir = -1; this.home = { x: this.x, y: this.y };
    this.small = o.small; this.sc = sc; this.cool = RI(40, 120); this.stepUp = false; this.boss = false; this.score = 10;
    this.y = o.y + TS * 2 - this.h; if (FLYING[this.kind]) this.y = o.y;
    this.wake = false; this.react = o.react; if (o.tough) this.hp = o.tough;
  }
  update(L) {
    this.t++; if (this.flash > 0) this.flash--;
    const p = Game.player, d = this.def, dx = p.cx - this.cx, ad = Math.abs(dx);
    if (!this.wake) { if (ad < W * .7) { this.wake = true; Save.see(this.kind); } else return; }
    if (this.stunT > 0) { this.stunT--; this.vx *= .8; this.vy += PHYS.grav; moveBody(this, L); return; }
    const target = Game.decoy && !Game.decoy.dead ? Game.decoy : p;
    const tdx = target.cx - this.cx;
    switch (d.beh) {
      case 'walk': this.vx = this.dir * d.spd; if (this.onGround && (this.hitWall || !this.groundAhead(L))) this.dir *= -1; if (ad < 140 && this.t % 60 === 0) this.dir = sign(tdx) || this.dir; break;
      case 'hop': if (this.onGround) { this.vx *= .8; if (--this.cool <= 0) { this.vy = -4.5 - R(2); this.vx = (sign(tdx) || -1) * d.spd * 1.6; this.cool = RI(40, 90); AudioSys.play_sfx(this.kind === 'gloopkin' ? 'gloop' : 'pop'); } } break;
      case 'charge': if (this.chargeT > 0) { this.chargeT--; this.vx = this.dir * d.spd * 2.4; if (this.hitWall) { this.chargeT = 0; this.stunT = 40; Cam.shake(2, 6); } } else { this.vx = this.dir * d.spd * .4; if (this.onGround && (this.hitWall || !this.groundAhead(L))) this.dir *= -1; if (ad < 160 && Math.abs(p.cy - this.cy) < 30 && --this.cool <= 0) { this.dir = sign(tdx); this.chargeT = 50; this.cool = 90; AudioSys.play_sfx('growl'); } } break;
      case 'shoot': this.vx = 0; this.dir = sign(dx) || -1; if (ad < 280 && --this.cool <= 0) { this.cool = RI(90, 150) / (Game.diffMul || 1); this.shoot(p); } break;
      case 'fly': { const ty = target.cy - 30 + Math.sin(this.t * .05) * 20; this.vx = approach(this.vx, sign(tdx) * d.spd, .05); this.vy = approach(this.vy, clamp((ty - this.cy) * .03, -1.5, 1.5), .08); this.dir = sign(this.vx) || this.dir; this.x += this.vx; this.y += this.vy; return this.contact(); }
      case 'float': { this.vx = approach(this.vx, sign(tdx) * d.spd * (ad < 220 ? 1 : 0), .03); this.y = this.home.y + Math.sin(this.t * .04) * 14; this.x += this.vx; this.dir = sign(this.vx) || this.dir; if (d.explode && ad < 30 && Math.abs(p.cy - this.cy) < 30) this.kill(true); return this.contact(); }
    }
    this.vy = clamp(this.vy + PHYS.grav * L.gravity, -6, 6); moveBody(this, L);
    if (this.y > L.h * TS + 40) this.dead = true;
    if (overlapsHazard(this, L) && L.liquidHazard && this.t > 30) this.kill();
    this.contact();
  }
  groundAhead(L) { const tx = Math.floor((this.dir > 0 ? this.x + this.w + 2 : this.x - 2) / TS), ty = Math.floor((this.y + this.h + 4) / TS); return L.solidAt(tx, ty) || L.onewayAt(tx, ty); }
  contact() { const p = Game.player; if (!this.dead && this.stunT <= 0 && overlap(this, p) && !p.dead) { if (p.dashT > 0 || p.form === 'mega') { this.hit(2, { kind: 'dash', dir: p.face }); } else if (p.vy > 1.5 && p.y + p.h < this.cy && !p.isPig()) { this.hit(1, { kind: 'stomp' }); p.vy = -5; AudioSys.play_sfx('boing'); } else p.hurt(1, this.cx); } }
  shoot(p) {
    const k = this.def.proj, ang = Math.atan2(p.cy - this.cy, p.cx - this.cx);
    const spd = k === 'knife' ? 3.6 : k === 'toast' ? 3 : 2.2;
    Game.add(new EnemyShot(this.cx, this.cy - 4, Math.cos(ang) * spd, k === 'toast' ? -3.5 : Math.sin(ang) * spd, k));
    AudioSys.play_sfx(k === 'knife' ? 'throw' : k === 'ring' ? 'zap' : 'pop');
  }
  hit(dmg, a = {}) {
    if (this.dead || this.flash > 0) return false;
    if (dmg <= 0) { this.stunT = Math.max(this.stunT, 120); return false; }
    this.lastDir = a.dir; this.hp -= dmg; this.flash = 8; this.vx = (a.dir || sign(this.cx - Game.player.cx) || 1) * (a.knock || 2.5); this.vy = -2.5; AudioSys.play_sfx('enemyHit');
    FX.burst(this.cx, this.cy, 6, '#fff', { speed: 2 }); G.hitstop = 2;
    if (AudioSys.onBeatWindow(.18)) { Game.player.metal = Math.min(100, Game.player.metal + 4); FX.pop(this.cx, this.y - 6, 'ON BEAT!', '#7fff3a'); }
    if (this.hp <= 0) this.kill();
    return true;
  }
  stun(t) { this.stunT = Math.max(this.stunT, t); }
  kill(explode) {
    if (this.dead) return; this.dead = true; AudioSys.play_sfx('squish');
    const cols = this.kind === 'gloopkin' ? ['#c8902a', '#ffd23a', '#8a5a10'] : ['#7fff3a', '#fff', '#ff5bd1'];
    FX.burst(this.cx, this.cy, 16, cols, { speed: 3.5, size: 3 }); FX.pop(this.cx, this.y, pick(['BONK!', 'POW!', 'SPLAT!', 'YEET!', 'WHAM!', 'KA-BOING!']), '#ffe14d');
    const kind = this.react ? this.react : this.kind === 'gloopkin' ? 'slime' : this.kind === 'puppet' || this.kind === 'soldier' || this.kind === 'felt' ? pick(['apart', 'fly', 'bg']) : pick(REACTIONS);
    if (kind === 'slime') FX.slime(this.cx, this.cy, 24, ['#ffd23a', '#c8902a', '#fff0a0']); else Game.add(new Ragdoll(this, this.lastDir || sign(this.cx - Game.player.cx) || 1, kind)); Game.levelStats.launched = (Game.levelStats.launched || 0) + 1; Save.data.launched = (Save.data.launched || 0) + 1; if (Save.data.launched >= 50) Save.achieve('launch50');
    Game.player.metal = Math.min(100, Game.player.metal + 3); Game.levelStats.kills++;
    if (this.def.split && !this.small) for (const s of [-1, 1]) { const e = new Enemy({ kind: this.kind, x: this.cx, y: this.y, small: true }); e.y = this.y; e.vx = s * 2.5; e.vy = -4; e.wake = true; Game.add(e); }
    if (explode || this.def.explode) { FX.ring(this.cx, this.cy, 40, '#ff5bd1'); if (dist(this.cx, this.cy, Game.player.cx, Game.player.cy) < 40) Game.player.hurt(1, this.cx); }
    if (R() < .25) Game.add(new Note(this.cx - 4, this.cy - 8, true));
    if (R() < .06) Game.add(new Heart(this.cx - 4, this.cy - 8));
  }
  draw(cx, cy) {
    if (!this.wake) return;
    const x = this.cx - cx, y = this.y + this.h - cy, fl = this.dir > 0, flash = this.flash > 0 ? '#fff' : false;
    if (this.kind === 'gloopkin') { drawGloopkin(x, y + 1, { face: this.dir, flash, sy: (this.onGround ? 1 : 1.15) * this.sc, sx: (this.onGround ? 1 : .9) * this.sc, phase: this.home.x }); }
    else {
      const frames = SPR[this.kind] || SPR.puppet, f = frames[Math.floor(this.t / 8) % frames.length];
      const charging = this.chargeT > 0;
      spr(f, x, y + 1, { flip: fl, flash, sx: this.sc, sy: this.sc * (charging ? .92 : 1), rot: this.stunT > 0 ? Math.sin(this.t * .5) * .2 : 0 });
    }
    if (this.stunT > 0) for (let i = 0; i < 3; i++) { const a = this.t * .15 + i * 2.1; ctx.drawImage(ICON.star, Math.round(x + Math.cos(a) * 10 - 7), Math.round(y - this.h - 8 + Math.sin(a) * 3)); }
  }
}
// ---------------------------------------------------------------- projectiles
class SlimeBall extends Ent {
  constructor(x, y, vx, vy, friendly, dmg = 1) { super(x - 5, y - 5, 10, 10); this.vx = vx; this.vy = vy; this.friendly = friendly; this.dmg = dmg; this.life = 90; }
  update(L) {
    this.t++; this.vy += .12; this.x += this.vx; this.y += this.vy; if (--this.life <= 0) this.dead = true;
    if (this.t % 2 === 0) FX.add({ x: this.cx, y: this.cy, vx: 0, vy: .3, col: '#3aa01a', size: 2, life: 12, grav: .05 });
    const tx = Math.floor(this.cx / TS), ty = Math.floor(this.cy / TS);
    if (L.solidAt(tx, ty)) { this.splat(); return; }
    if (this.friendly) {
      for (const e of Game.ents) if ((e instanceof Enemy || e.isBoss || e.hittable) && !e.dead && overlap(this, e.hitbox ? e.hitbox() : e)) { e.hit(this.dmg, { kind: 'spit', dir: sign(this.vx) }); this.splat(); return; }
      for (const s of Game.ents) if (s instanceof Switch && overlap(this, s)) { s.activate(); this.splat(); return; }
    } else if (overlap(this, Game.player)) { Game.player.hurt(1, this.cx); this.splat(); }
  }
  splat() { this.dead = true; FX.slime(this.cx, this.cy, 10, this.friendly ? undefined : ['#ffd23a', '#c8902a']); AudioSys.play_sfx('splat'); }
  draw(cx, cy) { const x = Math.round(this.cx - cx), y = Math.round(this.cy - cy), c = this.friendly ? ['#0a2a00', '#5be33c', '#c8ff8a'] : ['#2a1800', '#ffb02a', '#ffe8a0']; P.e(ctx, x, y, 6, 5, c[0]); P.e(ctx, x, y, 5, 4, c[1]); P.r(ctx, x - 2, y - 2, 2, 2, c[2]); }
}
class EnemyShot extends Ent {
  constructor(x, y, vx, vy, kind) { super(x - 5, y - 5, 10, 10); this.vx = vx; this.vy = vy; this.kind = kind; this.life = 160; this.reflected = false; }
  update(L) {
    this.t++; this.x += this.vx; this.y += this.vy; if (this.kind === 'toast' || this.kind === 'glob' || this.kind === 'brick') this.vy += .12; if (--this.life <= 0) this.dead = true;
    if (L.solidAt(Math.floor(this.cx / TS), Math.floor(this.cy / TS)) && this.kind !== 'ring' && this.kind !== 'wave') { this.dead = true; FX.burst(this.cx, this.cy, 5, '#ccc'); return; }
    const p = Game.player;
    for (const a of p.attacks) if (a.reflect && overlap(this, a) && !this.reflected) { this.reflected = true; this.vx = -this.vx * 1.3; this.vy = -Math.abs(this.vy) - 1; AudioSys.play_sfx('clangS'); FX.pop(this.cx, this.cy, 'REFLECT!', '#5bd4ff'); }
    if (this.reflected) { for (const e of Game.ents) if ((e instanceof Enemy || e.isBoss) && !e.dead && overlap(this, e.hitbox ? e.hitbox() : e)) { e.hit(2, { kind: 'reflect' }); this.dead = true; return; } }
    else if (overlap(this, p)) { p.hurt(1, this.cx); this.dead = true; }
  }
  draw(cx, cy) {
    const x = Math.round(this.cx - cx), y = Math.round(this.cy - cy);
    switch (this.kind) {
      case 'ring': ctx.strokeStyle = this.t % 6 < 3 ? '#ff3a6a' : '#ffe14d'; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(x, y, 5 + Math.sin(this.t * .4) * 2, 0, 7); ctx.stroke(); break;
      case 'toast': P.r(ctx, x - 6, y - 5, 12, 10, '#2a1500'); P.r(ctx, x - 5, y - 4, 10, 8, '#d49a4a'); P.r(ctx, x - 3, y - 2, 6, 4, '#f0d090'); break;
      case 'knife': ctx.save(); ctx.translate(x, y); ctx.rotate(this.t * .4); P.r(ctx, -7, -1, 9, 3, '#ddd'); P.r(ctx, 2, -2, 5, 5, '#7a3cff'); ctx.restore(); break;
      case 'spore': P.e(ctx, x, y, 4, 4, '#ff5bd1'); P.e(ctx, x - 1, y - 1, 1.5, 1.5, '#fff'); break;
      case 'glob': P.e(ctx, x, y, 7, 6, '#3a2000'); P.e(ctx, x, y, 6, 5, '#d4a02a'); P.r(ctx, x - 2, y - 3, 2, 2, '#ffe8a0'); break;
      case 'brick': P.r(ctx, x - 6, y - 4, 12, 8, '#2a0a00'); P.r(ctx, x - 5, y - 3, 10, 6, '#c24a2a'); break;
      case 'wave': ctx.strokeStyle = '#ff2a4a'; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(x - sign(this.vx) * 8, y, 12, -1, 1); ctx.stroke(); break;
      case 'spark': P.e(ctx, x, y, 4, 4, '#bff'); P.r(ctx, x - 1, y - 1, 2, 2, '#fff'); break;
      default: P.e(ctx, x, y, 4, 4, '#ff3a3a');
    }
  }
}
class StickProj extends Ent {
  constructor(x, y, vx, vy) { super(x - 6, y - 3, 12, 6); this.vx = vx; this.vy = vy; }
  update(L) { this.t++; this.vy += .2; this.x += this.vx; this.y += this.vy; if (L.solidAt(Math.floor(this.cx / TS), Math.floor(this.cy / TS)) || this.t > 80) { this.dead = true; FX.debris(this.cx, this.cy, 'stick', 2); }
    for (const e of Game.ents) if ((e instanceof Enemy || e.isBoss) && !e.dead && overlap(this, e.hitbox ? e.hitbox() : e)) { e.hit(1, { dir: sign(this.vx) }); this.dead = true; return; } }
  draw(cx, cy) { ctx.save(); ctx.translate(Math.round(this.cx - cx), Math.round(this.cy - cy)); ctx.rotate(this.t * .4); P.r(ctx, -7, -2, 14, 4, '#2a1500'); P.r(ctx, -6, -1, 12, 2, '#a0662a'); ctx.restore(); }
}
// ---------------------------------------------------------------- pickups
class Note extends Ent {
  constructor(x, y, drop) { super(x, y, 10, 12); this.base = y; this.drop = drop; if (drop) { this.vy = -3; this.vx = R(-1, 1); } }
  update(L) { this.t++; if (this.drop) { this.vy += .2; this.x += this.vx; this.y += this.vy; if (L.solidAt(Math.floor(this.cx / TS), Math.floor((this.y + this.h) / TS))) { this.vy = -Math.abs(this.vy) * .4; this.vx *= .7; this.y -= 1; } }
    const p = Game.player; const mag = p.tongueTip ? dist(this.cx, this.cy, p.tongueTip[0], p.tongueTip[1]) < 20 : false;
    if (overlap(this, p) || mag) { this.dead = true; Game.levelStats.notes++; Save.data.notes++; AudioSys.play_sfx('note'); Game.noteMilestone(); FX.burst(this.cx, this.cy, 4, '#ffe14d', { speed: 1.5 }); if (Save.data.notes >= 1000) Save.achieve('notes1000'); } }
  draw(cx, cy) { const s = Math.abs(Math.cos(this.t * .06)); spr(ICON.note, this.cx - cx, Math.round(this.y - cy + Math.sin(this.t * .08) * 2) + 10, { sx: Math.max(.2, s) }); }
}
class Shard extends Ent {
  constructor(x, y, id) { super(x, y, 14, 14); this.id = id; this.got = Game.shardsHave(id); }
  update(L) { this.t++; if (overlap(this, Game.player) && !this.dead) { this.dead = true; Game.collectShard(this.id); AudioSys.play_sfx('shard'); FX.burst(this.cx, this.cy, 30, ['#b04bff', '#ff5bd1', '#fff'], { speed: 4 }); FX.pop(this.cx, this.y - 6, 'DIMENSIONAL SHARD!', '#ff5bd1'); } }
  draw(cx, cy) { const y = this.y - cy + Math.sin(this.t * .07) * 3; ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.fillStyle = `rgba(176,75,255,${.25 + Math.sin(this.t * .1) * .1})`; ctx.beginPath(); ctx.arc(this.cx - cx, y + 7, 14, 0, 7); ctx.fill(); ctx.restore(); spr(ICON.shard, this.cx - cx, y + 14, { alpha: this.got ? .5 : 1 }); }
}
class Heart extends Ent {
  constructor(x, y) { super(x, y, 12, 12); this.vy = -3; }
  update(L) { this.t++; this.vy = Math.min(this.vy + .15, 2); this.y += this.vy; if (L.solidAt(Math.floor(this.cx / TS), Math.floor((this.y + this.h) / TS))) { this.vy = 0; this.y = Math.floor((this.y + this.h) / TS) * TS - this.h; }
    const p = Game.player; if (overlap(this, p)) { this.dead = true; p.hp = Math.min(p.maxHp, p.hp + 1); AudioSys.play_sfx('power'); FX.pop(this.cx, this.y, '+♥', '#ff2244'); } if (this.t > 900) this.dead = true; }
  draw(cx, cy) { if (this.t > 700 && this.t % 10 < 5) return; spr(ICON.heart, this.cx - cx, this.y + 12 - cy, { sx: 1.4, sy: 1.4 }); }
}
// ---------------------------------------------------------------- level objects
class Hook extends Ent {
  constructor(x, y) { super(x - 6, y - 6, 12, 12); }
  get hx() { return this.cx; }
  draw(cx, cy) { const x = this.cx - cx, y = this.cy - cy; P.l(ctx, x, y - 6, x, y - 40, '#555', 2); spr(ICON.hook, x, y + 6); const p = Game.player; if (!p.grapple && dist(p.cx, p.cy, this.cx, this.cy) < 130 && !p.onGround) { ctx.strokeStyle = `rgba(255,122,138,${.5 + Math.sin(G.t * 10) * .3})`; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(x, y, 10, 0, 7); ctx.stroke(); text('ATTACK!', x, y - 26, { color: '#ff7a8a', align: 'center', outline: true }); } }
}
class MovingPlat extends Ent {
  constructor(o) { super(o.x, o.y, (o.w || 4) * TS, 8); this.solid = true; this.oneway = true; this.o = o; this.x0 = o.x; this.y0 = o.y; this.dx = 0; this.vy = 0; }
  update(L) {
    this.t++; const ph = (Math.sin(this.t * (this.o.speed || .012) * 2) + 1) / 2, ox = this.x, oy = this.y;
    if (this.o.vert) this.y = this.y0 - ph * this.o.range; else this.x = this.x0 + ph * this.o.range;
    if (this.o.beat) { const b = AudioSys.beat(); this.y = this.y0 - (b.beat % 2 ? 1 - b.phase : b.phase) * 48; }
    this.dx = this.x - ox; this.vy = this.y - oy;
    const p = Game.player; if (p.riding === this) { p.x += this.dx; }
  }
  draw(cx, cy) { const x = Math.round(this.x - cx), y = Math.round(this.y - cy); P.r(ctx, x - 1, y - 1, this.w + 2, 10, '#000'); P.r(ctx, x, y, this.w, 8, '#c9a227'); P.r(ctx, x, y, this.w, 2, '#ffe9a0'); for (let i = 4; i < this.w; i += 12) P.r(ctx, x + i, y + 3, 4, 2, '#7a5a10'); }
}
class Checkpoint extends Ent {
  constructor(x, y) { super(x, y, 24, 32); this.on = false; }
  update(L) { this.t++; if (!this.on && overlap(this, Game.player)) { this.on = true; Game.checkpoint = { x: this.x, y: this.y }; AudioSys.play_sfx('checkpoint'); FX.notes(this.cx, this.y, 6); FX.pop(this.cx, this.y - 8, 'CHECKPOINT', '#7fff3a'); Game.player.hp = Math.max(Game.player.hp, Math.min(Game.player.maxHp, Game.player.hp + 1)); } }
  draw(cx, cy) {
    const x = Math.round(this.x - cx), y = Math.round(this.y - cy);
    P.r(ctx, x - 1, y - 1, 26, 34, '#000'); P.r(ctx, x, y, 24, 32, '#1c1c20'); P.r(ctx, x + 2, y + 2, 20, 4, this.on ? '#7fff3a' : '#555');
    const pulse = this.on ? Math.abs(Math.sin(this.t * .2)) * 2 : 0; P.e(ctx, x + 12, y + 19, 8 + pulse, 8 + pulse, '#333'); P.e(ctx, x + 12, y + 19, 3, 3, '#111');
    if (this.on && this.t % 30 === 0) FX.notes(this.cx, this.y, 1);
  }
}
class Exit extends Ent {
  constructor(x, y) { super(x, y - 140, 40, 140); }
  update(L) { this.t++; if (overlap(this, Game.player) && !Game.finishing) Game.finishLevel(); }
  draw(cx, cy) {
    const x = this.cx - cx, y = this.cy - cy;
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    const yy = this.y + this.h - 34 - cy; for (let i = 0; i < 5; i++) { ctx.strokeStyle = hsl((this.t * 4 + i * 50) % 360, 90, 60, .8); ctx.lineWidth = 3; ctx.beginPath(); ctx.ellipse(x, yy, 18 - i * 3 + Math.sin(this.t * .1 + i) * 2, 30 - i * 5, Math.sin(this.t * .02) * .2, 0, 7); ctx.stroke(); }
    ctx.fillStyle = 'rgba(176,75,255,.12)'; ctx.fillRect(x - 14, this.y - cy, 28, this.h - 60); ctx.restore(); text('EXIT', x, yy - 44, { color: '#fff', align: 'center', outline: true, wave: 1 });
  }
}
class Switch extends Ent {
  constructor(o) { super(o.x, o.y + 16, 16, 16); this.link = o.link; this.on = false; this.timed = o.timed; }
  activate() { if (this.on) return; this.on = true; AudioSys.play_sfx('switch'); FX.burst(this.cx, this.cy, 8, '#ffe14d'); for (const d of Game.ents) if (d instanceof Door && d.link === this.link) d.open(); if (this.timed) this.offT = this.timed; }
  update(L) { this.t++; for (const a of Game.player.attacks) if (overlap(a, this)) this.activate(); if (this.offT && --this.offT === 0) { this.on = false; for (const d of Game.ents) if (d instanceof Door && d.link === this.link) d.close(); } }
  draw(cx, cy) { const x = Math.round(this.x - cx), y = Math.round(this.y - cy); P.r(ctx, x - 1, y - 1, 18, 18, '#000'); P.r(ctx, x, y, 16, 16, '#444'); P.e(ctx, x + 8, y + 8, 5, 5, this.on ? '#7fff3a' : '#ff3a3a'); P.r(ctx, x + 6, y + 5, 2, 2, '#fff8'); }
}
class Door extends Ent {
  constructor(o) { super(o.x, o.y - (o.hgt || 4) * TS + 16, 16, (o.hgt || 4) * TS); this.link = o.link; this.solid = true; this.openT = 0; this.isOpen = false; }
  open() { this.isOpen = true; this.solid = false; AudioSys.play_sfx('door'); Cam.shake(2, 8); }
  close() { this.isOpen = false; this.solid = true; }
  update() { this.openT = approach(this.openT, this.isOpen ? 1 : 0, .05); }
  draw(cx, cy) { const x = Math.round(this.x - cx), y = Math.round(this.y - cy), h = this.h * (1 - this.openT); P.r(ctx, x - 1, y - 1, 18, h + 2, '#000'); P.r(ctx, x, y, 16, h, '#6a5a7a'); for (let i = 6; i < h; i += 12) P.r(ctx, x + 2, y + i, 12, 2, '#3a2a4a'); P.r(ctx, x + 5, y + h - 8, 6, 4, '#ffcc33'); }
}
class Blueprint extends Ent { // Porkington builds stick bridges/ladders here
  constructor(o) { super(o.x, o.y, (o.len || 6) * TS, 16); this.len = o.len || 6; this.kind = o.kind || 'bridge'; this.built = false; this.bt = 0; this.tx = Math.floor(o.x / TS); this.ty = Math.floor(o.y / TS) + 1; this.onBuild = o.onBuild; }
  build() {
    if (this.built) return; this.built = true; AudioSys.play_sfx('select'); FX.debris(this.cx, this.cy, 'stick', 14); Cam.shake(2, 8);
    const L = Game.L; if (this.kind === 'bridge') for (let i = 0; i < this.len; i++) L.set(this.tx + i, this.ty, T_ONEWAY);
    else for (let i = 0; i < this.len; i++) L.set(this.tx, this.ty - i, T_ONEWAY);
    FX.pop(this.cx, this.y - 10, 'BUILT!', '#ffcc33'); if (this.onBuild) Game.flag(this.onBuild);
  }
  update(L) { this.t++; }
  draw(cx, cy) {
    if (this.built) return; const x = Math.round(this.x - cx), y = Math.round(this.y - cy) + 16;
    ctx.strokeStyle = `rgba(90,180,255,${.6 + Math.sin(this.t * .1) * .3})`; ctx.setLineDash([3, 3]); ctx.lineWidth = 1;
    if (this.kind === 'bridge') ctx.strokeRect(x, y, this.w, 6); else ctx.strokeRect(x, y - this.len * TS + 16, 16, this.len * TS);
    ctx.setLineDash([]); text('BUILD', x + (this.kind === 'bridge' ? this.w / 2 : 8), y - 12, { color: '#5bd4ff', align: 'center', wave: 1 });
  }
}
class BrickItem extends Ent {
  constructor(x, y) { super(x, y, 18, 10); }
  update(L) { this.t++; this.vy = Math.min(this.vy + .2, 4); moveBody(this, L); const p = Game.player; if (overlap(this, p) && !p.carry && (p.char === 'trufflina' || p.char === 'monster')) { p.carry = 'brick'; this.dead = true; AudioSys.play_sfx('pop'); FX.pop(this.cx, this.y, 'GOT BRICK', '#ffcc33'); } }
  draw(cx, cy) { spr(ICON.brick, this.cx - cx, this.y + this.h - cy + Math.sin(this.t * .1)); }
}
class BrickSlot extends Ent {
  constructor(o) { super(o.x, o.y, 16, 16); this.filled = false; this.group = o.group; }
  fill() { this.filled = true; Game.L.set(Math.floor(this.x / TS), Math.floor(this.y / TS), T_SOLID); AudioSys.play_sfx('bash'); FX.burst(this.cx, this.cy, 8, '#c24a2a'); Game.flag(this.group + 'Brick'); }
  update(L) { this.t++; const p = Game.player; if (!this.filled && p.carry && p.char === 'monster' && dist(p.cx, p.cy, this.cx, this.cy) < 30) { this.fill(); p.carry = null; } }
  draw(cx, cy) { if (this.filled) return; const x = Math.round(this.x - cx), y = Math.round(this.y - cy); ctx.strokeStyle = `rgba(255,204,51,${.5 + Math.sin(this.t * .15) * .4})`; ctx.setLineDash([2, 2]); ctx.strokeRect(x + .5, y + .5, 15, 15); ctx.setLineDash([]); }
}
class Collectable extends Ent { // straw bundles / sticks for house building quests
  constructor(o) { super(o.x, o.y, 16, 14); this.kind = o.kind; this.flagName = o.flag; }
  update(L) { this.t++; if (overlap(this, Game.player)) { this.dead = true; Game.flag(this.flagName); AudioSys.play_sfx('note'); FX.debris(this.cx, this.cy, this.kind === 'straw' ? 'straw' : 'stick', 6); FX.pop(this.cx, this.y, '+1 ' + this.kind.toUpperCase() + '!', '#ffd860'); } }
  draw(cx, cy) { const ic = this.kind === 'straw' ? ICON.straw : this.kind === 'brick' ? ICON.brick : ICON.stick; ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.fillStyle = 'rgba(255,230,120,.25)'; ctx.beginPath(); ctx.arc(this.cx - cx, this.cy - cy, 14, 0, 7); ctx.fill(); ctx.restore(); spr(ic, this.cx - cx, this.y + 14 - cy + Math.sin(this.t * .1) * 2, { sx: 1.3, sy: 1.3 }); }
}
class Pullable extends Ent { // crates the tongue can yank
  constructor(o) { super(o.x, o.y, 24, 24); this.solid = true; }
  update(L) { this.t++; this.vy = Math.min(this.vy + PHYS.grav, 6); const s = this.solid; this.solid = false; moveBody(this, L); this.solid = s; this.vx *= .85; }
  pull(dir) { this.vx = dir * 5; AudioSys.play_sfx('slurp'); }
  push(dir) { this.vx = dir * 1.6; }
  draw(cx, cy) { const x = Math.round(this.x - cx), y = Math.round(this.y - cy); P.r(ctx, x - 1, y - 1, 26, 26, '#000'); P.r(ctx, x, y, 24, 24, '#a0662a'); P.l(ctx, x, y, x + 24, y + 24, '#5a3a10', 2); P.l(ctx, x + 24, y, x, y + 24, '#5a3a10', 2); P.r(ctx, x, y, 24, 2, '#d0965a'); }
}
class AmpTotem extends Ent { // destroyed only by guitar-powered METAL SCREAM / mega
  constructor(o) { super(o.x, o.y - 48 + 16, 32, 48); this.solid = true; this.hp = 1; }
  update(L) { this.t++; if (this.fallY < 0) { this.fallY = Math.min(0, this.fallY + 7); if (this.fallY === 0) { FX.dust(this.cx, this.y + this.h, 16); } } const p = Game.player; if ((p.form === 'mega' || p.dashT > 0 && p.form !== 'normal') && overlap({ x: p.x - 4, y: p.y, w: p.w + 8, h: p.h }, this)) this.blow(); }
  blow() { if (this.dead) return; this.dead = true; this.solid = false; AudioSys.play_sfx('explode'); AudioSys.play_sfx('riff'); Cam.shake(8, 20); FX.burst(this.cx, this.cy, 40, ['#c9a227', '#333', '#ff3a1a', '#fff'], { speed: 5, size: 3 }); FX.notes(this.cx, this.cy, 8); }
  draw(cx, cy) { const x = Math.round(this.x - cx), y = Math.round(this.y - cy + (this.fallY || 0)); P.r(ctx, x - 1, y - 1, 34, 50, '#000'); P.r(ctx, x, y, 32, 48, '#1c1c20'); P.r(ctx, x + 2, y + 2, 28, 5, '#c9a227'); P.e(ctx, x + 16, y + 20, 10, 10, '#333'); P.e(ctx, x + 16, y + 38, 6, 6, '#333'); text('MAX', x + 16, y + 9, { color: '#ff3a3a', align: 'center', shadow: false });
    if (this.t % 40 < 20 && dist(Game.player.cx, Game.player.cy, this.cx, this.cy) < 200) text('ATTACK IT!', x + 16, y - 12, { color: '#7fff3a', align: 'center', outline: true }); }
}
class Sign extends Ent { // wooden hint sign
  constructor(o) { super(o.x, o.y - 26, 22, 26); this.msg = o.msg; }
  draw(cx, cy) { const x = Math.round(this.x - cx), y = Math.round(this.y - cy); O.r(x + 9, y + 10, 4, 16, '#6a4a2a', 1); O.r(x, y, 22, 13, '#c8a070', 1); P.r(ctx, x + 3, y + 4, 16, 1, '#5a3a1a'); P.r(ctx, x + 3, y + 8, 12, 1, '#5a3a1a');
    const p = Game.player; if (Math.abs(p.cx - this.cx) < 70) { const lines = wrapText(this.msg, 30); const w = 6 + Math.max(...lines.map(l => textWidth(l))); panel(x + 11 - w / 2, y - 14 - lines.length * 9, w, lines.length * 9 + 4, { rim: '#c8a070' }); lines.forEach((l, i) => text(l, x + 11, y - 12 - lines.length * 9 + i * 9, { color: '#fff', align: 'center' })); } }
}
class Decoy extends Ent {
  constructor(x, y) { super(x - 13, y - 30, 26, 30); this.life = 240; Game.decoy = this; }
  update(L) { this.t++; if (--this.life <= 0) { this.dead = true; FX.confetti(this.cx, this.cy, 30); AudioSys.play_sfx('explode'); for (const e of Game.ents) if (e instanceof Enemy && dist(e.cx, e.cy, this.cx, this.cy) < 60) e.hit(2, {}); if (Game.decoy === this) Game.decoy = null; } }
  draw(cx, cy) { drawHero(this.cx - cx, this.cy - cy - 4, { face: 1, form: 'clown', alpha: .65 + Math.sin(this.t * .3) * .2, sy: 1 + Math.sin(this.t * .2) * .05 }); }
}
class Arena extends Ent { // locks camera and spawns waves
  constructor(o) { super(o.x, 0, o.w, 9999); this.o = Object.assign({}, o, { waves: o.waves.slice(0, 2).map(w => w.slice(0, 3)) }); this.wave = -1; this.active = false; this.done = false; this.spawned = []; }
  update(L) {
    if (this.done) return; const p = Game.player;
    if (!this.active && p.x > this.x + 40 && p.x < this.x + this.w) { this.active = true; L.camLock = { x0: this.x - 16, x1: this.x + this.w + 16 }; AudioSys.setIntensity(2); this.next(); HUD.banner('FIGHT!', '#ff3a3a'); this.walls(true); }
    if (this.active) this.rescue();
    if (this.active && this.spawned.every(e => e.dead)) { if (this.wave + 1 < this.o.waves.length) this.next(); else { this.done = true; this.active = false; L.camLock = null; AudioSys.setIntensity(1); this.walls(false); AudioSys.play_sfx('stinger'); HUD.banner('CLEARED!', '#7fff3a'); if (this.o.flag) Game.flag(this.o.flag); } }
  }
  walls(on) { const L = Game.L, tx0 = Math.floor(this.x / TS) - 1, tx1 = Math.floor((this.x + this.w) / TS); for (let ty = 0; ty < L.h - 2; ty++) { if (L.get(tx0, ty) === T_EMPTY || L.get(tx0, ty) === T_WALL) L.tiles[L.idx(tx0, ty)] = on ? T_WALL : T_EMPTY; if (L.get(tx1, ty) === T_EMPTY || L.get(tx1, ty) === T_WALL) L.tiles[L.idx(tx1, ty)] = on ? T_WALL : T_EMPTY; } }
  // spawn every wave relative to the arena's own floor (flyers used to spawn at a fixed y=120, which in
  // low arenas - e.g. Level 4's candlestick room - put them above the camera where they could never be reached)
  floorAt(x) { const L = Game.L; return Game.groundY(L, clamp(Math.floor(x / TS), 0, L.w - 1)); }
  next() { this.wave++; const kinds = this.o.waves[this.wave]; this.spawned = kinds.map((k, i) => { const x = this.x + 30 + ((i * 97) % (this.w - 60)), gy = this.floorAt(x); const e = new Enemy({ kind: k, x, y: FLYING[k] ? gy - 64 - (i % 2) * 22 : gy - 70 }); e.wake = true; e.offT = 0; if (e.home) e.home.y = e.y; Game.add(e); FX.ring(e.cx, e.cy, 20, '#ff5bd1'); return e; }); }
  // safety net: an enemy that stays out of view or out of the arena gets pulled back in; if it still
  // can't be reached it pops, so a fight can never soft-lock
  rescue() {
    for (const e of this.spawned) { if (e.dead) continue;
      const inView = e.cx > Cam.x - 8 && e.cx < Cam.x + VW + 8 && e.cy > Cam.y - 8 && e.cy < Cam.y + VH + 8, inArena = e.cx > this.x - 8 && e.cx < this.x + this.w + 8;
      e.offT = inView && inArena ? 0 : (e.offT || 0) + 1; e.stuckT = (e.stuckT || 0) + (inView && inArena ? 0 : 1);
      if (e.offT > 150) { const x = clamp(Game.player.cx + (Math.random() < .5 ? -1 : 1) * 90, this.x + 24, this.x + this.w - 40), gy = this.floorAt(x); e.x = x; e.y = FLYING[e.kind] ? gy - 70 : gy - e.h - 2; e.vx = e.vy = 0; if (e.home) { e.home.x = e.x; e.home.y = e.y; } e.offT = 0; FX.ring(e.cx, e.cy, 24, '#ff5bd1'); }
      if (e.stuckT > 600) { e.hit(99, { kind: 'rescue' }); if (!e.dead) e.dead = true; } }
  }
}
class Trigger extends Ent {
  constructor(o) { super(o.x, 0, o.w || 16, o.h || 9999); this.scene = o.scene; this.once = true; this.o = o; }
  update() { if (!this.dead && Game.player.x + Game.player.w > this.x && !Game.cutscene) { this.dead = true; Game.runScene(this.scene, this.o); } }
}
class NPC extends Ent { // static cast member that talks when approached (draws via rig)
  constructor(o) { super(o.x, o.y - 40, 30, 40); this.who = o.who; this.scene = o.scene; this.talked = false; this.o = o; this.face = o.face || -1; this.anim = 'idle'; }
  update(L) { this.t++; if (this.rideOff) { this.x += Math.min(7, (this.rideT = (this.rideT || 0) + 1) * .25); this.anim = 'go'; if (this.t % 3 === 0) FX.smoke(this.x, this.y + this.h - 8, -2); if (this.x > Cam.x + VW + 200) this.dead = true; return; } if (this.leaveT && --this.leaveT <= 0) { this.dead = true; FX.ring(this.cx, this.cy, 30, '#9fff8a'); FX.notes(this.cx, this.y, 4); return; } const p = Game.player; if (this.scene && !this.talked && Math.abs(p.cx - this.cx) < 60 && Math.abs(p.cy - this.cy) < 60 && !Game.cutscene) { this.talked = true; Game.runScene(this.scene, { npc: this }); } if (this.who) Save.see(this.who); }
  draw(cx, cy) { drawActor(this.who, this.cx - cx, this.y + this.h - cy, { face: this.face, t: this.t / 60, anim: this.anim }); if (this.scene && !this.talked) text('!', this.cx - cx, this.y - cy - 30 + Math.sin(this.t * .1) * 2, { color: '#ffe14d', align: 'center', outline: true, scale: 2 }); }
}
// generic "draw any cast member" used by NPCs, cutscene actors, concert, ending
function drawActor(who, x, y, o = {}) {
  const t = o.t || G.t;
  switch (who) {
    case 'hamwise': case 'porkington': case 'trufflina': drawPig(who, x, y, { face: o.face, state: o.anim === 'dance' ? 'dance' : o.anim || 'idle', t }); break;
    case 'razz': drawBiker(x, y, { face: o.face, t, speed: o.anim === 'idle' ? .1 : 1, wheelie: o.anim === 'wheelie' ? .35 + Math.sin(t * 4) * .05 : 0 }); break;
    case 'barnaby': drawWolf(x, y, { face: o.face, t, arm: o.anim === 'howl' ? -.3 : Math.sin(t * 2) * .2, rot: o.anim === 'howl' ? -.2 : 0, scale: o.scale || .7 }); break;
    case 'udderly': drawCow(x, y - (o.anim === 'fly' ? 20 + Math.sin(t * 3) * 6 : 0), { face: o.face, t, scale: o.scale || .6, rot: o.anim === 'fly' ? -.15 : 0, hypno: o.hypno }); break;
    case 'gloop': drawSludge(x, y, { face: o.face, t, scale: o.scale || .45 }); break;
    case 'gloopkin': drawGloopkin(x, y, { face: o.face, t }); break;
    case 'bear': spr(SPR.bear[Math.floor(t * 2) % 2], x, y, { flip: (o.face || 1) < 0 }); break;
    case 'monster': drawHero(x, y - 20, { face: o.face || 1, t, mouth: o.anim === 'sing' ? .5 + Math.sin(t * 12) * .4 : 0, rot: o.anim === 'dance' ? Math.sin(t * 8) * .3 : 0 }); break;
    default: { const f = SPR[who]; if (f) spr(f[Math.floor(t * 6) % f.length], x, y, { flip: (o.face || 1) > 0 }); }
  }
}
