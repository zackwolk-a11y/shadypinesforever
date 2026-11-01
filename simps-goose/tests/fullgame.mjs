/**
 * FULL GAME end-to-end checks (Levels 1-3, bosses, endings, saves, journals, touch, perf).
 * Gameplay uses REAL keyboard/touch input; window.__SIMPS.teleport is used only to move the
 * goose between sections (equivalent to the player walking there).
 */
import { createRequire } from 'module';
import fs from 'fs';
const { chromium } = createRequire(import.meta.url)('playwright');
const base = process.env.BASE ?? 'http://localhost:5173';
const SHOTS = process.env.SHOTS ?? 'screenshots/full';
fs.mkdirSync(SHOTS, { recursive: true });
const results = []; const errs = [];
const ok = (name, pass, info = '') => { results.push({ name, pass: !!pass, info: String(info) }); console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${info ? '  — ' + info : ''}`); };
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 960, height: 540 } });
async function page(url) { const p = await ctx.newPage(); p.on('pageerror', (e) => errs.push(`${url}: ${e.message}`)); p.on('console', (m) => { if (m.type() === 'error') errs.push(`${url}: console ${m.text()}`); }); await p.goto(base + url); return p; }
const wait = (p, fn, arg, timeout = 15000) => p.waitForFunction(fn, arg, { timeout, polling: 50 }).then(() => true, () => false);
const tp = (p, x, y) => p.evaluate(([x, y]) => window.__SIMPS.teleport(x, y), [x, y]);
const key = async (p, k, n = 1, gap = 110) => { for (let i = 0; i < n; i++) { await p.keyboard.press(k); await p.waitForTimeout(gap); } };
const shot = (p, n) => p.screenshot({ path: `${SHOTS}/${n}.png` });
const lvl = (p) => p.evaluate(() => { const l = window.__SIMPS.level; return l ? { key: l.scene.key, phase: l.phase, x: Math.round(l.goose.x), y: Math.round(l.goose.y), power: l.power, burp: l.burp, gtag: l.goose.body.ground?.tag ?? null } : null; });
const active = (p, k) => p.evaluate((k) => window.__SIMPS.game.scene.isActive(k), k);
const missing = (p) => p.evaluate(() => { let n = 0; for (const sc of window.__SIMPS.game.scene.getScenes(true)) sc.children.list.forEach((o) => { if (o.texture && o.texture.key === '__MISSING') n++; }); return n; });
const fps = (p) => p.evaluate(() => new Promise((res) => { let n = 0; const t0 = performance.now(); const f = () => { n++; if (performance.now() - t0 < 2000) requestAnimationFrame(f); else res(Math.round(n / 2)); }; requestAnimationFrame(f); }));
async function mix(p, picks, fizzRight = 0) {
  // picks: indices into the 10-ingredient grid; -1 = NONE
  let opened = false;
  for (let k = 0; k < 4 && !opened; k++) { await key(p, 'e', 1, 300); opened = await wait(p, () => window.__SIMPS.game.scene.isActive('Mixer'), null, 2500); }
  if (!opened) return { recipe: 'MIXER-DID-NOT-OPEN', q: '-', power: null, isSuper: false };
  let sel = 0;
  for (const target of picks) {
    if (target === -1) { await key(p, 'ArrowDown'); await key(p, 'ArrowDown'); await key(p, 'e'); continue; }
    while (sel !== target) { await key(p, sel < target ? 'ArrowRight' : 'ArrowLeft', 1, 60); sel += sel < target ? 1 : -1; }
    await key(p, 'e');
  }
  for (let i = 0; i < fizzRight; i++) await key(p, 'ArrowRight');
  await key(p, 'e');
  for (let i = 0; i < 3; i++) { await p.waitForFunction(() => Math.abs(window.__SIMPS.game.scene.getScene('Mixer').needle - 0.5) < 0.025, null, { timeout: 5000, polling: 4 }).catch(() => {}); await p.keyboard.press('Space'); await p.waitForTimeout(320); }
  await wait(p, () => window.__SIMPS.game.scene.getScene('Mixer').step === 'result', null, 3000);
  const r = await p.evaluate(() => { const m = window.__SIMPS.game.scene.getScene('Mixer'); return { recipe: m.result.recipe?.id ?? null, q: m.result.quality, power: m.result.power, isSuper: m.result.isSuper }; });
  await shot(p, 'lab-mixer-result');
  await key(p, 'e');
  return r;
}

// ============================================================ LEVEL 1 (story mode)
{
  const p = await page('/?scene=store');
  await wait(p, () => window.__SIMPS.level?.phase === 'play');
  await tp(p, 1045, 166); await p.waitForTimeout(400);
  ok('L1 storage route golden bottle collectable', (await p.evaluate(() => window.__SIMPS.level.counts.bottle)) === 1);
  await tp(p, 1820, 330); await p.waitForTimeout(200);
  await key(p, 'x', 1, 700); await key(p, 'x');
  ok('L1 two honks erupt the fountain (story)', await wait(p, () => window.__SIMPS.level.fountain.stage === 2, null, 4000));
  await tp(p, 2330, 168); await p.waitForTimeout(300); await key(p, 'e'); await p.waitForTimeout(400);
  ok('L1 main valve locked until pressure valves are open', !(await p.evaluate(() => window.__SIMPS.level.fountain.finaleStarted)));
  await tp(p, 1990, 250); await p.waitForTimeout(300); await key(p, 'x', 1, 500);
  await tp(p, 2245, 330); await p.waitForTimeout(300); await key(p, 'x', 1, 500);
  const vs = await p.evaluate(() => window.__SIMPS.level.valves.map((v) => v.on));
  ok('L1 both pressure valves opened (honk)', vs.every(Boolean), JSON.stringify(vs));
  await shot(p, 'L1-valves-giant-bubbles');
  await tp(p, 2330, 168); await p.waitForTimeout(300); await key(p, 'e');
  ok('L1 final trident valve starts the finale', await wait(p, () => window.__SIMPS.level.fountain.finaleStarted, null, 3000));
  await p.waitForTimeout(4500); await shot(p, 'L1-level-clear');
  ok('L1 transitions into Level 2 (Lab)', await wait(p, () => window.__SIMPS.game.scene.isActive('Lab'), null, 12000));
  await p.waitForTimeout(1500); await shot(p, 'L2-lab-arrival');
  ok('Lab arrival cutscene → play', await wait(p, () => window.__SIMPS.level?.phase === 'play' && window.__SIMPS.level.scene.key === 'Lab', null, 8000));
  ok('no missing textures (store/lab)', (await missing(p)) === 0);
  await p.close();
}
// ============================================================ LEVEL 2: LAB
{
  const p = await page('/?scene=lab&skipintro=1');
  await wait(p, () => window.__SIMPS.level?.phase === 'play');
  await tp(p, 300, 390); await p.waitForTimeout(300);
  const r1 = await mix(p, [0, 2, -1]);
  ok('Mixer: Cola + Black Cherry = Cherry Rocket', r1.recipe === 'cherry_rocket', JSON.stringify(r1));
  ok('Mixer: three green-zone pumps = PERFECT', r1.q === 'perfect');
  ok('Cherry Rocket power granted', await wait(p, () => window.__SIMPS.level.power === 'rocket', null, 5000));
  await tp(p, 560, 390); await p.waitForTimeout(200);
  await p.keyboard.down('ArrowRight'); await p.waitForTimeout(60); await key(p, 'c'); await p.waitForTimeout(400); await p.keyboard.up('ArrowRight');
  ok('Lab: rocket dash smashes the fragile glass wall', await p.evaluate(() => window.__SIMPS.level.glassBroken));
  await tp(p, 1262, 390); await p.waitForTimeout(300);
  const r2 = await mix(p, [8, 4, -1]);
  ok('Mixer: Blue Raspberry + Lemon Lime = Electric Fizz', r2.recipe === 'electric_fizz', JSON.stringify(r2));
  await wait(p, () => window.__SIMPS.level.power === 'electric', null, 5000);
  await tp(p, 1340, 390); await p.waitForTimeout(200); await p.keyboard.down('ArrowRight'); await p.waitForTimeout(30); await p.keyboard.up('ArrowRight');
  await key(p, 'c', 1, 2500);
  ok('Lab: Electric Fizz zaps the target and opens the gate', !(await p.evaluate(() => window.__SIMPS.level.gatePlat.active)));
  await shot(p, 'L2-lab-gate');
  await tp(p, 1928, 390); await p.waitForTimeout(300); await key(p, 'x', 1, 600);
  ok('Lab: pressure lever starts the trident lift', await p.evaluate(() => window.__SIMPS.level.lift.running));
  const r3 = await (async () => { await tp(p, 1262, 390); await p.waitForTimeout(300); return mix(p, [5, 9, -1]); })();
  ok('Mixer: unknown combo still gives a power (Mystery Fizz)', !!r3.power && r3.recipe === null, JSON.stringify(r3));
  await tp(p, 2600, 390); await p.waitForTimeout(300);
  const r4 = await mix(p, [0, 1, 2], 0);
  ok('Super Soda (Cola + Cream Soda + Black Cherry + MAX)', r4.isSuper, JSON.stringify(r4));
  await p.waitForTimeout(4200); await shot(p, 'L2-portal');
  ok('Portal accident → Soda Dimension', await wait(p, () => window.__SIMPS.game.scene.isActive('Dimension'), null, 10000));
  const s = await p.evaluate(() => JSON.parse(localStorage.getItem('simps-goose-save-v2')));
  ok('Recipes saved to the journal', !!s.recipes.cherry_rocket && !!s.recipes.electric_fizz, Object.keys(s.recipes).join(','));
  await p.close();
}
// ============================================================ LEVEL 2: DIMENSION
{
  const p = await page('/?scene=dimension');
  await wait(p, () => window.__SIMPS.level?.phase === 'play', null, 8000);
  await shot(p, 'L2-dimension');
  const slug = await p.evaluate(() => { const e = window.__SIMPS.level.enemies.find((e) => e.constructor.name === 'SyrupSlug'); return { x: e.x, y: e.y }; });
  await tp(p, slug.x, slug.y - 40); await p.waitForTimeout(700);
  ok('Dimension: stomping a Syrup Slug defeats it', await p.evaluate(() => window.__SIMPS.level.stomps >= 1));
  const types = await p.evaluate(() => [...new Set(window.__SIMPS.level.enemies.map((e) => e.constructor.name))].sort().join(','));
  ok('Dimension: all 5 enemy types present', types.split(',').length === 5, types);
  await tp(p, 1350, 345); await p.waitForTimeout(1200);
  ok('Dimension: collapsing foam pad gives way', await p.evaluate(() => window.__SIMPS.level.collapses[0].state !== 'idle'));
  await tp(p, 986, 320); await p.waitForTimeout(400);
  ok('Dimension: checkpoint reached', await p.evaluate(() => window.__SIMPS.level.checkpointSprites.some((c) => c.on)));
  ok('Dimension fps', (await fps(p)) >= 45);
  await tp(p, 3480, 330); 
  ok('Dimension exit portal → Carbonation boss', await wait(p, () => window.__SIMPS.game.scene.isActive('BossCarb'), null, 10000));
  await p.close();
}
// ============================================================ LEVEL 2: BOSS
{
  const p = await page('/?scene=carb');
  await wait(p, () => window.__SIMPS.boss?.bossPhase === 1, null, 10000);
  let t0 = Date.now();
  while (Date.now() - t0 < 60000 && (await p.evaluate(() => window.__SIMPS.boss.bossPhase)) === 1) {
    const b = await p.evaluate(() => { const bb = window.__SIMPS.boss.bubblesB.find((b) => b.alive && !b.reflected); return bb ? { x: bb.x, y: bb.y } : null; });
    if (b) { await tp(p, Math.max(30, b.x - 40), 280); await key(p, 'x', 1, 300); } else await p.waitForTimeout(150);
  }
  ok('Boss phase 1: honked bubbles hit the pressure switches', (await p.evaluate(() => window.__SIMPS.boss.bossPhase)) >= 2);
  await shot(p, 'L2-boss-phase2');
  t0 = Date.now();
  while (Date.now() - t0 < 60000 && (await p.evaluate(() => window.__SIMPS.boss.bossPhase)) === 2) {
    const tap = await p.evaluate(() => { const b = window.__SIMPS.boss; const t = b.taps[b.flavor]; return { x: t.x, y: t.y + 20 }; });
    await tp(p, tap.x, tap.y); await p.waitForTimeout(80); await key(p, 'e', 1, 350);
  }
  ok('Boss phase 2: matching flavor taps', (await p.evaluate(() => window.__SIMPS.boss.bossPhase)) >= 3);
  await p.waitForTimeout(1500); await shot(p, 'L2-boss-phase3');
  t0 = Date.now();
  while (Date.now() - t0 < 40000 && !(await p.evaluate(() => window.__SIMPS.boss.over))) {
    const v = await p.evaluate(() => { const v = window.__SIMPS.boss.valves3.find((v) => !v.on); return v ? { x: v.x, y: v.y + 22 } : null; });
    if (!v) break;
    await tp(p, v.x, v.y); await p.waitForTimeout(80); await key(p, 'e', 1, 400);
  }
  ok('Boss phase 3: all valves → Carbonator defeated', await p.evaluate(() => window.__SIMPS.boss.over));
  await p.waitForTimeout(2200); await shot(p, 'L2-boss-defeated');
  ok('Boss → fake ending', await wait(p, () => window.__SIMPS.game.scene.isActive('FakeEnd'), null, 10000));
  await p.close();
}
// ============================================================ FAKE ENDING → LEVEL 3
{
  const p = await page('/?scene=fake');
  await p.waitForTimeout(2600); await shot(p, 'fake-1-store-cheer');
  await p.waitForTimeout(4500); await shot(p, 'fake-2-congratulations');
  await p.waitForTimeout(9000); await shot(p, 'fake-3-credits');
  await p.waitForTimeout(9000); await shot(p, 'fake-4-goose-interrupts');
  ok('Fake ending: credits interrupted → Level 3 café', await wait(p, () => window.__SIMPS.game.scene.isActive('Cafe'), null, 20000));
  const s = await p.evaluate(() => JSON.parse(localStorage.getItem('simps-goose-save-v2')));
  ok('Level 3 revealed + unlocked (progress kept)', s.fakeEndingSeen && s.unlocked.includes('cafe'));
  await p.close();
}
// ============================================================ LEVEL 3: CAFÉ
{
  const p = await page('/?scene=cafe');
  await wait(p, () => window.__SIMPS.level?.phase === 'play');
  await tp(p, 400, 240); await p.waitForTimeout(300); await key(p, 'e');
  ok('Café: barista dialogue → coffee mini-game', await wait(p, () => window.__SIMPS.game.scene.isActive('Coffee'), null, 9000));
  await key(p, 'e'); await key(p, 'ArrowDown', 3); await key(p, 'e'); // peppermint
  await key(p, 'e'); await key(p, 'e'); await key(p, 'ArrowDown', 2); await key(p, 'e');
  await shot(p, 'L3-coffee-extract');
  await p.keyboard.down('e'); await wait(p, () => window.__SIMPS.game.scene.getScene('Coffee').level >= 0.69, null, 5000); await p.keyboard.up('e'); await p.waitForTimeout(200);
  await key(p, 'e', 3); await p.waitForTimeout(400);
  await p.keyboard.down('e'); await wait(p, () => window.__SIMPS.game.scene.getScene('Coffee').level >= 0.89, null, 5000); await p.keyboard.up('e'); await p.waitForTimeout(200);
  for (let i = 0; i < 4; i++) { await key(p, 'ArrowLeft'); await key(p, 'ArrowRight'); }
  await key(p, 'e'); await p.waitForTimeout(300); await shot(p, 'L3-latte-art'); await key(p, 'e');
  ok('Café: first burp → Bubble Burp unlocked (Peppermint)', await wait(p, () => window.__SIMPS.level.burp === 'peppermint' && window.__SIMPS.level.phase === 'play', null, 16000));
  await key(p, 'c', 1, 300);
  ok('Café: burp fires a bubble', (await p.evaluate(() => window.__SIMPS.level.shots.length)) >= 1);
  await shot(p, 'L3-cafe-burp');
  await tp(p, 930, 240);
  ok('Café → waterfront', await wait(p, () => window.__SIMPS.game.scene.isActive('Waterfront'), null, 8000));
  const s = await p.evaluate(() => JSON.parse(localStorage.getItem('simps-goose-save-v2')));
  ok('Coffee power persisted in the save', s.coffee === 'peppermint' || s.run?.coffee === 'peppermint', JSON.stringify({ c: s.coffee, r: s.run?.coffee }));
  await p.close();
}
// ============================================================ LEVEL 3: WATERFRONT
{
  const p = await page('/?scene=waterfront&burp=vanilla');
  await wait(p, () => window.__SIMPS.level?.phase === 'play');
  await tp(p, 250, 230); await p.keyboard.down('ArrowRight'); await p.waitForTimeout(20); await p.keyboard.up('ArrowRight');
  for (let i = 0; i < 6; i++) await key(p, 'c', 1, 800);
  ok('Waterfront: burp targets popped', (await p.evaluate(() => window.__SIMPS.level.switches.filter((s) => s.on).length)) >= 1);
  await tp(p, 540, 230); await p.keyboard.down('ArrowRight'); await p.waitForTimeout(20); await p.keyboard.up('ArrowRight'); await key(p, 'c', 1, 1200);
  ok('Waterfront: burp lifts the beach ball', await p.evaluate(() => window.__SIMPS.level.ballLifted));
  await tp(p, 760, 230); await key(p, 'e', 1, 300);
  ok('Waterfront: E makes a bubble platform', (await p.evaluate(() => window.__SIMPS.level.bubbles.activeCount())) >= 1);
  await shot(p, 'L3-waterfront');
  await tp(p, 1300, 230); await key(p, 'x', 1, 500);
  ok('Waterfront: bubble bell opens the dock', !(await p.evaluate(() => window.__SIMPS.level.gatePlat.active)));
  await tp(p, 1555, 222);
  ok('Waterfront: sit on the dock → ripples → Ogopogo', await wait(p, () => window.__SIMPS.game.scene.isActive('Ogopogo'), null, 12000));
  await p.waitForTimeout(7000); await shot(p, 'L3-ogopogo-rises');
  await p.close();
}
// ============================================================ TRUE ENDING
{
  const p = await page('/?scene=trueend');
  await p.waitForTimeout(8000); await shot(p, 'end-1-offer-sip');
  await p.waitForTimeout(5000); await shot(p, 'end-2-ogopogo-burp');
  await p.waitForTimeout(12000); await shot(p, 'end-3-panorama-fireworks');
  ok('True ending → final stats screen', await wait(p, () => window.__SIMPS.trueEnd?.menuOn, null, 12000));
  await shot(p, 'end-4-stats');
  const s = await p.evaluate(() => JSON.parse(localStorage.getItem('simps-goose-save-v2')));
  ok('Achievements saved (Friend of Ogopogo, Golden Goose)', s.achievements.includes('friend_of_ogopogo') && s.achievements.includes('golden_goose'), s.achievements.join(','));
  ok('Golden Goose Token collected', s.collected.includes('final:token:0'));
  await p.close();
}
// ============================================================ SAVE / MENUS / JOURNAL / A11Y
{
  const p = await page('/');
  await wait(p, () => window.__SIMPS.scene === 'Title'); await p.waitForTimeout(500);
  await key(p, 'Enter', 1, 400);
  const labels = await p.evaluate(() => window.__SIMPS.game.scene.getScene('Title').items.map((i) => i.label()));
  ok('Title shows CONTINUE after progress', labels[0] === 'CONTINUE', labels.join('|'));
  await key(p, 'ArrowDown', 2); await key(p, 'Enter', 1, 400);
  const lv = await p.evaluate(() => window.__SIMPS.game.scene.getScene('Title').panel?.list.filter((o) => o.type === 'BitmapText').map((t) => t.text).join('|'));
  ok('Level select lists Level 3 once revealed', lv.includes('OGOPOGO'), lv.slice(0, 120));
  await shot(p, 'menu-level-select');
  await key(p, 'Escape', 1, 300); await key(p, 'ArrowDown'); await key(p, 'Enter', 1, 500);
  ok('Journal opens from the title', await active(p, 'Journal'));
  await key(p, 'ArrowRight', 1, 200); await shot(p, 'menu-journal-recipes');
  await key(p, 'Escape', 1, 300);
  await p.close();
  const q = await page('/?scene=lab&skipintro=1');
  await wait(q, () => window.__SIMPS.level?.phase === 'play');
  await key(q, 'Escape', 1, 400);
  ok('Pause works in Level 2', await q.evaluate(() => window.__SIMPS.game.scene.isPaused('Lab')));
  await key(q, 'ArrowDown', 4); await key(q, 'Enter', 1, 200);
  ok('Pause menu toggles Reduce Flashing (saved)', await q.evaluate(() => JSON.parse(localStorage.getItem('simps-goose-v1')).reduceFlash === true));
  await shot(q, 'menu-pause-a11y');
  await key(q, 'Escape', 1, 400);
  ok('Resume works in Level 2', await q.evaluate(() => window.__SIMPS.game.scene.isActive('Lab')));
  await q.close();
}
// ============================================================ MOBILE TOUCH (Level 2)
{
  const m = await (await browser.newContext({ viewport: { width: 844, height: 390 }, hasTouch: true, isMobile: true })).newPage();
  m.on('pageerror', (e) => errs.push('mobile: ' + e.message));
  await m.goto(base + '/?scene=dimension&touch=1');
  await wait(m, () => window.__SIMPS.level?.phase === 'play', null, 9000);
  const cdp = await m.context().newCDPSession(m);
  const toPage = (gx, gy) => m.evaluate(([gx, gy]) => { const c = document.querySelector('canvas').getBoundingClientRect(); return { x: c.left + gx * c.width / 480, y: c.top + gy * c.height / 270 }; }, [gx, gy]);
  const R = await toPage(86, 236), J = await toPage(442, 232);
  const a0 = await lvl(m);
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ ...R, id: 0 }] }); await m.waitForTimeout(500);
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ ...R, id: 0 }, { ...J, id: 1 }] }); await m.waitForTimeout(150);
  const a1 = await lvl(m);
  await m.screenshot({ path: `${SHOTS}/mobile-dimension.png` });
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  ok('Mobile touch: move + jump in the Soda Dimension', a1.x > a0.x + 20 && a1.y < a0.y, `${JSON.stringify(a0)} → ${JSON.stringify(a1)}`);
  await m.close();
}
console.log('\n' + (errs.length ? 'ERRORS:\n' + [...new Set(errs)].slice(0, 20).join('\n') : 'no page errors'));
const pass = results.filter((r) => r.pass).length;
console.log(`\n${pass}/${results.length} full-game checks passed`);
fs.writeFileSync(`${SHOTS}/results.json`, JSON.stringify({ results, errors: [...new Set(errs)] }, null, 2));
await browser.close();
process.exit(pass === results.length && !errs.length ? 0 : 1);
