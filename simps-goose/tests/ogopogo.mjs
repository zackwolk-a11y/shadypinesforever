/** Verifies EVERY coffee burp can defeat Ogopogo (real C presses; teleport = player positioning). */
import { createRequire } from 'module';
const { chromium } = createRequire(import.meta.url)('playwright');
const base = process.env.BASE ?? 'http://localhost:5173';
const burps = (process.env.BURPS ?? 'vanilla,saltedcaramel,hazelnut,peppermint,lavender,marshmallow').split(',');
const b = await chromium.launch();
const out = [];
for (const burp of burps) {
  const p = await b.newPage();
  const errs = []; p.on('pageerror', (e) => errs.push(e.message));
  await p.goto(`${base}/?scene=ogopogo&burp=${burp}`);
  await p.waitForFunction(() => window.__SIMPS.og?.bossPhase === 1, null, { timeout: 20000 });
  const t0 = Date.now();
  let result = 'timeout';
  while (Date.now() - t0 < 150000) {
    const st = await p.evaluate(() => { const o = window.__SIMPS.og; return { ph: o.bossPhase, hp: o.hp, hx: o.hx, hy: o.hy, ty: o.ty, ready: o.superReady, over: o.over, scene: window.__SIMPS.scene }; });
    if (st.over) { result = 'super-burp'; break; }
    if (st.ready) { await p.keyboard.press('c'); continue; }
    // choose a spot like a player would: dock in phase 1, the buoy nearest the head's height later
    let spot = [262, 222];
    if (st.ph >= 2) spot = st.hy < 100 ? (st.hx < 320 ? [210, 140] : [330, 110]) : [290, 176];
    const face = st.hx > spot[0] ? 'ArrowRight' : 'ArrowLeft';
    await p.evaluate(([x, y]) => window.__SIMPS.teleport(x, y), spot);
    await p.keyboard.down(face); await p.waitForTimeout(16); await p.keyboard.up(face);
    await p.keyboard.press('c'); await p.waitForTimeout(220);
  }
  if (result === 'super-burp') { const ok = await p.waitForFunction(() => window.__SIMPS.scene === 'TrueEnd', null, { timeout: 20000 }).then(() => true, () => false); if (ok) result = 'defeated → true ending'; }
  const secs = Math.round((Date.now() - t0) / 1000);
  out.push({ burp, result, secs, errors: errs.length });
  console.log(`${result.startsWith('defeated') ? 'PASS' : 'FAIL'}  ${burp.padEnd(14)} ${result}  (${secs}s)${errs.length ? '  ERR: ' + errs[0] : ''}`);
  await p.close();
}
await b.close();
const fs = await import('fs'); fs.mkdirSync('screenshots', { recursive: true }); fs.writeFileSync('screenshots/ogopogo-results.json', JSON.stringify(out, null, 2));
process.exit(out.every((o) => o.result.startsWith('defeated')) ? 0 : 1);
