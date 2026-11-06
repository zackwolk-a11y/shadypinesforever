// Renders every menu / meta screen to PNG for visual QA (title menu, map, encyclopedia, jukebox,
// achievements, options, transformations, pause, results, concert, ending, cutscene dialogue).
const { chromium } = require('playwright'); const path = require('path'), fs = require('fs');
const OUT = process.env.OUT || '/tmp/claude-0/ui'; fs.mkdirSync(OUT, { recursive: true });
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1280, height: 720 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('file://' + path.resolve(__dirname, '../333-dimensions-of-madness.html'));
  await p.waitForFunction(() => window.DIM333 && DIM333.G.state === 'title');
  await p.evaluate(() => { window.adv = n => { for (let i = 0; i < n; i++) { if (DIM333.Game.cutscene && DIM333.G.state === 'level' && !window.keepScene) DIM333.skipScene(); DIM333.run(1); } DIM333.step(0); }; });
  const shot = async (name, fn, frames = 30) => { await p.evaluate(fn); await p.evaluate(n => adv(n), frames); await p.screenshot({ path: `${OUT}/${name}.png` }); };
  await shot('title_menu', () => { DIM333.Title.pressed = true; DIM333.Save.data.unlocked = 9; });
  await shot('worldmap', () => { DIM333.unlockAll(); const S = DIM333.Save.data; S.unlocked = 14; for (let i = 1; i <= 13; i++) S.done['L' + i] = { clear: true, shards: [1, i % 2, 0], notes: 40 + i }; DIM333.WorldMap.open(4); });
  await shot('encyclopedia', () => { DIM333.Menus.stack = []; DIM333.Menus.open('ency'); });
  await shot('encyclopedia_entry', () => { const m = DIM333.Menus.top; m.sel = 4; m.detail = true; });
  await shot('jukebox', () => { DIM333.Menus.stack = []; DIM333.Menus.open('jukebox'); });
  await shot('achievements', () => { DIM333.Menus.stack = []; DIM333.Save.data.ach.firstScream = 1; DIM333.Save.data.ach.pigs = 1; DIM333.Menus.open('ach'); });
  await shot('options', () => { DIM333.Menus.stack = []; DIM333.Menus.open('options'); });
  await shot('forms', () => { DIM333.Menus.stack = []; DIM333.Menus.open('forms'); });
  await shot('controls', () => { DIM333.Menus.stack = []; DIM333.Menus.open('controls'); });
  await shot('cutscene_dialogue', () => { window.keepScene = true; DIM333.Menus.stack = []; DIM333.load(2, 0); }, 260);
  await p.evaluate(() => { window.keepScene = false; });
  await shot('pause', () => { DIM333.Game.cutscene = null; DIM333.Menus.open('pause'); });
  await shot('transform_menu', () => { DIM333.Menus.stack = []; DIM333.Game.openTransform(); }, 5);
  await shot('boss_wolf', () => { DIM333.Game.transformMenu = null; DIM333.load(2, 5); DIM333.skipScene(); const G = DIM333.Game; G.player.x = G.ents.find(e => e.constructor.name === 'BossGate').x + 80; }, 200);
  await shot('boss_overlord', () => { DIM333.load(9); DIM333.skipScene(); const G = DIM333.Game; G.player.x = G.ents.find(e => e.constructor.name === 'BossGate').x + 80; }, 260);
  await shot('boss_heap', () => { DIM333.load(24); DIM333.skipScene(); const G = DIM333.Game; G.player.x = G.ents.find(e => e.constructor.name === 'BossGate').x + 80; }, 260);
  await shot('boss_heap_gloop', () => { const B = DIM333.Game.boss; B.hit(30, {}); B.inv = 0; }, 90);
  await shot('boss_feedback', () => { DIM333.load(29); DIM333.skipScene(); const G = DIM333.Game; G.player.x = G.ents.find(e => e.constructor.name === 'BossGate').x + 80; }, 260);
  await shot('boss_feedback_allies', () => { const B = DIM333.Game.boss; B.hp = B.maxHp * .35; B.phase = 3; B.allyT = 59; DIM333.god(); }, 50);
  await shot('concert', () => { DIM333.Concert.start('pigs'); }, 400);
  await shot('concert_final', () => { DIM333.Concert.start('L30', true); }, 400);
  await shot('ending', () => { DIM333.G.state = 'ending'; window.Ending && 0; }, 1);
  await p.evaluate(() => { const E = eval('Ending'); E.start(); }); await p.evaluate(() => DIM333.step(500)); await p.screenshot({ path: `${OUT}/ending.png` });
  await shot('results', () => { const G = DIM333.Game; DIM333.load(0); G.levelStats.notes = 87; G.levelStats.kills = 31; G.levelStats.shards = [true, false, true]; eval('Results').show(G.def, G.levelStats, () => { }); }, 90);
  console.log('errors:', errs); await b.close();
})();
