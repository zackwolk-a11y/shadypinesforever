// Exports the six character collections (eight atlases: the Three Little Pigs are three characters)
// baked by src/09b_anims.js to assets/atlas/<id>.png + <id>.json (frame rects, fps, loop, pivot,
// collision box, attack hitboxes, opaque bounds), plus checkerboard previews for visual review.
// Usage: node tools/export_atlases.js [--previews]   (after node tools/build.js)
const { chromium } = require('playwright'), fs = require('fs'), path = require('path');
(async () => {
  const out = path.resolve(__dirname, '../assets/atlas'); fs.mkdirSync(out, { recursive: true });
  const b = await chromium.launch(); const p = await b.newPage();
  await p.goto('file://' + path.resolve(__dirname, '../333-dimensions-of-madness.html'));
  await p.waitForFunction(() => window.DIM333 && DIM333.G.state === 'title');
  const res = await p.evaluate(() => { CharAnim.bakeAll(); const o = {};
    const checker = (sheet, a, b2) => { const c = document.createElement('canvas'); c.width = sheet.width; c.height = sheet.height; const x = c.getContext('2d'); for (let y = 0; y < c.height; y += 10) for (let i = 0; i < c.width; i += 10) { x.fillStyle = ((i + y) / 10) % 2 ? a : b2; x.fillRect(i, y, 10, 10); } x.drawImage(sheet, 0, 0); return c.toDataURL(); };
    for (const id in CharAnim.atlas) { const m = CharAnim.atlas[id], meta = Object.assign({}, m); delete meta.sheet;
      o[id] = { png: m.sheet.toDataURL(), light: checker(m.sheet, '#eeeeee', '#c4c4c4'), dark: checker(m.sheet, '#2a2a2a', '#111111'), meta }; }
    return o; });
  const w = (f, d) => fs.writeFileSync(path.join(out, f), Buffer.from(d.split(',')[1], 'base64'));
  const previews = process.argv.includes('--previews');
  for (const id in res) { w(id + '.png', res[id].png); if (previews) { w('preview_' + id + '_light.png', res[id].light); w('preview_' + id + '_dark.png', res[id].dark); } fs.writeFileSync(path.join(out, id + '.json'), JSON.stringify(res[id].meta, null, 1)); console.log('exported', id); }
  await b.close();
})();
