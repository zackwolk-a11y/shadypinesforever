import { createRequire } from 'module';
const { chromium } = createRequire(import.meta.url)('playwright');
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 960, height: 540 } });
p.on('pageerror', (e) => console.log('ERR', e.message, e.stack.split('\n').slice(0, 4).join('\n')));
await p.goto('http://localhost:5173/?scene=cafe');
await p.waitForFunction(() => window.__SIMPS.level?.phase === 'play');
await p.evaluate(() => window.__SIMPS.teleport(400, 240)); await p.waitForTimeout(300);
await p.keyboard.press('e');
await p.waitForFunction(() => window.__SIMPS.game.scene.isActive('Coffee'), null, { timeout: 9000 });
const k = async (key, n = 1) => { for (let i = 0; i < n; i++) { await p.keyboard.press(key); await p.waitForTimeout(120); } };
await k('e'); // espresso
await k('ArrowDown', 1); await p.screenshot({ path: '/tmp/claude-0/coffee1.png' }); await k('e'); // salted caramel
await k('ArrowDown', 5); await k('e'); // none
await k('ArrowDown', 1); await k('e'); // oat
await k('ArrowDown', 1); await k('e'); // 2 pumps
const step = () => p.evaluate(() => window.__SIMPS.game.scene.getScene('Coffee').step);
console.log('step', await step());
await p.keyboard.down('e'); await p.waitForFunction(() => window.__SIMPS.game.scene.getScene('Coffee').level >= 0.69, null, { polling: 5 }); await p.keyboard.up('e'); await p.waitForTimeout(200);
console.log('step', await step());
await k('e', 2); await p.waitForTimeout(400);
console.log('step', await step());
await p.keyboard.down('e'); await p.waitForFunction(() => window.__SIMPS.game.scene.getScene('Coffee').level >= 0.89, null, { polling: 5 }); await p.keyboard.up('e'); await p.waitForTimeout(200);
console.log('step', await step());
for (let i = 0; i < 4; i++) { await k('ArrowLeft'); await k('ArrowRight'); }
console.log('step', await step());
await k('ArrowDown'); await k('e');
await p.waitForTimeout(300); await p.screenshot({ path: '/tmp/claude-0/coffee2.png' });
console.log('step', await step());
await k('e');
await p.waitForTimeout(11500);
console.log(await p.evaluate(() => ({ burp: window.__SIMPS.level.burp, phase: window.__SIMPS.level.phase })));
await p.keyboard.press('c'); await p.waitForTimeout(300);
await p.screenshot({ path: '/tmp/claude-0/cafe2.png' });
console.log('shots', await p.evaluate(() => window.__SIMPS.level.shots.filter((s) => s.active).length));
await b.close();
