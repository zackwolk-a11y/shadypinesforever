// "Overhear a village conversation": a generated DEMO scene between residents,
// in the conversation styles the Founder chose (canon/curriculum/conversation_patterns.yaml,
// derived from the authored Days 1-75). Uses the artifact's `sample` capability.
//
// Honesty (Part XXII): this is category 2 ("a model generating a conversation after
// a button press"), not the persistent simulation. It is labelled as such, is not
// stored, and is not remembered by anyone.
import { WORLD, assetUrl, type Resident } from "./world";
import { getSample } from "./talk";

const $ = (id: string) => document.getElementById(id)!;
const pick = <T,>(xs: T[]) => xs[Math.floor(Math.random() * xs.length)];
const shuffle = <T,>(xs: T[]) => [...xs].sort(() => Math.random() - 0.5);
const ZONE_NAMES: Record<string, string> = Object.fromEntries(WORLD.zones.map((z) => [z.id, z.name]));
const PLACE = (id: string) => ZONE_NAMES[id] ?? ({ kitchen: "the Community Kitchen", library: "the Community Library", town_hall: "the Gathering Lodge" } as Record<string, string>)[id] ?? id;
const TIMES = ["Morning", "Late Morning", "Afternoon", "Late Afternoon", "Evening"];
let busy = false;

export interface ScenePlan { genre: (typeof WORLD.patterns.genres)[number]; cast: Resident[]; setting: string; time: string; theme: string }

export function planScene(genreId?: string): ScenePlan {
  const genres = WORLD.patterns.genres;
  const genre = genres.find((g) => g.id === genreId) ?? pick(genres);
  const size = Math.random() < 0.5 ? 2 : 3;
  const cast = shuffle(genre.typical_voices).slice(0, size).map((id) => WORLD.residents.find((r) => r.id === id)!);
  const day = pick(genre.example_days);
  const theme = WORLD.patterns.topics.find((t) => t.day === day)!.title;
  const time = genre.id === "evening_reflection" ? "Evening" : pick(TIMES);
  return { genre, cast, setting: PLACE(pick(genre.settings)), time, theme };
}

export function scenePrompt(p: ScenePlan): string {
  const c = WORLD.patterns.craft;
  const who = p.cast.map((r) => `${r.name} (${r.persona.pronouns}), ${r.title}.
  Tension: ${r.tension}
  How they talk: ${r.persona.habits.join(" ")}
  Signature move: ${WORLD.patterns.moves[r.id]}
  Current beliefs: ${r.persona.beliefs.slice(0, 3).map((b) => `${b.statement} (confidence ${b.confidence})`).join(" | ")}
  Boundaries: ${r.persona.boundaries.join(" ")}`).join("\n\n");
  const names = p.cast.map((r) => r.name).join(", ");
  return `Write one short scene of dialogue between fictional residents of Healthy Village, a small ecological village of nine simulated AI residents. The residents are simulated characters, not real people and not the real people who inspired them; never quote real people.

Scene: ${p.time}, at ${p.setting}.
Conversation type: ${p.genre.name}. ${p.genre.shape}
Starting theme (one of the village's story titles, use only as loose inspiration, do not retell any story): "${p.theme}"

Cast:
${who}

Style (follow closely):
- ${c.ordinary_hooks}
- ${c.turn_length}
- ${c.humor}
- Use moves like: ${c.reasoning_moves.join(" ")}
- ${c.endings}
- Avoid: ${c.what_to_avoid.join("; ")}.
- Each resident sounds distinct and stays true to their tension and boundaries. Someone should concede something specific; someone should push back.
- They have no shared memories to cite: do not invent past events or earlier conversations.

Output format, exactly:
First line: "Scene: " followed by one plain sentence naming the ordinary situation.
Then 14 to 22 lines, each "Name: words", using only these names: ${names}.
No other narration, no stage directions, no headings, nothing after the last line.`;
}

function bubble(name: string, text: string) {
  const el = document.createElement("div");
  el.className = "bubble them";
  const b = document.createElement("b"); b.textContent = `${name}: `;
  const t = document.createElement("span"); t.textContent = text;
  el.append(b, t); $("talk-log").append(el); $("talk-log").scrollTop = 1e9;
}

export async function startOverhear(genreId?: string) {
  if (busy) return;
  const plan = planScene(genreId);
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
  status.textContent = `Demo scene (${plan.genre.name}). Generated now from the residents' character files in the style you chose. Not part of the village's history; nobody will remember it.`;
  busy = true;
  const shown = new Set<number>();
  const names = new Map(plan.cast.map((r) => [r.name, r]));
  const render = (full: string, final: boolean) => {
    const lines = full.split("\n").map((l) => l.trim()).filter(Boolean);
    const ready = final ? lines.length : lines.length - 1; // last line may still be streaming
    for (let i = 0; i < ready; i++) {
      if (shown.has(i)) continue; shown.add(i);
      const m = lines[i].match(/^([A-Za-z]+):\s*(.+)$/);
      if (!m) continue;
      if (m[1] === "Scene") { const s = document.createElement("p"); s.className = "muted"; s.textContent = m[2]; log.append(s); continue; }
      const r = names.get(m[1]); if (!r) continue;
      bubble(r.name, m[2]);
      window.dispatchEvent(new CustomEvent("resident-say", { detail: { id: r.id, text: m[2] } }));
    }
  };
  try {
    const res = await sample(scenePrompt(plan), { modelTier: "default", cache: false, onText: ({ text }: { text: string }) => render(text, false) });
    render(res.text, true);
  } catch (e: any) {
    const p = document.createElement("p"); p.className = "muted";
    p.textContent = e?.code === "rate_limited" ? "(Claude is rate-limited right now; try again shortly.)"
      : e?.code === "not_granted" ? "(Permission to ask Claude wasn't granted.)" : "(The scene failed to generate; nothing was invented.)";
    log.append(p);
  } finally { busy = false; }
}

export function initOverhear() {
  const sel = $("overhear-genre") as HTMLSelectElement;
  for (const g of WORLD.patterns.genres) { const o = document.createElement("option"); o.value = g.id; o.textContent = g.name; sel.append(o); }
  $("overhear-btn").addEventListener("click", () => startOverhear(sel.value || undefined));
}
