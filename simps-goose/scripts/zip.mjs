// Packages the project (source, docs, assets, screenshots, dist) into release/simps-goose-slice-v0.1.zip
import { execSync } from 'child_process';
import fs from 'fs';
fs.mkdirSync('release', { recursive: true });
const out = 'release/simps-goose-on-the-loose-v1.0.zip';
if (fs.existsSync(out)) fs.unlinkSync(out);
execSync(`zip -rq ${out} README.md ART_BIBLE.md TESTING.md PREPRODUCTION.md package.json package-lock.json tsconfig.json vite.config.ts index.html debug.html debug-audio.html .gitignore src tests scripts assets screenshots dist`, { stdio: 'inherit' });
console.log(out, (fs.statSync(out).size / 1e6).toFixed(1) + ' MB');
