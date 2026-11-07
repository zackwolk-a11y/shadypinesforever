// Desktop + mobile layout screenshots, touch-control presence, frame rate in a busy scene, offline check.
const { chromium, devices } = require('playwright'); const path = require('path'), fs = require('fs');
const OUT = process.env.OUT || '/tmp/claude-0/platform'; fs.mkdirSync(OUT, { recursive: true });
const URL = 'file://' + path.resolve(__dirname, '../333-dimensions-of-madness.html');
(async () => {
  const b = await chromium.launch(); let fail = 0; const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fail++; };
  // ---- desktop
  const dp = await b.newPage({ viewport: { width: 1920, height: 1080 } }); const reqs = [];
  dp.on('request', r => { if (!r.url().startsWith('file:') && !r.url().startsWith('data:')) reqs.push(r.url()); });
  await dp.goto(URL); await dp.waitForFunction(() => window.DIM333 && DIM333.G.state === 'title');
  await dp.evaluate(() => { DIM333.unlockAll(); DIM333.load(27); DIM333.skipScene(); }); await dp.waitForTimeout(500);
  const fps = await dp.evaluate(() => new Promise(r => { const D = DIM333; D.god(); D.Input._down.right = true; let n = 0, t0 = performance.now(); const tick = () => { n++; if (performance.now() - t0 < 3000) requestAnimationFrame(tick); else { D.Input._down.right = false; r({ raf: n / 3, game: D.G.fps, ents: D.Game.ents.length }); } }; requestAnimationFrame(tick); }));
  ok(fps.raf >= 50, `desktop frame rate ${fps.raf.toFixed(0)} rAF/s (game ${fps.game}fps, ${fps.ents} entities)`);
  await dp.screenshot({ path: OUT + '/desktop_1080p.png' });
  const sz = await dp.evaluate(() => [document.getElementById('screen').style.width, document.getElementById('screen').style.height]);
  ok(sz[0] === '1920px', 'desktop scales canvas to ' + sz.join('x'));
  ok(reqs.length === 0, 'no network requests (' + reqs.length + ')');
  // ---- mobile (landscape phone, touch)
  const ctxM = await b.newContext({ ...devices['iPhone 13 landscape'] }); const mp = await ctxM.newPage();
  await mp.goto(URL); await mp.waitForFunction(() => window.DIM333 && DIM333.G.state === 'title');
  await mp.tap('#screen'); await mp.waitForTimeout(300);
  const touchOn = await mp.evaluate(() => document.getElementById('touch').classList.contains('on') && document.querySelectorAll('.tb:not([data-a=fs])').length);
  ok(touchOn === 3, 'only JUMP, ATTACK and pause on the touch screen (' + touchOn + ' buttons)');
  await mp.screenshot({ path: OUT + '/mobile_title.png' });
  await mp.evaluate(() => { DIM333.load(0); }); await mp.waitForTimeout(300);
  for (let i = 0; i < 14; i++) { await mp.tap('#screen'); await mp.waitForTimeout(60); }
  await mp.evaluate(() => DIM333.skipScene()); await mp.waitForTimeout(400);
  const y0 = await mp.evaluate(() => DIM333.Game.player.y);
  const jb = await mp.$$('.tb:not([data-a=fs])'); await jb[0].dispatchEvent('touchstart'); await mp.waitForTimeout(150);
  const y1 = await mp.evaluate(() => DIM333.Game.player.y); await jb[0].dispatchEvent('touchend');
  ok(y1 < y0 - 5, `touch JUMP button makes the monster jump (${y0 | 0} -> ${y1 | 0})`);
  await mp.waitForTimeout(400); await mp.screenshot({ path: OUT + '/mobile_level.png' });
  const tab = await b.newPage({ viewport: { width: 820, height: 1180 }, hasTouch: true, isMobile: true });
  await tab.goto(URL); await tab.waitForFunction(() => window.DIM333 && DIM333.G.state === 'title'); await tab.screenshot({ path: OUT + '/tablet_portrait.png' });
  console.log(fail ? fail + ' FAILED' : 'ALL PLATFORM CHECKS PASS'); await b.close(); process.exit(fail ? 1 : 0);
})();
