// ============================================================================
// Game: level lifecycle, entity management, scene runner, special objects
// ============================================================================
class HouseSite extends Ent { // straw / stick / brick houses for LEVEL 333 — press ATTACK to build
  constructor(o) { super(o.x - 40, o.y - 80, 96, 80); this.kind = o.kind; this.built = false; this.gone = false; this.ground = o.y; this.scene = o.scene; }
  activate() { if (this.built || Game.cutscene) return; const have = Game.flags[this.kind] || 0; Game.levelStats.built = have; AudioSys.play_sfx('select'); FX.debris(this.cx, this.cy, this.kind === 'straw' ? 'straw' : this.kind === 'stick' ? 'stick' : 'brick', 30); Game.runScene(this.scene); }
  update() { this.t++; }
  draw(cx, cy) {
    if (this.gone) return; const x = Math.round(this.x - cx), y = Math.round(this.ground - cy), k = this.kind;
    if (!this.built) { ctx.strokeStyle = 'rgba(255,255,255,.7)'; ctx.lineWidth = 1.5; ctx.setLineDash([4, 4]); ctx.strokeRect(x + 8, y - 56, 80, 56); ctx.beginPath(); ctx.moveTo(x, y - 56); ctx.lineTo(x + 48, y - 90); ctx.lineTo(x + 96, y - 56); ctx.stroke(); ctx.setLineDash([]); const near = Math.abs(Game.player.cx - this.cx) < 90; text(near ? 'PRESS ATTACK TO BUILD!' : k.toUpperCase() + ' HOUSE GOES HERE', x + 48, y - 104 + (near ? Math.sin(this.t * .2) * 2 : 0), { color: near ? '#ffe14d' : '#fff', align: 'center', outline: true }); text((Game.flags[k] || 0) + ' ' + k.toUpperCase() + ' COLLECTED', x + 48, y - 92, { color: '#fff', align: 'center', outline: true }); return; }
    const wall = k === 'straw' ? '#f0c040' : k === 'stick' ? '#a0662a' : '#c24a2a', roof = k === 'straw' ? '#d8a020' : k === 'stick' ? '#7a4a1a' : '#5a2a2a';
    O.r(x + 8, y - 56, 80, 56, wall); if (k === 'straw') for (let i = 0; i < 20; i++) P.r(ctx, x + 10 + (i * 13) % 76, y - 54 + (i * 7) % 50, 6, 1, '#b08a20');
    if (k === 'stick') for (let i = 0; i < 10; i++) P.r(ctx, x + 10 + i * 8, y - 56, 3, 56, '#6a3a10'); if (k === 'brick') for (let r = 0; r < 7; r++) for (let c = 0; c < 6; c++) P.r(ctx, x + 9 + c * 13 + (r % 2) * 6, y - 55 + r * 8, 12, 1, '#2a0a00');
    O.poly([[x, y - 56], [x + 48, y - 92], [x + 96, y - 56]], roof); O.r(x + 38, y - 30, 20, 30, '#3a1a0a'); O.r(x + 16, y - 46, 14, 12, '#ffe9a0'); O.r(x + 66, y - 46, 14, 12, '#ffe9a0');
  }
}
class Quest extends Ent { constructor(o) { super(o.x, o.y - 32, 16, 32); this.flag = o.flag; this.need = o.need; this.scene = o.scene; Game.need[o.flag] = o.need; Game.quest = this; this.silent = o.silent; }
  update() { if (!this.dead && !Game.cutscene && (Game.player.x > this.x - 40 || (Game.flags[this.flag] || 0) >= this.need)) { this.dead = true; Game.quest = null; Game.runScene(this.scene); } } }
class ChaseZone extends Ent { constructor(o) { super(o.x, 0, 16, 9999); this.o = o; this.on = false; }
  update(L) { if (!this.on && Game.player.x > this.x) { this.on = true; Game.startChase(this.o, this.x); } } }
class ChaseEnd extends Ent { constructor(o) { super(o.x, 0, 16, 9999); this.o = o; } update() { if (!this.dead && Game.player.x > this.x) { this.dead = true; Game.endChase(this.o.scene); } } }
class BossGate extends Ent { constructor(o) { super(o.x, 0, 16, 9999); this.o = o; this.used = false; }
  update() { if (!this.used && Game.player.x > this.x + 40 && !Game.cutscene) { this.used = true; Game.bossGate = this; if (this.seen) { Game.scene.lockArena(); Game.scene.spawnBoss(); } else { this.seen = true; Game.runScene(this.o.scene); } } } }
class Portal extends Ent { constructor(o) { super(o.x, o.y - 48, 28, 48); this.pair = o.pair; this.to = o.to; this.cool = 0; }
  update() { this.t++; if (this.cool > 0) this.cool--; const p = Game.player; if (this.to && !this.cool && overlap(this, p)) { const d = Game.ents.find(e => e instanceof Portal && e.pair === this.to); if (d) { p.x = d.cx - p.w / 2 + 24; p.y = d.y + d.h - p.h - 2; d.cool = 40; this.cool = 40; AudioSys.play_sfx('zap'); FX.ring(d.cx, d.cy, 40, '#b04bff'); Cam.follow(Game.L, p.cx, p.cy, p.face, true); } } }
  draw(cx, cy) { const x = this.cx - cx, y = this.cy - cy; ctx.save(); ctx.globalCompositeOperation = 'lighter'; for (let i = 0; i < 4; i++) { ctx.strokeStyle = hsl((this.t * 6 + i * 40 + (this.to ? 0 : 180)) % 360, 90, 60, .8); ctx.lineWidth = 2; ctx.beginPath(); ctx.ellipse(x, y, 12 - i * 2, 24 - i * 4, 0, 0, 7); ctx.stroke(); } ctx.restore(); if (this.to) text('IN', x, y - 32, { color: '#b04bff', align: 'center', outline: true }); } }
class GravityOrb extends Ent { constructor(o) { super(o.x, o.y, 20, 20); this.cool = 0; }
  update() { this.t++; if (this.cool > 0) this.cool--; const p = Game.player; if (!this.cool && overlap(this, p)) { this.cool = 60; Game.L.gravity *= -1; AudioSys.play_sfx('transform'); FX.ring(this.cx, this.cy, 60, '#ff5bd1'); HUD.toast(Game.L.gravity < 0 ? 'GRAVITY: UPSIDE DOWN' : 'GRAVITY: RESTORED', '#ff5bd1'); } }
  draw(cx, cy) { const x = this.cx - cx, y = this.cy - cy; O.e(x, y, 8, 8, hsl(this.t * 5 % 360, 90, 60)); text(Game.L && Game.L.gravity > 0 ? '▲' : '▼', x - 2, y - 3, { color: '#fff', shadow: false }); } }
