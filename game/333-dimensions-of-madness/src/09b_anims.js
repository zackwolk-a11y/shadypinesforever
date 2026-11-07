// ============================================================================
// CHARACTER ANIMATION ATLASES
// Six independent character collections (Moshmouth, The Three Little Pigs x3, Electric Harley House
// (of Love), Big Bad Wolf, Cowgod, Shitman). Every frame is baked from the individually separated,
// transparent sprites in assets/gen (never from the six-panel reference collage) into one atlas sheet
// per character, with explicit metadata: frame count, fps, loop, fixed frame canvas, pivot,
// collision box and attack hitboxes. CharAnim.frame() never returns a blank frame: an invalid index
// is clamped and a blank frame falls back to the last valid one (with a one-time warning).
// Baked lazily (inspector / tests / exporter), so it costs nothing at boot.
// ============================================================================
const TAU = Math.PI * 2;
// helpers used inside frame painters (pivot = feet/centre point in frame pixels)
const AnimP = {
  stars(x, y, n = 3, t = 0) { for (let i = 0; i < n; i++) { const a = t * 6 + i * TAU / n; PP.star(ctx, x + Math.cos(a) * 16, y + Math.sin(a) * 5, 5, i % 2 ? '#fff' : '#ffe14d'); } },
  puff(x, y, r, a = .8) { ctx.save(); ctx.globalAlpha = a; PP.ell(ctx, x, y, r, r * .8, '#d8d8e8', 2); ctx.restore(); },
  glob(x, y, r) { P.e(ctx, x, y, r + 1.5, r + 1.5, '#0a2a00'); P.e(ctx, x, y, r, r, '#7fff3a'); P.e(ctx, x - r * .3, y - r * .3, r * .3, r * .3, '#e8ffb0'); },
  confetti(x, y, i) { const C = ['#ff5bd1', '#ffe14d', '#5bd4ff', '#7fff3a']; for (let k = 0; k < 6; k++) P.r(ctx, x + Math.cos(k * 1.7 + i) * (20 + k * 4), y - 30 + Math.sin(k * 2.3 + i * .7) * 16, 3, 3, C[k % 4]); }
};
// Electric Harley's mouth in frame pixels, for a rider drawn with its rear-tyre pivot at (x, y) at native scale
function harleyMouth(x, y) { const an = A('biker'), rw = an.rearWheel, H2 = IMG.biker.height; return [x + an.mouth[0] - rw[0], y + an.mouth[1] - (H2 - 2)]; }
const CHAR_DEFS = {
  // ---------------------------------------------------------------- 1. MOSHMOUTH (pivot = centre of the head)
  moshmouth: { label: 'MOSHMOUTH', w: 280, h: 176, px: 100, py: 88, k: 1, box: [-20, -22, 40, 45], anims: {
    idle:    { n: 6, fps: 8, loop: true, draw: (i, n, x, y, s) => drawHero(x, y, { face: 1, closed: true, scale: s, sy: 1 + Math.sin(i / n * TAU) * .03, sx: 1 - Math.sin(i / n * TAU) * .02 }) },
    bounce:  { n: 6, fps: 12, loop: true, draw: (i, n, x, y, s) => { const h = Math.abs(Math.sin(i / n * Math.PI)); drawHero(x, y - h * 12, { face: 1, closed: true, scale: s, sy: h < .2 ? .86 : 1.06, sx: h < .2 ? 1.12 : .96 }); } },
    walk:    { n: 6, fps: 12, loop: true, draw: (i, n, x, y, s) => drawHero(x, y - Math.abs(Math.sin(i / n * TAU)) * 4, { face: 1, closed: true, scale: s, rot: Math.sin(i / n * TAU) * .12 }) },
    jump:    { n: 4, fps: 10, loop: false, draw: (i, n, x, y, s) => drawHero(x, y - [0, 6, 10, 12][i], { face: 1, closed: true, scale: s, sy: [.85, 1.15, 1.1, 1.02][i], sx: [1.12, .9, .94, 1][i] }) },
    tongue:  { n: 8, fps: 12, loop: false, hit: { frames: [2, 3, 4], box: [30, -10, 90, 30] }, draw: (i, n, x, y, s) => drawTongueFrame(x, y, 1, i, { scale: s }) },
    slimeSpit: { n: 6, fps: 12, loop: false, hit: { frames: [3, 4, 5], box: [40, -16, 90, 32] }, draw: (i, n, x, y, s) => { drawHero(x, y, { face: 1, closed: true, form: 'slime', scale: s, mouth: [0, .5, 1, 1, .6, .2][i], sx: i === 2 ? 1.08 : 1 }); if (i >= 2) for (let k = 0; k < 3; k++) AnimP.glob(x + 30 + (i - 2) * 22 + k * 6, y + 8 + (k - 1) * 9 + (i - 2) * k * 2, 4 + (k === 1)); } },
    spin:    { n: 8, fps: 20, loop: true, hit: { frames: [0, 1, 2, 3, 4, 5, 6, 7], box: [-40, -40, 80, 80] }, draw: (i, n, x, y, s) => { ctx.save(); ctx.globalAlpha = .45; ctx.strokeStyle = '#fff6d0'; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(x, y, 44, 0, TAU); ctx.stroke(); ctx.restore(); drawHero(x, y, { face: 1, closed: true, scale: s, rot: i / n * TAU }); } },
    scream:  { n: 6, fps: 12, loop: true, draw: (i, n, x, y, s) => { drawHero(x, y, { face: 1, closed: true, scale: s, mouth: .6 + Math.sin(i / n * TAU) * .4, aura: true, sx: 1.06, sy: 1.06, rot: Math.sin(i * 2.1) * .05 }); for (let k = 1; k <= 2; k++) { ctx.strokeStyle = 'rgba(255,255,255,.6)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(x + 30, y + 8, 18 + k * 12 + i * 2, -.7, .7); ctx.stroke(); } } },
    hurt:    { n: 4, fps: 12, loop: false, draw: (i, n, x, y, s) => drawHero(x - [0, -6, -4, -1][i], y, { face: 1, closed: true, scale: s, flash: i < 2 ? '#ff3a3a' : false, rot: [-.1, -.32, -.2, -.05][i], sx: [1.1, .9, 1, 1][i], sy: [.9, 1.1, 1, 1][i] }) },
    death:   { n: 8, fps: 8, loop: false, draw: (i, n, x, y, s) => { const k = i / (n - 1); drawHero(x, y + k * 26, { face: 1, closed: true, scale: s, rot: -k * .9, sy: 1 - k * .55, sx: 1 + k * .35 }); if (i >= 3) AnimP.stars(x, y - 20 + k * 20, 3, i * .3); } },
    victory: { n: 6, fps: 10, loop: true, draw: (i, n, x, y, s) => { const h = Math.abs(Math.sin(i / n * TAU)); drawHero(x, y - h * 14, { face: 1, closed: true, scale: s, mouth: .7, rot: Math.sin(i / n * TAU) * .2 }); AnimP.confetti(x, y - 10, i); } }
  } },
  // ---------------------------------------------------------------- 3. ELECTRIC HARLEY HOUSE (OF LOVE) (pivot = rear tyre contact)
  harley: { label: 'ELECTRIC HARLEY HOUSE (OF LOVE)', w: 470, h: 260, px: 192, py: 226, k: 1, anims: {
    idle:    { n: 4, fps: 8, loop: true, baked: 'idle' },
    drive:   { n: 8, fps: 14, loop: true, baked: 'drive' },
    jump:    { n: 6, fps: 10, loop: false, draw: (i, n, x, y, s) => { const k = i / (n - 1); drawBiker(x, y - Math.sin(k * Math.PI) * 40, { face: 1, scale: s, t: i * .05, speed: 1, tilt: -.25 + k * .4, hairBoost: 3 }); } },
    attack:  { n: 8, fps: 12, loop: false, baked: 'tongue', hit: { frames: [3, 4, 5], fromMouth: [70, -20, 90, 40] },
      // the boss draws its tongue live on top of the baked frame; the atlas bakes it in so the frames are complete
      after: (i, n, x, y) => { const m = harleyMouth(x, y), ext = BIKER_TONGUE_EXT[i]; if (ext > 0) drawTongue(m[0], m[1], m[0] + ext * 150, m[1] + ext * 10, 6, 4, ['#3a0018', '#ff6aa8', '#ffc0dc']); } },
    turbo:   { n: 6, fps: 14, loop: true, baked: 'charge', hit: { frames: [0, 1, 2, 3, 4, 5], box: [-20, -110, 220, 110] } },
    wheelie: { n: 6, fps: 10, loop: true, draw: (i, n, x, y, s) => drawBiker(x, y, { face: 1, scale: s, t: i * .06, speed: 1.4, wheelie: .32 + Math.sin(i / n * TAU) * .05, hairBoost: 2 }) },
    special: { n: 6, fps: 12, loop: true, draw: (i, n, x, y, s) => { for (let k = 0; k < 3; k++) AnimP.puff(x - 40 - k * 22 - i * 3, y - 18 - k * 4, 8 + k * 3, .7); drawBiker(x, y, { face: 1, scale: s, t: i * .08, speed: 2, turbo: true, hairBoost: 6, mouthOpen: .8, riderRot: -.08 }); } },
    hurt:    { n: 4, fps: 16, loop: false, baked: 'hit' },
    crash:   { n: 12, fps: 7, loop: false, baked: 'defeat' },
    victory: { n: 6, fps: 10, loop: true, draw: (i, n, x, y, s) => { drawBiker(x, y, { face: 1, scale: s, t: i * .07, speed: .6, wheelie: .22, mouthOpen: .9, riderRot: -.1 + Math.sin(i / n * TAU) * .06 }); AnimP.confetti(x + 120, y - 120, i); } }
  } },
  // ---------------------------------------------------------------- 4. BIG BAD WOLF (pivot = feet)
  wolf: { label: 'BIG BAD WOLF', w: 320, h: 276, px: 160, py: 252, k: .8, anims: {
    idle:    { n: 6, fps: 8, loop: true, draw: (i, n, x, y, s) => drawWolf(x, y, { face: 1, scale: s, t: i / n * 2.09, arm: Math.sin(i / n * TAU) * .12 }) },
    walk:    { n: 6, fps: 10, loop: true, draw: (i, n, x, y, s) => drawWolf(x, y - Math.abs(Math.sin(i / n * TAU)) * 4, { face: 1, scale: s, t: i * .2, rot: Math.sin(i / n * TAU) * .05, arm: Math.sin(i / n * TAU) * .4 }) },
    run:     { n: 6, fps: 14, loop: true, draw: (i, n, x, y, s) => drawWolf(x, y - Math.abs(Math.sin(i / n * TAU)) * 9, { face: 1, scale: s, t: i * .2, rot: .12 + Math.sin(i / n * TAU) * .06, arm: .6 + Math.sin(i / n * TAU) * .6 }) },
    clawAttack: { n: 6, fps: 12, loop: false, hit: { frames: [2, 3], box: [20, -170, 90, 120] }, draw: (i, n, x, y, s) => drawWolf(x, y, { face: 1, scale: s, t: i * .1, arm: [-.6, -.9, 1.2, 1.5, 1, .3][i], claw: i === 2 || i === 3 ? .9 : 0, rot: [-.05, -.08, .08, .1, .05, 0][i] }) },
    bite:    { n: 5, fps: 12, loop: false, hit: { frames: [2, 3], box: [30, -150, 60, 50] }, draw: (i, n, x, y, s) => drawWolf(x + [0, -4, 10, 12, 4][i], y, { face: 1, scale: s, t: i * .1, rot: [0, -.1, .22, .25, .08][i], sx: [1, .95, 1.08, 1.1, 1][i] }) },
    howl:    { n: 6, fps: 8, loop: true, draw: (i, n, x, y, s) => { drawWolf(x, y, { face: 1, scale: s, t: i * .1, rot: -.22, arm: -.35, eyes: true }); ctx.strokeStyle = 'rgba(255,255,255,.55)'; ctx.lineWidth = 2; for (let k = 0; k < 3; k++) { ctx.beginPath(); ctx.arc(x + 40, y - 190, 14 + k * 14 + (i % 3) * 4, -2.4, -.8); ctx.stroke(); } } },
    hurt:    { n: 4, fps: 12, loop: false, draw: (i, n, x, y, s) => drawWolf(x - [0, 8, 6, 2][i], y, { face: 1, scale: s, t: i * .1, rot: [-.1, -.25, -.15, -.05][i], flash: i < 2 ? '#ff3a3a' : false }) },
    death:   { n: 8, fps: 8, loop: false, draw: (i, n, x, y, s) => { const k = i / (n - 1); ctx.save(); ctx.translate(x, y - k * 46); ctx.rotate(-k * 1.35); ctx.translate(-x, -y); drawWolf(x, y, { face: 1, scale: s, t: 0, arm: k, breath: 0 }); ctx.restore(); if (i >= 5) AnimP.stars(x - 70, y - 50, 3, i * .3); } },
    victory: { n: 6, fps: 10, loop: true, draw: (i, n, x, y, s) => drawWolf(x, y - Math.abs(Math.sin(i / n * TAU)) * 10, { face: 1, scale: s, t: i * .1, arm: -.6 + Math.sin(i / n * TAU) * .5, eyes: true }) }
  } },
  // ---------------------------------------------------------------- 5. COWGOD (pivot = feet)
  cowgod: { label: 'COWGOD', w: 350, h: 236, px: 196, py: 206, k: .8, anims: {
    idle:    { n: 6, fps: 8, loop: true, draw: (i, n, x, y, s) => drawCow(x, y - Math.sin(i / n * TAU) * 2, { face: 1, scale: s, t: i / n * 2.09 }) },
    run:     { n: 6, fps: 14, loop: true, draw: (i, n, x, y, s) => drawCow(x, y - Math.abs(Math.sin(i / n * TAU)) * 8, { face: 1, scale: s, t: i * .15, rot: .08 + Math.sin(i / n * TAU) * .05, capeLift: .6 }) },
    jump:    { n: 4, fps: 10, loop: false, draw: (i, n, x, y, s) => drawCow(x, y - [0, 14, 22, 26][i], { face: 1, scale: s, t: i * .1, rot: [-.05, -.15, -.1, 0][i], sy: [.9, 1.08, 1.04, 1][i], capeLift: 1 }) },
    charge:  { n: 6, fps: 14, loop: true, hit: { frames: [0, 1, 2, 3, 4, 5], box: [30, -110, 80, 100] }, draw: (i, n, x, y, s) => { for (let k = 0; k < 3; k++) P.r(ctx, x - 120 - k * 18 - (i * 7) % 20, y - 30 - k * 26, 40, 3, '#ffffffaa'); drawCow(x, y, { face: 1, scale: s, t: i * .15, rot: .2, capeLift: 1, capeStretch: 1 }); } },
    stomp:   { n: 6, fps: 12, loop: false, hit: { frames: [4, 5], box: [-120, -30, 240, 34] }, draw: (i, n, x, y, s) => { drawCow(x, y - [30, 40, 36, 10, 0, 0][i], { face: 1, scale: s, t: i * .1, sy: [1, 1.05, 1.08, 1.1, .82, .9][i], sx: [1, .95, .94, .92, 1.16, 1.08][i] }); if (i >= 4) { ctx.strokeStyle = '#fff'; ctx.lineWidth = 3; ctx.beginPath(); ctx.ellipse(x, y, 60 + (i - 4) * 40, 10, 0, 0, TAU); ctx.stroke(); } } },
    headbutt: { n: 5, fps: 12, loop: false, hit: { frames: [2, 3], box: [40, -120, 60, 70] }, draw: (i, n, x, y, s) => drawCow(x + [0, -8, 14, 16, 4][i], y, { face: 1, scale: s, t: i * .1, rot: [0, -.12, .3, .32, .1][i] }) },
    hurt:    { n: 4, fps: 12, loop: false, draw: (i, n, x, y, s) => drawCow(x - [0, 8, 5, 1][i], y, { face: 1, scale: s, t: i * .1, rot: [-.1, -.25, -.12, 0][i], flash: i < 2 ? '#ff3a3a' : false }) },
    death:   { n: 8, fps: 8, loop: false, draw: (i, n, x, y, s) => { const k = i / (n - 1); ctx.save(); ctx.translate(x, y - k * 56); ctx.rotate(-k * 1.4); ctx.translate(-x, -y); drawCow(x, y, { face: 1, scale: s, t: 0, sy: 1 - k * .1 }); ctx.restore(); if (i >= 4) AnimP.stars(x - 60, y - 40, 3, i * .3); } },
    victory: { n: 6, fps: 10, loop: true, draw: (i, n, x, y, s) => { drawCow(x, y - 20 - Math.sin(i / n * TAU) * 8, { face: 1, scale: s, t: i * .1, rot: -.15, capeLift: 1 }); AnimP.confetti(x, y - 100, i); } }
  } },
  // ---------------------------------------------------------------- 6. SHITMAN (pivot = body baseline)
  shitman: { label: 'SHITMAN', w: 470, h: 246, px: 222, py: 228, k: .62, anims: {
    idle:    { n: 6, fps: 8, loop: true, draw: (i, n, x, y, s) => drawSludge(x, y, { face: -1, scale: s, t: i / n * 2.09 }) },
    ooze:    { n: 6, fps: 10, loop: true, draw: (i, n, x, y, s) => drawSludge(x, y, { face: -1, scale: s, t: i * .2, wobble: 1.6, sy: 1 + Math.sin(i / n * TAU) * .06, sx: 1 - Math.sin(i / n * TAU) * .05 }) },
    move:    { n: 6, fps: 12, loop: true, draw: (i, n, x, y, s) => drawSludge(x + Math.sin(i / n * TAU) * 4, y, { face: -1, scale: s, t: i * .25, wobble: 1.3, sx: 1 + Math.abs(Math.sin(i / n * TAU)) * .08, sy: 1 - Math.abs(Math.sin(i / n * TAU)) * .06 }) },
    splash:  { n: 6, fps: 12, loop: false, draw: (i, n, x, y, s) => { drawSludge(x, y - [0, 20, 30, 20, 0, 0][i], { face: -1, scale: s, t: i * .2, sy: [.8, 1.2, 1.1, 1, .7, .9][i], sx: [1.2, .85, .9, 1, 1.35, 1.1][i] }); if (i >= 4) for (let k = 0; k < 6; k++) P.e(ctx, x + (k - 2.5) * 30, y - 6 - (k % 2) * 10, 5, 4, '#c8822a'); } },
    slam:    { n: 6, fps: 12, loop: false, hit: { frames: [3, 4], box: [-150, -40, 300, 44] }, draw: (i, n, x, y, s) => { drawSludge(x, y, { face: -1, scale: s, t: i * .2, sy: [1.1, 1.25, 1.3, .65, .75, .95][i], sx: [.95, .88, .85, 1.3, 1.22, 1.05][i], bulge: i === 3 ? .2 : 0 }); if (i >= 3) { ctx.strokeStyle = '#ffd860'; ctx.lineWidth = 3; ctx.beginPath(); ctx.ellipse(x, y, 90 + (i - 3) * 30, 9, 0, 0, TAU); ctx.stroke(); } } },
    spit:    { n: 6, fps: 12, loop: false, hit: { frames: [3, 4, 5], box: [-160, -110, 70, 40] }, draw: (i, n, x, y, s) => { drawSludge(x, y, { face: -1, scale: s, t: i * .2, bulge: [0, .1, .2, 0, 0, 0][i], sx: i === 2 ? 1.08 : 1 }); if (i >= 3) { const gx = x - 90 - (i - 3) * 26; P.e(ctx, gx, y - 90 + (i - 3) * 6, 9, 7, '#3a1a00'); P.e(ctx, gx, y - 90 + (i - 3) * 6, 8, 6, '#c8822a'); } } },
    shapeShift: { n: 8, fps: 10, loop: false, draw: (i, n, x, y, s) => { const k = Math.sin(i / (n - 1) * Math.PI); drawSludge(x, y, { face: -1, scale: s, t: i * .3, wobble: 1 + k * 2.5, bulge: k * .35, sy: 1 - k * .3 + (i > 4 ? k * .2 : 0), sx: 1 + k * .25 }); } },
    hurt:    { n: 4, fps: 12, loop: false, draw: (i, n, x, y, s) => drawSludge(x + [0, 6, 4, 1][i], y, { face: -1, scale: s, t: i * .2, flash: i < 2 ? '#ff3a3a' : false, sx: [1.1, .9, 1, 1][i], sy: [.9, 1.12, 1, 1][i] }) },
    death:   { n: 8, fps: 8, loop: false, draw: (i, n, x, y, s) => { const k = i / (n - 1); drawSludge(x, y, { face: -1, scale: s, t: i * .2, sy: Math.max(.18, 1 - k * .85), sx: 1 + k * .45, wobble: 1.4 }); if (i >= 5) for (let d = 0; d < 3; d++) AnimP.puff(x - 60 + d * 60, y - 30 - (i - 5) * 6, 10 + d * 2, .6); } },
    victory: { n: 6, fps: 10, loop: true, draw: (i, n, x, y, s) => drawSludge(x, y - Math.abs(Math.sin(i / n * TAU)) * 14, { face: -1, scale: s, t: i * .2, wobble: 1.5, sy: 1.05 + Math.sin(i / n * TAU) * .08 }) }
  } }
};
// ---------------------------------------------------------------- 2. THE THREE LITTLE PIGS: one collection, three individual characters
const PIG_IDS = ['hamwise', 'porkington', 'trufflina'];
function pigDef(id) {
  const st = (state, extra = {}) => (i, n, x, y, s) => drawPig(id, x, y - (extra.hop ? Math.abs(Math.sin(i / n * TAU)) * extra.hop : 0), Object.assign({ face: 1, scale: s, state, t: extra.t ? extra.t(i, n) : i / n }, extra.o ? extra.o(i, n) : {}));
  return { label: ((PIGS[id] && PIGS[id].name) || id).toUpperCase(), group: 'THE THREE LITTLE PIGS', w: 166, h: 142, px: 88, py: 124, k: 1, anims: {
    idle:   { n: 4, fps: 6, loop: true, draw: st('idle', { t: (i, n) => i / n * 1.57 }) },
    walk:   { n: 4, fps: 10, loop: true, draw: st('walk', { t: (i) => (i + .5) / 10 }) },
    run:    { n: 4, fps: 16, loop: true, draw: st('run', { t: (i) => (i + .5) / 16 }) },
    jump:   { n: 3, fps: 10, loop: false, draw: (i, n, x, y, s) => drawPig(id, x, y - [0, 12, 18][i], { face: 1, scale: s, state: 'jump', sq: [.85, 1.12, 1.05][i] }) },
    attack: { n: 4, fps: 12, loop: false, hit: { frames: [1, 2], box: [10, -40, 30, 30] }, draw: (i, n, x, y, s) => drawPig(id, x + [0, 4, 6, 2][i], y, { face: 1, scale: s, state: i === 0 || i === 3 ? 'idle' : 'attack', sq: [1, .92, .9, 1][i] }) },
    build:  { n: 6, fps: 10, loop: true, draw: (i, n, x, y, s) => { drawPig(id, x, y, { face: 1, scale: s, state: i % 2 ? 'attack' : 'idle', sq: i % 2 ? .92 : 1.04 }); const hx = x + 26, hy = y - 30 + (i % 2) * 10; ctx.save(); ctx.translate(hx, hy); ctx.rotate(i % 2 ? .9 : -.4); P.r(ctx, -1.5, 0, 3, 14, '#7a4520'); P.r(ctx, -6, -3, 12, 6, '#9aa0aa'); ctx.restore(); if (i % 2) PP.star(ctx, x + 36, y - 10, 4, '#ffe14d'); } },
    teamSpecial: { n: 6, fps: 12, loop: true, draw: st('dance', { t: (i, n) => i / n * .63, hop: 10 }) },
    hurt:   { n: 3, fps: 12, loop: false, draw: (i, n, x, y, s) => drawPig(id, x - [0, 5, 3][i], y, { face: 1, scale: s, state: 'hurt', flash: i === 0 ? '#ff3a3a' : false }) },
    death:  { n: 6, fps: 8, loop: false, draw: (i, n, x, y, s) => { const k = i / (n - 1); ctx.save(); ctx.translate(x, y - k * 22); ctx.rotate(-k * 1.5); ctx.translate(-x, -y); drawPig(id, x, y, { face: 1, scale: s, state: 'hurt' }); ctx.restore(); if (i >= 3) AnimP.stars(x - 20, y - 20, 3, i * .3); } },
    victory: { n: 6, fps: 12, loop: true, draw: (i, n, x, y, s) => { drawPig(id, x, y - Math.abs(Math.sin(i / n * TAU)) * 14, { face: 1, scale: s, state: 'dance', t: i / n * .63 }); AnimP.confetti(x, y - 30, i); } }
  } };
}
for (const id of PIG_IDS) CHAR_DEFS['pig_' + id] = pigDef(id);
// the six character groups (the pigs group holds three individual characters)
const CHAR_GROUPS = [['MOSHMOUTH', ['moshmouth']], ['THE THREE LITTLE PIGS', PIG_IDS.map(id => 'pig_' + id)], ['ELECTRIC HARLEY HOUSE (OF LOVE)', ['harley']], ['BIG BAD WOLF', ['wolf']], ['COWGOD', ['cowgod']], ['SHITMAN', ['shitman']]];
// animations each character is required to have (the acceptance list)
const REQUIRED_ANIMS = {
  moshmouth: ['idle', 'bounce', 'walk', 'jump', 'tongue', 'slimeSpit', 'spin', 'scream', 'hurt', 'death', 'victory'],
  pig: ['idle', 'walk', 'run', 'jump', 'attack', 'build', 'teamSpecial', 'hurt', 'death', 'victory'],
  harley: ['idle', 'drive', 'jump', 'attack', 'turbo', 'wheelie', 'special', 'hurt', 'crash', 'victory'],
  wolf: ['idle', 'walk', 'run', 'clawAttack', 'bite', 'howl', 'hurt', 'death', 'victory'],
  cowgod: ['idle', 'run', 'jump', 'charge', 'stomp', 'headbutt', 'hurt', 'death', 'victory'],
  shitman: ['idle', 'ooze', 'move', 'splash', 'slam', 'spit', 'shapeShift', 'hurt', 'death', 'victory']
};

const CharAnim = {
  atlas: {}, warned: {},
  // bake one character into a single atlas sheet: one row per animation, fixed frame size
  bake(id) {
    if (this.atlas[id]) return this.atlas[id];
    const d = CHAR_DEFS[id]; if (!d) return null;
    if (id === 'harley' && !BIKER_ANIMS.ready) bakeBikerFrames();
    const names = Object.keys(d.anims), cols = Math.max(...names.map(n => d.anims[n].n));
    const sheet = makeCanvas(d.w * cols, d.h * names.length); sheet.ctx.imageSmoothingEnabled = false;
    const meta = { id, label: d.label, group: d.group || d.label, frameW: d.w, frameH: d.h, pivot: [d.px, d.py], box: d.box, anims: {}, problems: [] };
    names.forEach((name, row) => {
      const a = d.anims[name], rects = [], bounds = [];
      for (let i = 0; i < a.n; i++) {
        const c = makeCanvas(d.w, d.h); c.ctx.imageSmoothingEnabled = false;
        if (a.baked) { const src = BIKER_ANIMS[a.baked] && BIKER_ANIMS[a.baked][i]; if (src) c.ctx.drawImage(src, d.px - BIKER_FRAME.ax, d.py - BIKER_FRAME.ay); if (a.after) withCtx(c, () => a.after(i, a.n, d.px, d.py)); }
        else withCtx(c, () => { ctx.save(); try { a.draw(i, a.n, d.px, d.py, ZOOM * d.k); } catch (e) { meta.problems.push(name + '#' + i + ': ' + e.message); } ctx.restore(); });
        const x = i * d.w, y = row * d.h; sheet.ctx.drawImage(c, x, y); rects.push([x, y, d.w, d.h]);
        bounds.push(this.measure(c));
      }
      let hit = a.hit || null; if (hit && hit.fromMouth) { const m = harleyMouth(d.px, d.py), f = hit.fromMouth; hit = { frames: hit.frames, box: [Math.round(m[0] - d.px + f[0]), Math.round(m[1] - d.py + f[1]), f[2], f[3]] }; }
      meta.anims[name] = { row, count: a.n, fps: a.fps, loop: !!a.loop, rects, bounds, hit };
    });
    // collision box: explicit for Moshmouth (= the player's hitbox), otherwise the idle pose's opaque
    // area inset by 12% - so it always sits on the body, relative to the pivot, in frame pixels
    if (!meta.box) { const b0 = meta.anims.idle.bounds[0], ix = b0.w * .12, iy = b0.h * .12; meta.box = [Math.round(b0.x + ix - d.px), Math.round(b0.y + iy - d.py), Math.round(b0.w - 2 * ix), Math.round(b0.h - 2 * iy)]; }
    meta.sheet = sheet; this.atlas[id] = meta; return meta;
  },
  bakeAll() { for (const id in CHAR_DEFS) this.bake(id); return this.atlas; },
  // opaque-pixel bounds of a frame (null = blank)
  measure(c) {
    const { width: w, height: h } = c, px = c.ctx.getImageData(0, 0, w, h).data; let x0 = w, y0 = h, x1 = -1, y1 = -1, n = 0;
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) if (px[(y * w + x) * 4 + 3] > 0) { n++; if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
    return n ? { x: x0, y: y0, w: x1 - x0 + 1, h: y1 - y0 + 1, px: n } : null;
  },
  // safe frame lookup: clamps the index; blank/missing frames fall back to the last valid one
  frame(id, anim, i) {
    const m = this.bake(id); if (!m) return null; let a = m.anims[anim];
    if (!a) { this.warn(id + ':' + anim, 'missing animation ' + anim + ' on ' + id + ' -> idle'); a = m.anims.idle; }
    let k = a.loop ? ((i % a.count) + a.count) % a.count : clamp(i | 0, 0, a.count - 1);
    if (!a.bounds[k]) { this.warn(id + ':' + anim + ':' + k, 'blank frame ' + id + '.' + anim + '[' + k + '] -> last valid frame'); while (k > 0 && !a.bounds[k]) k--; if (!a.bounds[k]) k = a.bounds.findIndex(b => b); if (k < 0) return null; }
    return { sheet: m.sheet, rect: a.rects[k], index: k, pivot: m.pivot, bounds: a.bounds[k] };
  },
  warn(key, msg) { if (!this.warned[key]) { this.warned[key] = 1; console.warn('[CharAnim] ' + msg); } },
  // draw a frame with its pivot at (x, y)
  draw(id, anim, i, x, y, o = {}) {
    const f = this.frame(id, anim, i); if (!f) return; const [sx, sy] = f.rect, s = o.scale || 1, flip = o.face < 0;
    ctx.save(); ctx.translate(Math.round(x), Math.round(y)); if (flip) ctx.scale(-1, 1); ctx.scale(s, s);
    ctx.drawImage(f.sheet, sx, sy, f.rect[2], f.rect[3], -f.pivot[0], -f.pivot[1], f.rect[2], f.rect[3]); ctx.restore();
  },
  // validation report used by the inspector and tests/sprites.js
  validate() {
    const out = []; this.bakeAll();
    for (const id in this.atlas) {
      const m = this.atlas[id], req = REQUIRED_ANIMS[id.startsWith('pig_') ? 'pig' : id], missing = req.filter(r => !m.anims[r]);
      let blank = 0, outOfBounds = 0, frames = 0, clipped = 0; const pivots = new Set(), sizes = new Set();
      for (const n in m.anims) { const a = m.anims[n]; for (let i = 0; i < a.count; i++) { frames++; const r = a.rects[i], b = a.bounds[i]; sizes.add(r[2] + 'x' + r[3]); pivots.add(m.pivot.join(',')); if (!b || b.px < 40) blank++; else if (b.x <= 0 || b.y <= 0 || b.x + b.w >= r[2] || b.y + b.h >= r[3]) clipped++; if (r[0] < 0 || r[1] < 0 || r[0] + r[2] > m.sheet.width || r[1] + r[3] > m.sheet.height) outOfBounds++; } }
      out.push({ id, label: m.label, group: m.group, anims: Object.keys(m.anims).length, frames, missing, blank, outOfBounds, clipped, frameSizes: [...sizes], pivots: [...pivots], problems: m.problems });
    }
    return out;
  }
};
