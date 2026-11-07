// Character sprite & animation validation (all six character groups).
// - every group present (the Three Little Pigs as three individual characters)
// - every required animation exists, every frame has visible pixels, none clipped by its frame,
//   frame rects inside the atlas, one fixed frame size and pivot per character
// - transparent background around every frame; hard alpha (no semi-transparent fringes) on the
//   separated source sprites; no see-through holes inside bodies (the old wireframe motorcycle)
// - grounded characters keep their feet on one baseline while idle
// - safe frame lookup never returns nothing (bad index / missing animation fall back)
// - in-game: Moshmouth is drawn on EVERY frame while invulnerable (no blinking)
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 640, height: 360 } });
  const errs = []; p.on('pageerror', e => errs.push(String(e)));
  await p.goto('file://' + path.resolve(__dirname, '../333-dimensions-of-madness.html'));
  await p.waitForFunction(() => window.DIM333 && DIM333.G.state === 'title');
  const R = await p.evaluate(() => {
    const out = [], t = (name, fn) => { try { const r = fn(); out.push([name, !!r.ok, JSON.stringify(r)]); } catch (e) { out.push([name, false, String(e)]); } };
    const val = CharAnim.validate();
    t('all six character groups are present (pigs = three characters)', () => ({ ok: CHAR_GROUPS.length === 6 && CHAR_GROUPS.every(([, ids]) => ids.every(id => CharAnim.atlas[id])) && CHAR_GROUPS[1][1].length === 3, groups: CHAR_GROUPS.map(g => g[0]) }));
    t('every required animation exists for every character', () => { const miss = val.filter(v => v.missing.length).map(v => v.id + ':' + v.missing); return { ok: !miss.length, miss, anims: val.map(v => v.id + '=' + v.anims) }; });
    t('no blank, clipped or out-of-atlas frames', () => { const bad = val.filter(v => v.blank || v.clipped || v.outOfBounds || v.problems.length); return { ok: !bad.length, frames: val.reduce((s, v) => s + v.frames, 0), bad }; });
    t('one fixed frame size and one pivot per character', () => { const bad = val.filter(v => v.frameSizes.length !== 1 || v.pivots.length !== 1); return { ok: !bad.length, bad }; });
    t('transparent background around every frame (corners clear on light and dark)', () => { const bad = []; for (const id in CharAnim.atlas) { const m = CharAnim.atlas[id], c = m.sheet.ctx; for (const n in m.anims) m.anims[n].rects.forEach((r, i) => { for (const [cx, cy] of [[r[0] + 1, r[1] + 1], [r[0] + r[2] - 2, r[1] + 1], [r[0] + 1, r[1] + r[3] - 2], [r[0] + r[2] - 2, r[1] + r[3] - 2]]) if (c.getImageData(cx, cy, 1, 1).data[3] !== 0) bad.push(id + '.' + n + '[' + i + ']'); }); } return { ok: !bad.length, bad: bad.slice(0, 10) }; });
    // source sprites: separated, transparent, hard alpha, solid bodies
    const SRC = ['hero', 'hero_closed', 'pig_hamwise', 'pig_porkington', 'pig_trufflina', 'biker', 'biker_bike', 'biker_rider', 'wolf_body', 'cow_body', 'cow_cape', 'sludge', 'gloopkin'];
    const scan = img => { const c = makeCanvas(img.width, img.height); c.ctx.drawImage(img, 0, 0); const d = c.ctx.getImageData(0, 0, img.width, img.height).data, W = img.width, H = img.height; let semi = 0, op = 0; const tr = new Uint8Array(W * H), seen = new Uint8Array(W * H), st = [];
      for (let i = 0; i < W * H; i++) { const a = d[i * 4 + 3]; if (a > 0 && a < 255) semi++; if (a > 0) op++; else tr[i] = 1; }
      for (let x = 0; x < W; x++) for (const y of [0, H - 1]) { const i = y * W + x; if (tr[i] && !seen[i]) { seen[i] = 1; st.push(i); } }
      for (let y = 0; y < H; y++) for (const x of [0, W - 1]) { const i = y * W + x; if (tr[i] && !seen[i]) { seen[i] = 1; st.push(i); } }
      while (st.length) { const i = st.pop(), x = i % W, y = (i / W) | 0; for (const j of [x > 0 ? i - 1 : -1, x < W - 1 ? i + 1 : -1, y > 0 ? i - W : -1, y < H - 1 ? i + W : -1]) if (j >= 0 && tr[j] && !seen[j]) { seen[j] = 1; st.push(j); } }
      let holes = 0; for (let i = 0; i < W * H; i++) if (tr[i] && !seen[i]) holes++;
      const border = [0, W - 1, (H - 1) * W, H * W - 1].every(i => d[i * 4 + 3] === 0);
      return { semi, holes, ratio: +(holes / Math.max(1, op)).toFixed(3), border }; };
    const S = {}; for (const k of SRC) S[k] = IMG[k] ? scan(IMG[k]) : null;
    t('separated source sprites exist with transparent borders', () => { const bad = SRC.filter(k => !S[k] || !S[k].border); return { ok: !bad.length, bad }; });
    t('hard alpha: no semi-transparent pixels in character sprites', () => { const bad = SRC.filter(k => S[k] && S[k].semi > 0).map(k => k + ':' + S[k].semi); return { ok: !bad.length, bad }; });
    t('solid bodies: no see-through holes (old wireframe bike had 17%)', () => { const bad = SRC.filter(k => S[k] && S[k].ratio > .06).map(k => k + ':' + S[k].ratio); return { ok: !bad.length, bad, biker: S.biker, bike: S.biker_bike }; });
    t('motorcycle tyres are solid all the way round', () => { const img = IMG.biker_bike, an = A('biker'), c = makeCanvas(img.width, img.height); c.ctx.drawImage(img, 0, 0); const res = {}; for (const k of ['rearWheel', 'frontWheel']) { const [wx, wy] = an[k]; let n = 0, o = 0; for (let a = 0; a < 360; a += 5) { const x = Math.round(wx + Math.cos(a * Math.PI / 180) * 19), y = Math.round(wy + Math.sin(a * Math.PI / 180) * 19); if (x < 0 || y < 0 || x >= img.width || y >= img.height) continue; n++; if (c.ctx.getImageData(x, y, 1, 1).data[3] === 255) o++; } res[k] = +(o / n).toFixed(2); } return { ok: res.rearWheel > .9 && res.frontWheel > .9, res }; });
    t('grounded characters keep their feet on the baseline while idle', () => { const res = {}; let ok = true; for (const id of ['wolf', 'cowgod', 'shitman', 'harley', 'pig_hamwise', 'pig_porkington', 'pig_trufflina']) { const bs = CharAnim.atlas[id].anims.idle.bounds.map(b => b.y + b.h); const sp = Math.max(...bs) - Math.min(...bs); res[id] = sp; if (sp > 4) ok = false; } return { ok, spread: res }; });
    t('Moshmouth stays centred while idle (floating head)', () => { const cs = CharAnim.atlas.moshmouth.anims.idle.bounds.map(b => b.y + b.h / 2); const sp = Math.max(...cs) - Math.min(...cs); return { ok: sp <= 4, spread: sp }; });
    t('safe frame lookup: bad index or missing animation still returns a valid frame', () => { const a = CharAnim.frame('wolf', 'idle', 9999), b2 = CharAnim.frame('cowgod', 'death', -5), c = CharAnim.frame('shitman', 'doesNotExist', 3); return { ok: !!(a && b2 && c && a.bounds && b2.bounds && c.bounds), a: a && a.index, b: b2 && b2.index, c: c && c.index }; });
    return out;
  });
  // in-game: no blinking while invulnerable
  const blink = await p.evaluate(() => { const D = DIM333, Gm = D.Game; D.load(0); Gm.cutscene = null; D.run(30); const pl = Gm.player; pl.hurt(1, pl.cx + 20); let drawn = 0, frames = 0;
    const oh = window.drawHero, ot = window.drawTongueFrame; window.drawHero = function () { drawn++; return oh.apply(this, arguments); }; window.drawTongueFrame = function () { drawn++; return ot.apply(this, arguments); };
    const missed = []; for (let i = 0; i < 100 && pl.inv > 0; i++) { const d0 = drawn; D.run(1); Gm.draw(); frames++; if (drawn === d0) missed.push(pl.inv); }
    window.drawHero = oh; window.drawTongueFrame = ot; return { ok: frames > 60 && !missed.length, frames, missed: missed.slice(0, 10) }; });
  R.push(['Moshmouth is drawn on every frame while invulnerable (no blinking)', blink.ok, JSON.stringify(blink)]);
  const insp = await p.evaluate(() => { Inspector.open(); let drawn = 0; const bad = [];
    for (let ci = 0; ci < Inspector.ids.length; ci++) { Inspector.ci = ci; const names = Object.keys(CharAnim.atlas[Inspector.ids[ci]].anims);
      for (let ai = 0; ai < names.length; ai++) { Inspector.ai = ai; const n = CharAnim.atlas[Inspector.ids[ci]].anims[names[ai]].count; for (let f = 0; f < n; f++) { Inspector.f = f; try { Inspector.draw(); drawn++; } catch (e) { bad.push(Inspector.ids[ci] + '.' + names[ai] + ': ' + e.message); } } } }
    const st = DIM333.G.state; Inspector.close(); return { ok: st === 'inspector' && !bad.length && drawn > 400, drawn, bad: bad.slice(0, 5), after: DIM333.G.state }; });
  R.push(['developer inspector opens and draws every frame of every character', insp.ok, JSON.stringify(insp)]);
  let fail = 0; for (const [n, ok, d] of R) { if (!ok) fail++; console.log((ok ? 'PASS ' : 'FAIL ') + n + '  ' + d.slice(0, 400)); }
  console.log('page errors:', JSON.stringify(errs));
  console.log(fail || errs.length ? fail + ' SPRITE CHECKS FAILED' : 'ALL SPRITE CHECKS PASS'); await b.close(); process.exit(fail || errs.length ? 1 : 0);
})();
