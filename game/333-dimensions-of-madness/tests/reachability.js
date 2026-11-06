// Static reachability validator: for every level/chapter, builds a graph of standable cells using the
// player's real jump limits (plus springs, grapple hooks, breakable walls, built blueprints) and checks
// that every exit / quest item / boss gate is reachable from the start position.
const { chromium } = require('playwright'); const path = require('path');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  await p.goto('file://' + path.resolve(__dirname, '../333-dimensions-of-madness.html'));
  await p.waitForFunction(() => window.DIM333 && DIM333.G.state === 'title');
  const res = await p.evaluate(() => {
    const D = DIM333, out = [];
    D.LEVELS.forEach((lv, i) => (lv.chapters || [0]).forEach((_, ch) => {
      D.load(i, ch); const Gm = D.Game, L = Gm.L, Wd = L.w, Hd = L.h;
      const T = (x, y) => L.get(x, y);
      const party = Gm.party || ['monster'];
      const solidish = (x, y) => { const t = T(x, y); return t === 1 || t === 2 || t === 7 || t === 8 || t === 9 || t === 10 || t === 11 || t === 12 || t === 14 || (t === 3); };
      const passable = (x, y) => { const t = T(x, y); return t === 0 || t === 3 || t === 2 || t === 4 || t === 5 || t === 6 || t === 13 || t === 11 || t === 12 || t === 7; };
      // blueprints count as built (Porkington), doors as open (switches reachable), ladders become one-way stacks
      for (const e of Gm.ents) if (e.constructor.name === 'Blueprint') { if (e.kind === 'bridge') for (let k = 0; k < e.len; k++) L.tiles[L.idx(e.tx + k, e.ty)] = 2; else for (let k = 0; k < e.len; k++) L.tiles[L.idx(e.tx, e.ty - k)] = 2; }
      const swim = !!Gm.sub.swim; const liquidOK = (x, y) => swim && (T(x, y) === 5 || T(x, y) === 6);
      const stand = (x, y) => x >= 0 && x < Wd && y >= 1 && y < Hd && (solidish(x, y) || (liquidOK(x, y))) && passable(x, y - 1) && passable(x, y - 2) && T(x, y) !== 4 && T(x, y) !== 13 && !(T(x, y - 1) === 4) && !(T(x, y - 1) === 13);
      // calibrate jump envelope by simulating the real arc (hold jump; gravity .32, x .62 while rising & held)
      const envelope = (speed, jump, glideOn) => { const env = {}; let x = 0, y = 0, vy = -jump; for (let f = 0; f < 400; f++) { const g = .32 * (vy < 0 ? .62 : 1); vy = Math.min(vy + g, glideOn && vy > 0 ? 1.0 : 6.2); y += vy; x += speed; const up = Math.floor(-y / 16); if (vy > 0) { if (env[up] === undefined || env[up] < x) env[up] = x; } if (y > 16 * 16) break; } const out = {}; for (const k in env) out[k] = Math.floor(env[k] / 16 * .85) - 1; return out; };
      const chars = Gm.sub.race ? [[7.0, 7.2, false]] : party.map(c => c === 'monster' ? [2.5, 6.5, false] : c === 'hamwise' ? [2.5, 6.0, true] : c === 'porkington' ? [2.3, 6.4, false] : [2.1, 5.7, false]);
      const envs = chars.map(c => envelope(...c)); const reachAt = dyUp => { let m = -1; for (const e of envs) { let best = -1; for (const k in e) if (+k >= dyUp) best = Math.max(best, e[k]); m = Math.max(m, best); } return m; };
      const glide = party.includes('hamwise');
      const maxUp = Math.max(...envs.map(e => Math.max(...Object.keys(e).map(Number))));
      const hooks = Gm.ents.filter(e => e.constructor.name === 'Hook').map(h => [Math.floor(h.cx / 16), Math.floor(h.cy / 16)]);
      const key = (x, y) => y * Wd + x; const seen = new Uint8Array(Wd * Hd); const q = [];
      // moving platforms / coasters: mark their travelled cells as standable one-way
      for (const e of Gm.ents) { const n = e.constructor.name; if (n === 'MovingPlat') { const o = e.o, x0 = Math.floor(o.x / 16), y0 = Math.floor(o.y / 16), r = Math.ceil(o.range / 16); for (let k = 0; k <= r; k++) for (let w = 0; w < (o.w || 4); w++) { if (o.vert) { if (T(x0 + w, y0 - k) === 0) L.tiles[L.idx(x0 + w, y0 - k)] = 2; } else if (T(x0 + k + w, y0) === 0) L.tiles[L.idx(x0 + k + w, y0)] = 2; } }
        if (n === 'Coaster') { const x0 = Math.floor(e.x / 16), y0 = Math.floor((e.y + 4) / 16); for (let k = 0; k < e.len / 16 + 3; k++) if (T(x0 + k, y0) === 0 || T(x0 + k, y0) === 5) L.tiles[L.idx(x0 + k, y0)] = 2; } }
      const portals = Gm.ents.filter(e => e.constructor.name === 'Portal');
      const crates = Gm.ents.filter(e => e.constructor.name === 'Pullable').map(e => [Math.floor(e.cx / 16), Math.floor((e.y + e.h) / 16)]);
      const sx = Math.floor((Gm.player.x + 13) / 16); let sy = Math.floor((Gm.player.y + Gm.player.h) / 16); for (let k = 0; k < 30 && !stand(sx, sy); k++) sy++;
      if (stand(sx, sy)) { seen[key(sx, sy)] = 1; q.push([sx, sy]); }
      const clearCol = (x, y0, y1) => { for (let y = Math.min(y0, y1) - 2; y <= Math.max(y0, y1) - 1; y++) if (!passable(x, y)) return false; return true; };
      while (q.length) {
        const [x, y] = q.pop();
        const tryAdd = (nx, ny) => { if (nx >= 0 && nx < Wd && ny > 0 && ny < Hd && stand(nx, ny) && !seen[key(nx, ny)]) { seen[key(nx, ny)] = 1; q.push([nx, ny]); } };
        const up = T(x, y) === 8 ? 10 : maxUp + (swim && liquidOK(x, y) ? 3 : 0);
        for (let dy = -up; dy <= 14; dy++) { const reach = T(x, y) === 8 ? 6 : dy <= 0 ? reachAt(-dy) : Math.max(reachAt(0), 0) + Math.floor(dy / 2) + (glide ? 10 : 0); if (reach < 0) continue; for (let dx = -reach; dx <= reach; dx++) { const nx = x + dx, ny = y + dy; if (ny <= 0 || ny >= Hd) continue; if (dy < 0 && !clearCol(x, y, ny)) continue; tryAdd(nx, ny); } }
        for (const c of crates) if (Math.abs(c[0] - x) <= 16 && Math.abs(c[1] - y) <= 3) for (let dx = -3; dx <= 3; dx++) for (let dy = -(maxUp + 2); dy <= 0; dy++) if (clearCol(x, y, y + dy)) tryAdd(x + dx, y + dy);
        for (const [hx, hy] of hooks) if (Math.abs(hx - x) <= 9 && y - hy <= maxUp + 7 && y > hy) for (let dx = -10; dx <= 10; dx++) for (let dy = -3; dy <= 12; dy++) tryAdd(hx + dx, hy + dy);
        for (const pt of portals) if (pt.to && Math.abs(Math.floor(pt.cx / 16) - x) <= 1 && Math.abs(Math.floor((pt.y + pt.h) / 16) - y) <= 1) { const d = portals.find(o => o.pair === pt.to); if (d) { let dx2 = Math.floor((d.cx + 24) / 16), dy2 = Math.floor((d.y + d.h) / 16); for (let k = 0; k < 4 && !stand(dx2, dy2); k++) dy2++; tryAdd(dx2, dy2); } }
      }
      // targets
      const reachableNear = (px, py, r = 2) => { const tx = Math.floor(px / 16), ty = Math.floor(py / 16); for (let dx = -r; dx <= r; dx++) for (let dy = -1; dy <= 6; dy++) { const k = key(tx + dx, ty + dy); if (tx + dx >= 0 && tx + dx < Wd && ty + dy < Hd && ty + dy >= 0 && seen[k]) return true; } return false; };
      const targets = Gm.ents.filter(e => ['Exit', 'BossGate', 'Collectable', 'BrickItem', 'Shard', 'ChaseEnd', 'FinishLine', 'Quest'].includes(e.constructor.name));
      const colReach = px => { const tx = Math.floor(px / 16); for (let dx = -2; dx <= 2; dx++) for (let y = 0; y < Hd; y++) if (tx + dx >= 0 && tx + dx < Wd && seen[key(tx + dx, y)]) return true; return false; };
      const nearSeen = (tx, r) => { for (let dx = -r; dx <= r; dx++) for (let y = 0; y < Hd; y++) if (tx + dx >= 0 && tx + dx < Wd && seen[key(tx + dx, y)]) return true; return false; };
      const hookReach = e => hooks.some(([hx, hy]) => Math.abs(hx * 16 - e.cx) < 100 && Math.abs(hy * 16 - e.cy) < 100 && nearSeen(hx, 9));
      const bad = targets.filter(e => { const n = e.constructor.name; if (n === 'BossGate' || n === 'ChaseEnd' || n === 'FinishLine' || n === 'Quest') return !colReach(e.cx); return !reachableNear(e.cx, e.y + e.h - 2, n === 'Shard' ? 4 : 3) && !(n === 'Collectable' && hookReach(e)); }).map(e => e.constructor.name + '@' + Math.floor(e.x / 16) + ',' + Math.floor(e.y / 16));
      const hasEnd = targets.some(e => ['Exit', 'BossGate', 'ChaseEnd', 'FinishLine', 'Quest'].includes(e.constructor.name)) || Gm.sub.concert;
      out.push({ id: lv.id + (lv.chapters ? '.' + (ch + 1) : ''), cells: seen.reduce((a, v) => a + v, 0), bad, hasEnd });
    }));
    return out;
  });
  let fails = 0; for (const r of res) { const ok = !r.bad.length && r.hasEnd; if (!ok) fails++; console.log((ok ? 'OK  ' : 'FAIL') + ' ' + r.id.padEnd(6) + ' reachable cells ' + String(r.cells).padStart(5) + (r.bad.length ? '  UNREACHABLE: ' + r.bad.join(' ') : '') + (r.hasEnd ? '' : ' NO END')); }
  console.log(fails ? fails + ' FAILURES' : 'ALL LEVELS REACHABLE'); await b.close(); process.exit(fails ? 1 : 0);
})();
