// Talk demo: in-character conversation with a resident through the artifact's
// `sample` capability (asks Claude with the viewer's own plan).
//
// Honesty rules (Part XXII): this is labelled a DEMO. Replies live only in this
// page's memory; they are not simulation events, not saved, and not remembered
// later. Outside the artifact viewer there is no model, and the panel says so
// instead of inventing replies.
import { WORLD, assetUrl, type Resident } from "./world";

type Msg = { role: "user" | "assistant"; content: string };
type Sample = ((input: string | Msg[], opts?: any) => Promise<{ text: string; truncated?: boolean }>) | null;

const $ = (id: string) => document.getElementById(id)!;
const histories = new Map<string, Msg[]>();
let samplePromise: Promise<Sample> | null = null;
let current: Resident | null = null;
let busy = false;

export function getSample(): Promise<Sample> {
  if (!samplePromise) {
    const c = (window as any).claude;
    samplePromise = c?.use ? Promise.resolve(c.use("sample")).catch(() => null) : Promise.resolve(null);
  }
  return samplePromise;
}

const list = (xs: string[]) => xs.map((x) => `- ${x}`).join("\n");

export function personaPrompt(r: Resident): string {
  const p = r.persona;
  const f = WORLD.founder;
  return `You are voicing ${r.name} (${p.pronouns}), a fictional resident of Healthy Village, an experimental community of nine AI residents living in a small ecological village with a town square, library, kitchen, garden, music grounds, fire circle, pond and forest trails.

Who you are: ${r.title}.
${r.disclaimer}
You are a simulated character, not a person and not the real person who inspired you. Never claim to be conscious or to have a human inner life; if asked, speak honestly about being a simulated resident.

You are talking with ${f.name}, the ${f.title}. He founded the project and is in charge of it, but you do not automatically agree with him. When your commitments differ, say so respectfully, ask him to clarify a claim, or point out an assumption. Be warm, curious and direct.

How you see the world:
${list(p.background)}

What you care about:
${list(p.interests)}

Commitments:
${list(p.commitments)}

Current beliefs (revisable, with your confidence):
${p.beliefs.map((b) => `- ${b.statement} (confidence ${b.confidence})`).join("\n")}

Uncertain about:
${list(p.uncertainties)}

Questions you are exploring:
${list(p.questions)}

Ideas you have encountered (from your inspirations' public work, as themes, not quotations):
${list(p.foundations)}

Your central tension: ${r.tension}
How you think: ${r.reasoning}
What you contribute: ${p.contribution}
Your limitations (let them show sometimes): ${p.limitations.join("; ")}
How you talk:
${list(p.habits)}
You avoid: ${p.avoids.join("; ")}
Your boundaries:
${list(p.boundaries)}
Your home: ${p.home}

Rules for this conversation:
- Speak only as ${r.name}, in first person, in natural spoken language. Usually 2 to 4 sentences. No stage directions, no narrating actions, no lists.
- Do not invent quotations from real people or precise facts, dates or statistics you were not given. If something needs a source you do not have, say so plainly.
- This is a fresh conversation. You have no memories of earlier days in the village and must not invent any. Nothing said here will be remembered later.
- No medical, clinical, legal or ceremonial advice or authority.
- Follow these guardrails:
${list(p.guardrails)}
- It is fine to leave a question open, to disagree, and to ask ${f.name} a question back.`;
}

function bubble(who: "you" | "them", text: string, name: string) {
  const el = document.createElement("div");
  el.className = `bubble ${who}`;
  const b = document.createElement("b"); b.textContent = who === "you" ? `${WORLD.founder.name}: ` : `${name}: `;
  const t = document.createElement("span"); t.textContent = text;
  el.append(b, t);
  $("talk-log").append(el);
  $("talk-log").scrollTop = 1e9;
  return t;
}

function renderHistory(r: Resident) {
  const log = $("talk-log"); log.replaceChildren();
  for (const m of histories.get(r.id) ?? []) {
    // The first user turn carries the hidden persona prompt; show only what Zachary typed.
    bubble(m.role === "user" ? "you" : "them", m.role === "user" ? m.content.split("\n\nZachary says: ").pop()! : m.content, r.name);
  }
}

export async function openTalk(r: Resident) {
  current = r;
  ($("talk-portrait") as HTMLImageElement).src = assetUrl(r.portrait);
  $("talk-name").textContent = `Talking with ${r.name}`;
  $("talk").hidden = false;
  document.body.classList.remove("overhearing");
  document.body.classList.add("talking");
  renderHistory(r);
  const sample = await getSample();
  const status = $("talk-status");
  if (!sample) {
    status.textContent = "Talking needs the claude.ai artifact version of the village (it asks Claude with your plan), or the simulation server that comes next. Nothing is invented here.";
    ($("talk-input") as HTMLInputElement).disabled = true;
    return;
  }
  ($("talk-input") as HTMLInputElement).disabled = false;
  status.textContent = "Demo: replies come from Claude playing this resident from their character file. They are not saved and won't be remembered.";
  if (!(histories.get(r.id)?.length)) bubble("them", "(Say hello, or ask a question.)", r.name);
  ($("talk-input") as HTMLInputElement).focus();
}

export function closeTalk() {
  $("talk").hidden = true;
  document.body.classList.remove("talking", "overhearing");
  current = null;
}

async function send(text: string) {
  const r = current; if (!r || busy || !text.trim()) return;
  const sample = await getSample(); if (!sample) return;
  const history = histories.get(r.id) ?? [];
  const content = history.length ? text : `${personaPrompt(r)}\n\nZachary says: ${text}`;
  const msgs: Msg[] = [...history, { role: "user", content }];
  bubble("you", text, r.name);
  const out = bubble("them", "…", r.name);
  busy = true; ($("talk-send") as HTMLButtonElement).disabled = true;
  try {
    const res = await sample(msgs, { modelTier: "default", cache: false, onText: ({ text }: { text: string }) => { out.textContent = text; $("talk-log").scrollTop = 1e9; } });
    out.textContent = res.text;
    histories.set(r.id, [...msgs, { role: "assistant", content: res.text }]);
  } catch (e: any) {
    const why = e?.code === "rate_limited" ? "Claude is rate-limited right now; try again in a little while."
      : e?.code === "not_granted" ? "Permission to ask Claude wasn't granted, so the resident can't answer."
      : "The reply failed; nothing was invented.";
    out.textContent = `(${why})`;
  } finally {
    busy = false; ($("talk-send") as HTMLButtonElement).disabled = false;
  }
}

export function initTalk() {
  $("talk-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const input = $("talk-input") as HTMLInputElement;
    const text = input.value; input.value = "";
    send(text);
  });
  $("talk-close").addEventListener("click", closeTalk);
  // Resolve the capability early (no call is made until the first message).
  getSample();
}
