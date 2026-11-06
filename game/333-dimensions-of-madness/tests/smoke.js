// Smoke test: boots the bundled game, loads every level & chapter, simulates input, collects errors + screenshots.
const { chromium } = require('playwright'); const path = require('path'), fs = require('fs');
const OUT = process.env.OUT || '/tmp/claude-0/shots'; fs.mkdirSync(OUT, { recursive: true });
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1280, height: 720 } });
  const errs = []; p.on('pageerror', e => errs.push('pageerror: ' + e.message)); p.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text()); });
  await p.goto('file://' + path.resolve(__dirname, '../333-dimensions-of-madness.html'));
  await p.waitForFunction(() => window.DIM333 && DIM333.G.state === 'title', null, { timeout: 15000 });
  await p.waitForTimeout(600); await p.screenshot({ path: OUT + '/00_title.png' });
  const only = process.argv[2] ? process.argv[2].split(',').map(Number) : null;
  const levels = await p.evaluate(() => DIM333.LEVELS.map(l => ({ id: l.id, ch: l.chapters ? l.chapters.length : 1 })));
  for (let i = 0; i < levels.length; i++) {
    if (only && !only.includes(i + 1)) continue;
    for (let ch = 0; ch < levels[i].ch; ch++) {
      const r = await p.evaluate(([i, ch]) => {
        const D = DIM333; D.god(true); D.load(i, ch); const out = { w: D.Game.L.w, ents: D.Game.ents.length };
        for (let f = 0; f < 900; f++) {
          if (D.Game.cutscene) D.skipScene();
          const k = f % 90; D.Input._down.right = true; D.Input._down.jump = k < 14; D.Input._down.whip = f % 37 === 0; D.Input._down.dash = f % 61 === 0; D.Input._down.spit = f % 53 === 0; D.Input._down.bash = f % 71 === 0; D.Input._down.scream = (f % 200) > 140; D.Input._down.headbang = f % 29 === 0;
          D.step(1);
          if (D.G.state !== 'level') break;
        }
        for (const k in D.Input._down) D.Input._down[k] = false;
        out.x = Math.round(D.Game.player.x); out.state = D.G.state; out.errors = D.G.errors.slice(); D.G.errors.length = 0; out.boss = !!D.Game.boss;
        return out;
      }, [i, ch]);
      await p.screenshot({ path: `${OUT}/L${String(i + 1).padStart(2, '0')}_c${ch}.png` });
      console.log(levels[i].id, 'ch' + ch, JSON.stringify(r).slice(0, 300));
    }
  }
  console.log('PAGE ERRORS:', errs.slice(0, 20));
  await b.close();
})();
