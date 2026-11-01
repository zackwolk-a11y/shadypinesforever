// "Overhear a village conversation": a generated DEMO scene between residents,
// in the conversation styles the Founder chose (canon/curriculum/conversation_patterns.yaml,
// derived from the authored Days 1-75). Uses the artifact's `sample` capability.
//
// Honesty (Part XXII): this is category 2 ("a model generating a conversation after
// a button press"), not the persistent simulation. It is labelled as such, is not
// stored, and is not remembered by anyone.
import { WORLD, assetUrl, type Resident } from "./world";
import { getSample, showSources } from "./talk";
import { search } from "./research";
import { groupTurn, type Line } from "./dialogue/prompts";
import { nextSpeaker, cleanLine, sceneLength } from "./dialogue/engine";

const $ = (id: string) => document.getElementById(id)!;
const pick = <T,>(xs: T[]) => xs[Math.floor(Math.random() * xs.length)];
const shuffle = <T,>(xs: T[]) => [...xs].sort(() => Math.random() - 0.5);
const ZONE_NAMES: Record<string, string> = Object.fromEntries(WORLD.zones.map((z) => [z.id, z.name]));
const PLACE = (id: string) => ZONE_NAMES[id] ?? ({ kitchen: "the Community Kitchen", library: "the Community Library", town_hall: "the Gathering Lodge" } as Record<string, string>)[id] ?? id;
const TIMES = ["Morning", "Late Morning", "Afternoon", "Late Afternoon", "Evening"];
let busy = false;

export interface ScenePlan { genre: (typeof WORLD.patterns.genres)[number]; cast: Resident[]; setting: string; time: string; theme: string; consulted: string[] }

export function planScene(genreId?: string): ScenePlan {
  const genres = WORLD.patterns.genres;
  const genre = genres.find((g) => g.id === genreId) ?? pick(genres);
  const size = Math.random() < 0.5 ? 2 : 3;
  const cast = shuffle(genre.typical_voices).slice(0, size).map((id) => WORLD.residents.find((r) => r.id === id)!);
  const day = pick(genre.example_days);
  const theme = WORLD.patterns.topics.find((t) => t.day === day)!.title;
  const time = genre.id === "evening_reflection" ? "Evening" : pick(TIMES);
  return { genre, cast, setting: PLACE(pick(genre.settings)), time, theme, consulted: [] };
}

/** The pre-revision one-call scene prompt is frozen in dialogue/prompts_v1.ts. */

function bubble(name: string, text: string) {
  const el = document.createElement("div");
  el.className = "bubble them";
  const b = document.createElement("b"); b.textContent = `${name}: `;
  const t = document.createElement("span"); t.textContent = text;
  el.append(b, t); $("talk-log").append(el); $("talk-log").scrollTop = 1e9;
}

let runId = 0;

/** Turn-by-turn scene: each line is written by one resident who sees the conversation so far. */
export async function startOverhear(genreId?: string) {
  if (busy) return;
  const plan = planScene(genreId);
  const my = ++runId;
  const log = $("talk-log"); log.replaceChildren();
  ($("talk-portrait") as HTMLImageElement).src = assetUrl(plan.cast[0].portrait);
  $("talk-name").textContent = `${plan.cast.map((r) => r.name).join(", ")} · ${plan.time}, ${plan.setting}`;
  $("talk").hidden = false; document.body.classList.add("talking", "overhearing");
  const status = $("talk-status");
  const sample = await getSample();
  if (!sample) {
    status.textContent = "Overhearing needs the claude.ai artifact version (it asks Claude with your plan), or the simulation server that comes next. Nothing is invented here.";
    return;
  }
  status.textContent = `Fictional AI residents, voiced by Claude one line at a time from their character files and reading. Demo scene (${plan.genre.name}); not part of the village's history and not remembered. Close to stop.`;
  busy = true;
  const situation = `An ordinary ${plan.time.toLowerCase()} at ${plan.setting}. Something small and practical in front of you touches the village theme "${plan.theme}". The kind of conversation: ${plan.genre.name.toLowerCase()} (${plan.genre.shape})`;
  const transcript: Line[] = [];
  const maxTurns = sceneLength();
  const typing = document.createElement("p"); typing.className = "muted small";
  try {
    for (let turn = 0; turn < maxTurns; turn++) {
      if (my !== runId || $("talk").hidden) break; // closed or restarted
      const speaker = turn === 0 ? plan.cast[0] : nextSpeaker(plan.cast, transcript);
      const reading = search(`${plan.theme} ${transcript[transcript.length - 1]?.text ?? plan.genre.shape}`, speaker, 2);
      plan.consulted.push(...reading.flatMap((p) => p.codes));
      if (reading.some((p) => p.kind === "founder_note")) plan.consulted.push("__notes");
      typing.textContent = `${speaker.name} is speaking…`; log.append(typing);
      const res = await sample(groupTurn({ speaker, cast: plan.cast, setting: plan.setting, time: plan.time, situation, transcript, passages: reading, turn, maxTurns }), { modelTier: "default", cache: false });
      typing.remove();
      if (my !== runId) break;
      const text = cleanLine(res.text, speaker.name);
      if (!text) continue;
      transcript.push({ speaker: speaker.name, text });
      bubble(speaker.name, text);
      window.dispatchEvent(new CustomEvent("resident-say", { detail: { id: speaker.id, text } }));
    }
    if (my === runId && transcript.length) showSources(transcript.map((l) => l.text).join(" "), plan.consulted);
  } catch (e: any) {
    typing.remove();
    const p = document.createElement("p"); p.className = "muted";
    p.textContent = e?.code === "rate_limited" ? "(Claude is rate-limited right now; the scene stopped. Try again shortly.)"
      : e?.code === "not_granted" ? "(Permission to ask Claude wasn't granted.)" : "(The scene stopped: a line failed to generate. Nothing was invented.)";
    log.append(p);
  } finally { if (my === runId) busy = false; }
}

export function initOverhear() {
  const sel = $("overhear-genre") as HTMLSelectElement;
  for (const g of WORLD.patterns.genres) { const o = document.createElement("option"); o.value = g.id; o.textContent = g.name; sel.append(o); }
  $("overhear-btn").addEventListener("click", () => startOverhear(sel.value || undefined));
}
