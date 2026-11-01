// Visual-world acceptance test (Part XXIV): walk the avatar from the town
// square to every building door, enter it, and leave again, in a real browser.
// Usage: npm run build && (npm run preview &) && npm run test:e2e
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const URL = process.env.VILLAGE_URL ?? "http://localhost:4173/";
const shots = process.env.SHOTS_DIR;
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
await page.goto(URL);
await page.waitForFunction(() => window.village?.scene?.() === "Village", null, { timeout: 30000 });
if (shots) await page.screenshot({ path: `${shots}/village_start.png` });

const doors = await page.evaluate(() => window.village.doors);
const buildings = [...new Map(doors.map((d) => [d.building, d])).values()];
const results = [];
for (const d of buildings) {
  const ok = await page.evaluate(([x, y]) => window.village.walkTo(x, y), [d.x, d.y]);
  if (!ok) { results.push([d.building, "NO PATH"]); continue; }
  await page.waitForFunction(() => window.village.arrived(), null, { timeout: 60000 });
  const tile = await page.evaluate(() => window.village.tile());
  if (tile.x !== d.x || tile.y !== d.y) { results.push([d.building, `stopped at ${tile.x},${tile.y}`]); continue; }
  await page.waitForTimeout(50);
  await page.evaluate(() => window.village.enter());
  await page.waitForFunction((b) => window.village?.scene?.() === "Interior" && window.village.inside === b, d.building, { timeout: 10000 });
  if (shots && d.building === "library") await page.screenshot({ path: `${shots}/interior_library.png` });
  await page.evaluate(() => window.village.leave());
  await page.waitForFunction(() => window.village?.scene?.() === "Village", null, { timeout: 10000 });
  results.push([d.building, "entered and left"]);
}
if (shots) await page.screenshot({ path: `${shots}/village_end.png` });
await browser.close();

for (const [b, r] of results) console.log(`${r === "entered and left" ? "PASS" : "FAIL"}  ${b}: ${r}`);
if (errors.length) console.log("page errors:", errors);
const failed = results.filter(([, r]) => r !== "entered and left").length + errors.length;
console.log(`${results.length - failed}/${results.length} buildings OK`);
process.exit(failed ? 1 : 0);