class Coaster extends Ent { constructor(o) { super(o.x, o.y - 4, 48, 10); this.solid = true; this.oneway = true; this.len = o.len * TS; this.x0 = o.x; this.go = false; this.dx = 0; this.vy = 0; this.ride = 0; }
  update(L) { this.t++; const p = Game.player; if (p.riding === this) this.go = true; const ox = this.x; if (this.go && this.x < this.x0 + this.len) { this.ride = Math.min(4.2, this.ride + .05); this.x += this.ride; if (this.t % 8 === 0) AudioSys.play_sfx('coaster'); } this.dx = this.x - ox; if (p.riding === this) p.x += this.dx; }
  draw(cx, cy) { const x = Math.round(this.x - cx), y = Math.round(this.y - cy); O.r(x, y - 14, 48, 18, '#ff3a6a'); P.r(ctx, x + 4, y - 12, 40, 4, '#ffe14d'); for (const wx of [10, 38]) O.e(x + wx, y + 6, 5, 5, '#333'); if (!this.go) text('RIDE!', x + 24, y - 26, { color: '#ffe14d', align: 'center', outline: true, wave: 1 }); } }
class SoundSwitch extends Switch { draw(cx, cy) { const x = Math.round(this.x - cx), y = Math.round(this.y - cy); O.r(x - 6, y - 12, 28, 30, this.on ? '#3a6a3a' : '#2a2a30'); P.e(ctx, x + 8, y + 4, 8 + (this.on ? 0 : Math.sin(G.t * 8) * 2), 8, this.on ? '#7fff3a' : '#555'); if (!this.on) text('ATTACK!', x + 8, y - 24, { color: '#7fff3a', align: 'center', outline: true }); }
  update(L) { this.t++; } }
class FinishLine extends Ent { constructor(o) { super(o.x, 0, 16, 9999); } update() { if (!Game.raceDone && Game.player.x > this.x) Game.raceWon(); }
  draw(cx, cy) { const x = Math.round(this.x - cx); for (let y = 0; y < H; y += 8) { P.r(ctx, x, y, 8, 8, (y / 8) % 2 ? '#fff' : '#000'); P.r(ctx, x + 8, y, 8, 8, (y / 8) % 2 ? '#000' : '#fff'); } text('FINISH', x + 8, 80, { color: '#ffe14d', align: 'center', outline: true, scale: 2 }); } }
class Actor { constructor(who, x, y, face, anim, o) { this.who = who; this.x = x; this.y = y; this.face = face; this.anim = anim || 'idle'; this.o = o || {}; this.mv = null; this.t = 0; }
  update() { this.t++; if (this.mv) { const m = this.mv; m.t++; const k = Math.min(1, m.t / m.n); this.x = lerp(m.x0, m.x1, k); this.y = lerp(m.y0, m.y1, k); if (k >= 1) this.mv = null; } }
  draw(cx, cy) { drawActor(this.who, this.x - cx, this.y - cy, Object.assign({ face: this.face, t: this.t / 60, anim: this.mv ? 'walk' : this.anim }, this.o)); } }

