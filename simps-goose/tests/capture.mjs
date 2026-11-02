/** Records short gameplay demonstration clips (WebM) with Playwright's video capture. */
import { createRequire } from 'module';
import fs from 'fs';
const { chromium } = createRequire(import.meta.url)('playwright');
const base = process.env.BASE ?? 'http://localhost:4173';
const OUT = 'captures';
fs.mkdirSync(OUT, { recursive: true });
const b = await chromium.launch();
const ONLY = process.env.CLIPS ? process.env.CLIPS.split(',') : null;
async function clip(name, url, script) {
  if (ONLY && !ONLY.some((o) => name.startsWith(o))) return;
  const ctx = await b.newContext({ viewport: { width: 960, height: 540 }, recordVideo: { dir: OUT + '/tmp', size: { width: 640, height: 360 } } });
  const p = await ctx.newPage();
  await p.goto(base + url);
  await script(p);
  const v = p.video(); await ctx.close();
  fs.renameSync(await v.path(), `${OUT}/${name}.webm`);
  console.log('captured', name);
}
const tp = (p, x, y) => p.evaluate(([x, y]) => window.__SIMPS.teleport(x, y), [x, y]);
const hold = async (p, k, ms) => { await p.keyboard.down(k); await p.waitForTimeout(ms); await p.keyboard.up(k); };
await clip('01-intro-cinematic', '/?scene=intro', async (p) => { await p.waitForTimeout(11000); });
await clip('02-store-bubble-trouble', '/?scene=store&mode=demo', async (p) => {
  await p.waitForFunction(() => window.__SIMPS.store?.phase === 'play');
  await hold(p, 'ArrowRight', 1200); await p.keyboard.press('x'); await p.waitForTimeout(800);
  await tp(p, 1820, 330); await p.waitForTimeout(400); await p.keyboard.press('x'); await p.waitForTimeout(900); await p.keyboard.press('x');
  await p.waitForTimeout(4500); await tp(p, 2085, 190); await p.waitForTimeout(1500);
  await tp(p, 2330, 168); await p.waitForTimeout(400); await p.keyboard.press('e'); await p.waitForTimeout(8500);
});
await clip('03-lab-mixer', '/?scene=lab', async (p) => { await p.waitForTimeout(4200); await tp(p, 300, 390); await p.waitForTimeout(300); await p.keyboard.press('e'); await p.waitForTimeout(600); for (const k of ['e', 'ArrowRight', 'ArrowRight', 'e', 'ArrowDown', 'ArrowDown', 'e', 'e']) { await p.keyboard.press(k); await p.waitForTimeout(250); } for (let i = 0; i < 3; i++) { await p.waitForFunction(() => Math.abs(window.__SIMPS.game.scene.getScene('Mixer').needle - 0.5) < 0.03, null, { polling: 4 }); await p.keyboard.press('Space'); await p.waitForTimeout(400); } await p.waitForTimeout(900); await p.keyboard.press('e'); await p.waitForTimeout(3500); await tp(p, 540, 390); await p.keyboard.down('ArrowRight'); await p.waitForTimeout(100); await p.keyboard.press('c'); await p.waitForTimeout(1500); await p.keyboard.up('ArrowRight'); });
await clip('04-soda-dimension', '/?scene=dimension', async (p) => { await p.waitForTimeout(3000); await hold(p, 'ArrowRight', 900); await p.keyboard.down('ArrowRight'); for (let i = 0; i < 6; i++) { await p.keyboard.down('Space'); await p.waitForTimeout(350); await p.keyboard.up('Space'); await p.waitForTimeout(400); } await p.keyboard.up('ArrowRight'); await p.waitForTimeout(1500); });
await clip('05-carbonation-boss', '/?scene=carb', async (p) => { await p.waitForFunction(() => window.__SIMPS.boss?.bossPhase === 1, null, { timeout: 15000 }); const t0 = Date.now(); while (Date.now() - t0 < 14000) { const bb = await p.evaluate(() => { const b = window.__SIMPS.boss.bubblesB.find((b) => b.alive && !b.reflected); return b ? { x: b.x } : null; }); if (bb) { await tp(p, Math.max(30, bb.x - 40), 280); await p.keyboard.press('x'); } await p.waitForTimeout(400); } });
await clip('06-fake-ending-interruption', '/?scene=fake', async (p) => { await p.waitForTimeout(36000); });
await clip('07-ogopogo-battle', '/?scene=ogopogo&burp=vanilla', async (p) => { await p.waitForFunction(() => window.__SIMPS.og?.bossPhase === 1, null, { timeout: 20000 }); const t0 = Date.now(); while (Date.now() - t0 < 40000) { const st = await p.evaluate(() => { const o = window.__SIMPS.og; return { ph: o.bossPhase, hx: o.hx, hy: o.hy, ready: o.superReady, over: o.over }; }); if (st.over) break; if (st.ready) { await p.keyboard.press('c'); continue; } let spot = [262, 222]; if (st.ph >= 2) spot = st.hy < 100 ? (st.hx < 320 ? [210, 140] : [330, 110]) : [290, 176]; await tp(p, spot[0], spot[1]); await p.keyboard.press(st.hx > spot[0] ? 'ArrowRight' : 'ArrowLeft'); await p.keyboard.press('c'); await p.waitForTimeout(500); } await p.waitForTimeout(6000); });
await clip('08-true-ending', '/?scene=trueend', async (p) => { await p.waitForTimeout(33000); });
fs.rmSync(OUT + '/tmp', { recursive: true, force: true });
await b.close();
