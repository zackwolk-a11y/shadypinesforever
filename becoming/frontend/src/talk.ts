// Talk demo: in-character conversation with a resident through the artifact's
// `sample` capability (asks Claude with the viewer's own plan).
//
// Honesty rules (Part XXII): this is labelled a DEMO. Replies live only in this
// page's memory; they are not simulation events, not saved, and not remembered
// later. Outside the artifact viewer there is no model, and the panel says so
// instead of inventing replies.
import { WORLD, assetUrl, type Resident } from "./world";
import { search, cite, sourceList } from "./research";
import { directOpening, directFollowUp, NOTES_MARK } from "./dialogue/prompts";
import { cleanLine } from "./dialogue/engine";

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

/** Prompts live in dialogue/prompts.ts (v2). The pre-revision prompt is frozen in dialogue/prompts_v1.ts. */

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
    // Show only what the founder typed: strip the hidden setup and the per-turn reading notes.
    const said = m.content.includes("\n\nHe says: ") ? m.content.split("\n\nHe says: ").pop()!.split("\n\nReply as ")[0] : m.content.split(NOTES_MARK)[0];
    bubble(m.role === "user" ? "you" : "them", m.role === "user" ? said : m.content, r.name);
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
  status.textContent = `${r.name} is a fictional AI resident, voiced by Claude from their character file and research notes. Demo: this conversation isn't saved or remembered.`;
  if (!(histories.get(r.id)?.length)) { const hint = document.createElement("p"); hint.className = "muted small"; hint.textContent = "Say something to start."; $("talk-log").append(hint); }
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
  // Fresh reading for every turn: what they've read that bears on what was just said.
  const lastReply = history.length ? history[history.length - 1].content : "";
  const reading = search(`${text} ${lastReply}`, r, history.length ? 2 : 3);
  const content = history.length ? directFollowUp(text, reading) : directOpening(r, text, reading);
  const consulted: string[] = reading.flatMap((p) => p.codes).concat(reading.some((p) => p.kind === "founder_note") ? ["__notes"] : []);
  const msgs: Msg[] = [...history, { role: "user", content }];
  bubble("you", text, r.name);
  const out = bubble("them", "…", r.name);
  busy = true; ($("talk-send") as HTMLButtonElement).disabled = true;
  const tools = [{
    name: "search_library",
    description: `Search what ${r.name} has read: research notes and source excerpts, each with source codes. Returns up to 4 passages.`,
    inputSchema: { type: "object", properties: { query: { type: "string", description: "What to look up, in a few words" } }, required: ["query"] },
    execute: async ({ query }: { query: string }) => {
      const found = search(String(query ?? ""), r, 4);
      for (const p of found) consulted.push(...p.codes, p.kind === "founder_note" ? "__notes" : "__src");
      (window as any).__lastSearch = { query, ids: found.map((p) => p.id) };
      return found.length ? found.map(cite).join("\n\n---\n\n") : "Nothing in your library matches that.";
    },
  }];
  try {
    const res = await sample(msgs, { modelTier: "default", cache: false, tools, onText: ({ text }: { text: string }) => { out.textContent = text; $("talk-log").scrollTop = 1e9; } });
    const said = cleanLine(res.text, r.name);
    out.textContent = said;
    showSources(said, consulted);
    histories.set(r.id, [...msgs, { role: "assistant", content: said }]);
  } catch (e: any) {
    const why = e?.code === "rate_limited" ? "Claude is rate-limited right now; try again in a little while."
      : e?.code === "not_granted" ? "Permission to ask Claude wasn't granted, so the resident can't answer."
      : "The reply failed; nothing was invented.";
    out.textContent = `(${why})`;
  } finally {
    busy = false; ($("talk-send") as HTMLButtonElement).disabled = false;
  }
}

/** Under a reply: the sources it cited (prominent) and the rest it consulted (folded). */
export function showSources(reply: string, consulted: string[]) {
  const citedCodes = [...reply.matchAll(/\[([A-Z]{1,3}\d{1,2})\]/g)].map((m) => m[1]);
  const cited = sourceList(citedCodes);
  const more = sourceList(consulted.filter((c) => !c.startsWith("__") && !citedCodes.includes(c)));
  const notes = consulted.includes("__notes");
  const box = document.createElement("div"); box.className = "sources";
  const link = (s: ReturnType<typeof sourceList>[number]) => {
    const a = document.createElement(s.url ? "a" : "span") as HTMLAnchorElement;
    a.textContent = `[${s.code}] ${s.label}${s.date ? ` (${s.date})` : ""}`;
    if (s.url) { a.href = s.url; a.target = "_blank"; a.rel = "noopener"; }
    return a;
  };
  if (!cited.length && !more.length) { box.textContent = "No library sources consulted for this reply."; box.classList.add("muted"); }
  if (cited.length) {
    box.append(document.createTextNode("Cited: "));
    cited.forEach((s, i) => { box.append(link(s)); if (i < cited.length - 1) box.append("; "); });
  }
  if (more.length) {
    const d = document.createElement("details");
    const sm = document.createElement("summary");
    sm.textContent = `${cited.length ? "Also consulted" : "Consulted"} ${more.length} source${more.length > 1 ? "s" : ""}${notes ? " (via the Founder's research notes)" : ""}`;
    d.append(sm);
    more.forEach((s, i) => { d.append(link(s)); if (i < more.length - 1) d.append("; "); });
    box.append(d);
  }
  $("talk-log").append(box); $("talk-log").scrollTop = 1e9;
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
