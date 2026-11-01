import { createRequire } from 'module';
const { chromium } = createRequire(import.meta.url)('playwright');
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 960, height: 540 } });
p.on('pageerror', (e) => console.log('ERR', e.message, e.stack.split('\n').slice(0, 4).join('\n')));
await p.goto('http://localhost:5173/?scene=lab&skipintro=1');
await p.waitForFunction(() => window.__SIMPS.level?.phase === 'play');
await p.evaluate(() => window.__SIMPS.teleport(300, 390)); await p.waitForTimeout(300);
await p.keyboard.press('e'); await p.waitForTimeout(400);
const k = async (key, n = 1) => { for (let i = 0; i < n; i++) { await p.keyboard.press(key); await p.waitForTimeout(90); } };
await k('e');               // base: cola (sel 0)
await k('ArrowRight', 2); await k('e'); // primary: black cherry (idx 2)
await p.screenshot({ path: '/tmp/claude-0/mixer1.png' });
await k('ArrowDown'); await k('e'); // secondary: none
await k('e');               // fizz medium -> pump
for (let i = 0; i < 3; i++) { await p.waitForFunction(() => { const m = window.__SIMPS.game.scene.getScene('Mixer'); return Math.abs(m.needle - 0.5) < 0.03; }, null, { polling: 5, timeout: 5000 }); await p.keyboard.press('Space'); await p.waitForTimeout(300); }
await p.waitForTimeout(500);
await p.screenshot({ path: '/tmp/claude-0/mixer2.png' });
console.log(await p.evaluate(() => { const m = window.__SIMPS.game.scene.getScene('Mixer'); return { step: m.step, res: m.result && { r: m.result.recipe?.id, q: m.result.quality, p: m.result.power } }; }));
await k('e'); await p.waitForTimeout(3000);
console.log(await p.evaluate(() => ({ power: window.__SIMPS.level.power, phase: window.__SIMPS.level.phase })));
// dash through glass
await p.evaluate(() => window.__SIMPS.teleport(560, 390)); await p.waitForTimeout(200);
await p.keyboard.down('ArrowRight'); await p.waitForTimeout(60); await p.keyboard.press('c'); await p.waitForTimeout(400); await p.keyboard.up('ArrowRight');
console.log('glass', await p.evaluate(() => window.__SIMPS.level.glassBroken));
await b.close();
