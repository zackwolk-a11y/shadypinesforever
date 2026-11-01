// Quick smoke: load a scene, report errors, screenshot.
import { createRequire } from 'module';
const { chromium } = createRequire(import.meta.url)('playwright');
const [scene = 'store', out = '/tmp/claude-0/shots/smoke.png', wait = '1500'] = process.argv.slice(2);
const base = process.env.BASE ?? 'http://localhost:5173';
const b = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
const p = await b.newPage({ viewport: { width: 960, height: 540 } });
const errs = [];
p.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') errs.push(m.type() + ': ' + m.text()); });
p.on('pageerror', (e) => errs.push('pageerror: ' + e.message + '\n' + e.stack));
await p.goto(`${base}/?scene=${scene}`);
await p.waitForTimeout(+wait);
await p.screenshot({ path: out });
console.log(JSON.stringify(await p.evaluate(() => ({ gen: window.__SIMPS.genMs, fps: window.__SIMPS.game?.loop.actualFps }))));
console.log(errs.slice(0, 10).join('\n') || 'no errors');
await b.close();
