// Autoplay bot: tries to reach the exit of every level/chapter (god-mode, no shortcuts/teleports).
// Reports progress, completion and time. Usage: node tests/autoplay.js [levelNumbers,comma]
const { chromium } = require('playwright'); const path = require('path'), fs = require('fs');
const OUT = '/tmp/claude-0/auto'; fs.mkdirSync(OUT, { recursive: true });
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1280, height: 720 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('file://' + path.resolve(__dirname, '../333-dimensions-of-madness.html'));
  await p.waitForFunction(() => window.DIM333 && DIM333.G.state === 'title', null, { timeout: 15000 });
  await p.evaluate(() => {
    window.BOT = function (maxFrames) {
      const D = DIM333, Gm = D.Game, I = D.Input._down; let stuck = 0, bestX = 0, f = 0, mode = 0, modeT = 0, startDef = Gm.def.id, startCh = Gm.chapter, maxX = 0;
      const solid = (tx, ty) => Gm.L.solidAt(tx, ty) || Gm.L.onewayAt(tx, ty);
      for (f = 0; f < maxFrames; f++) {
        if (D.G.state === 'results' || D.G.state === 'map' || D.G.state === 'ending') return { done: true, f, why: D.G.state };
        if (D.G.state === 'concert') { const c = D.Concert; for (const k in I) I[k] = false; if (c.done) { I.confirm = f % 10 < 5; } else { const pos = c.pos(); for (const n of c.notes) if (!n.hit && !n.miss && Math.abs(n.b - pos) < .05) I[['jump', 'whip', 'spit', 'bash'][n.lane]] = true; } D.run(1); for (const k in I) I[k] = false; continue; }
        if (Gm.def.id !== startDef || Gm.chapter !== startCh) return { done: true, f, why: 'nextChapter' };
        if (D.Menus.stack.length) { D.Menus.stack = []; }
        for (const k in I) I[k] = false;
        if (Gm.cutscene) { if (f % 2) I.confirm = true; D.skipScene(); D.run(1); continue; }
        if (D.G.state !== 'level') { I.confirm = f % 10 < 5; D.run(1); continue; }
        const pl = Gm.player, L = Gm.L, tx = Math.floor((pl.x + pl.w + 4) / 16), fy = Math.floor((pl.y + pl.h - 1) / 16), cx = pl.x + pl.w / 2;
        if (pl.vehicle) { I.right = true; const ahead = Math.floor((pl.x + pl.w + 30) / 16); let gapA = true; for (let ty = fy + 1; ty < L.h; ty++) if (solid(ahead, ty)) gapA = false; if (gapA || solid(ahead, fy) || solid(ahead, fy - 1)) I.jump = true; if (f % 20 === 0) I.whip = true; I.dash = true; D.run(1); maxX = Math.max(maxX, pl.x); continue; }
        // quest helpers: go toward uncollected quest items / bricks / blueprints when on screen
        let goal = null;
        const quest = Gm.ents.filter(e => !e.dead && ((e.constructor.name === 'Collectable') || (e.constructor.name === 'BrickItem' && !pl.carry) || (e.constructor.name === 'BrickSlot' && pl.carry && !e.filled) || (e.constructor.name === 'Blueprint' && !e.built)));
        if (quest.length) { quest.sort((a, b2) => Math.abs(a.cx - cx) - Math.abs(b2.cx - cx)); const q = quest[0]; if (Math.abs(q.cx - cx) < 400) goal = q; }
        // boss: fight
        const boss = Gm.boss && !Gm.boss.defeated ? Gm.boss : null; const enemy = Gm.ents.find(e => e.constructor.name === 'Enemy' && !e.dead && e.wake && Math.abs(e.cx - cx) < 90 && Math.abs(e.cy - pl.cy) < 60);
        const arena = Gm.ents.find(e => e.constructor.name === 'Arena' && e.active); if (arena && !boss) { const tg = arena.spawned.find(e => !e.dead); if (tg) goal = { cx: tg.cx, cy: tg.cy, x: tg.x, w: tg.w, constructor: { name: 'Target' } }; I.whip = f % 8 === 0; I.bash = f % 40 === 0; I.spit = f % 14 === 0; if (tg && tg.cy < pl.y) { I.up = f % 16 < 8; } }
        const sw = Gm.ents.find(e => (e.constructor.name === 'Switch' || e.constructor.name === 'SoundSwitch') && !e.on && Math.abs(e.cx - cx) < 140);
        if (sw && !boss) { if (sw.constructor.name === 'SoundSwitch') { goal = sw; I.scream = f % 80 < 50; } else { goal = sw; if (Math.abs(sw.cx - cx) < 50) { I.up = true; I.whip = f % 10 === 0; I.spit = f % 20 === 5; pl.face = sign(sw.cx - cx) || 1; } } }
        const totem = Gm.ents.find(e => e.constructor.name === 'AmpTotem' && !e.dead && e.cx > cx && e.cx - cx < 140); if (totem && !boss) { I.headbang = f % 30 === 0; if (pl.metal < 100) { pl.metal = Math.min(100, pl.metal + .5); } I.scream = f % 90 < 70; }
        let dir = 1;
        if (boss) { const hb = boss.hitbox(); const bx = hb.x + hb.w / 2; dir = bx > cx + 30 ? 1 : bx < cx - 30 ? -1 : (f % 120 < 60 ? 1 : -1); pl.face = sign(bx - cx) || 1; I.whip = f % 8 === 0; I.bash = f % 30 === 0; I.spit = f % 12 === 4; I.jump = f % 50 < 18; I.headbang = f % 23 === 0; if (pl.metal >= 50 && D.Save.data.summons.length) I.summon = f % 200 === 0; I.scream = f % 120 > 70; if (pl.metal >= 100) I.scream = f % 140 > 70; }
        else if (goal) { dir = goal.cx > cx + 4 ? 1 : goal.cx < cx - 4 ? -1 : 0; if (goal.constructor.name === 'Blueprint') { if (pl.char !== 'porkington' && Gm.party && Gm.party.includes('porkington') && f % 30 === 0) I.transform = true; else if (pl.char === 'porkington' && cx > goal.x && cx < goal.x + goal.w) { I.whip = f % 6 === 0; dir = 0; } dir = goal.cx > cx + 4 ? 1 : 0; if (cx > goal.x + 4 && cx < goal.x + goal.w) dir = 0; }
          if (goal.constructor.name === 'BrickSlot' && Math.abs(goal.cx - cx) < 30) { I.whip = f % 6 === 0; dir = 0; if (pl.char === 'monster') dir = sign(goal.cx - cx); }
          if (goal.cy < pl.y - 20 && pl.onGround && Math.abs(goal.cx - cx) < 80) I.jump = true; }
        if (!boss && !goal) dir = 1;
        if (goal && goal.constructor.name === 'Target') { dir = goal.cx > cx + 20 ? 1 : goal.cx < cx - 20 ? -1 : 0; pl.face = sign(goal.cx - cx) || 1; if (goal.cy < pl.y - 10 && pl.onGround) I.jump = true; }
        if (enemy && !boss) { pl.face = sign(enemy.cx - cx) || 1; I.whip = f % 8 === 0; }
        if (dir > 0) I.right = true; else if (dir < 0) I.left = true;
        const fx = dir >= 0 ? Math.floor((pl.x + pl.w + 6) / 16) : Math.floor((pl.x - 6) / 16);
        // wall ahead
        let wallH = 0; for (let k = 0; k < 8; k++) if (Gm.L.solidAt(fx, fy - k)) wallH = k + 1; else break;
        if (wallH > 0 && dir !== 0) { if (L.get(fx, fy) === 3 || L.get(fx, fy - 1) === 3) { I.dash = f % 20 === 0; I.whip = true; } else I.jump = true; }
        // gap ahead
        const gx = dir >= 0 ? Math.floor((pl.x + pl.w + 10) / 16) : Math.floor((pl.x - 10) / 16); let gap = true; for (let ty = fy + 1; ty < Math.min(L.h, fy + 5); ty++) if (solid(gx, ty)) gap = false;
        if (gap && pl.onGround && dir !== 0) I.jump = true;
        if (!pl.onGround && pl.vy < 1) I.jump = true;
        if (pl.char === 'hamwise' && !pl.onGround) I.jump = true;
        // grapple
        const hook = Gm.nearestHook(pl); if (!pl.grapple && hook && !pl.onGround && hook.x > cx - 20 && pl.vy > -2) I.grapple = true;
        if (pl.grapple) { I.right = true; I.up = f % 3 === 0; if (pl.cx > pl.grapple.h.x + 30 && pl.vx > 0) I.jump = true; }
        if (pl.dashT === 0 && gap && !pl.onGround && pl.vy > 0 && pl.airDash) I.dash = true;
        // stuck recovery
        if (pl.x > bestX + 4) { bestX = pl.x; stuck = 0; } else stuck++;
        if (stuck > 240 && !boss && !goal) { mode = (mode + 1) % 4; modeT = 60; stuck = 120; }
        if (modeT > 0) { modeT--; if (mode === 1) { I.right = false; I.left = modeT > 30; I.jump = modeT < 30; } if (mode === 2) { I.jump = true; I.dash = modeT % 15 === 0; } if (mode === 3) { I.up = true; I.grapple = modeT % 10 === 0; I.jump = modeT % 20 < 10; } if (mode === 0) { I.down = true; I.jump = modeT % 20 < 4; } }
        if (Gm.party && Gm.party.length > 1 && stuck > 200 && f % 90 === 0 && !(goal && goal.constructor.name === 'Blueprint')) I.transform = true;
        if (goal && goal.constructor.name === 'BrickItem' && pl.char !== 'trufflina' && pl.char !== 'monster' && f % 40 === 0) I.transform = true;
        D.run(1); maxX = Math.max(maxX, pl.x);
      }
      return { done: false, state: D.G.state, f, maxX: Math.round(maxX), w: Gm.L.w * 16, x: Math.round(Gm.player.x), y: Math.round(Gm.player.y), boss: !!(Gm.boss && !Gm.boss.defeated), bossHp: Gm.boss ? Gm.boss.hp : null, quest: Gm.quest ? (Gm.flags[Gm.quest.flag] || 0) + '/' + Gm.quest.need : null };
    };
  });
  const only = process.argv[2] ? process.argv[2].split(',').map(Number) : null;
  const levels = await p.evaluate(() => DIM333.LEVELS.map(l => ({ id: l.id, ch: l.chapters ? l.chapters.length : 1 })));
  const summary = [];
  for (let i = 0; i < levels.length; i++) {
    if (only && !only.includes(i + 1)) continue;
    for (let ch = 0; ch < levels[i].ch; ch++) {
      const r = await p.evaluate(([i, ch]) => { DIM333.unlockAll(); DIM333.god(true); DIM333.load(i, ch); const r = BOT(30000); r.errors = DIM333.G.errors.splice(0); return r; }, [i, ch]);
      if (!r.done) await p.screenshot({ path: `${OUT}/stuck_L${i + 1}_c${ch}.png` });
      const line = `${levels[i].id} ch${ch} ${r.done ? 'DONE in ' + (r.f / 60).toFixed(0) + 's (' + r.why + ')' : 'STUCK ' + JSON.stringify(r)}${r.errors && r.errors.length ? ' ERR ' + r.errors[0].slice(0, 200) : ''}`;
      console.log(line); summary.push(line);
    }
  }
  console.log('PAGE ERRORS', errs.slice(0, 10)); fs.writeFileSync(OUT + '/summary.txt', summary.join('\n'));
  await b.close();
})();
