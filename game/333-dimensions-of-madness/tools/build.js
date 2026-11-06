// Bundles src/*.js + assets/gen/*.png into one offline HTML file.
const fs = require('fs'), path = require('path');
const ROOT = path.resolve(__dirname, '..');
const gen = path.join(ROOT, 'assets', 'gen');
const assets = {};
for (const f of fs.readdirSync(gen).sort()) {
  if (f.endsWith('.png')) assets[f.slice(0, -4)] = 'data:image/png;base64,' + fs.readFileSync(path.join(gen, f)).toString('base64');
}
const meta = JSON.parse(fs.readFileSync(path.join(gen, 'sprites.json'), 'utf8'));
const srcDir = path.join(ROOT, 'src');
const files = fs.readdirSync(srcDir).filter(f => f.endsWith('.js')).sort();
let js = `"use strict";\nconst ASSET_DATA=${JSON.stringify(assets)};\nconst SPRITE_META=${JSON.stringify(meta)};\n`;
for (const f of files) js += `\n// ===== ${f} =====\n` + fs.readFileSync(path.join(srcDir, f), 'utf8');
const tpl = fs.readFileSync(path.join(srcDir, 'index.template.html'), 'utf8');
const out = tpl.replace('/*__GAME__*/', () => js);
const dest = path.join(ROOT, '333-dimensions-of-madness.html');
fs.writeFileSync(dest, out);
console.log('built', dest, (out.length / 1024).toFixed(0) + 'KB', files.length + ' modules');
