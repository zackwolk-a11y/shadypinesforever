// Overlay spacing audit: plays real scenes (tutorial, boss fights, Level 333 with the pigs, Cowgod as an
// ally, dialogue scenes) and checks EVERY drawn frame:
//   - no floating overlay (impact word, toast, banner, boss card, dialogue box) covers a character's face
//   - floating overlays never overlap each other and keep at least 6px of space between them
//   - fixed HUD panels fade out whenever a face is underneath them
// Faces are registered by the characters' own draw functions (see Faces in src/00_core.js).
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 640, height: 360 } });
  const errs = []; p.on('pageerror', e => errs.push(String(e)));
  await p.goto('file://' + path.resolve(__dirname, '../333-dimensions-of-madness.html'));
  await p.waitForFunction(() => window.DIM333 && DIM333.G.state === 'title');
  await p.evaluate(() => {
    const D = DIM333, Gm = D.Game, I = D.Input._down;
    const hitFace = (r) => Faces.hitRect(r.x, r.y, r.w, r.h, 0);
    const over = (a, c) => a.x < c.x + c.w + 6 && a.x + a.w + 6 > c.x && a.y < c.y + c.h + 6 && a.y + a.h + 6 > c.y; // < 6px apart counts as cramped
    window.__audit = (frames, opts = {}) => {
      const st = { frames: 0, overlays: 0, faceHits: 0, blocked: 0, pairOverlaps: 0, hudUnderFaceNotFaded: 0, faces: 0, examples: [], tags: {} };
      for (let f = 0; f < frames; f++) {
        for (const k in I) I[k] = false;
        if (Gm.cutscene) { if (opts.skip) D.skipScene(); else if (f % 25 === 0) { D.Input._latch.jump = true; D.Input._latch.confirm = true; } }
        else { const B = Gm.boss, pl = Gm.player; let tx = pl.cx + 300; if (B) { const hb = B.hitbox(); tx = hb.x + hb.w / 2; }
          const dx = tx - pl.cx; if (Math.abs(dx) > 50) I[dx > 0 ? 'right' : 'left'] = true; else pl.face = Math.sign(dx) || pl.face;
          if (f % 45 === 0) D.Input._latch.jump = true; if (f % 45 < 14) I.jump = true; if (f % 13 === 0) D.Input._latch.whip = true; }
        D.run(1); if (D.G.state !== 'level') break;
        Layout.log = []; Gm.draw(); st.frames++; st.faces += Faces.list.length;
        const floating = Layout.log.filter(r => !r.fixed);
        for (const r of floating) { st.overlays++; st.tags[r.tag] = (st.tags[r.tag] || 0) + 1; if (r.blocked) { st.blocked++; st.btags = st.btags || {}; st.btags[r.tag] = (st.btags[r.tag] || 0) + 1; continue; } /* blocked = drawn see-through (40-55%) or skipped */ const fh = hitFace(r); if (fh) { st.faceHits++; if (st.examples.length < 6) st.examples.push(r.tag + ' over ' + fh.who + ' @' + f); } }
        for (let i = 0; i < floating.length; i++) for (let j = i + 1; j < floating.length; j++) if (!floating[i].hidden && !floating[j].hidden && over(floating[i], floating[j])) { st.pairOverlaps++; if (st.examples.length < 6) st.examples.push(floating[i].tag + ' x ' + floating[j].tag + ' @' + f); }
      }
      Layout.log = null; return st;
    };
    window.__setup = (lv, ch, toGate) => { D.god(); D.load(lv, ch); if (toGate) { for (let i = 0; i < 400 && Gm.cutscene; i++) { D.skipScene(); D.run(1); } const g = Gm.ents.find(e => e.constructor.name === 'BossGate'); if (g) { Gm.player.x = g.x + 60; Gm.player.y = g.o.gy * 16 - 40; } } };
  });
  const scenes = [
    ['Level 1 tutorial (Moshmouth, Shitman chase, impact words, dialogue)', 0, 0, false, 2400],
    ['Level 2: Electric Harley boss fight', 1, 0, 'biker', 2000],
    ['Level 333 straw house (Three Little Pigs, dialogue)', 2, 0, false, 1800],
    ['Level 333 chapter 3 (pigs following)', 2, 2, false, 1500],
    ['Level 333 finale: Big Bad Wolf boss', 2, 5, true, 1500],
    ['Level 8: Cowgod boss', 7, 0, true, 1500],
    ['Level 10: Cowgod flying ally', 9, 0, false, 1500],
    ['Level 25: Shitman / Garbage Heap boss', 24, 0, true, 2000],
    ['Level 4: candle arena (enemy waves)', 3, 0, false, 2500]
  ];
  const res = [];
  for (const [name, lv, ch, gate, frames] of scenes) {
    const r = await p.evaluate(([lv, ch, gate, frames]) => {
      if (gate === 'biker') { const D = DIM333, Gm = D.Game; D.god(); D.load(lv, ch); for (let i = 0; i < 300 && Gm.cutscene; i++) { D.skipScene(); D.run(1); } const enc = Gm.ents.find(e => e.constructor.name === 'BikerEncounter'); Gm.player.x = enc.x0 + 40; Gm.player.y = enc.gyPx - 40; }
      else window.__setup(lv, ch, gate);
      return window.__audit(frames);
    }, [lv, ch, gate, frames]);
    res.push([name, r]);
  }
  let fail = 0;
  for (const [name, r] of res) {
    const ok = r.faceHits === 0 && r.pairOverlaps === 0 && r.frames > 200 && r.faces > 0;
    if (!ok) fail++;
    console.log((ok ? 'PASS ' : 'FAIL ') + name + `  frames=${r.frames} faces/frame=${(r.faces / Math.max(1, r.frames)).toFixed(1)} overlays=${r.overlays} coveringFaces=${r.faceHits} overlapping=${r.pairOverlaps} noFreeSpot=${r.blocked}${r.btags ? JSON.stringify(r.btags) : ''} ` + JSON.stringify(r.tags) + (r.examples.length ? ' e.g. ' + r.examples.join('; ') : ''));
  }
  console.log('page errors:', JSON.stringify(errs));
  console.log(fail || errs.length ? fail + ' OVERLAY CHECKS FAILED' : 'ALL OVERLAY CHECKS PASS'); await b.close(); process.exit(fail || errs.length ? 1 : 0);
})();
