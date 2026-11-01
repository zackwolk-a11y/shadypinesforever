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
// 3) Overhear: generated demo scene with a stand-in that streams a fake scene.
{
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  await ctx.addInitScript(() => {
    window.__prompts = []; window.__said = [];
    window.addEventListener("resident-say", (e) => window.__said.push(e.detail.id));
    const sample = async (input, opts) => {
      window.__prompts.push(input);
      const names = input.match(/using only these names: (.+)\./)[1].split(", ");
      let text = "Scene: Two baskets wait by the kitchen door.\n";
      for (let i = 0; i < 6; i++) {
        text += `${names[i % names.length]}: test line ${i + 1}.\n`;
        opts?.onText?.({ text, delta: "" });
        await new Promise((r) => setTimeout(r, 30));
      }
      text += "Narrator: this must be ignored\n";
      return { text, truncated: false };
    };
    window.claude = { use: async (n) => (n === "sample" ? sample : null) };
  });
  const p = await ctx.newPage();
  await p.goto(URL);
  await p.waitForFunction(() => window.village?.scene?.() === "Village");
  await p.selectOption("#overhear-genre", "friendly_dispute");
  await p.click("#overhear-btn");
  await p.waitForFunction(() => document.querySelectorAll("#talk-log .bubble").length === 6, null, { timeout: 10000 });
  const prompt = await p.evaluate(() => window.__prompts[0]);
  check(prompt.includes("A friendly dispute between commitments") && prompt.includes("Starting theme"), "prompt carries the chosen conversation type and a Days theme");
  check(prompt.includes("Concede specifically") && prompt.includes("No moral lesson"), "prompt carries the craft rules from Days 1-75");
  check(prompt.includes("do not invent past events"), "prompt forbids invented shared memories");
  const header = await p.locator("#talk-name").textContent();
  const cast = header.split(" · ")[0].split(", ");
  check(cast.length >= 2 && cast.every((n) => ["Bernie", "Ralph", "Tony", "Mark"].includes(n)), `cast drawn from the genre's voices (${cast.join(", ")})`);
  const log = await p.locator("#talk-log").innerText();
  check(log.includes("Two baskets wait") && !log.includes("must be ignored"), "scene line shown; non-cast lines ignored");
  check((await p.evaluate(() => window.__said.length)) === 6, "each line raised a speech bubble on the map");
  check(!(await p.locator("#talk-form").isVisible()), "message box hidden while overhearing");
  check((await p.locator("#talk-status").textContent()).includes("Not part of the village's history"), "labelled as a demo, not history");
  check(prompt.includes("What the residents have read") && /\[[A-Z]{1,3}\d{1,2}\]/.test(prompt), "overheard scene carries each resident's reading with source codes");
  if (shots) await p.screenshot({ path: `${shots}/overhear.png` });
  await ctx.close();
  const ctx2 = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const p2 = await ctx2.newPage(); await p2.goto(URL);
  await p2.waitForFunction(() => window.village?.scene?.() === "Village");
  await p2.click("#overhear-btn");
  await p2.waitForSelector("#talk:not([hidden])");
  check((await p2.locator("#talk-status").textContent()).includes("Nothing is invented"), "without Claude, overhearing says so");
  await ctx2.close();
}
// 4) Research: the library tool is offered, used, and its sources shown.
{
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  await ctx.addInitScript(() => {
    window.__tool = null;
    const sample = async (input, opts) => {
      const t = opts?.tools?.find((x) => x.name === "search_library");
      window.__tool = !!t;
      let found = "";
      if (t) found = await t.execute({ query: "veterans care agreement McCain compromise" });
      window.__found = found;
      const code = (found.match(/\[(B\d+)\]/) || [])[1] || "none";
      const text = `From what I've read about that agreement [${code}], an imperfect deal can still be progress.`;
      opts?.onText?.({ text, delta: text });
      return { text, truncated: false };
    };
    window.claude = { use: async (n) => (n === "sample" ? sample : null) };
  });
  const p = await ctx.newPage();
  await p.goto(URL);
  await p.waitForFunction(() => window.village?.scene?.() === "Village");
  const hits = await p.evaluate(() => window.villageResearch.search("veterans care agreement McCain", "bernie"));
  check(hits.length > 0 && hits.some((h) => h.codes.includes("B8")), `search finds Bernie's McCain passage [B8] (${hits.map((h) => h.id).join(", ")})`);
  const ralph = await p.evaluate(() => window.villageResearch.search("Walden possessions deliberate living", "ralph"));
  check(ralph.length > 0 && ralph.every((h) => h.id.includes("ralph") || h.codes.some((c) => c.startsWith("R"))), "Ralph's search stays within what Ralph has read");
  await p.getByRole("button", { name: "Bernie", exact: true }).click();
  await p.getByRole("button", { name: "Talk with Bernie" }).first().click();
  await p.fill("#talk-input", "Was the veterans deal with McCain worth it?");
  await p.press("#talk-input", "Enter");
  await p.waitForSelector("#talk-log .sources", { timeout: 10000 });
  check(await p.evaluate(() => window.__tool), "search_library tool offered to the resident");
  check((await p.evaluate(() => window.__found)).includes("FOUNDER RESEARCH NOTE"), "tool results are labelled as Founder research notes");
  const src = await p.locator("#talk-log .sources").innerText();
  check(src.startsWith("Cited:") && (await p.locator("#talk-log .sources details").count()) === 1, `cited source shown first, the rest folded (${src.slice(0, 80)}…)`);
  const all = await p.locator("#talk-log .sources").evaluate((e) => e.textContent);
  check(all.includes("[B8]") && all.includes("Congressional Record"), "the McCain agreement source [B8] is among the sources");
  check(await p.locator("#talk-log .sources a[href*='govinfo.gov']").count() > 0, "source links to the original document");
  if (shots) await p.screenshot({ path: `${shots}/talk_research.png` });
  await ctx.close();
}
await browser.close();
console.log(failures ? `${failures} check(s) failed` : "all talk/mobile checks passed");
process.exit(failures ? 1 : 0);
