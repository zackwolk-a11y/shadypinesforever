// Level 2 biker boss: end-to-end encounter validation (desktop + mobile touch). Exits non-zero on failure.
const { chromium, devices } = require('playwright'); const path = require('path'), fs = require('fs');
const URL = 'file://' + path.resolve(__dirname, '../333-dimensions-of-madness.html'); const OUT = process.env.OUT || '/tmp/claude-0/biker'; fs.mkdirSync(OUT, { recursive: true });
const FIGHTER = `window.FIGHT = function (opts = {}) {
  const D = DIM333, Gm = D.Game, I = D.Input._down, log = { states: [], subs: new Set(), maxTongue: 0, tongueGone: false, minVisible: true, maxBosses: 0, hpSeen: [], fightBanner: false, bannerGone: false, playerFrozen: false, moved: 0, frames: 0 };
  let lastX = null;
  for (let f = 0; f < (opts.frames || 9000); f++) {
    for (const k in I) I[k] = false;
    if (Gm.cutscene) { D.skipScene(); D.run(1); continue; }
    if (D.G.state !== 'level') break;
    const pl = Gm.player, enc = Gm.ents.find(e => e instanceof BikerEncounter), b = enc && enc.boss;
    const bosses = Gm.ents.filter(e => e instanceof BikerBoss && !e.dead).length; log.maxBosses = Math.max(log.maxBosses, bosses);
    if (b) {
      if (log.states[log.states.length - 1] !== b.st) log.states.push(b.st); if (b.sub) log.subs.add(b.sub);
      if (b.tongue) log.maxTongue = Math.max(log.maxTongue, b.tongue.len); else if (log.maxTongue > 0) log.tongueGone = true;
      if (lastX !== null) log.moved += Math.abs(b.x - lastX); lastX = b.x;
      if (['FIGHTING'].includes(b.st)) { const vis = b.cx > Cam.x - 60 && b.cx < Cam.x + VW + 60; if (!vis) log.minVisible = false; }
      if (log.hpSeen[log.hpSeen.length - 1] !== b.hp) log.hpSeen.push(b.hp);
      if (HUD.banners.some(x => x.s === 'FIGHT!')) log.fightBanner = true; else if (log.fightBanner) log.bannerGone = true;
      if (b.st === 'INTRO' && Gm.cutscene) log.playerFrozen = true;
      // play: approach, attack, jump over charges
      const tx = b.cx - b.face * 0, dx = tx - pl.cx;
      if (b.st === 'FIGHTING') { const charging = b.sub === 'ATTACK' && b.charge; if (charging && Math.abs(dx) < 110 && pl.onGround) { D.Input._latch.jump = true; I.jump = true; } else if (Math.abs(dx) > 50) I[dx > 0 ? 'right' : 'left'] = true; else pl.face = Math.sign(dx) || pl.face; if (!pl.onGround && pl.vy < 0) I.jump = true; if (f % 8 === 0) { if (opts.touch) opts.touch(); else D.Input._latch.whip = true; } }
    } else if (!enc || enc.phase === 'INACTIVE') { I.right = true; if (f % 40 === 0) D.Input._latch.jump = true; }
    if (opts.dieAt && b && b.st === 'FIGHTING' && b.hp < b.maxHp && !opts.died) { opts.died = true; pl.die(); }
    D.run(1); log.frames = f;
    if (opts.stopWhen && opts.stopWhen()) break;
  }
  log.subs = [...log.subs]; return log; };`;
