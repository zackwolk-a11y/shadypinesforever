// The residents' research library: BM25 search over passages with provenance.
// founder_note = the Founder's research summaries (not the sources' own words);
// source_text  = short excerpts fetched from the original sources.
import lib from "./generated/library.json";
import { WORLD, type Resident } from "./world";

export interface Passage { id: string; kind: "founder_note" | "source_text"; resident: string; codes: string[]; text: string; provenance: string }
export interface SourceInfo { label: string; url: string | null; date: string | null; role: string }
export const LIBRARY = lib as unknown as { built: string; passages: Passage[]; sources: Record<string, SourceInfo> };

const STOP = new Set("a an and are as at be but by for from has have he her his i in is it its not of on or she that the their them they this to was we what when which who will with you your does do how why".split(" "));
const tok = (s: string) => s.toLowerCase().replace(/[^a-z0-9\s]/g, " ").split(/\s+/).filter((w) => w.length > 2 && !STOP.has(w));
const docs = LIBRARY.passages.map((p) => tok(p.text));
const df = new Map<string, number>();
for (const d of docs) for (const w of new Set(d)) df.set(w, (df.get(w) ?? 0) + 1);
const avg = docs.reduce((a, d) => a + d.length, 0) / Math.max(1, docs.length);

/** Passages relevant to `query` that this resident could plausibly have read. */
export function search(query: string, r?: Resident, k = 4): Passage[] {
  const q = tok(query); const N = docs.length;
  const mine = (p: Passage) => !r || p.resident === r.id || p.codes.some((c) => r.source_codes.includes(c));
  return LIBRARY.passages
    .map((p, i) => {
      if (!mine(p)) return [p, 0] as const;
      const d = docs[i]; let s = 0;
      for (const w of q) {
        const f = d.filter((x) => x === w).length; if (!f) continue;
        const idf = Math.log(1 + (N - (df.get(w) ?? 0) + 0.5) / ((df.get(w) ?? 0) + 0.5));
        s += idf * (f * 2.2) / (f + 1.2 * (0.25 + 0.75 * d.length / avg));
      }
      return [p, s] as const;
    })
    .filter(([, s]) => s > 0).sort((a, b) => b[1] - a[1]).slice(0, k).map(([p]) => p);
}

/** Text the model sees for a passage: kind, codes and provenance always attached. */
export function cite(p: Passage): string {
  const kind = p.kind === "founder_note" ? "FOUNDER RESEARCH NOTE (a summary, not the source's words)" : "SOURCE EXCERPT";
  const codes = p.codes.length ? p.codes.map((c) => `[${c}] ${LIBRARY.sources[c]?.label ?? c}`).join("; ") : "no specific source code";
  return `${kind} ${p.id}\nSources: ${codes}\n${p.text}`;
}

export function sourceList(codes: string[]): (SourceInfo & { code: string })[] {
  return [...new Set(codes)].filter((c) => LIBRARY.sources[c]).map((c) => ({ code: c, ...LIBRARY.sources[c] }));
}

export const residentById = (id: string) => WORLD.residents.find((r) => r.id === id);
