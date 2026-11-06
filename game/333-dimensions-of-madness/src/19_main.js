// ============================================================================
// Boot + main loop (fixed 60 Hz timestep, hit-stop, state machine)
// ============================================================================
G.hitstop = 0; G.fps = 60;
function update() {
  AudioSys.schedule();
  if (G.hitstop > 0) { G.hitstop--; return; } // input is not sampled during hit-stop, so presses carry over
  Input.update();
  switch (G.state) {
    case 'title': Title.update(); break;
    case 'map': WorldMap.update(); break;
    case 'level':
      if (Menus.update()) break;
      Game.update();
      if (Game.pendingWin && !Game.cutscene && --Game.bossWinTimer <= 0) { const w = Game.pendingWin; Game.pendingWin = null; Game.runScene(w.scene, {}, w.done); if (!STORY[w.scene]) w.done(); }
      break;
    case 'results': Results.update(); break;
    case 'concert': if (Concert.done) Concert.updateEnd(); else Concert.update(); break;
    case 'ending': Ending.update(); break;
  }
}
function draw() {
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
  switch (G.state) {
    case 'boot': ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H); text('LOADING DIMENSIONS...', W / 2, H / 2, { color: '#7fff3a', align: 'center' }); break;
    case 'title': Title.draw(); break;
    case 'map': WorldMap.draw(); break;
    case 'level': Game.draw(); Menus.draw(); break;
    case 'results': Results.draw(); break;
    case 'concert': Concert.draw(); break;
    case 'ending': Ending.draw(); break;
  }
}
let _acc = 0, _last = performance.now(), _fpsT = 0, _fpsN = 0;
function loop(now) {
  const dt = Math.min(100, now - _last); _last = now; _acc += dt; _fpsT += dt; _fpsN++;
  if (_fpsT > 1000) { G.fps = _fpsN; _fpsN = 0; _fpsT = 0; }
  let steps = 0;
  while (_acc >= 1000 / 60 && steps < 4) { try { update(); } catch (e) { reportError(e); } G.t += 1 / 60; G.frame++; _acc -= 1000 / 60; steps++; }
  if (steps === 4) _acc = 0;
  try { draw(); } catch (e) { reportError(e); }
  requestAnimationFrame(loop);
}
G.errors = [];
function reportError(e) { if (G.errors.length < 20) { G.errors.push(String(e && e.stack || e)); console.error(e); } }
window.addEventListener('error', e => reportError(e.error || e.message));
async function boot() {
  draw();
  AudioSys.init();
  await loadAssets();
  buildProceduralSprites(); buildIcons(); buildPigBodies(); bakeBikerFrames(); sliceTongueFrames();
  Save.load(); Touch.init(); applyTouchPref();
  if ('ontouchstart' in window && (Save.data.opt.touch || 'auto') === 'auto') Touch.enable();
  Title.open();
  requestAnimationFrame(loop);
}
// test / debug hooks (used by the automated test-suite)
window.DIM333 = {
  G, Game, LEVELS, Save, AudioSys, Input, Concert, Menus, WorldMap, Title,
  load(i, ch = 0) { Menus.stack = []; Game.loadLevel(LEVELS[i], ch); },
  skipScene() { if (Game.cutscene) Game.cutscene.skip = true; },
  run(n = 1) { for (let i = 0; i < n; i++) { update(); G.t += 1 / 60; G.frame++; } },
  step(n = 1) { for (let i = 0; i < n; i++) { update(); G.t += 1 / 60; G.frame++; } draw(); },
  press(a, held) { Input._down[a] = true; if (!held) setTimeout(() => Input._down[a] = false, 50); },
  release(a) { Input._down[a] = false; },
  god(on = true) { G.cheatGod = on; },
  unlockAll() { G.unlockAll = true; Save.data.unlocked = 30; Save.data.forms = ['normal', 'pig', 'wolf', 'cow', 'bear', 'clown', 'mega']; Save.data.summons = ['pigs', 'razz', 'udderly']; for (const k in ENCY) Save.data.seen[k] = 1; }
};
boot();
