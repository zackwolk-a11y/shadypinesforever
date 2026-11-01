// Dialogue comparison: v1 (frozen baseline) vs v2 (revised engine).
// Same question to all nine residents, same model, same neutral system prompt,
// no tools, identical library passages. Plus one group scene each way.
// Run from frontend/:  npx tsx ../evaluation/compare.mts
import { execFile } from "node:child_process";
import { writeFileSync, readFileSync, existsSync } from "node:fs";
import { WORLD } from "../frontend/src/world.ts";
import { search, cite } from "../frontend/src/research.ts";
import { personaPrompt, scenePrompt } from "../frontend/src/dialogue/prompts_v1.ts";
import { directOpening, groupTurn, turnShape } from "../frontend/src/dialogue/prompts.ts";
import { nextSpeaker, cleanLine } from "../frontend/src/dialogue/engine.ts";
import { summarize, summarizeGroup, measure } from "../frontend/src/dialogue/evaluate.ts";

const QUESTION = "Do people actually have free will, or does it just feel that way?";
const SYSTEM = "You are Claude.";
const DATE = "2026-11-01";

function ask(prompt: string): Promise<{ text: string; cost: number }> {
  return new Promise((resolve, reject) => {
    execFile("claude", ["-p", prompt, "--system-prompt", SYSTEM, "--tools", "", "--no-session-persistence",
      "--strict-mcp-config", "--output-format", "json"], { maxBuffer: 1 << 24, timeout: 240_000 }, (err, out) => {
      if (err) return reject(err);
      const j = JSON.parse(out); resolve({ text: String(j.result ?? "").trim(), cost: j.total_cost_usd ?? 0 });
    });
  });
}

async function pool<T>(jobs: (() => Promise<T>)[], n = 4): Promise<T[]> {
  const out: T[] = new Array(jobs.length); let i = 0;
  await Promise.all(Array.from({ length: n }, async () => { while (i < jobs.length) { const k = i++; out[k] = await jobs[k](); } }));
  return out;
}

// REUSE_V1=1 reuses baseline outputs from an earlier run (re-scored with the current evaluator).
const LABEL = process.env.LABEL ?? "v2";
const prior = process.env.REUSE_V1 && existsSync(new URL(`./results/${DATE}_compare.json`, import.meta.url))
  ? JSON.parse(readFileSync(new URL(`./results/${DATE}_compare.json`, import.meta.url), "utf8")) : null;
let cost = 0;
const singles = await pool(WORLD.residents.map((r) => async () => {
  const passages = search(`${QUESTION} choice freedom responsibility conditions`, r, 3);
  const research = passages.length ? `\n\nResults of your search_library for this question:\n${passages.map(cite).join("\n\n")}` : "";
  const v1p = `${personaPrompt(r)}${research}\n\nZachary says: ${QUESTION}`;
  const v2p = directOpening(r, QUESTION, passages);
  const old = prior?.singles.find((x: any) => x.resident === r.name);
  const [a, b] = await Promise.all([old ? Promise.resolve({ text: old.v1, cost: 0 }) : ask(v1p), ask(v2p)]);
  cost += a.cost + b.cost;
  console.error(`done ${r.name}`);
  return { resident: r.name, passages: passages.map((p) => p.id), v1: a.text, v2: b.text };
}));

// Group scene: same cast, theme and setting both ways.
const cast = ["bernie", "ralph", "anna"].map((id) => WORLD.residents.find((r) => r.id === id)!);
const genre = WORLD.patterns.genres.find((g) => g.id === "friendly_dispute")!;
const theme = WORLD.patterns.topics.find((t) => t.day === 30)!.title; // "The Causes of a Choice"
const setting = "the Community Kitchen", time = "Morning";
const situation = "Over breakfast, the garden rota is being redrawn; last month one neighbour said no to a shift and is being asked again. The question underneath: how free is anyone's choice?";
const v1scene = prior ? { text: prior.group.v1_raw as string, cost: 0 } : await ask(scenePrompt({ genre, cast, setting, time, theme, consulted: [] }));
cost += v1scene.cost;
const v1lines = v1scene.text.split("\n").map((l) => l.trim()).map((l) => l.match(/^([A-Za-z]+):\s*(.+)$/)).filter((m) => m && m[1] !== "Scene").map((m) => ({ speaker: m![1], text: m![2] }));

const v2lines: { speaker: string; text: string }[] = [];
const maxTurns = Number(process.env.TURNS ?? 16);
let seed = 7; const rand = () => ((seed = (seed * 9301 + 49297) % 233280) / 233280);
for (let turn = 0; turn < maxTurns; turn++) {
  const speaker = turn === 0 ? cast[0] : nextSpeaker(cast, v2lines, rand);
  const last = v2lines[v2lines.length - 1]?.text ?? "";
  const passages = search(`${theme} ${situation} ${last}`, speaker, 2);
  const res = await ask(groupTurn({ speaker, cast, setting, time, situation, transcript: v2lines, passages, turn, maxTurns, shape: turnShape(rand) }));
  cost += res.cost;
  v2lines.push({ speaker: speaker.name, text: cleanLine(res.text, speaker.name) });
  console.error(`turn ${turn + 1}: ${speaker.name}`);
}

const report = {
  date: DATE, question: QUESTION, system: SYSTEM, model: "Claude Code default model (same for both)", notional_cost_usd: Math.round(cost * 100) / 100,
  singles: singles.map((s) => ({ ...s, v1_metrics: measure(s.v1), v2_metrics: measure(s.v2) })),
  single_summary: { v1: summarize(singles.map((s) => s.v1)), v2: summarize(singles.map((s) => s.v2)) },
  group: { cast: cast.map((c) => c.name), theme, setting, situation, v1_raw: v1scene.text, v1: v1lines, v2: v2lines,
    v1_summary: summarizeGroup(v1lines), v2_summary: summarizeGroup(v2lines) },
};
writeFileSync(new URL(`./results/${DATE}_compare${prior ? "_" + LABEL : ""}.json`, import.meta.url), JSON.stringify(report, null, 1));
console.log(JSON.stringify({ single_summary: report.single_summary, group_v1: report.group.v1_summary, group_v2: report.group.v2_summary, cost: report.notional_cost_usd }, null, 1));