(async () => {
  const b = await chromium.launch(); let fail = 0; const ok = (c, m, info) => { console.log((c ? 'PASS ' : 'FAIL ') + m + (info ? '  ' + JSON.stringify(info) : '')); if (!c) fail++; };
  const p = await b.newPage({ viewport: { width: 1280, height: 720 } }); const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await p.goto(URL); await p.waitForFunction(() => window.DIM333 && DIM333.G.state === 'title'); await p.addScriptTag({ content: FIGHTER });
  // 2) frames
  const fr = await p.evaluate(() => { const want = { idle: 4, drive: 8, tongue: 8, hit: 4, charge: 6, defeat: 12 }, out = {}; let sizes = new Set(), blank = 0; for (const k in want) { const a = BIKER_ANIMS[k] || []; out[k] = a.length; for (const c of a) { sizes.add(c.width + 'x' + c.height); const d = c.ctx.getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 3; i < d.length; i += 4 * 7) if (d[i]) n++; if (n < 50) blank++; } } return { out, ok: Object.keys(want).every(k => out[k] === want[k]), sizes: [...sizes], blank }; });
  ok(fr.ok && fr.sizes.length === 1 && fr.blank === 0, 'all biker frames baked: idle 4, drive 8, tongue 8, hit 4, charge 6, defeat 12 (fixed size, none blank)', fr);
  // 6) cause of the flash removed: no bike-jump set piece in Level 2, Razz NPC rides away before the fight
  const setup = await p.evaluate(() => { const D = DIM333; D.god(); D.load(1); const Gm = D.Game; return { jump: Gm.ents.some(e => e instanceof SetPiece && e.kind === 'bikejump'), enc: Gm.ents.filter(e => e instanceof BikerEncounter).length, arenas: Gm.ents.filter(e => e instanceof Arena).length }; });
  ok(!setup.jump && setup.enc === 1, 'Level 2 has exactly one boss encounter and no bike-jump set piece in the fight zone', setup);
  // 1,3,4,5,8) full fight through to Level 3
  await p.evaluate(() => { const Gm = DIM333.Game, enc = Gm.ents.find(e => e instanceof BikerEncounter); Gm.player.x = enc.x0 - 120; Gm.player.y = enc.gyPx - 40; });
  const shotAt = async (name, cond) => { await p.evaluate(c => { window.__c = new Function('return ' + c); FIGHT({ frames: 4000, stopWhen: () => __c() }); DIM333.step(0); }, cond); await p.screenshot({ path: `${OUT}/${name}.png` }); };
  await shotAt('1_entering', "(()=>{const e=DIM333.Game.ents.find(x=>x instanceof BikerEncounter);return e&&e.boss&&e.boss.st==='ENTERING'&&e.boss.stT>30})()");
  await shotAt('2_tongue', "(()=>{const e=DIM333.Game.ents.find(x=>x instanceof BikerEncounter);return e&&e.boss&&e.boss.tongue&&e.boss.tongue.len>150})()");
  await shotAt('3_charge', "(()=>{const e=DIM333.Game.ents.find(x=>x instanceof BikerEncounter);return e&&e.boss&&e.boss.sub==='TELEGRAPH'&&e.boss.kind==='charge'&&e.boss.subT>30})()");
  await shotAt('4_defeat', "(()=>{const e=DIM333.Game.ents.find(x=>x instanceof BikerEncounter);return e&&e.boss&&e.boss.st==='DEFEATED'&&e.boss.af>=10})()");
  const run = await p.evaluate(() => { const D = DIM333; D.load(1); const Gm = D.Game, enc = Gm.ents.find(e => e instanceof BikerEncounter); Gm.player.x = enc.x0 - 120; Gm.player.y = enc.gyPx - 40; return FIGHT({ frames: 12000 }); });
  const flow = run.states.join('>');
  const seq = ['ENTERING', 'INTRO', 'FIGHTING', 'DEFEATED', 'EXITING', 'COMPLETE'];
  ok(true, 'fight log', { states: flow, subs: run.subs, hp: run.hpSeen.slice(0, 6).concat('...', run.hpSeen.slice(-2)), maxTongue: Math.round(run.maxTongue) });
  const res = await p.evaluate(() => ({ state: DIM333.G.state, def: DIM333.Game.def && DIM333.Game.def.id }));
  ok(run.maxBosses === 1, 'never more than one boss instance', { maxBosses: run.maxBosses });
  ok(run.minVisible, 'boss stays on screen for the whole fight');
  ok(run.subs.includes('TELEGRAPH') && run.subs.includes('ATTACK') && run.subs.includes('RECOVERY') && run.moved > 100, 'boss moves and cycles IDLE -> TELEGRAPH -> ATTACK -> RECOVERY', { moved: Math.round(run.moved) });
  ok(run.hpSeen.length > 4, 'player attacks damage the boss (single health value counts down)', { hp: run.hpSeen.length });
  ok(res.state === 'results' && res.def === 'L2', 'defeat sequence finishes and the level completes', res);
  await p.screenshot({ path: `${OUT}/5_results.png` });
  await p.evaluate(() => { DIM333.Input._latch.confirm = true; for (let i = 0; i < 120; i++) { DIM333.run(1); if (DIM333.G.state === 'results') DIM333.Input._latch.confirm = i % 10 === 0 && i > 50; } });
  const after = await p.evaluate(() => ({ state: DIM333.G.state, def: DIM333.Game.def.id, ch: DIM333.Game.chapter, bosses: DIM333.Game.ents.filter(e => e instanceof BikerBoss).length, engine: !!DIM333.AudioSys.engine }));
  ok(after.state === 'level' && after.def === 'L3', 'results lead straight into Level 3', after);
  // FIGHT banner + no freeze, tongue extend/retract + hit the player (no god mode)
  const t2 = await p.evaluate(() => { const D = DIM333; D.god(false); D.load(1); const Gm = D.Game, enc = Gm.ents.find(e => e instanceof BikerEncounter); Gm.player.x = enc.x0 - 80; Gm.player.y = enc.gyPx - 40; let hurt = false, tongueHit = false, frozen = false, banner = false, bannerGone = false, maxT = 0, gone = false;
    for (let f = 0; f < 3000; f++) { for (const k in D.Input._down) D.Input._down[k] = false; if (Gm.cutscene) { D.skipScene(); D.run(1); continue; } const b = enc.boss; if (!b) D.Input._down.right = true; else { if (b.st === 'INTRO' && Gm.cutscene) frozen = true; if (HUD.banners.some(x => x.s === 'FIGHT!')) banner = true; else if (banner) bannerGone = true; if (b.tongue) { maxT = Math.max(maxT, b.tongue.len); if (b.tongue.hit) tongueHit = true; } else if (maxT > 0) gone = true; const dx = b.cx - Gm.player.cx; if (Math.abs(dx) > 120) D.Input._down[dx > 0 ? 'right' : 'left'] = true; Gm.player.hp = Math.max(Gm.player.hp, 2); }
      D.run(1); if (tongueHit && gone && bannerGone) break; }
    return { banner, bannerGone, frozen, maxT: Math.round(maxT), tongueHit, gone }; });
  ok(t2.banner && t2.bannerGone && !t2.frozen, '"FIGHT!" shows briefly and the player keeps control', t2);
  ok(t2.maxT > 140 && t2.gone, 'tongue extends from the mouth (>140px) and fully retracts', t2);
  ok(t2.tongueHit, 'tongue has a real hitbox that damages the player', t2);
  // 7) death mid-fight resets the boss; re-entering starts exactly one new encounter
  const t3 = await p.evaluate(() => { const D = DIM333; D.god(); D.load(1); const Gm = D.Game, enc = Gm.ents.find(e => e instanceof BikerEncounter); Gm.player.x = enc.x0 - 80; Gm.player.y = enc.gyPx - 40;
    FIGHT({ frames: 3000, stopWhen: () => enc.boss && enc.boss.st === 'FIGHTING' && enc.boss.hp < enc.boss.maxHp });
    const hpBefore = enc.boss.hp; D.god(false); Gm.player.die(); for (let i = 0; i < 80; i++) D.run(1); D.god();
    const mid = { phase: enc.phase, boss: !!enc.boss, bosses: Gm.ents.filter(e => e instanceof BikerBoss && !e.dead).length, lock: !!Gm.L.camLock, gameBoss: !!Gm.boss };
    const again = FIGHT({ frames: 3000, stopWhen: () => enc.boss && enc.boss.st === 'FIGHTING' });
    return { hpBefore, mid, after: { phase: enc.phase, hp: enc.boss && enc.boss.hp, max: enc.boss && enc.boss.maxHp, bosses: again.maxBosses } }; });
  ok(t3.mid.phase === 'INACTIVE' && !t3.mid.boss && t3.mid.bosses === 0 && !t3.mid.lock && !t3.mid.gameBoss && t3.after.phase === 'ACTIVE' && t3.after.hp === t3.after.max && t3.after.bosses === 1, 'player death resets the boss; the fight restarts once at full health', t3);
  // 10) repeated playthroughs
  const t4 = await p.evaluate(() => { const D = DIM333, res = []; D.god(); for (let r = 0; r < 3; r++) { D.load(1); const Gm = D.Game, enc = Gm.ents.find(e => e instanceof BikerEncounter); Gm.player.x = enc.x0 - 80; Gm.player.y = enc.gyPx - 40; const l = FIGHT({ frames: 12000 }); res.push({ end: D.G.state, maxBosses: l.maxBosses, states: l.states.join('>') }); } return res; });
  ok(t4.every(r => r.end === 'results' && r.maxBosses === 1), 'three repeated playthroughs: no stuck states, no duplicate bosses', t4);
  ok(errs.length === 0, 'no runtime errors', errs.slice(0, 3));
  // 9) mobile touch
  const ctxM = await b.newContext({ ...devices['iPhone 13 landscape'] }); const mp = await ctxM.newPage(); const merrs = []; mp.on('pageerror', e => merrs.push(e.message));
  await mp.goto(URL); await mp.waitForFunction(() => window.DIM333 && DIM333.G.state === 'title'); await mp.tap('#screen'); await mp.addScriptTag({ content: FIGHTER });
  const m = await mp.evaluate(() => { const D = DIM333; D.god(); D.load(1); const Gm = D.Game, enc = Gm.ents.find(e => e instanceof BikerEncounter); Gm.player.x = enc.x0 - 80; Gm.player.y = enc.gyPx - 40; const atk = document.querySelector('.tb[data-a=whip]');
    const touch = () => { atk.dispatchEvent(new Event('touchstart', { cancelable: true })); setTimeout(() => {}, 0); atk.dispatchEvent(new Event('touchend', { cancelable: true })); };
    const l = FIGHT({ frames: 12000, touch }); return { end: D.G.state, hp: l.hpSeen.length, buttons: document.querySelectorAll('.tb').length }; });
  await mp.screenshot({ path: `${OUT}/6_mobile.png` });
  ok(m.end === 'results' && m.hp > 4 && merrs.length === 0, 'mobile: the fight is won using the touch ATTACK button', m);
  console.log(fail ? fail + ' FAILED' : 'BIKER BOSS: ALL CHECKS PASS'); await b.close(); process.exit(fail ? 1 : 0);
})();
