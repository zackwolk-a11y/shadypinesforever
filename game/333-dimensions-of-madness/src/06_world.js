// ============================================================================
// World: tilemap, collision, level builder (segment DSL), chunked tile render
// ============================================================================
const T_EMPTY = 0, T_SOLID = 1, T_ONEWAY = 2, T_BREAK = 3, T_SPIKE = 4, T_LIQ = 5, T_LIQF = 6, T_CRUMBLE = 7, T_SPRING = 8,
  T_CONVL = 9, T_CONVR = 10, T_BEATA = 11, T_BEATB = 12, T_ZAP = 13, T_WALL = 14;
const CHUNK = 32;
class Level {
  constructor(def) {
    this.def = def; this.w = def.w || 400; this.h = def.h || 24;
    this.tiles = new Uint8Array(this.w * this.h); this.theme = THEMES[def.theme]; this.seed = hashStr(def.id);
    this.props = []; this.spawns = []; this.crumbles = new Map(); this.beatPhase = 0; this.dirty = new Set();
    this.tileset = buildTileset(this.theme, this.seed); this.bg = buildBackground(this.theme, this.seed); this.propImgs = buildProps(this.theme, this.seed);
    this.liquidHazard = ['acid', 'void', 'electric', 'lava'].includes(this.theme.hz) && !def.swim;
    this.gravity = 1; this.wind = 0; this.camLock = null; this.autoScroll = 0; this.startX = 48; this.startY = 0;
    this.decoSeed = mulberry(this.seed + 3);
  }
  idx(tx, ty) { return ty * this.w + tx; }
  get(tx, ty) { if (tx < 0 || tx >= this.w) return T_WALL; if (ty < 0) { const t0 = this.tiles[tx]; return t0 === T_WALL || (this.def.ceiling && t0 === T_SOLID) ? T_WALL : T_EMPTY; } if (ty >= this.h) return T_EMPTY; return this.tiles[ty * this.w + tx]; }
  set(tx, ty, v) { if (tx < 0 || ty < 0 || tx >= this.w || ty >= this.h) return; this.tiles[ty * this.w + tx] = v; this.dirty.add(Math.floor(tx / CHUNK)); }
  fill(x0, y0, x1, y1, v) { for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) this.set(x, y, v); }
  solidAt(tx, ty, forBody) {
    const t = this.get(tx, ty);
    switch (t) {
      case T_SOLID: case T_BREAK: case T_SPRING: case T_CONVL: case T_CONVR: case T_WALL: return true;
      case T_CRUMBLE: { const c = this.crumbles.get(this.idx(tx, ty)); return !c || c.t < 40; }
      case T_BEATA: return this.beatOn === true;
      case T_BEATB: return this.beatOn === false;
    }
    return false;
  }
  onewayAt(tx, ty) { const t = this.get(tx, ty); return t === T_ONEWAY; }
  hazardAt(tx, ty) { const t = this.get(tx, ty); return t === T_SPIKE || t === T_ZAP || ((t === T_LIQ || t === T_LIQF) && this.liquidHazard); }
  liquidAt(tx, ty) { const t = this.get(tx, ty); return t === T_LIQ || t === T_LIQF; }
  update() {
    // rhythm machinery: beat blocks flip every 2 beats of the music
    const b = AudioSys.beat(); const on = Math.floor(b.beat / 2) % 2 === 0;
    if (on !== this.beatOn) { this.beatOn = on; this.beatFlip = 10; if (this.hasBeat) { this.dirtyAll(); } }
    if (this.beatFlip > 0) this.beatFlip--;
    for (const [k, c] of this.crumbles) { c.t++; if (c.t === 40) { this.dirty.add(Math.floor((k % this.w) / CHUNK)); FX.burst((k % this.w) * TS + 8, Math.floor(k / this.w) * TS + 4, 6, '#a07a4a'); } if (c.t > 260) { this.crumbles.delete(k); this.dirty.add(Math.floor((k % this.w) / CHUNK)); } }
  }
  dirtyAll() { for (let i = 0; i * CHUNK < this.w; i++) this.dirty.add(i); }
  // ---------- rendering
  buildChunks() { this.chunks = []; for (let i = 0; i * CHUNK < this.w; i++) { this.chunks.push(makeCanvas(CHUNK * TS, this.h * TS)); this.renderChunk(i); } this.dirty.clear(); }
  renderChunk(i) {
    const c = this.chunks[i], x = c.ctx, T = this.tileset; x.clearRect(0, 0, c.width, c.height);
    const r = mulberry(this.seed + i * 31);
    for (let ty = 0; ty < this.h; ty++) for (let lx = 0; lx < CHUNK; lx++) {
      const tx = i * CHUNK + lx; if (tx >= this.w) break; const t = this.tiles[ty * this.w + tx], px = lx * TS, py = ty * TS;
      const sol = v => v === T_SOLID;
      switch (t) {
        case T_SOLID:
          x.drawImage(T.solid[(tx * 7 + ty * 13) % 3], px, py);
          if (!sol(this.get(tx, ty - 1)) && this.get(tx, ty - 1) !== T_BREAK) x.drawImage(T.cap, px, py);
          if (!sol(this.get(tx - 1, ty)) && this.get(tx - 1, ty) !== T_WALL) x.drawImage(T.edgeL, px, py);
          if (!sol(this.get(tx + 1, ty)) && this.get(tx + 1, ty) !== T_WALL) x.drawImage(T.edgeR, px, py);
          if (!sol(this.get(tx, ty + 1)) && ty < this.h - 1) x.drawImage(T.edgeB, px, py);
          if (ty > 0 && sol(this.get(tx, ty - 1)) && r() < .04) { x.fillStyle = '#0003'; x.fillRect(px + 4, py + 5, 3, 2); }
          break;
        case T_ONEWAY: x.drawImage(T.oneway, px, py); break;
        case T_BREAK: x.drawImage(T.brk, px, py); break;
        case T_SPIKE: x.drawImage(T.spike, px, py); break;
        case T_CRUMBLE: { const cc = this.crumbles.get(this.idx(tx, ty)); if (!cc || cc.t < 40) x.drawImage(T.crumble, px + (cc ? (cc.t % 4 < 2 ? 1 : -1) : 0), py); break; }
        case T_BEATA: x.drawImage(this.beatOn ? T.beatOn : T.beatOff, px, py); break;
        case T_BEATB: x.drawImage(this.beatOn === false ? T.beatOnB : T.beatOffB, px, py); break;
        case T_LIQF: x.drawImage(T.liquidFill, px, py); break;
      }
    }
  }
  drawTiles(cx, cy) {
    for (const i of this.dirty) if (this.chunks[i]) this.renderChunk(i); this.dirty.clear();
    const T = this.tileset, f = Math.floor(G.t * 8) % 4;
    const i0 = Math.max(0, Math.floor(cx / (CHUNK * TS))), i1 = Math.min(this.chunks.length - 1, Math.floor((cx + W) / (CHUNK * TS)));
    for (let i = i0; i <= i1; i++) ctx.drawImage(this.chunks[i], Math.round(i * CHUNK * TS - cx), Math.round(-cy));
    // animated tiles
    const tx0 = Math.floor(cx / TS) - 1, tx1 = Math.ceil((cx + W) / TS) + 1, ty0 = Math.max(0, Math.floor(cy / TS)), ty1 = Math.min(this.h - 1, Math.ceil((cy + H) / TS));
    for (let ty = ty0; ty <= ty1; ty++) for (let tx = Math.max(0, tx0); tx <= Math.min(this.w - 1, tx1); tx++) {
      const t = this.tiles[ty * this.w + tx]; const px = Math.round(tx * TS - cx), py = Math.round(ty * TS - cy);
      if (t === T_LIQ) ctx.drawImage(T.liquid[(f + tx) % 4], px, py);
      else if (t === T_CONVL) ctx.drawImage(T.conv[3 - f], px, py); else if (t === T_CONVR) ctx.drawImage(T.conv[f], px, py);
      else if (t === T_SPRING) ctx.drawImage(T.spring[this.springAnim && this.springAnim[tx + ',' + ty] > 0 ? 1 : 0], px, py);
      else if (t === T_ZAP) ctx.drawImage(T.zap[(f + tx) % 4], px, py);
    }
  }
}
// ---------------------------------------------------------------- body physics against tiles
const PHYS = { grav: .32, maxFall: 6.2 };
function moveBody(b, L) {
  b.hitWall = 0; b.hitCeil = false; const wasGround = b.onGround; b.onGround = false; b.groundTile = 0;
  // X
  let nx = b.x + b.vx;
  if (b.vx !== 0) {
    const dir = sign(b.vx), edge = dir > 0 ? nx + b.w : nx, tx = Math.floor((dir > 0 ? edge - .01 : edge) / TS);
    const ty0 = Math.floor((b.y + 1) / TS), ty1 = Math.floor((b.y + b.h - 1.01) / TS);
    let hit = false; for (let ty = ty0; ty <= ty1; ty++) if (L.solidAt(tx, ty, b)) { hit = true; break; }
    if (!hit && L.solidEnts) for (const s of L.solidEnts) if (s !== b && s.solid && nx < s.x + s.w && nx + b.w > s.x && b.y + 1 < s.y + s.h && b.y + b.h - 1 > s.y && !s.oneway) { hit = true; nx = dir > 0 ? s.x - b.w : s.x + s.w; b.hitWall = dir; break; }
    if (hit && !b.hitWall) {
      // step-up small ledges (feels better for a bouncing head)
      if (wasGround && b.stepUp && !L.solidAt(tx, Math.floor((b.y - 5) / TS)) && !L.solidAt(tx, Math.floor((b.y + b.h - 10) / TS)) && L.solidAt(tx, ty1)) { b.y -= TS - ((b.y + b.h) % TS || TS) + 0; }
      else { nx = dir > 0 ? tx * TS - b.w : (tx + 1) * TS; b.hitWall = dir; }
    }
    if (b.hitWall) b.vx = 0;
  }
  b.x = nx;
  // Y
  const gdir = b.gdir || 1;
  let ny = b.y + b.vy;
  const tx0 = Math.floor((b.x + 1) / TS), tx1 = Math.floor((b.x + b.w - 1.01) / TS);
  if (b.vy * gdir > 0 || b.vy !== 0) {
    if (b.vy > 0) {
      const ty = Math.floor((ny + b.h) / TS), prevBottom = b.y + b.h;
      for (let tx = tx0; tx <= tx1; tx++) {
        if (L.solidAt(tx, ty, b) || (L.onewayAt(tx, ty) && prevBottom <= ty * TS + 1 && !b.dropThrough)) { ny = ty * TS - b.h; b.vy = 0; if (gdir > 0) { b.onGround = true; b.groundTile = L.get(tx, ty); b.groundTx = tx; b.groundTy = ty; } else b.hitCeil = true; break; }
      }
    } else if (b.vy < 0) {
      const ty = Math.floor(ny / TS);
      for (let tx = tx0; tx <= tx1; tx++) if (L.solidAt(tx, ty, b)) { ny = (ty + 1) * TS; b.vy = 0; if (gdir < 0) { b.onGround = true; b.groundTile = L.get(tx, ty); b.groundTx = tx; b.groundTy = ty; } else b.hitCeil = true; if (b.onHead) b.onHead(tx, ty); break; }
    }
  }
  if (L.solidEnts) for (const s of L.solidEnts) {
    if (s === b || !s.solid) continue;
    if (b.x + b.w > s.x + 1 && b.x < s.x + s.w - 1) {
      if (b.vy >= 0 && b.y + b.h <= s.y + 2 + Math.max(0, s.vy || 0) && ny + b.h >= s.y) { ny = s.y - b.h; b.vy = 0; b.onGround = true; b.riding = s; }
      else if (!s.oneway && b.vy < 0 && b.y >= s.y + s.h - 2 && ny <= s.y + s.h) { ny = s.y + s.h; b.vy = 0; b.hitCeil = true; }
    }
  }
  b.y = ny;
}
function overlapsHazard(b, L) {
  const tx0 = Math.floor((b.x + 3) / TS), tx1 = Math.floor((b.x + b.w - 3) / TS), ty0 = Math.floor((b.y + 4) / TS), ty1 = Math.floor((b.y + b.h - 2) / TS);
  for (let ty = ty0; ty <= ty1; ty++) for (let tx = tx0; tx <= tx1; tx++) if (L.hazardAt(tx, ty)) return true; return false;
}
function inLiquid(b, L) { return L.liquidAt(Math.floor((b.x + b.w / 2) / TS), Math.floor((b.y + b.h / 2) / TS)); }

