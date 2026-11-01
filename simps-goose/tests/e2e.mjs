/**
 * End-to-end test of the vertical slice in real Chromium.
 * Gameplay actions use REAL keyboard / touch input. A teleport hook is used only to
 * jump between sections quickly (marked [tp] in the log).
 * Usage: BASE=http://localhost:4173 node tests/e2e.mjs
 */
import { createRequire } from 'module';
import fs from 'fs';
const { chromium } = createRequire(import.meta.url)('playwright');
const base = process.env.BASE ?? 'http://localhost:5173';
const SHOTS = process.env.SHOTS ?? 'screenshots';
fs.mkdirSync(SHOTS, { recursive: true });
const results = [];
const errs = [];
const ok = (name, pass, info = '') => { results.push({ name, pass: !!pass, info }); console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${info ? '  — ' + info : ''}`); };

const browser = await chromium.launch();
async function page(opts = {}) {
  const ctx = await browser.newContext({ viewport: { width: 960, height: 540 }, ...opts });
  const p = await ctx.newPage();
  p.on('pageerror', (e) => errs.push('pageerror: ' + e.message));
  p.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text()); });
  return p;
}
const wait = (p, fn, arg, timeout = 15000) => p.waitForFunction(fn, arg, { timeout, polling: 50 }).then(() => true, () => false);
const st = (p) => p.evaluate(() => { const s = window.__SIMPS.store; if (!s) return null; const g = s.goose; return { x: Math.round(g.x), y: Math.round(g.y), ground: g.body.onGround, gtag: g.body.ground?.tag ?? null, mode: g.mode, phase: s.phase, power: s.power, drops: s.dropCount, fountain: s.fountain.stage, wall: s.boxWall.toppled, bubbles: s.bubbles.activeCount(), anim: g.sprite.anims.currentAnim?.key }; });
const hold = async (p, k, ms) => { await p.keyboard.down(k); await p.waitForTimeout(ms); await p.keyboard.up(k); };
const tp = (p, x, y) => p.evaluate(([x, y]) => window.__SIMPS.teleport(x, y), [x, y]);
const activeScenes = (p) => p.evaluate(() => window.__SIMPS.game.scene.getScenes(true).map((s) => s.scene.key));
const shot = (p, n) => p.screenshot({ path: `${SHOTS}/${n}.png` });
const missingTextures = (p) => p.evaluate(() => { let n = 0; for (const sc of window.__SIMPS.game.scene.getScenes(true)) sc.children.list.forEach((o) => { if (o.texture && o.texture.key === '__MISSING') n++; }); return n; });

// ---------------------------------------------------------------- 1. title + cinematic
{
  const p = await page();
  await p.goto(base + '/');
  ok('title screen loads', await wait(p, () => window.__SIMPS.scene === 'Title'));
  await p.waitForTimeout(800); await shot(p, '01-title');
  await p.keyboard.press('Enter'); await p.waitForTimeout(400);
  await shot(p, '02-title-menu');
  await p.keyboard.press('Enter');
  ok('START DEMO → intro cinematic', await wait(p, () => window.__SIMPS.scene === 'Intro', null, 5000));
  await p.waitForTimeout(5800); await shot(p, '03-intro-notices-bottle');
  await p.waitForTimeout(1700); await shot(p, '04-intro-enormous-honk');
  await p.waitForTimeout(900); await shot(p, '05-intro-door-opens');
  ok('cinematic plays through to the store', await wait(p, () => window.__SIMPS.store?.phase === 'play', null, 6000));
  ok('no missing textures (title/intro/store)', (await missingTextures(p)) === 0);
  await p.close();
}
{
  const p = await page();
  await p.goto(base + '/?scene=intro');
  await wait(p, () => window.__SIMPS.scene === 'Intro');
  await p.waitForTimeout(1500);
  await p.keyboard.press('Space');
  ok('cinematic is skippable', await wait(p, () => window.__SIMPS.store?.phase === 'play', null, 3000));
  await p.close();
}

// ---------------------------------------------------------------- 2. store gameplay
const p = await page();
await p.goto(base + '/?scene=store');
await wait(p, () => window.__SIMPS.store?.phase === 'play');
await p.waitForTimeout(300);
let s0 = await st(p);
await hold(p, 'ArrowRight', 700);
let s1 = await st(p);
ok('goose walks right', s1.x > s0.x + 40, `${s0.x} → ${s1.x}`);
await hold(p, 'ArrowLeft', 300);
let s2 = await st(p);
ok('goose turns and walks left', s2.x < s1.x, `${s1.x} → ${s2.x}`);
await p.keyboard.down('Space'); await p.waitForTimeout(250);
let sj = await st(p);
await p.keyboard.up('Space'); await p.waitForTimeout(700);
let sl = await st(p);
ok('jump leaves ground and lands', !sj.ground && sj.y < 320 && sl.ground && sl.y === 330, `apex-ish y=${sj.y}, landed y=${sl.y}`);
// climb crate (real input)
await tp(p, 280, 330); await p.waitForTimeout(150);
await p.keyboard.down('ArrowRight'); await p.keyboard.down('Space'); await p.waitForTimeout(260); await p.keyboard.up('Space'); await p.waitForTimeout(230); await p.keyboard.up('ArrowRight'); await p.waitForTimeout(500);
let sc = await st(p);
ok('jump onto display crate', sc.ground && sc.y < 330, `y=${sc.y} on ${sc.gtag}`);
// honk at a customer
await tp(p, 210, 330); await p.waitForTimeout(200);
const before = await p.evaluate(() => window.__SIMPS.store.people.map((x) => x.state).join(','));
await p.keyboard.press('x'); await p.waitForTimeout(450);
const after = await p.evaluate(() => window.__SIMPS.store.people.filter((x) => ['react', 'laugh', 'flee'].includes(x.state)).length);
const jig = await p.evaluate(() => window.__SIMPS.store.bottles.filter((b) => b.wob > 0).length);
ok('honk makes customers react', after >= 1, `${after} reacting (was ${before})`);
await shot(p, '06-store-honk-reaction');
await tp(p, 430, 330); await p.waitForTimeout(150); await p.keyboard.press('x'); await p.waitForTimeout(300);
const jig2 = await p.evaluate(() => window.__SIMPS.store.bottles.filter((b) => b.wob > 0).length);
ok('honk jiggles bottles on shelves', jig2 > 0, `${jig2} wobbling`);
// trident stand climb with real jumps
await tp(p, 540, 330); await p.waitForTimeout(200);
const jumpRight = async (hRight, hJump) => { await p.keyboard.down('ArrowRight'); await p.keyboard.down('Space'); await p.waitForTimeout(hJump); await p.keyboard.up('Space'); await p.waitForTimeout(Math.max(0, hRight - hJump)); await p.keyboard.up('ArrowRight'); await p.waitForTimeout(450); return st(p); };
let t1 = await jumpRight(140, 260);
ok('trident stand: pedestal', t1.gtag === 'tridentPedestal', JSON.stringify(t1.gtag));
await tp(p, 594, 300); await p.waitForTimeout(150);
await p.keyboard.down('Space'); await p.waitForTimeout(300); await p.keyboard.up('Space'); await p.waitForTimeout(600);
let t2 = await st(p);
ok('trident stand: crossbar ledge', t2.gtag === 'trident0', JSON.stringify(t2.gtag));
await shot(p, '07-trident-stand');

// ---------------------------------------------------------------- 3. sampling + powers
async function sample(idx) {
  await tp(p, 1380, 330); await p.waitForTimeout(200);
  await p.keyboard.press('e');
  const opened = await wait(p, () => window.__SIMPS.store.phase === 'picker', null, 2000);
  const cur = await p.evaluate(() => window.__SIMPS.store.sampling.idx);
  for (let i = 0; i < (idx - cur + 3) % 3; i++) { await p.keyboard.press('ArrowRight'); await p.waitForTimeout(80); }
  if (idx === 1) await shot(p, '08-flavor-picker');
  await p.keyboard.press('e');
  await p.waitForTimeout(1300);
  if (idx === 0) await shot(p, '09-goose-drinking');
  await p.waitForTimeout(700);
  if (idx === 2) await shot(p, '10-flavor-reaction');
  const done = await wait(p, () => window.__SIMPS.store.phase === 'play' && window.__SIMPS.store.power !== null, null, 5000);
  return { opened, done, power: (await st(p)).power };
}
const restart = async () => { await p.evaluate(() => window.__SIMPS.restartStore()); await wait(p, () => window.__SIMPS.store?.phase === 'play'); await p.waitForTimeout(200); };

// COLA
let r = await sample(0);
ok('sampling station opens picker', r.opened);
ok('sip COLA → Fizzy Dash', r.done && r.power === 'cola', r.power);
await tp(p, 1530, 330); await p.waitForTimeout(250); await p.keyboard.down('ArrowRight'); await p.waitForTimeout(60); await p.keyboard.press('c'); await p.waitForTimeout(80); await p.keyboard.up('ArrowRight');
await p.waitForTimeout(250); await shot(p, '11-cola-dash');
await p.waitForTimeout(500);
ok('Fizzy Dash smashes the delivery box wall', (await st(p)).wall);
// CREAM SODA
await restart();
r = await sample(1);
ok('sip CREAM SODA → Foam Float', r.done && r.power === 'cream', r.power);
await tp(p, 1555, 330); await p.waitForTimeout(250);
await p.keyboard.press('c'); await p.waitForTimeout(650);
let sf = await st(p);
ok('Foam Float lifts the goose on a foam cloud', sf.gtag === 'foam' && sf.y < 300, `y=${sf.y} on ${sf.gtag}`);
await shot(p, '12-cream-foam');
await jumpRight(700, 300); await p.waitForTimeout(200);
let so = await st(p);
ok('foam cloud lets goose clear the box wall', so.x > 1630, `x=${so.x}`);
// BLACK CHERRY
await restart();
r = await sample(2);
ok('sip BLACK CHERRY → Cherry Blast', r.done && r.power === 'cherry', r.power);
await tp(p, 1520, 330); await p.waitForTimeout(250); await hold(p, 'ArrowRight', 60);
await p.keyboard.press('c'); await p.waitForTimeout(350); await shot(p, '13-cherry-blast');
ok('Cherry Blast topples the box wall', await wait(p, () => window.__SIMPS.store.boxWall.toppled, null, 3000));
ok('only one power active at a time (HUD shows cherry)', (await st(p)).power === 'cherry');
const exp = await p.evaluate(() => { const s = window.__SIMPS.store; s.powerT = 0.05; return true; });
await p.waitForTimeout(400);
ok('power expires (burp) after its timer', exp && (await st(p)).power === null);

// ---------------------------------------------------------------- 4. fountain + bubble trouble
await tp(p, 1820, 330); await p.waitForTimeout(200);
await p.keyboard.press('x'); await p.waitForTimeout(700);
ok('first honk wakes the fountain (stage 1)', (await st(p)).fountain === 1);
await shot(p, '14-fountain-rumble');
await p.waitForTimeout(500); await p.keyboard.press('x');
ok('second honk → eruption (stage 2)', await wait(p, () => window.__SIMPS.store.fountain.stage === 2 && window.__SIMPS.store.bubbles.activeCount() > 0, null, 4000));
await p.waitForTimeout(2500); await shot(p, '15-bubble-trouble');
const nb = (await st(p)).bubbles;
ok('bubbles spawn continuously', nb >= 4, `${nb} active`);
// stand on hover bubble A (drop onto it)
const ha = await p.evaluate(() => { const b = window.__SIMPS.store.fountain.hoverRefs[0]; return b ? { x: b.x, y: b.y } : { x: 2085, y: 224 }; });
await tp(p, ha.x, ha.y - 30);
const onBub = await wait(p, () => window.__SIMPS.store.goose.body.ground?.tag === 'bubble', null, 3000);
ok('floating bubble supports the goose', onBub, JSON.stringify(await st(p)));
await p.waitForTimeout(500);
ok('goose rides the bubble (still on it after 0.5s)', (await st(p)).gtag === 'bubble');
await shot(p, '16-on-bubble');
// stomp-pop: jump in place on the bubble repeatedly
for (let i = 0; i < 3; i++) { await p.keyboard.down('Space'); await p.waitForTimeout(90); await p.keyboard.up('Space'); await p.waitForTimeout(650); }
const popped = await p.evaluate(() => window.__SIMPS.store.fountain.hoverRefs[0]?.active === false || window.__SIMPS.store.fountain.hoverRefs[0]?.stomps === 0);
ok('bubble pops after repeated landings', popped);
// trident lift moving
const ly0 = await p.evaluate(() => window.__SIMPS.store.lift.y); await p.waitForTimeout(700); const ly1 = await p.evaluate(() => window.__SIMPS.store.lift.y);
ok('trident lift is moving', Math.abs(ly1 - ly0) > 1, `${ly0.toFixed(1)} → ${ly1.toFixed(1)}`);
// hover B → mezzanine with real jump
await p.waitForFunction(() => window.__SIMPS.store.fountain.hoverRefs[1]?.active, null, { timeout: 5000 }).catch(() => {});
const hb = await p.evaluate(() => { const b = window.__SIMPS.store.fountain.hoverRefs[1]; return b ? { x: b.x, y: b.y } : { x: 2092, y: 204 }; });
await tp(p, hb.x, hb.y - 30);
await wait(p, () => window.__SIMPS.store.goose.body.ground?.tag === 'bubble', null, 2000);
await p.waitForTimeout(150);
await jumpRight(520, 320);
await p.waitForTimeout(300);
let sm = await st(p);
ok('bubble → elevated mezzanine (real jump)', sm.gtag === 'mezz' && sm.y === 168, JSON.stringify(sm));
// pause / resume
await p.keyboard.press('Escape'); await p.waitForTimeout(300);
const paused = await p.evaluate(() => window.__SIMPS.game.scene.isPaused('Store'));
await shot(p, '17-pause-menu');
await p.keyboard.press('Escape'); await p.waitForTimeout(300);
const resumed = await p.evaluate(() => window.__SIMPS.game.scene.isActive('Store'));
ok('pause and resume', paused && resumed);
// valve finale
await tp(p, 2330, 168); await p.waitForTimeout(300);
await p.keyboard.press('e');
ok('valve triggers finale', await wait(p, () => window.__SIMPS.store.fountain.finaleStarted, null, 2000));
await p.waitForTimeout(3200); await shot(p, '18-bubble-ride');
ok('goose rides the giant bubble upward', (await st(p)).mode === 'ride' && (await st(p)).y < 150, JSON.stringify(await st(p)));
ok('freeze frame + demo end', await wait(p, () => window.__SIMPS.store.phase === 'frozen', null, 8000));
await p.waitForTimeout(2300); await shot(p, '19-to-be-continued');
ok('no missing textures (gameplay)', (await missingTextures(p)) === 0);
// replay
await p.keyboard.press('Enter');
ok('REPLAY DEMO restarts at the cinematic', await wait(p, () => window.__SIMPS.game.scene.isActive('Intro'), null, 3000));
await p.close();

// ---------------------------------------------------------------- 5. mobile / touch
{
  const m = await page({ viewport: { width: 844, height: 390 }, hasTouch: true, isMobile: true, deviceScaleFactor: 2 });
  await m.goto(base + '/?scene=store&touch=1');
  await wait(m, () => window.__SIMPS.store?.phase === 'play');
  await m.waitForTimeout(300);
  const cdp = await m.context().newCDPSession(m);
  // map game coords → page coords (canvas FIT)
  const toPage = (gx, gy) => m.evaluate(([gx, gy]) => { const c = document.querySelector('canvas').getBoundingClientRect(); return { x: c.left + gx * c.width / 480, y: c.top + gy * c.height / 270 }; }, [gx, gy]);
  const touch = async (pts, type) => cdp.send('Input.dispatchTouchEvent', { type, touchPoints: pts.map((q, i) => ({ x: q.x, y: q.y, id: i })) });
  const R = await toPage(86, 236), J = await toPage(442, 232), H = await toPage(394, 246);
  const a0 = await st(m);
  await touch([R], 'touchStart'); await m.waitForTimeout(700);
  const a1 = await st(m);
  await touch([R, J], 'touchStart'); await m.waitForTimeout(120);
  const a2 = await st(m);
  await m.screenshot({ path: `${SHOTS}/20-mobile-touch.png` });
  await touch([], 'touchEnd'); await m.waitForTimeout(600);
  ok('mobile: touch RIGHT moves goose', a1.x > a0.x + 30, `${a0.x} → ${a1.x}`);
  ok('mobile: multi-touch RIGHT+JUMP jumps', !a2.ground || a2.y < 330, JSON.stringify(a2));
  await touch([H], 'touchStart'); await m.waitForTimeout(100); await touch([], 'touchEnd'); await m.waitForTimeout(400);
  ok('mobile: HONK button honks', (await m.evaluate(() => window.__SIMPS.store.honkCount)) >= 1);
  await m.close();
}

console.log('\n' + (errs.length ? 'ERRORS:\n' + [...new Set(errs)].slice(0, 15).join('\n') : 'no page errors'));
const pass = results.filter((r) => r.pass).length;
console.log(`\n${pass}/${results.length} checks passed`);
fs.writeFileSync(`${SHOTS}/results.json`, JSON.stringify({ results, errors: [...new Set(errs)] }, null, 2));
await browser.close();
process.exit(pass === results.length && !errs.length ? 0 : 1);
