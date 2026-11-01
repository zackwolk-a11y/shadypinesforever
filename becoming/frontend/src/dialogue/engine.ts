// Group conversation engine, v2: turn by turn. Each line is written by one
// resident who sees the conversation so far, so residents can build on, cut
// into and disagree with each other instead of one model writing a whole script.
import type { Resident } from "../world";
import type { Line } from "./prompts";

/** Remove labels, quotation marks and stage directions a model may add. */
export function cleanLine(raw: string, name: string): string {
  let s = raw.trim();
  s = s.replace(new RegExp(`^\\**${name}\\**\\s*:\\s*`, "i"), "");
  s = s.split(/\n\s*\n/)[0];                  // one turn only
  s = s.replace(/^["“]|["”]$/g, "");
  s = s.replace(/\*[^*]{1,80}\*/g, "").replace(/^\([^)]{1,80}\)\s*/, ""); // *sighs*, (pausing)
  return s.replace(/\s+/g, " ").trim();
}

/**
 * Who speaks next: someone addressed by name answers; otherwise whoever has
 * waited longest, with a little randomness. Never the same person twice running.
 */
export function nextSpeaker(cast: Resident[], transcript: Line[], rand: () => number = Math.random): Resident {
  const last = transcript[transcript.length - 1];
  const candidates = cast.filter((c) => !last || c.name !== last.speaker);
  if (last) {
    const addressed = candidates.filter((c) => new RegExp(`\\b${c.name}\\b`).test(last.text));
    if (addressed.length && rand() < 0.75) return addressed[0];
  }
  const waited = (c: Resident) => {
    for (let i = transcript.length - 1, n = 0; i >= 0; i--, n++) if (transcript[i].speaker === c.name) return n;
    return transcript.length + 1;
  };
  const weights = candidates.map((c) => waited(c) + 1 + rand());
  let best = 0;
  for (let i = 1; i < candidates.length; i++) if (weights[i] > weights[best]) best = i;
  return candidates[best];
}

/** 14 to 20 short turns: enough exchanges for the idea to develop. */
export const sceneLength = (rand: () => number = Math.random) => 14 + Math.floor(rand() * 7);
