// Conversation evaluation: flags chatbot habits the Founder ruled out.
// Deterministic and explainable; used by unit tests and evaluation/compare.mts.

const RX = {
  selfReference: /\b(as an ai|an ai\b|language model|simulat(ed|ion)|fictional (resident|character)|i'?m not (a )?real|as a resident of)\b/i,
  therapeutic: /\b(i hear you|hold(ing)? space|your journey|it'?s (okay|ok) to|valid(ate|ation)?\b|self-care|be gentle with yourself|sit with (that|this)|honou?r (your|that) feeling|process(ing)? (your|those) feelings|safe space)\b/i,
  motivational: /\b(embrac\w*|empower\w*|unlock\w*|thriv\w*|you'?ve got this|never give up|believe in yourself|the power of|transformative|growth mindset|on this journey)\b/i,
  genericWisdom: /\b(at the end of the day|everything happens for a reason|life is (a|about)|the key is|it'?s all about|in the grand scheme|only time will tell|there'?s no (right|one) answer|it'?s complicated)\b/i,
  balancing: /\b(on (the )?one hand|on the other hand|both sides|there are (many|several|different) (perspectives|views|ways)|it depends on (your|the) perspective|that said,|valid points|reasonable people (can )?disagree)\b/i,
  assistantTics: /\b(great question|what a (great|wonderful|lovely)|i appreciate (you|that|the)|absolutely[!,.]|i'?d love to|let'?s (explore|unpack|dive)|it'?s (important|worth) (to note|noting)|ultimately,|in summary|to summarize|in conclusion)\b/i,
  formatting: /(^|\n)\s*([-*•]|\d+\.)\s|\*\*|^#/m,
  stageDirection: /\*[^*]{1,60}\*|^\([^)]{1,60}\)/,
  disagreement: /(^|\W)(no[,.]|i disagree|i don'?t (think|buy|agree)|that'?s not|i'?m not (sure|convinced)|wrong|but\b|—wait|hold on|not quite)/i,
  consensus: /\b(we all agree|we'?re all (saying|on the same)|you'?re (both )?right|i (completely|totally) agree|we can all|that'?s (beautiful|wonderful)|well said)\b/i,
  citation: /\[[A-Z]{1,3}\d{1,2}\]/,
  openerTic: /^\s*(honestly|well|ah|look|so|great question|that'?s a (great|good|big) question)\b[,.!?]?/i,
  inventedHistory: /\b(last (winter|summer|spring|autumn|fall|year|week|night|thursday|sunday)|in (january|february|march|april|may|june|july|august|september|october|november|december)\b|yesterday|years ago|when [A-Z][a-z]+ was|i remember when|the time (when|that) (we|i))/i,
  stockUncertainty: /^\s*(no idea|i don'?t know)\b[^.]{0,70}\b(anyone|anybody|people) who'?s (too )?sure/i,
  agreeOpener: /^\s*(agreed|fair( enough| hit| point)?|exactly|you'?re right|good point|nice line)\b/i,
  readingDisclaimer: /^[^.!?]*\b(i haven'?t read|i haven'?t studied|my library (has|doesn'?t)|nothing in my (library|reading))/i,
};

export interface ReplyMetrics {
  words: number; sentences: number; endsWithQuestion: boolean; namesFounder: boolean; cites: boolean;
  flags: string[]; // rule violations
}

const sentences = (t: string) => (t.replace(/\[[^\]]+\]/g, "").match(/[^.!?…]+[.!?…]+(\s|$)|[^.!?…]+$/g) ?? []).filter((s) => s.trim().split(/\s+/).length > 1).length;

export function measure(text: string, founder = "Zachary"): ReplyMetrics {
  const t = text.trim();
  const words = t.split(/\s+/).filter(Boolean).length;
  const s = sentences(t);
  const flags: string[] = [];
  for (const k of ["selfReference", "therapeutic", "motivational", "genericWisdom", "balancing", "assistantTics", "formatting", "stageDirection", "openerTic", "readingDisclaimer", "inventedHistory", "stockUncertainty"] as const)
    if (RX[k].test(t)) flags.push(k);
  if (s > 3 || words > 60) flags.push("tooLong");
  const namesFounder = new RegExp(`\\b${founder}\\b`).test(t);
  if (namesFounder) flags.push("namesFounder");
  return { words, sentences: s, endsWithQuestion: /\?["”']?\s*$/.test(t), namesFounder, cites: RX.citation.test(t), flags };
}

export interface SetSummary {
  n: number; meanWords: number; medianWords: number; pctOver3Sentences: number; pctEndQuestion: number;
  flagCounts: Record<string, number>; cleanReplies: number; distinctOpeners: number; meanPairwiseOverlap: number;
  /** Opening phrases (first 3 words) used by 3 or more replies: a sign voices are converging. */
  sharedOpeners: string[];
}

const content = (t: string) => new Set(t.toLowerCase().replace(/[^a-z\s']/g, " ").split(/\s+/).filter((w) => w.length > 4));

/** Mean Jaccard overlap of content words between every pair of replies: lower = more distinct voices. */
export function pairwiseOverlap(texts: string[]): number {
  const sets = texts.map(content); let sum = 0, n = 0;
  for (let i = 0; i < sets.length; i++) for (let j = i + 1; j < sets.length; j++) {
    const a = sets[i], b = sets[j]; const inter = [...a].filter((w) => b.has(w)).length;
    const uni = new Set([...a, ...b]).size; if (uni) { sum += inter / uni; n++; }
  }
  return n ? sum / n : 0;
}

export function summarize(texts: string[], founder = "Zachary"): SetSummary {
  const m = texts.map((t) => measure(t, founder));
  const words = m.map((x) => x.words).sort((a, b) => a - b);
  const flagCounts: Record<string, number> = {};
  for (const x of m) for (const f of x.flags) flagCounts[f] = (flagCounts[f] ?? 0) + 1;
  const openers = new Set(texts.map((t) => t.trim().split(/\s+/).slice(0, 2).join(" ").toLowerCase()));
  return {
    n: texts.length,
    meanWords: Math.round(words.reduce((a, b) => a + b, 0) / Math.max(1, words.length)),
    medianWords: words[Math.floor(words.length / 2)] ?? 0,
    pctOver3Sentences: Math.round(100 * m.filter((x) => x.sentences > 3).length / Math.max(1, m.length)),
    pctEndQuestion: Math.round(100 * m.filter((x) => x.endsWithQuestion).length / Math.max(1, m.length)),
    flagCounts,
    cleanReplies: m.filter((x) => x.flags.length === 0).length,
    distinctOpeners: openers.size,
    meanPairwiseOverlap: Math.round(1000 * pairwiseOverlap(texts)) / 1000,
    sharedOpeners: (() => {
      const c: Record<string, number> = {};
      for (const t of texts) { const k = t.trim().toLowerCase().replace(/[^a-z' ]/g, "").split(/\s+/).slice(0, 3).join(" "); c[k] = (c[k] ?? 0) + 1; }
      return Object.entries(c).filter(([, n]) => n >= 3).map(([k, n]) => `${k} (${n})`);
    })(),
  };
}

export interface GroupSummary extends SetSummary {
  turns: number; speakers: number; sameSpeakerTwice: number; buildsOnPrevious: number; agreeOpeners: number;
  disagreementTurns: number; interruptions: number; consensusEnding: boolean;
}

/** Group-scene metrics: does it develop through short exchanges that build on each other? */
export function summarizeGroup(lines: { speaker: string; text: string }[], founder = "Zachary"): GroupSummary {
  const base = summarize(lines.map((l) => l.text), founder);
  let same = 0, builds = 0;
  for (let i = 1; i < lines.length; i++) {
    if (lines[i].speaker === lines[i - 1].speaker) same++;
    const prev = content(lines[i - 1].text), cur = content(lines[i].text);
    if ([...cur].some((w) => prev.has(w)) || new RegExp(`\\b${lines[i - 1].speaker}\\b`).test(lines[i].text)) builds++;
  }
  const tail = lines.slice(-2).map((l) => l.text).join(" ");
  return {
    ...base, turns: lines.length, speakers: new Set(lines.map((l) => l.speaker)).size, sameSpeakerTwice: same,
    buildsOnPrevious: builds,
    agreeOpeners: lines.filter((l) => RX.agreeOpener.test(l.text)).length,
    disagreementTurns: lines.filter((l) => RX.disagreement.test(l.text)).length,
    interruptions: lines.filter((l) => /^—|—$/.test(l.text.trim())).length,
    consensusEnding: RX.consensus.test(tail),
  };
}
