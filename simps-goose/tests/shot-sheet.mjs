// usage: node tests/shot-sheet.mjs <sheet> <out.png> [scale]
import { createRequire } from 'module';
const { chromium } = createRequire(import.meta.url)('playwright');
const [sheet = 'goose', out = '/tmp/sheet.png', scale = '4'] = process.argv.slice(2);
const base = process.env.BASE ?? 'http://localhost:5173';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1600, height: 1200 } });
p.on('console', (m) => { if (m.type() === 'error') console.log('console:', m.text()); });
p.on('pageerror', (e) => console.log('pageerror:', e.message));
await p.goto(`${base}/debug.html?sheet=${sheet}&scale=${scale}`);
await p.waitForFunction(() => window.__ready, null, { timeout: 20000 });
await p.locator('#sheet').screenshot({ path: out });
await b.close();
console.log('saved', out);
