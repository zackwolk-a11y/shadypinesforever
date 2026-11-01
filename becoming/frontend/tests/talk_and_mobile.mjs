// Mobile controls + Talk flow. Uses a TEST-ONLY stand-in for the artifact's
// `sample` capability to check what the page sends; real replies come only
// from Claude in the artifact viewer.
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium, devices } = require("playwright");
const URL = process.env.VILLAGE_URL ?? "http://localhost:4173/";
const shots = process.env.SHOTS_DIR;
let failures = 0;
const check = (ok, msg) => { console.log(`${ok ? "PASS" : "FAIL"}  ${msg}`); if (!ok) failures++; };
const browser = await chromium.launch();

// 1) Phone: pad movement, Talk button, honest fallback without the capability.
{
  const ctx = await browser.newContext({ ...devices["iPhone 13"] });
  const p = await ctx.newPage();
  await p.goto(URL);
  await p.waitForFunction(() => window.village?.scene?.() === "Village");
  check(await p.locator("#dpad").isVisible(), "movement pad visible on phone");
  const before = await p.evaluate(() => window.village.tile());
  const up = p.locator('#dpad [data-dir="up"]');
  const box = await up.boundingBox();
  await p.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await p.mouse.down(); await p.waitForTimeout(700); await p.mouse.up();
  const after = await p.evaluate(() => window.village.tile());
  check(after.y < before.y, `holding ▲ moves up (${before.y} → ${after.y})`);
  await p.evaluate(() => window.village.walkTo(33, 50)); // two tiles in front of Mao
  await p.waitForFunction(() => window.village.arrived(), null, { timeout: 60000 });
  await p.waitForTimeout(200);
  check(await p.locator("#talk-btn").isVisible(), "Talk button appears near a resident");
  check((await p.locator("#talk-btn").textContent()).includes("Mao"), "Talk button names the nearby resident");
  await p.locator("#talk-btn").tap();
  await p.waitForSelector("#talk:not([hidden])");
  const status = await p.locator("#talk-status").textContent();
  check(status.includes("Nothing is invented"), "without Claude, Talk says so instead of inventing replies");
  check(await p.locator("#talk-input").isDisabled(), "input disabled without Claude");
  if (shots) await p.screenshot({ path: `${shots}/phone_talk_unavailable.png` });
  await p.locator("#talk-close").tap();
  await ctx.close();
}

// 2) Desktop with a stand-in `sample`: prompt, history and streaming display.
{
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  await ctx.addInitScript(() => {
    window.__calls = [];
    const sample = async (msgs, opts) => {
      window.__calls.push(msgs);
      const text = `[test reply ${window.__calls.length}]`;
      opts?.onText?.({ text, delta: text });
      return { text, truncated: false };
    };
    window.claude = { use: async (name) => (name === "sample" ? sample : null) };
  });
  const p = await ctx.newPage();
  await p.goto(URL);
  await p.waitForFunction(() => window.village?.scene?.() === "Village");
  await p.getByRole("button", { name: "Ralph", exact: true }).click();
  await p.getByRole("button", { name: "Talk with Ralph" }).first().click();
  await p.waitForSelector("#talk:not([hidden])");
  check(await p.locator("#talk-input").isEnabled(), "input enabled when Claude is available");
  await p.fill("#talk-input", "What does self-reliance owe the people who cook your meals?");
  await p.press("#talk-input", "Enter");
  await p.waitForFunction(() => window.__calls.length === 1);
  await p.fill("#talk-input", "And what would change your mind?");
  await p.locator("#talk-send").click();
  await p.waitForFunction(() => window.__calls.length === 2);
  const calls = await p.evaluate(() => window.__calls);
  const first = calls[0][0].content;
  check(first.includes("You are voicing Ralph") && first.includes("Zachary says: What does self-reliance"), "first message carries Ralph's character and Zachary's words");
  check(first.includes("You have no memories of earlier days") && first.includes("Never claim to be conscious"), "honesty rules included");
  check(calls[1].length === 3 && calls[1][1].role === "assistant", "second turn sends the conversation so far");
  const log = await p.locator("#talk-log").innerText();
  check(log.includes("[test reply 2]") && log.includes("And what would change your mind?"), "transcript shows both sides");
  check(!log.includes("You are voicing"), "hidden character prompt never shown in the transcript");
  // typing letters must not move the avatar or trigger doors
  await p.waitForFunction(() => window.village.arrived(), null, { timeout: 60000 });
  await p.waitForTimeout(300);
  const t0 = await p.evaluate(() => window.village.tile());
  await p.fill("#talk-input", ""); await p.type("#talk-input", "wasdwasdet", { delay: 30 });
  await p.waitForTimeout(300);
  const t1 = await p.evaluate(() => window.village.tile());
  const typed = await p.inputValue("#talk-input");
  check(t0.x === t1.x && t0.y === t1.y && typed === "wasdwasdet", `typing WASD/E/T goes into the chat, not the game (tile ${t0.x},${t0.y}→${t1.x},${t1.y}; typed "${typed}")`);
  if (shots) await p.screenshot({ path: `${shots}/desktop_talk.png` });
  await ctx.close();
}
await browser.close();
console.log(failures ? `${failures} check(s) failed` : "all talk/mobile checks passed");
process.exit(failures ? 1 : 0);