// ---------------------------------------------------------------- Level builder DSL
// A level definition is a list of segments; the builder walks left->right keeping a ground height.
class Builder {
  constructor(L, def) {
    this.L = L; this.def = def; this.cx = 0; this.gy = def.gy || 18; this.r = mulberry(L.seed); this.diff = def.diff || 1;
    this.shardsPlaced = 0; this.enemyPool = def.enemies || ['puppet']; this.noteCount = 0;
  }
  R(a, b) { return b === undefined ? this.r() * a : a + this.r() * (b - a); } RI(a, b) { return Math.floor(this.R(a, b + 1)); } pick(a) { return a[Math.floor(this.r() * a.length)]; }
  col(x, top) { this.L.fill(x, top, x, this.L.h - 1, T_SOLID); }
  ground(n, deco = true) {
    for (let i = 0; i < n; i++) { this.col(this.cx + i, this.gy); }
    if (deco) for (let i = 1; i < n - 1; i += 3 + this.RI(0, 4)) if (this.r() < .5) this.prop(this.cx + i);
    this.cx += n;
  }
  prop(tx, ty = this.gy) { const imgs = this.L.propImgs; if (!imgs.length) return; const im = this.pick(imgs); this.L.props.push({ img: im, x: tx * TS + 8, y: ty * TS + 1, layer: this.r() < .25 ? 1 : 0 }); }
  spawn(type, tx, ty, o = {}) { this.L.spawns.push(Object.assign({ type, x: tx * TS, y: ty * TS }, o)); }
  enemy(type, dx = 0, o = {}) { this.spawn('enemy', this.cx + dx, this.gy - 2, Object.assign({ kind: type || this.pick(this.enemyPool) }, o)); }
  notes(n, dx = 0, dy = 3, arc = 0) { for (let i = 0; i < n; i++) { const a = arc ? Math.sin(i / (n - 1 || 1) * Math.PI) * arc : 0; this.spawn('note', this.cx + dx + i * 1.5, this.gy - dy - a); this.noteCount++; } }
  step(dh) { this.gy = clamp(this.gy + dh, 8, this.L.h - 3); }
  gap(n, liquid = true) {
    for (let i = 0; i < n; i++) if (liquid) { this.L.set(this.cx + i, this.L.h - 2, T_LIQ); this.L.set(this.cx + i, this.L.h - 1, T_LIQF); }
    this.cx += n;
  }
  pit(n) { // gap with spikes floor
    for (let i = 0; i < n; i++) { this.L.set(this.cx + i, this.L.h - 1, T_SOLID); this.L.set(this.cx + i, this.L.h - 2, T_SPIKE); }
    this.cx += n;
  }
  platforms(n, w = 3) { // floating one-way platforms across a pit
    const y0 = this.gy;
    for (let i = 0; i < n; i++) { const y = y0 - 1 - this.RI(0, 3); for (let k = 0; k < w; k++) this.L.set(this.cx + 2 + i * (w + 2) + k, y, T_ONEWAY); if (this.r() < .6) this.spawn('note', this.cx + 2 + i * (w + 2) + 1, y - 2); }
    const len = 2 + n * (w + 2); this.gapFill(len); this.cx += len;
  }
  gapFill(len) { for (let i = 0; i < len; i++) { this.L.set(this.cx + i, this.L.h - 2, T_LIQ); this.L.set(this.cx + i, this.L.h - 1, T_LIQF); } }
  hookGap(n = 12) { // wide gap crossed with the tongue grapple
    this.gapFill(n); const hooks = Math.max(1, Math.round(n / 7));
    for (let i = 0; i < hooks; i++) this.spawn('hook', this.cx + (i + 1) * n / (hooks + 1), this.gy - 7);
    this.notes(3, n / 2 - 2, 5, 2); this.cx += n;
  }
  movingGap(n = 10, vert = false) { this.gapFill(n); this.spawn('mplat', this.cx + 2, this.gy - 1, { range: vert ? 4 * TS : (n - 6) * TS, vert, w: 4 }); this.cx += n; }
  wall(h = 4, breakable = true) { for (let y = this.gy - h; y < this.gy; y++) this.L.set(this.cx, y, breakable ? T_BREAK : T_SOLID); for (let y = this.gy - h; y < this.gy; y++) this.L.set(this.cx + 1, y, breakable ? T_BREAK : T_SOLID); this.ground(2, false); this.cx -= 2; this.col(this.cx, this.gy); this.col(this.cx + 1, this.gy); this.cx += 2; }
  stairs(n, dir = -1, w = 3) { for (let i = 0; i < n; i++) { this.step(dir); this.ground(w); } }
  spikes(n) { for (let i = 0; i < n; i++) { this.col(this.cx + i, this.gy); this.L.set(this.cx + i, this.gy - 1, T_SPIKE); } this.notes(Math.min(n, 3), 0, 5, 1); this.cx += n; }
  spring(dx = 1) { this.L.set(this.cx + dx, this.gy - 1, T_SPRING); }
  checkpoint() { this.spawn('checkpoint', this.cx + 1, this.gy - 2); }
  beatBridge(n = 10) { this.L.hasBeat = true; this.gapFill(n); for (let i = 0; i < n; i++) this.L.set(this.cx + i, this.gy, (Math.floor(i / 3) % 2) ? T_BEATB : T_BEATA); this.notes(3, 2, 3); this.cx += n; }
  conveyor(n, dir = 1) { for (let i = 0; i < n; i++) { this.col(this.cx + i, this.gy); this.L.set(this.cx + i, this.gy, dir > 0 ? T_CONVR : T_CONVL); } this.cx += n; }
  crumble(n) { this.gapFill(n); for (let i = 0; i < n; i++) this.L.set(this.cx + i, this.gy, T_CRUMBLE); this.cx += n; }
  pool(n, depth = 4) { // liquid pool (swimmable if level.swim)
    for (let i = 0; i < n; i++) { this.L.fill(this.cx + i, this.gy + depth, this.cx + i, this.L.h - 1, T_SOLID); this.L.set(this.cx + i, this.gy, T_LIQ); for (let d = 1; d < depth; d++) this.L.set(this.cx + i, this.gy + d, T_LIQF); }
    this.cx += n;
  }
  zap(n) { for (let i = 0; i < n; i++) { this.col(this.cx + i, this.gy); this.L.set(this.cx + i, this.gy - 1, T_ZAP); } this.cx += n; }
  tower(h = 8) { // zig-zag one-way climb then a high ledge
    const x0 = this.cx; this.ground(10, false);
    for (let i = 1; i <= h; i++) { const x = x0 + (i % 2 ? 1 : 6); for (let k = 0; k < 3; k++) this.L.set(x + k, this.gy - i * 2, T_ONEWAY); if (i % 2) this.spawn('note', x + 1, this.gy - i * 2 - 2); }
    return this.gy - h * 2;
  }
  shard(kind) {
    if (this.shardsPlaced >= 3) return; const id = this.shardsPlaced++;
    kind = kind || this.pick(['high', 'wall', 'hook', 'under']);
    if (kind === 'under' && this.gy > this.L.h - 6) kind = 'wall';
    if (kind === 'high') { this.ground(8); const x = this.cx - 5; for (let k = 0; k < 3; k++) this.L.set(x + k, this.gy - 6, T_ONEWAY); for (let k = 0; k < 3; k++) this.L.set(x + 3 + k, this.gy - 10, T_ONEWAY); this.spring(-7); this.spawn('shard', x + 4, this.gy - 12, { id }); }
    else if (kind === 'wall') { this.ground(3); const x = this.cx; this.ground(6, false); this.L.fill(x, this.gy - 3, x + 5, this.gy - 1, T_SOLID); this.L.fill(x + 1, this.gy - 2, x + 4, this.gy - 1, T_EMPTY); this.L.fill(x, this.gy - 2, x, this.gy - 1, T_BREAK); this.L.fill(x + 5, this.gy - 2, x + 5, this.gy - 1, T_BREAK); this.spawn('shard', x + 2, this.gy - 2, { id }); this.ground(2); }
    else if (kind === 'hook') { this.ground(4); this.spawn('hook', this.cx, this.gy - 11); const x = this.cx + 3; for (let k = 0; k < 4; k++) this.L.set(x + k, this.gy - 12, T_ONEWAY); this.spawn('shard', x + 2, this.gy - 14, { id }); this.ground(8); }
    else { const x = this.cx; this.ground(10); this.L.fill(x + 2, this.gy, x + 8, this.gy + 3, T_EMPTY); this.L.set(x + 2, this.gy, T_BREAK); this.L.set(x + 3, this.gy, T_BREAK); this.L.fill(x + 4, this.gy, x + 8, this.gy, T_SOLID); this.spawn('shard', x + 6, this.gy + 2, { id }); this.L.fill(x + 1, this.gy + 4, x + 9, this.L.h - 1, T_SOLID); }
  }
  arena(n, waves, o = {}) { // combat arena: camera locks, waves of enemies
    const x0 = this.cx; this.ground(n); this.spawn('arena', x0, this.gy, Object.assign({ w: n * TS, waves }, o));
  }
  npc(who, scene, dx = 2, o = {}) { this.spawn('npc', this.cx + dx, this.gy, Object.assign({ who, scene }, o)); }
  trigger(scene, dx = 0, o = {}) { this.spawn('trigger', this.cx + dx, 0, Object.assign({ scene, h: this.L.h * TS }, o)); }
  exit() { this.ground(14); this.spawn('exit', this.cx - 6, this.gy); this.cx += 0; this.L.fill(this.cx, 0, this.cx + 1, this.L.h - 1, T_WALL); }
  // random fill drawn from a pool appropriate to the world/difficulty
  auto(n, pool) {
    pool = pool || this.def.pool || ['flat', 'gap', 'steps', 'plats', 'enemy'];
    for (let i = 0; i < n; i++) {
      const s = this.pick(pool), d = this.diff;
      switch (s) {
        case 'flat': this.ground(this.RI(6, 10)); this.notes(this.RI(2, 4), 1, 3); if (this.r() < .5 + d * .1) this.enemy(null, -3); break;
        case 'gap': this.ground(4); this.gap(this.RI(2, Math.min(4, 2 + d))); this.ground(4); this.notes(3, -9, 4, 2); break;
        case 'steps': this.stairs(this.RI(2, 3), this.r() < .5 ? -1 : 1, this.RI(3, 5)); this.enemy(null, -2); break;
        case 'plats': this.ground(3); this.platforms(this.RI(2, 3), this.RI(2, 3)); this.ground(4); break;
        case 'enemy': this.ground(12); this.enemy(null, -9); this.enemy(null, -4); if (d > 2) this.enemy(null, -6); this.notes(4, -10, 3); break;
        case 'spikes': this.ground(4); this.spikes(this.RI(2, 4)); this.ground(4); break;
        case 'pit': this.ground(3); this.pit(this.RI(2, 4)); this.ground(3); break;
        case 'hook': this.ground(4); this.hookGap(this.RI(10, 14)); this.ground(4); break;
        case 'moving': this.ground(3); this.movingGap(this.RI(10, 13)); this.ground(4); break;
        case 'wall': this.ground(5); this.wall(this.RI(3, 4)); this.ground(3); break;
        case 'beat': this.ground(3); this.beatBridge(this.RI(9, 12)); this.ground(4); break;
        case 'conveyor': this.ground(2); this.conveyor(this.RI(8, 12), this.r() < .5 ? 1 : -1); this.enemy(null, -4); this.ground(2); break;
        case 'crumble': this.ground(3); this.crumble(this.RI(6, 9)); this.ground(4); break;
        case 'tower': { const top = this.tower(this.RI(3, 5)); const g = this.gy; this.gy = top; this.ground(6); this.gy = g; this.step(0); break; }
        case 'zap': this.ground(3); this.zap(this.RI(2, 3)); this.ground(3); break;
        case 'pool': this.ground(3); this.pool(this.RI(6, 10), this.RI(3, 5)); this.ground(3); break;
        case 'up': this.ground(4); this.step(-this.RI(2, 3)); this.ground(4); break;
        case 'down': this.ground(4); this.step(this.RI(2, 3)); this.ground(4); break;
        case 'flyers': this.ground(10); this.spawn('enemy', this.cx - 6, this.gy - 6, { kind: this.pick(this.def.flyers || ['bookbat']) }); this.notes(3, -8, 3); break;
      }
    }
  }
}