const Game = {
  ents: [], flags: {}, need: {}, actors: [], player: null, L: null, def: null, chapter: 0, cutscene: null, decoy: null, ally: null,
  levelStats: { notes: 0, kills: 0, time: 0, shards: [] }, finishing: false, checkpoint: null, party: null, partyIdx: 0, followers: [], transformMenu: null,
  add(e) { this.ents.push(e); return e; }, countEnts(f) { let n = 0; for (const e of this.ents) if (!e.dead && f(e)) n++; return n; }, findEnt(f) { return this.ents.find(e => !e.dead && f(e)); },
  flag(n) { this.flags[n] = (this.flags[n] || 0) + 1; },
  noteMilestone() { const n = this.levelStats.notes; if (n > 0 && n % 25 === 0) { HUD.banner(n + ' NOTES!!', '#ffe14d', pick(['HISTORY WILL REMEMBER THIS DAY.', 'THE NARRATOR IS CRYING.', 'SOMEBODY CALL YOUR MOM.', 'A STATUE WILL BE BUILT.', 'THE UNIVERSE IS 0.01% SAVED.'])); FX.confetti(this.player.cx, this.player.y - 100, 40); AudioSys.play_sfx('cheer'); } },
  shardsHave(id) { const d = Save.data.done[this.saveKey()]; return d && d.shards && d.shards[id]; },
  saveKey() { return this.def.id; },
  collectShard(id) { this.levelStats.shards[id] = true; },
  // ------------------------------------------------------------------ level loading
  loadLevel(def, chapter = 0, keepStats) {
    this.def = def; this.chapter = chapter; const ch = def.chapters ? def.chapters[chapter] : null; const sub = ch ? Object.assign({}, def, ch, { id: def.id, w: ch.w }) : def;
    this.sub = sub; this.ents = []; this.flags = {}; this.need = {}; this.actors = []; this.cutscene = null; this.finishing = false; this.decoy = null; this.ally = null; this.quest = null; this.chase = null; this.raceDone = false; this.bossGate = null; this.boss = null; this.followers = []; this.party = null; this.slow = 0;
    FX.clear(); AudioSys.setEngine(false); rnd = mulberry(hashStr(def.id + chapter));
    if (!keepStats) this.levelStats = { notes: 0, kills: 0, time: 0, shards: [], hits: 0 };
    const L = new Level(Object.assign({}, sub, { id: def.id + '_' + chapter })); this.L = L; L.solidEnts = [];
    const B = new Builder(L, sub); sub.build(B);
    if (!sub.vertical) { const lastX = B.cx; if (lastX + 2 < L.w) { L.w = Math.max(lastX + 4, 60); const nt = new Uint8Array(L.w * L.h); for (let y = 0; y < L.h; y++) for (let x = 0; x < L.w; x++) nt[y * L.w + x] = L.tiles[y * (sub.w || 1400) + x] || 0; L.tiles = nt; } }
    if (sub.ceiling) for (let x = 0; x < L.w; x++) { L.tiles[x] = T_SOLID; L.tiles[L.w + x] = T_SOLID; }
    if (sub.styleShift) { L.styles = sub.styleShift.map(t => ({ th: THEMES[t], ts: buildTileset(THEMES[t], L.seed + t.length), bg: buildBackground(THEMES[t], L.seed + t.length) })); L.styleIdx = 0; L.styleT = 0; }
    L.buildChunks();
    // player
    const sx = L.startX || 48, sy = L.startY || this.groundY(L, Math.floor(sx / TS)) - 40;
    this.player = new Player(sx, sy); this.checkpoint = { x: sx, y: sy }; this.player.gdir = 1;
    if (sub.party) { this.party = null; this.followers = sub.party.filter(c => c !== 'monster').map((c, i) => new PigFollower(c, sx - 20 - i * 20, sy)); }
    if (sub.race) this.player.vehicle = true;
    for (const s of L.spawns) this.spawn(s, L);
    if (!sub.chapters && !sub.concert) this.decorateLevel(L, sub);
    if (sub.allyCow) this.add(new UdderlyAlly(sx - 60, sy - 60));
    Cam.follow(L, this.player.cx, this.player.cy, 1, true);
    AudioSys.play(sub.song || def.song); AudioSys.setIntensity(1);
    G.state = 'level'; HUD.reset();
    if (def.id === 'L3') { Save.data.ch333 = chapter; Save.write(); }
    if (sub.intro) this.runScene(sub.intro);
    if (sub.wind) L.windGusts = true;
    if (sub.concert) { /* concert chapter starts from its intro scene */ }
  },
  decorateLevel(L, sub) { // campaign-wide: a set-piece spectacle, themed power-ups and generous checkpoints
    const arenas = this.ents.filter(e => e instanceof Arena || e instanceof BossGate).map(e => [e.x - 80, e.x + (e.o && e.o.w || 600) + 80]);
    const free = tx => !arenas.some(([a, b]) => tx * TS > a && tx * TS < b);
    const flatAt = frac => { for (let tx = Math.floor(L.w * frac); tx < L.w - 10; tx++) { const gy = this.groundY(L, tx); if (gy < L.h * TS - 48 && this.groundY(L, tx + 1) === gy && this.groundY(L, tx - 1) === gy && free(tx)) return [tx, gy]; } return null; };
    if (sub.spectacle) { const p = sub.vertical ? [8, 0] : flatAt(.42); if (p) this.add(new SetPiece({ x: p[0] * TS, kind: sub.spectacle })); }
    if (sub.powers) sub.powers.forEach((k, i) => { const p = flatAt([.22, .62][i]); if (p) this.add(new PowerUp({ x: p[0] * TS, y: p[1] - 3 * TS, kind: k })); });
    if (!sub.vertical && !sub.race) { const cps = this.ents.filter(e => e instanceof Checkpoint).map(e => e.x / TS); for (let tx = 40; tx < L.w - 30; tx += 38) { if (cps.some(c => Math.abs(c - tx) < 24)) continue; for (let k = 0; k < 10; k++) { const x = tx + k, gy = this.groundY(L, x); if (gy < L.h * TS - 48 && this.groundY(L, x + 1) === gy && free(x)) { this.add(new Checkpoint(x * TS, gy - 32)); cps.push(x); break; } } } }
  },
  groundY(L, tx) { for (let ty = 3; ty < L.h; ty++) if (L.solidAt(tx, ty) && !L.solidAt(tx, ty - 1) && !L.solidAt(tx, ty - 2)) return ty * TS; return L.h * TS - 48; },
  spawn(s, L) {
    switch (s.type) {
      case 'enemy': this.add(new Enemy(s)); break;
      case 'note': this.add(new Note(s.x + 3, s.y)); break;
      case 'hook': this.add(new Hook(s.x + 8, s.y + 8)); break;
      case 'mplat': { const m = this.add(new MovingPlat(s)); L.solidEnts.push(m); break; }
      case 'checkpoint': this.add(new Checkpoint(s.x, s.y)); break;
      case 'exit': this.add(new Exit(s.x, s.y)); break;
      case 'shard': this.add(new Shard(s.x, s.y, s.id || 0)); break;
      case 'arena': this.add(new Arena(s)); break;
      case 'trigger': this.add(new Trigger(s)); break;
      case 'npc': this.add(new NPC(s)); break;
      case 'switch': this.add(new Switch(s)); break;
      case 'soundswitch': this.add(new SoundSwitch(s)); break;
      case 'door': { const d = this.add(new Door(s)); L.solidEnts.push(d); break; }
      case 'blueprint': this.add(new Blueprint(s)); break;
      case 'slot': this.add(new BrickSlot(s)); break;
      case 'brick': this.add(new BrickItem(s.x, s.y)); break;
      case 'collect': this.add(new Collectable(s)); this.need[s.flag] = (this.need[s.flag] || 0) + 1; break;
      case 'pull': { const p = this.add(new Pullable(s)); L.solidEnts.push(p); break; }
      case 'amp': { const a = this.add(new AmpTotem(s)); L.solidEnts.push(a); break; }
      case 'sign': this.add(new Sign(s)); break;
      case 'power': this.add(new PowerUp({ x: s.x, y: s.y, kind: s.kind })); break;
      case 'prompt': this.add(new Prompt(s)); break;
      case 'joke': { const j = this.add(new JokeBlock(s)); L.solidEnts.push(j); break; }
      case 'bigamp': this.add(new BigAmp(s)); break;
      case 'meganote': this.add(new MegaNote(s)); break;
      case 'setpiece': this.add(new SetPiece(s)); break;
      case 'housesite': this.add(new HouseSite(s)); break;
      case 'quest': this.add(new Quest(s)); break;
      case 'chasezone': case 'scrollzone': this.add(new ChaseZone(Object.assign({ collapse: s.type === 'scrollzone' }, s))); break;
      case 'chaseend': this.add(new ChaseEnd(s)); break;
      case 'bossgate': this.add(new BossGate(s)); break;
      case 'portal': this.add(new Portal(s)); break;
      case 'gravity': break; // gravity flips removed for clarity
      case 'coaster': { const c = this.add(new Coaster(s)); L.solidEnts.push(c); break; }
      case 'racestart': this.racer = this.add(new RazzRacer({ x: s.x + 20, y: s.y, finishX: 0 })); break;
      case 'finish': this.add(new FinishLine(s)); if (this.racer) this.racer.finishX = s.x; break;
    }
  },
  // ------------------------------------------------------------------ main update
  update() {
    const L = this.L, p = this.player; if (!L) return;
    if (this.transformMenu) return this.updateTransformMenu();
    if (Input.pressed.pause && !this.cutscene) { Menus.open('pause'); return; }
    this.levelStats.time++;
    if (this.slow > 0) { this.slow--; if (this.slow % 3) return; }
    L.update();
    if (L.styles && ++L.styleT > 600) { L.styleT = 0; L.styleIdx = (L.styleIdx + 1) % L.styles.length; const s = L.styles[L.styleIdx]; L.theme = Object.assign({}, s.th, { hz: L.theme.hz }); L.tileset = s.ts; L.bg = s.bg; L.dirtyAll(); HUD.banner('REALITY SHIFT!', hsl(R(360), 90, 60)); AudioSys.play_sfx('transform'); Cam.shake(4, 10); FX.burst(p.cx, p.cy, 30, ['#fff', '#b04bff', '#ffe14d'], { speed: 6 }); }
    if (L.windGusts) { const ph = (L.windT = (L.windT || 0) + 1) % 420; L.wind = ph > 300 ? -.18 * Math.sin((ph - 300) / 120 * Math.PI) : 0; if (L.wind && ph % 4 === 0) FX.add({ x: Cam.x + W, y: Cam.y + R(H), vx: -6, vy: 0, col: '#fff8', size: 2, life: 120, grav: 0 }); }
    if (this.chase) { L.scrollX += this.chase.speed; if (this.chase.collapse && L.scrollX > 0) { const tx = Math.floor(L.scrollX / TS) - 1; for (let ty = 0; ty < L.h; ty++) { const t = L.get(tx, ty); if (t === T_SOLID || t === T_ONEWAY || t === T_CRUMBLE) { L.set(tx, ty, T_EMPTY); if (R() < .15) FX.add({ x: tx * TS + 8, y: ty * TS, vx: R(-1, 1), vy: R(-1, 1), col: L.theme.g[R() < .5 ? 0 : 1], size: 4, life: 60, grav: .2 }); } } if (this.levelStats.time % 70 === 0) this.add(new EnemyShot(Cam.x + R(100, W), Cam.y - 10, 0, 2.5, 'brick')); } }
    if (!this.cutscene || this.cutscene.free) { if (p.vehicle) updateVehicle(p, L); else p.update(L); }
    else { p.attacks = []; if (!p.onGround) { p.vy = Math.min(p.vy + PHYS.grav, 6); moveBody(p, L); } p.vx *= .8; if (p.dead) { p.dead++; if (p.dead > 80) this.respawn(); } }
    p.gdir = L.gravity;
    for (const f of this.followers) f.update(L, p, this.followers.indexOf(f));
    for (const e of this.ents) if (!e.dead && (Math.abs(e.cx - p.cx) < W * 1.2 || e.isBoss || e instanceof MovingPlat || e instanceof Chaser || e instanceof GiantChaser || e instanceof SetPiece || e instanceof RazzRacer || e instanceof Arena || e instanceof Quest || e instanceof UdderlyAlly || e instanceof Summon || e instanceof Coaster)) e.update(L);
    // player attacks vs enemies & bosses
    if (p.attacks.length) for (const e of this.ents) {
      if (e.dead) continue;
      if (e instanceof Enemy && e.wake) { for (const a of p.attacks) if (overlap(a, e)) { if (a.circle && dist(p.cx, p.cy, e.cx, e.cy) > a.circle) continue; const landed = e.hit(a.dmg, Object.assign({ dir: p.face }, a)); if (landed && a.onHit) a.onHit(e); if (landed && a.kind === 'bash' && !p.onGround) { p.vy = -5.5; p.airSpun = false; FX.pop(e.cx, e.y - 8, 'BOING!', '#7fff3a'); } break; } }
      else if (e.isBoss) { const hb = e.hitbox(); for (const a of p.attacks) if (overlap(a, hb)) { if (a.circle && dist(p.cx, p.cy, hb.x + hb.w / 2, hb.y + hb.h / 2) > a.circle + Math.max(hb.w, hb.h) / 2) continue; if (e.hit(a.dmg, a) && a.onHit) a.onHit(e); break; } }
    }
    this.ents = this.ents.filter(e => !e.dead || e instanceof Trigger);
    if (L.solidEnts.some(s => s.dead)) L.solidEnts = L.solidEnts.filter(s => !s.dead);
    for (const a of this.actors) a.update();
    if (this.cutscene) this.stepScene();
    FX.update();
    if (L.wind && !this.chase && !L.windGusts && !this.boss) L.wind *= .9;
    Cam.follow(L, p.cx, p.cy, p.face, false);
    HUD.update();
  },
  // ------------------------------------------------------------------ draw
  draw() {
    const L = this.L, p = this.player; if (!L) return;
    const sx = Cam.ox(), sy = Cam.oy(), cx = Cam.x + sx / ZOOM, cy = Cam.y + sy / ZOOM, scx = cx * ZOOM;
    // ---- screen-space painted parallax backdrop
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    if (L.bg.skyC) ctx.drawImage(L.bg.skyC, 0, 0); else { ctx.fillStyle = L.theme.sky[0]; ctx.fillRect(0, 0, W, H); }
    const vy = clamp((cy - (L.h * TS - VH)) * .25, -60, 0);
    const par = (img, f, oy) => { const ox = -((scx * f) % img.width + img.width) % img.width, yy = Math.round(oy + vy * f * 2); ctx.drawImage(img, Math.round(ox), yy); ctx.drawImage(img, Math.round(ox) + img.width, yy); };
    par(L.bg.far, .15, 0);
    for (const fn of L.bg.anim) fn(ctx, G.t, scx);
    par(L.bg.mid, .4, 10);
    for (const fn of L.bg.animF || []) fn(ctx, G.t, scx);
    // ---- world (zoomed)
    ctx.setTransform(ZOOM, 0, 0, ZOOM, 0, 0);
    for (const e of this.ents) if (e.drawBG && !e.dead) e.drawBG(cx, cy);
    for (const pr of L.props) { const x = pr.x - cx; if (x > -80 && x < VW + 80) spr(pr.img, x, pr.y - cy, pr.img.hd ? { sx: HD, sy: HD } : {}); }
    L.drawTiles(cx, cy);
    for (const e of this.ents) if (!e.dead && !(e instanceof Enemy) && !e.isBoss && !(e instanceof SlimeBall) && !(e instanceof EnemyShot) && Math.abs(e.cx - cx - VW / 2) < VW) e.draw(cx, cy);
    for (const e of this.ents) if (!e.dead && e.isBoss) e.draw(cx, cy);
    for (const e of this.ents) if (!e.dead && e instanceof Enemy && Math.abs(e.cx - cx - VW / 2) < VW) e.draw(cx, cy);
    for (const f of this.followers) f.draw(cx, cy);
    for (const a of this.actors) a.draw(cx, cy);
    if (p.vehicle) drawVehicle(p, cx, cy); else p.draw(cx, cy);
    for (const e of this.ents) if (!e.dead && (e instanceof SlimeBall || e instanceof EnemyShot)) e.draw(cx, cy);
    FX.draw(cx, cy);
    for (const e of this.ents) if (e.drawFG && !e.dead) e.drawFG(cx, cy);
    if (this.chase && this.chase.collapse) { const x = L.scrollX - cx; const gg = ctx.createLinearGradient(x - 30, 0, x + 40, 0); gg.addColorStop(0, 'rgba(20,0,30,1)'); gg.addColorStop(1, 'rgba(60,0,80,0)'); ctx.fillStyle = gg; ctx.fillRect(-10, -10, x + 50, VH + 20); }
    // ---- screen-space overlays
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    drawLighting(L, scx);
    HUD.draw();
    if (this.cutscene) this.drawScene();
    if (G.debug) { text('ents ' + this.ents.length + ' fx ' + FX.list.length + ' x ' + (p.x | 0) + ' y ' + (p.y | 0) + ' ' + G.fps + 'fps', 4, H - 10, { color: '#0f0' }); }
  },
  // ------------------------------------------------------------------ gameplay helpers
  nearestHook(p) { let best = null, bd = 135; for (const e of this.ents) if (e instanceof Hook) { const d = dist(p.cx, p.cy, e.cx, e.cy); if (d < bd && e.cy < p.cy + 10) { bd = d; best = e; } } return best ? { x: best.cx, y: best.cy } : null; },
  stunAll(x, y, r, t) { for (const e of this.ents) if (e instanceof Enemy && !e.dead && dist(x, y, e.cx, e.cy) < r) e.stun(t); },
  soundSwitch(x, y, r) { for (const e of this.ents) if (e instanceof SoundSwitch && dist(x, y, e.cx, e.cy) < r + 20) e.activate(); },
  onHeadbang(p) { for (const e of this.ents) if (e instanceof SoundSwitch && dist(p.cx, p.cy, e.cx, e.cy) < 80 && p.combo >= 3) e.activate(); },
  megaScream(x, y, r) { for (const e of this.ents) if (e instanceof AmpTotem && dist(x, y, e.cx, e.cy) < r) e.blow(); Cam.shake(10, 30); FX.burst(x, y, 50, ['#7fff3a', '#fff', '#ffe14d'], { speed: 7 }); },
  bossAttack(box) { const p = this.player; if (overlap(box, p)) p.hurt(1, box.x + box.w / 2); },
  summon() {
    const s = Save.data.summons; if (!s.length) { HUD.toast('NO ALLIES TO SUMMON YET', '#aaa'); return; }
    if (Input.held.down) { this.player.summonSel = (this.player.summonSel + 1) % s.length; HUD.toast('SUMMON: ' + SUMMONS[s[this.player.summonSel]].name, '#5bd4ff'); AudioSys.play_sfx('menu'); return; }
    if (this.player.metal < 50) { HUD.toast('NEED 50 METAL TO SUMMON', '#ff3a3a'); AudioSys.play_sfx('miss'); return; }
    if (this.countEnts(e => e instanceof Summon)) return;
    const k = s[this.player.summonSel % s.length]; this.player.metal -= 50; this.add(new Summon(k)); HUD.banner(SUMMONS[k].name + '!', '#5bd4ff'); AudioSys.play_sfx('stinger'); Save.achieve('summon');
  },
  switchPig() {
    if (!this.party || this.party.length < 2) return; const p = this.player;
    const oldChar = p.char; this.partyIdx = (this.partyIdx + 1) % this.party.length; const next = this.party[this.partyIdx];
    const fIdx = this.followers.findIndex(f => f.id === next);
    let nx = p.x, ny = p.y; if (fIdx >= 0) { const f = this.followers[fIdx]; nx = f.x; ny = f.y; this.followers.splice(fIdx, 1); }
    if (oldChar !== 'monster') { const nf = new PigFollower(oldChar, p.x, p.y + p.h - 20); this.followers.push(nf); }
    const bottom = ny + (fIdx >= 0 ? 20 : p.h); p.setChar(next); p.x = nx; p.y = bottom - p.h; p.vx = p.vy = 0; p.carry = null;
    AudioSys.play_sfx(next === 'monster' ? 'growl' : 'oink', { pitch: next === 'monster' ? 1 : PIGS[next].pitch }); FX.ring(p.cx, p.cy, 30, '#ff8ab0'); HUD.toast('NOW PLAYING: ' + (next === 'monster' ? 'MOSHMOUTH' : PIGS[next].name.toUpperCase()), '#ff8ab0');
    this.swapped = this.swapped || {}; this.swapped[next] = 1; if (['hamwise', 'porkington', 'trufflina'].every(k => this.swapped[k] || this.party.indexOf(k) < 0) && this.party.length >= 3) Save.achieve('pigSwap');
  },
  openTransform() { const forms = Save.data.forms; if (forms.length < 2) { HUD.toast('NO TRANSFORMATIONS UNLOCKED YET', '#aaa'); return; } this.transformMenu = { sel: Math.max(0, forms.indexOf(this.player.form)) }; AudioSys.play_sfx('menu'); },
  updateTransformMenu() {
    const m = this.transformMenu, forms = ['normal', ...['pig', 'wolf', 'cow', 'bear', 'clown', 'mega'].filter(f => Save.data.forms.includes(f))];
    if (Input.pressed.left) { m.sel = (m.sel + forms.length - 1) % forms.length; AudioSys.play_sfx('menu'); } if (Input.pressed.right) { m.sel = (m.sel + 1) % forms.length; AudioSys.play_sfx('menu'); }
    if (Input.pressed.confirm || Input.pressed.transform || Input.pressed.whip) {
      const f = forms[m.sel]; if (f === 'mega' && this.player.metal < 100 && this.player.form !== 'mega') { HUD.toast('MEGA NEEDS A FULL METAL METER', '#ff3a3a'); AudioSys.play_sfx('miss'); } else { this.player.setForm(f); }
      this.transformMenu = null; this.formsCheck(); }
    if (Input.pressed.back || Input.pressed.pause) this.transformMenu = null;
    m.forms = forms;
  },
  formsCheck() { if (['pig', 'wolf', 'cow', 'bear', 'clown', 'mega'].every(f => Save.data.forms.includes(f))) Save.achieve('allForms'); },
  drawTransformMenu() {
    const m = this.transformMenu, forms = m.forms || ['normal']; ctx.fillStyle = 'rgba(10,0,20,.7)'; ctx.fillRect(0, 0, W, H);
    text('TRANSFORMATION', W / 2, 40, { color: '#7fff3a', align: 'center', scale: 2, outline: true });
    const n = forms.length, sp = 84, x0 = W / 2 - (n - 1) * sp / 2;
    forms.forEach((f, i) => { const x = x0 + i * sp, sel = i === m.sel; panel(x - 36, 110, 72, 92, { rim: sel ? '#7fff3a' : '#444' }); drawHero(x, 152, { face: 1, form: f, sx: f === 'mega' ? .7 : .9, sy: f === 'mega' ? .7 : .9, rot: sel ? Math.sin(G.t * 6) * .1 : 0 }); text(FORMS[f].name.replace(' MODE', ''), x, 190, { color: sel ? '#fff' : '#888', align: 'center' }); });
    const f = forms[m.sel]; panel(80, 230, W - 160, 40, { rim: '#7fff3a' }); text(FORMS[f].name, W / 2, 238, { color: '#7fff3a', align: 'center' }); text(FORMS[f].desc, W / 2, 252, { color: '#fff', align: 'center' });
    text('◄ ► choose    CONFIRM / ' + (K().form) + ' select', W / 2, 290, { color: '#aaa', align: 'center' });
  },
  // ------------------------------------------------------------------ chase / race
  startChase(o, x) { const L = this.L; L.autoScroll = true; L.scrollX = Cam.x; this.chase = { speed: o.scroll, startX: x, collapse: o.collapse }; this.checkpoint = { x: x - 32, y: this.groundY(L, Math.floor(x / TS)) - 40 }; if (o.giant) { this.chaser = this.add(new GiantChaser({ x: Cam.x - 100, y: this.groundY(L, Math.floor(Cam.x / TS) + 2) })); } else if (!o.collapse) { this.chaser = this.add(new Chaser({ x: Cam.x - 100, y: this.groundY(L, Math.floor(Cam.x / TS) + 2), rider: o.rider, lines: o.lines })); } AudioSys.setIntensity(2); HUD.banner(o.collapse ? 'THE STAGE IS COLLAPSING!' : o.giant ? 'RUN!!!' : 'CHASE!', '#ff3a3a'); },
  endChase(scene) { const L = this.L; L.autoScroll = false; this.chase = null; if (this.chaser) { this.chaser.dead = true; this.chaser = null; } AudioSys.setEngine(false); AudioSys.setIntensity(1); if (scene) this.runScene(scene); },
  raceWon() { this.raceDone = true; AudioSys.setEngine(false); AudioSys.play_sfx('cheer'); HUD.banner('YOU WIN!', '#7fff3a'); this.player.vehicle = true; this.runScene('L23_win', {}, () => { this.player.vehicle = false; this.finishLevel(); }); },
  raceLost() { this.raceDone = true; AudioSys.play_sfx('miss'); HUD.banner('RAZZ WINS...', '#ff3a3a'); this.runScene('L23_lose', {}, () => { this.restartLevel(); }); },
  // ------------------------------------------------------------------ bosses
  bossDefeated(b) {
    this.boss = null; Save.see({ wolf: 'barnaby', cow: 'cowboss', overlord: 'overlord', puppetking: 'puppetking', devourer: 'devourer', clown: 'clownboss', heap: 'heap', feedback: 'feedback' }[this.bossGate ? this.bossGate.o.kind : ''] || 'barnaby');
    if (this.player.hitTaken === this.bossHits) Save.achieve('noHit');
    if (this.def.id === 'L3') Save.achieve('wolf1');
    AudioSys.setIntensity(1); this.L.wind = 0; this.L.gravity = 1;
    setTimeout(() => { for (const e of this.ents) if (e instanceof Enemy) e.kill(); }, 0);
    this.bossWinTimer = 130;
    const done = () => {
      if (this.def.chapters) { if (this.cutscene && this.cutscene.nextChapter) return; }
      const g = this.bossGate; if (g) { const L = this.L, tx = Math.floor((g.o.x0 + g.o.w) / TS); L.fill(tx, 0, tx + 1, L.h - 1, T_EMPTY); L.fill(tx, g.o.gy, tx + 1, L.h - 1, T_SOLID); L.camLock = null; this.add(new Exit((tx + 6) * TS, g.o.gy * TS)); L.dirtyAll(); HUD.toast('THE WAY FORWARD IS OPEN  ►', '#7fff3a'); }
    };
    this.pendingWin = { scene: this.def.id + '_win', done };
  },
  // ------------------------------------------------------------------ life cycle
  respawn() {
    const p = this.player, cp = this.checkpoint, L = this.L; Save.write();
    const wasChar = p.char, form = p.form === 'mega' ? 'normal' : p.form, metal = p.metal;
    this.player = new Player(cp.x, cp.y - 8); if (p.powerT > 0 && form !== 'mega') { this.player.setForm(form, true); this.player.powerT = p.powerT; }
    if (this.def.race || this.sub.race) { this.player.vehicle = true; if (this.racer) this.racer.x = Math.min(this.racer.x, cp.x - 40); }
    FX.ring(this.player.cx, this.player.cy, 50, '#7fff3a', 30); AudioSys.play_sfx('transform');
    if (this.boss || (this.bossGate && this.bossGate.used && !this.ents.some(e => e.isBoss && e.defeated))) { for (const e of this.ents) if (e.isBoss) e.dead = true; this.boss = null; L.camLock = null; if (this.bossGate) { this.bossGate.used = false; } L.wind = 0; L.gravity = 1; AudioSys.setEngine(false); AudioSys.setIntensity(1); const a = this.ents.find(e => e instanceof Arena); }
    for (const e of this.ents) if (e instanceof Arena && e.active) { e.active = false; e.wave = -1; e.walls(false); L.camLock = null; for (const s of e.spawned) s.dead = true; }
    if (this.chase) { L.scrollX = Math.max(0, cp.x - 80); Cam.x = L.scrollX; if (this.chaser) this.chaser.x = Cam.x - 100; }
    Cam.follow(L, this.player.cx, this.player.cy, 1, true);
  },
  restartLevel() { this.loadLevel(this.def, this.chapter); },
  nextChapter() {
    const ch = this.def.chapters; if (!ch) return; if (this.chapter + 1 < ch.length) { const st = this.levelStats; this.loadLevel(this.def, this.chapter + 1, true); this.levelStats = st; HUD.banner('LEVEL 333 — ' + ch[this.chapter].name.split(':')[0].toUpperCase(), '#ff8ab0'); } else this.finishLevel();
  },
  finishLevel() {
    if (this.finishing) return; this.finishing = true;
    if (this.def.chapters && this.chapter + 1 < this.def.chapters.length) { this.finishing = false; this.nextChapter(); return; }
    AudioSys.play_sfx('stinger'); AudioSys.setEngine(false);
    const id = this.def.id, d = Save.data.done[id] || { shards: [], best: 0, notes: 0 };
    for (let i = 0; i < 3; i++) d.shards[i] = d.shards[i] || !!this.levelStats.shards[i];
    d.notes = Math.max(d.notes || 0, this.levelStats.notes); d.time = Math.min(d.time || 1e9, this.levelStats.time); d.clear = true;
    Save.data.done[id] = d; Save.data.unlocked = Math.max(Save.data.unlocked, this.def.num + 1); Save.unlockSong(this.def.song); if (this.def.chapters) this.def.chapters.forEach(c => c.song && Save.unlockSong(c.song)); if (id === 'L3') { Save.data.ch333 = 0; }
    const rw = LEVEL_REWARDS[id] || {}; if (rw.form) Save.form(rw.form); if (rw.form2) Save.form(rw.form2); if (rw.summon) Save.summon(rw.summon); if (rw.ach) Save.achieve(rw.ach);
    const tot = Object.values(Save.data.done).reduce((a, d) => a + (d.shards || []).filter(Boolean).length, 0); if (tot >= 10) Save.achieve('shards10'); if (tot >= 45) Save.achieve('shards45');
    if (Object.keys(Save.data.seen).length >= 30) Save.achieve('ency'); this.formsCheck();
    Save.write();
    Results.show(this.def, this.levelStats, () => {
      if (id === 'L30') { Ending.start(); return; }
      const outro = id === 'L3' ? 'L3_outro' : null;
      if (outro) { this.runScene(outro, {}, () => WorldMap.open(this.def.num + 1)); this.finishing = false; G.state = 'level'; } else WorldMap.open(this.def.num + 1);
    });
  },
  // ------------------------------------------------------------------ cutscene runner
  runScene(id, o = {}, onDone) {
    const steps = STORY[id]; if (!steps) { if (onDone) onDone(); return; }
    this.cutscene = { id, steps, i: 0, wait: 0, dlg: null, o, onDone, skip: false, charT: 0 };
    if (id.startsWith('L1_tut') || id === 'rescue') this.cutscene.free = false;
    AudioSys.setIntensity(Math.min(AudioSys.targetIntensity, 1));
  },
  stepScene() {
    const c = this.cutscene; if (!c) return;
    if ((Input.pressed.pause || Input.pressed.back) && !c.skip) { c.skip = true; }
    for (let guard = 0; guard < 400; guard++) {
      if (c.dlg) {
        const full = c.dlg.text; c.charT += c.skip ? 999 : 1.2; if (Math.floor(c.charT) % 3 === 0 && c.charT < full.length) AudioSys.play_sfx('text');
        if (c.skip) { c.dlg = null; continue; }
        if (Input.pressed.confirm || Input.pressed.whip) { if (c.charT < full.length) c.charT = full.length; else { c.dlg = null; AudioSys.play_sfx('menu'); } }
        return;
      }
      if (c.waitFn) { if (c.skip || c.waitFn()) c.waitFn = null; else return; }
      if (c.wait > 0) { if (c.skip) c.wait = 0; else { c.wait--; return; } }
      if (c.i >= c.steps.length) { this.endScene(); return; }
      const st = c.steps[c.i++];
      if (typeof st === 'number') c.wait = st;
      else if (Array.isArray(st)) { const t = typeof st[1] === 'function' ? st[1]() : st[1]; c.dlg = { who: st[0], text: t }; c.charT = 0; if (st[0] !== 'narrator' && st[0] !== 'sign') Save.see(st[0] === 'monster' ? 'monster' : st[0]); }
      else if (typeof st === 'function') { const r = st(this.scene); if (typeof r === 'number') c.wait = r; else if (typeof r === 'function') c.waitFn = r; if (!this.cutscene || this.cutscene !== c) return; }
    }
  },
  endScene() {
    const c = this.cutscene; this.cutscene = null; if (G.state === 'level') AudioSys.setIntensity(this.boss ? 3 : 1);
    if (c.nextChapter) { this.nextChapter(); return; }
    if (c.concert) { Concert.start(c.concert, c.final); return; }
    if (c.onDone) c.onDone();
    if (this.pendingWin && !this.cutscene) { const w = this.pendingWin; this.pendingWin = null; this.runScene(w.scene, {}, w.done); }
  },
  drawScene() {
    const c = this.cutscene; if (!c) return;
    if (c.card) { ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H); text(c.card[0], W / 2, H / 2 - 20, { color: '#7fff3a', align: 'center', scale: 3, outline: '#300', wave: 1 }); text(c.card[1], W / 2, H / 2 + 20, { color: '#fff', align: 'center', scale: 1 }); }
    if (c.flash > 0) { ctx.globalAlpha = c.flash / 20; ctx.fillStyle = c.flashCol; ctx.fillRect(0, 0, W, H); ctx.globalAlpha = 1; c.flash--; }
    if (!c.free) { ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, 18); ctx.fillRect(0, H - 18, W, 18); text('SKIP: ' + (Input.mode === 'touch' ? 'II' : Input.mode === 'pad' ? 'START' : 'ESC'), W - 6, 6, { color: '#666', align: 'right', shadow: false }); }
    if (c.dlg) {
      const d = c.dlg, who = CAST[d.who] || CAST.narrator, n = Math.floor(c.charT), str = d.text.slice(0, n);
      const lines = wrapText(str, who.portrait ? 74 : 92), y = H - 92;
      panel(10, y, W - 20, 70, { rim: who.col }); let tx = 20;
      if (who.portrait) { const im = who.portrait(); if (im) { const s = Math.min(64 / im.height, 80 / im.width); ctx.save(); ctx.beginPath(); ctx.rect(14, y + 3, 84, 64); ctx.clip(); spr(im, 56, y + 66 + (d.who === 'monster' ? 6 : 0), { sx: s, sy: s, ay: im.height }); ctx.restore(); tx = 104; } }
      if (who.name) text(who.name, tx, y + 5, { color: who.col }); else if (d.who === 'narrator') text('NARRATOR', tx, y + 5, { color: '#888' });
      lines.slice(0, 5).forEach((l, i) => text(l, tx, y + 18 + i * 10, { color: '#fff' }));
      if (n >= d.text.length && Math.floor(G.t * 3) % 2) text('▼', W - 26, y + 58, { color: who.col });
    }
  },
  // ------------------------------------------------------------------ scene API used by STORY steps
  scene: {
    music(id) { AudioSys.play(id); }, sfx(n, o) { AudioSys.play_sfx(n, o); }, shake(a, t) { Cam.shake(a, t); }, intensity(n) { AudioSys.setIntensity(n); },
    flash(col = '#fff') { const c = Game.cutscene; if (c) { c.flash = 20; c.flashCol = col; } },
    card(a, b) { const c = Game.cutscene; c.card = [a, b]; setTimeout(() => { if (Game.cutscene === c) c.card = null; }, 2500); Game.cutscene.waitFn = null; },
    title(a, b) { HUD.banner(a, '#7fff3a', b); },
    banner(a, col) { HUD.banner(a, col); },
    rift() { FX.burst(Game.player.cx, Game.player.cy, 80, ['#7fff3a', '#b04bff', '#fff', '#ff5bd1'], { speed: 8, life: 80 }); for (let i = 0; i < 4; i++) FX.ring(Game.player.cx, Game.player.cy, 120 + i * 60, '#b04bff', 40, 3); },
    px() { return Game.player.cx; }, gy() { return Game.player.y + Game.player.h; },
    actor(id, who, x, y, face, anim, o) { Game.actors = Game.actors.filter(a => a.id !== id); const a = new Actor(who, x, y, face, anim, o); a.id = id; Game.actors.push(a); Save.see(who); },
    move(id, x, y, n) { const a = Game.actors.find(a => a.id === id); if (a) a.mv = { x0: a.x, y0: a.y, x1: x, y1: y, n, t: 0 }; },
    removeActors() { Game.actors = []; },
    quest(label, flag, n) { HUD.questLabel = label; },
    flagHouse(kind) { const h = Game.ents.find(e => e instanceof HouseSite && e.kind === kind); if (h) { h.built = true; const p = Game.player; if (Math.abs(p.cx - h.cx) > 200) { p.x = h.x + h.w + 20; p.y = h.ground - p.h - 2; Cam.follow(Game.L, p.cx, p.cy, -1, true); } FX.burst(h.cx, h.cy, 30, ['#ffd860', '#fff'], { speed: 4 }); AudioSys.play_sfx('stinger'); } },
    blowHouse() { const h = Game.ents.find(e => e instanceof HouseSite && e.built && !e.gone); if (h) { h.gone = true; FX.debris(h.cx, h.cy, h.kind === 'straw' ? 'straw' : h.kind === 'stick' ? 'stick' : 'brick', 40); FX.burst(h.cx, h.cy, 30, '#fff8', { speed: 6 }); } },
    wind() { for (let i = 0; i < 60; i++) FX.add({ x: Cam.x + R(W), y: Cam.y + R(H), vx: 8, vy: R(-1, 1), col: '#fff8', size: 2, life: 50, grav: 0 }); },
    nextChapter() { Game.cutscene.nextChapter = true; Game.cutscene.i = Game.cutscene.steps.length; },
    lockArena() { const g = Game.bossGate; if (!g) return; const L = Game.L; L.camLock = { x0: g.o.x0, x1: g.o.x0 + g.o.w }; const tx = Math.floor(g.o.x0 / TS) - 1; for (let ty = 0; ty < g.o.gy; ty++) L.tiles[L.idx(tx, ty)] = T_WALL; AudioSys.setIntensity(3); },
    spawnBoss() { const g = Game.bossGate; if (!g) return; const C = BOSS_CLASSES[g.o.kind]; const b = new C(g.o.x0 + g.o.w * .7, g.o.gy * TS, g.o); Game.add(b); Game.boss = b; Game.bossHits = Game.player.hitTaken; HUD.bossIntro = 120; AudioSys.setIntensity(3); AudioSys.setBossPhase(1); },
    gloopkins() { for (let i = 0; i < 3; i++) { const e = new Enemy({ kind: 'gloopkin', x: Game.player.cx + 100 + i * 40, y: Game.player.y - 30 }); e.wake = true; Game.add(e); } },
    ally() { if (!Game.ally) Game.add(new UdderlyAlly(Game.player.cx - 60, Game.player.cy - 80)); },
    give(f) { Save.form(f); if (POWERS[f]) { Game.player.setPower(f); HUD.banner(POWERS[f].label, POWERS[f].col, POWERS[f].joke); AudioSys.play_sfx('power'); } },
    giveSummon(s) { if (Save.summon(s)) { HUD.toast(SUMMONS[s].name + ' WILL SHOW UP TO HELP!', '#5bd4ff'); AudioSys.play_sfx('power'); } },
    megaFree() { const p = Game.player; p.setPower('mega'); p.powerT = 60 * 60 * 5; },
    slowmo() { Game.slow = 240; },
    rescue() { Game.levelStats.rescued = (Game.levelStats.rescued || 0) + 1; FX.notes(Game.player.cx, Game.player.y, 6); const n = Game.cutscene.o.npc; if (n) { n.anim = 'dance'; n.leaveT = 90; } Game.player.hp = Math.min(Game.player.maxHp, Game.player.hp + 1); },
    startConcert(song, final) { Game.cutscene.concert = song; Game.cutscene.final = final; Game.cutscene.i = Game.cutscene.steps.length; }
  }
};
// LEVEL 333 boss gets temporary access to the pig summon
const _origSpawnBoss = Game.scene.spawnBoss;
Game.scene.spawnBoss = function () { _origSpawnBoss(); if (Game.def.id === 'L3' && !Save.data.summons.includes('pigs')) { Save.data.summons.push('pigs'); Game._tempPigs = true; } };
