// Every combat arena in every level: each wave's enemies must appear on screen inside the arena
// (reachable), and the arena must open once they are beaten. Regression for the Level 4 candle soft-lock.
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 640, height: 360 } });
  const errs = []; p.on('pageerror', e => errs.push(String(e)));
  await p.goto('file://' + path.resolve(__dirname, '../333-dimensions-of-madness.html'));
  await p.waitForFunction(() => window.DIM333 && DIM333.G.state === 'title');
  const res = await p.evaluate(() => { const D = DIM333, Gm = D.Game, out = [];
    for (let li = 0; li < LEVELS.length; li++) { D.load(li); Gm.cutscene = null; D.god && D.god(); D.run(3);
      const arenas = Gm.ents.filter(e => e.constructor.name === 'Arena');
      for (const a of arenas) { const pl = Gm.player, tx = Math.floor((a.x + 60) / 16); pl.x = a.x + 60; pl.y = Gm.groundY(Gm.L, tx) - pl.h; pl.vx = pl.vy = 0; Gm.cutscene = null;
        let bad = [], waves = 0;
        for (let k = 0; k < 400 && !a.done; k++) { D.run(1); if (a.wave >= waves) { waves = a.wave + 1; D.run(100);
            for (const e of a.spawned) if (!e.dead) { const vis = e.cx > Cam.x && e.cx < Cam.x + VW && e.cy > Cam.y && e.cy < Cam.y + VH; if (!vis) bad.push([e.kind, e.cx | 0, e.cy | 0, Cam.y | 0]); }
            for (const e of a.spawned) if (!e.dead) e.hit(99, { kind: 'test' }); } Gm.cutscene = null; }
        out.push({ lv: LEVELS[li].id, x: a.x, done: a.done, bad }); } }
    return out; });
  let fail = 0; for (const r of res) { const ok = r.done && !r.bad.length; if (!ok) fail++; console.log((ok ? 'OK  ' : 'FAIL') + ' ' + r.lv + ' arena@' + r.x + (r.bad.length ? ' off-screen: ' + JSON.stringify(r.bad) : '') + (r.done ? '' : ' (never opened)')); }
  console.log('page errors:', JSON.stringify(errs));
  console.log(fail || errs.length ? fail + ' ARENA FAILURES' : 'ALL ' + res.length + ' ARENAS CLEARABLE'); await b.close(); process.exit(fail || errs.length ? 1 : 0);
})();
