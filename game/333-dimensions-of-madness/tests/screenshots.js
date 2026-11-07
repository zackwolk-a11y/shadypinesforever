// Captures real gameplay screenshots of every character group (and the sprite inspector) into
// screenshots/*.jpg. Bosses are fought with the same MOVE/JUMP/ATTACK driver as tests/bosses.js.
const { chromium } = require('playwright'); const path = require('path'), fs = require('fs');
const OUT = path.resolve(__dirname, '../screenshots');
(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 640, height: 360 }, deviceScaleFactor: 2 }); const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('file://' + path.resolve(__dirname, '../333-dimensions-of-madness.html'));
  await p.waitForFunction(() => window.DIM333 && DIM333.G.state === 'title');
  await p.evaluate(() => { const D = DIM333, Gm = D.Game, I = D.Input._down;
    window.__fight = (frames, stopWhen) => { for (let f = 0; f < frames; f++) { for (const k in I) I[k] = false; if (Gm.cutscene) { D.skipScene(); D.run(1); continue; }
      const B = Gm.boss, pl = Gm.player; let tx = pl.cx + 200; if (B) { const hb = B.hitbox(); tx = hb.x + hb.w / 2; }
      const dx = tx - pl.cx; if (Math.abs(dx) > 60) I[dx > 0 ? 'right' : 'left'] = true; else pl.face = Math.sign(dx) || pl.face;
      if (f % 50 === 0) D.Input._latch.jump = true; if (f % 50 < 16) I.jump = true; if (f % 11 === 0) D.Input._latch.whip = true; D.run(1); if (stopWhen && stopWhen()) return f; } return frames; };
    window.__gate = (lv, ch) => { D.god(); D.load(lv, ch); for (let i = 0; i < 400 && Gm.cutscene; i++) { D.skipScene(); D.run(1); } const g = Gm.ents.find(e => e.constructor.name === 'BossGate'); if (g) { Gm.player.x = g.x + 60; Gm.player.y = g.o.gy * 16 - 40; } };
  });
  const shot = async (name) => { await p.evaluate(() => DIM333.Game.draw && 0); await p.waitForTimeout(80); await p.screenshot({ path: path.join(OUT, name + '.jpg'), type: 'jpeg', quality: 86 }); console.log('saved', name); };
  // 1. Moshmouth: tutorial, tongue strike
  await p.evaluate(() => { const D = DIM333, Gm = D.Game; D.load(0); for (let i = 0; i < 300 && Gm.cutscene; i++) { D.skipScene(); D.run(1); } const pl = Gm.player; for (let i = 0; i < 160; i++) { D.Input._down.right = true; D.run(1); } D.Input._down.right = false; const e = new Enemy({ kind: 'soldier', x: pl.cx + 58, y: pl.y + pl.h - 32 }); e.wake = true; e.cool = 999; Gm.add(e); D.run(2); D.Input._latch.whip = true; D.run(19); });
  await shot('01_moshmouth_tongue_attack');
  // 2. Shitman crashes through the wall in the tutorial chase
  await p.evaluate(() => { const D = DIM333, Gm = D.Game, I = D.Input._down; for (let f = 0; f < 4000; f++) { for (const k in I) I[k] = false; if (Gm.cutscene) { D.skipScene(); D.run(1); continue; } I.right = true; if (f % 40 === 0) D.Input._latch.jump = true; if (f % 40 < 14) I.jump = true; D.run(1); if (Gm.ents.some(e => e.constructor.name === 'GiantChaser' && !e.dead && e.x > Cam.x - 120)) break; } for (let f = 0; f < 50; f++) { for (const k in I) I[k] = false; I.right = true; D.run(1); } });
  await shot('02_shitman_tutorial_chase');
  // 3. Electric Harley House (of Love): Level 2 boss - intro card, then mid-fight
  await p.evaluate(() => { const D = DIM333, Gm = D.Game; D.god(); D.load(1); for (let i = 0; i < 300 && Gm.cutscene; i++) { D.skipScene(); D.run(1); } const enc = Gm.ents.find(e => e.constructor.name === 'BikerEncounter'); Gm.player.x = enc.x0 + 40; Gm.player.y = enc.gyPx - 40; window.__fight(900, () => HUD.bossIntro > 40 && Gm.boss); });
  await shot('03_electric_harley_intro');
  await p.evaluate(() => window.__fight(700, () => { const B = DIM333.Game.boss; return B && B.sub === 'ATTACK' && B.tongue && B.tongue.tip; }));
  await shot('04_electric_harley_tongue_attack');
  await p.evaluate(() => window.__fight(4000, () => { const B = DIM333.Game.boss; return B && B.st === 'DEFEATED' && B.stT > 50; }));
  await shot('05_electric_harley_crash');
  // 4. Level 333: the Three Little Pigs building the straw house
  await p.evaluate(() => { const D = DIM333, Gm = D.Game; D.god(); D.load(2, 2); for (let i = 0; i < 400 && Gm.cutscene; i++) { D.skipScene(); D.run(1); } const I = D.Input._down; for (let f = 0; f < 1500; f++) { for (const k in I) I[k] = false; if (Gm.cutscene) { D.skipScene(); D.run(1); continue; } I.right = f % 120 < 90; if (f % 45 === 0) D.Input._latch.jump = true; D.run(1); if (f > 200 && Gm.followers.length >= 3 && Gm.followers.every(x => Math.abs(x.cx - Gm.player.cx) < 160)) break; } });
  await shot('06_three_little_pigs_level333');
  // 5. Big Bad Wolf boss (Level 333 finale)
  await p.evaluate(() => { window.__gate(2, 5); window.__fight(420); });
  await shot('07_big_bad_wolf_boss');
  // 6. Cowgod (hypnotised boss, Level 8)
  await p.evaluate(() => { window.__gate(7, 0); window.__fight(1500, () => { const B = DIM333.Game.boss; if (!B || B.t < 150) return false; const hb = B.hitbox(); return hb.x > Cam.x + 20 && hb.x + hb.w < Cam.x + VW - 20 && hb.y > Cam.y && hb.y + hb.h < Cam.y + VH; }); });
  await shot('08_cowgod_boss');
  // 7. Shitman core (King of the Garbage Heap, phase 2)
  await p.evaluate(() => { window.__gate(24, 0); window.__fight(9000, () => { const B = DIM333.Game.boss; return B && B.phase >= 2 && B.st > 120; }); });
  await shot('09_shitman_garbage_heap');
  // 8. developer sprite inspector
  await p.evaluate(() => { Inspector.open(); Inspector.ci = Inspector.ids.indexOf('harley'); Inspector.ai = 4; Inspector.f = 2; Inspector.playing = false; });
  await shot('10_sprite_inspector_harley');
  await p.evaluate(() => { Inspector.ci = Inspector.ids.indexOf('pig_trufflina'); Inspector.ai = 6; Inspector.f = 1; Inspector.bg = 1; });
  await shot('11_sprite_inspector_pigs_dark');
  await p.evaluate(() => Inspector.close());
  console.log('errors', JSON.stringify(errs)); await b.close();
})();
