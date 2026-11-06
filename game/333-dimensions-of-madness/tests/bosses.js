// Boss check: every boss can be defeated using only MOVE / JUMP / ATTACK (god mode, no damage cheats).
const { chromium } = require('playwright'); const path = require('path');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage(); const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('file://' + path.resolve(__dirname, '../333-dimensions-of-madness.html'));
  await p.waitForFunction(() => window.DIM333 && DIM333.G.state === 'title');
  const list = [[2, 5, 'Barnaby v1'], [4, 0, 'Puppet King'], [7, 0, 'Udderly'], [9, 0, 'Overlord'], [10, 0, 'Barnaby v2'], [14, 0, 'Devourer'], [19, 0, 'Colossus'], [24, 0, 'Garbage Heap'], [27, 0, 'Barnaby v3'], [29, 0, 'Eternal Feedback']];
  let fail = 0;
  const only = process.argv[2]; for (const [lv, ch, name] of list) { if (only && !name.includes(only)) continue;
    const r = await p.evaluate(([lv, ch]) => { const D = DIM333, Gm = D.Game, I = D.Input._down; D.god(); D.load(lv, ch);
      for (let i = 0; i < 400 && Gm.cutscene; i++) { D.skipScene(); D.run(1); }
      const gate = Gm.ents.find(e => e.constructor.name === 'BossGate'); Gm.player.x = gate.x + 60; Gm.player.y = gate.o.gy * 16 - 40;
      let f = 0, spawned = false;
      for (; f < 20000; f++) {
        for (const k in I) I[k] = false; if (Gm.cutscene) { D.skipScene(); D.run(1); continue; }
        const B = Gm.boss; if (B) spawned = true; if (spawned && (!B || B.defeated)) break;
        const pl = Gm.player; let tx = pl.cx;
        if (B) { const hb = B.hitbox(); tx = hb.x + hb.w / 2; if (B.hands && B.phase === 1) { const h = B.hands.find(h => h.hp > 0 && h.st === 'down') || B.hands.find(h => h.hp > 0); if (h) tx = B.cx0 + h.x; } if (B.blobs) { const bl = B.blobs.find(x => x.hp > 0); if (bl) tx = bl.x; } }
        const dx = tx - pl.cx; if (Math.abs(dx) > 34) I[dx > 0 ? 'right' : 'left'] = true; else pl.face = Math.sign(dx) || pl.face;
        if (f % 50 === 0) D.Input._latch.jump = true; if (f % 50 < 16) I.jump = true;
        if (f % 9 === 0) D.Input._latch.whip = true;
        D.run(1);
      }
      return { f, defeated: spawned && (!Gm.boss || Gm.boss.defeated), spawned }; }, [lv, ch]);
    if (!r.defeated) fail++; console.log((r.defeated ? 'PASS ' : 'FAIL ') + name.padEnd(18) + (r.defeated ? ' defeated in ' + (r.f / 60).toFixed(0) + 's of fighting' : JSON.stringify(r)));
  }
  console.log('errors', errs.slice(0, 5)); console.log(fail ? fail + ' FAILED' : 'ALL BOSSES BEATABLE'); await b.close(); process.exit(fail ? 1 : 0);
})();
