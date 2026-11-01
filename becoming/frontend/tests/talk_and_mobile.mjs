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
  check(first.includes("You are Ralph") && first.includes("He says: What does self-reliance"), "first message carries Ralph's character and the founder's words (v2)");
  check(first.includes("No invented past") && first.includes("tell the truth briefly") && first.includes("one or two short sentences"), "v2 speech and honesty rules included");
  check(!first.includes("Zachary"), "the founder's name is not fed to the resident");
  check(calls[1].length === 3 && calls[1][1].role === "assistant" && calls[1][2].content.includes("notes for you, not said aloud"), "second turn sends the conversation so far plus fresh reading notes");
  const statusLine = await p.locator("#talk-status").textContent();
  check(statusLine.includes("fictional AI resident"), "AI disclosure shown in the interface");
  const log = await p.locator("#talk-log").innerText();
  check(log.includes("[test reply 2]") && log.includes("And what would change your mind?"), "transcript shows both sides");
  check(!log.includes("You are Ralph") && !log.includes("notes for you"), "hidden prompt and reading notes never shown in the transcript");
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
// 3) Overhear: turn-by-turn scene with a stand-in that writes one line per call.
{
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  await ctx.addInitScript(() => {
    window.__prompts = []; window.__said = [];
    window.addEventListener("resident-say", (e) => window.__said.push(e.detail.id));
    const sample = async (input) => {
      window.__prompts.push(input);
      const name = input.match(/Write only (\w+)'s next line/)[1];
      await new Promise((r) => setTimeout(r, 10));
      return { text: `${name}: *sighs* test line ${window.__prompts.length}.`, truncated: false };
    };
    window.claude = { use: async (n) => (n === "sample" ? sample : null) };
  });
  const p = await ctx.newPage();
  await p.goto(URL);
  await p.waitForFunction(() => window.village?.scene?.() === "Village");
  await p.selectOption("#overhear-genre", "friendly_dispute");
  await p.click("#overhear-btn");
  await p.waitForSelector("#talk-log .sources", { timeout: 20000 });
  const prompts = await p.evaluate(() => window.__prompts);
  check(prompts.length >= 14 && prompts.length <= 20, `one call per line, 14-20 turns (${prompts.length})`);
  check(prompts[0].includes("a friendly dispute between commitments") && prompts[0].includes("touches the village theme"), "prompt carries the chosen conversation type and a Days theme");
  check(prompts[0].includes("Long answers kill a conversation") && prompts[0].includes("never force agreement") && prompts[0].includes("No invented past"), "v2 group rules included");
  check(prompts[1].includes(": test line 1."), "each line sees the conversation so far");
  const speakers = prompts.map((q) => q.match(/Write only (\w+)'s/)[1]);
  check(speakers.every((s, k) => k === 0 || s !== speakers[k - 1]), "nobody speaks twice in a row");
  const header = await p.locator("#talk-name").textContent();
  const cast = header.split(" · ")[0].split(", ");
  check(cast.length >= 2 && cast.every((n) => ["Bernie", "Ralph", "Tony", "Mark"].includes(n)), `cast drawn from the genre's voices (${cast.join(", ")})`);
  const log = await p.locator("#talk-log").innerText();
  check(!log.includes("sighs") && !/\b\w+: \w+: /.test(log), "labels and stage directions cleaned from lines");
  check((await p.evaluate(() => window.__said.length)) === prompts.length, "each line raised a speech bubble on the map");
  check(!(await p.locator("#talk-form").isVisible()), "message box hidden while overhearing");
  const st = await p.locator("#talk-status").textContent();
  check(st.includes("Fictional AI residents") && st.includes("not part of the village's history"), "labelled as fictional AI residents and as a demo");
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
