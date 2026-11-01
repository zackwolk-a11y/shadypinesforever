// Dialogue engine v2: evaluator, speaker selection and prompt rules.
// Run: npx tsx --test tests/dialogue.test.mts
import test from "node:test";
import assert from "node:assert/strict";
import { measure, summarize, summarizeGroup } from "../src/dialogue/evaluate.ts";
import { nextSpeaker, cleanLine, sceneLength } from "../src/dialogue/engine.ts";
import { directOpening, directFollowUp, groupTurn, turnShape, SPEECH_RULES, NOTES_MARK } from "../src/dialogue/prompts.ts";
import { personaPrompt } from "../src/dialogue/prompts_v1.ts";
import { WORLD } from "../src/world.ts";
import { search } from "../src/research.ts";

const R = (id: string) => WORLD.residents.find((r) => r.id === id)!;

test("evaluator flags chatbot habits", () => {
  const bot = "What a great question, Zachary! As an AI resident, I think it's important to note that there are many perspectives here. On one hand, freedom is about choice; on the other hand, it's about conditions. Ultimately, it's all about embracing your journey. What do you think?";
  const m = measure(bot);
  for (const f of ["assistantTics", "selfReference", "balancing", "genericWisdom", "motivational", "therapeutic", "namesFounder"]) assert.ok(m.flags.includes(f), `expected ${f} in ${m.flags}`);
  assert.equal(m.endsWithQuestion, true);
});

test("evaluator passes natural, opinionated speech", () => {
  for (const ok of [
    "No. You're not free if you can't afford to say no, and most people can't.",
    "Free will? I'd settle for free afternoons. Ask me again when the rent's paid.",
    "A self is more like a habit than a thing. Watch what happens when the habit gets interrupted.",
  ]) assert.deepEqual(measure(ok).flags, [], ok);
});

test("evaluator flags the opener and reading-disclaimer tics", () => {
  assert.ok(measure("Honestly, I think it's mostly habit.").flags.includes("openerTic"));
  assert.ok(measure("I haven't read the philosophy, but it's mostly habit.").flags.includes("readingDisclaimer"));
  assert.deepEqual(measure("It's mostly habit. I haven't read the philosophy, mind you.").flags, []);
});

test("evaluator flags invented history and stock uncertainty", () => {
  assert.ok(measure("When Ruth was sick last winter, somebody brought soup.").flags.includes("inventedHistory"));
  assert.ok(measure("I skipped two of my Thursdays in June.").flags.includes("inventedHistory"));
  assert.ok(measure("I don't know, and I distrust anyone who's sure.").flags.includes("stockUncertainty"));
  assert.deepEqual(measure("Say someone's ill: nobody asks whether the soup was freely chosen.").flags, []);
  assert.equal(summarizeGroup([{ speaker: "Anna", text: "Agreed, though not quite." }, { speaker: "Ralph", text: "Fair point." }]).agreeOpeners, 2);
});

test("set summary spots converging openers", () => {
  const sum = summarize(["I don't know, and A.", "I don't know, and B.", "I don't know, and C.", "Free of what?"]);
  assert.deepEqual(sum.sharedOpeners, ["i don't know (3)"]);
  assert.ok(measure("No idea about the metaphysics, and I'm suspicious of anyone who's sure.").flags.includes("stockUncertainty"));
});

test("prompts forbid invented history and stock openers", () => {
  const p = directOpening(R("mao"), "Is free will real?", []);
  assert.ok(p.includes("No invented past") && p.includes("stock line about nobody being sure"));
});

test("group turns get varied target lengths", () => {
  const shapes = new Set(Array.from({ length: 200 }, () => turnShape()));
  assert.equal(shapes.size, 3);
});

test("evaluator flags essays", () => {
  const long = Array(6).fill("This sentence keeps going about the general subject of freedom in society.").join(" ");
  assert.ok(measure(long).flags.includes("tooLong"));
});

test("group summary detects building, disagreement, consensus endings", () => {
  const g = summarizeGroup([
    { speaker: "Bernie", text: "Who pays for the new bench?" },
    { speaker: "Ralph", text: "—Wait, nobody asked for a bench." },
    { speaker: "Mark", text: "Ralph, people stand at that corner every evening; a bench is asked for by feet." },
    { speaker: "Bernie", text: "You're both right, we all agree." },
  ]);
  assert.equal(g.turns, 4); assert.equal(g.sameSpeakerTwice, 0);
  assert.ok(g.interruptions >= 1 && g.disagreementTurns >= 1 && g.consensusEnding);
  assert.ok(g.buildsOnPrevious >= 2);
});

test("next speaker: never repeats, answers when addressed", () => {
  const cast = ["bernie", "ralph", "mark"].map(R);
  for (let i = 0; i < 50; i++) {
    const s = nextSpeaker(cast, [{ speaker: "Bernie", text: "Mark, what does that cost?" }], () => 0.1);
    assert.equal(s.name, "Mark");
    const t = nextSpeaker(cast, [{ speaker: "Ralph", text: "Hm." }]);
    assert.notEqual(t.name, "Ralph");
  }
  const len = sceneLength(() => 0.99); assert.ok(len >= 14 && len <= 20);
});

test("cleanLine strips labels, quotes and stage directions", () => {
  assert.equal(cleanLine('Pepper: "*looks at the pond* Leave it alone."', "Pepper"), "Leave it alone.");
  assert.equal(cleanLine("(pausing) No.\n\nAnother paragraph", "Ralph"), "No.");
});

test("v2 direct prompt: rules in, founder name and self-announcement out", () => {
  const r = R("tony");
  const p = directOpening(r, "Do we have free will?", search("free will choice", r, 3));
  assert.ok(p.includes(SPEECH_RULES));
  assert.ok(p.includes("one or two short sentences") && p.includes("don't have to end with a question"));
  assert.ok(!p.includes(WORLD.founder.name), "founder's name not fed to the resident");
  assert.ok(!/You are a simulated character|Never claim to be conscious/.test(p), "no disclosure-first framing");
  assert.ok(p.includes("tell the truth briefly"), "still honest if sincerely asked");
  assert.ok(p.includes(r.voice.strong_opinions[0]) && p.includes(r.voice.never_says[0]));
  const v1 = personaPrompt(r);
  assert.ok(v1.length > p.length * 0.6, "sanity: v1 baseline still builds");
  assert.ok(directFollowUp("Really?", []).startsWith("Really?" + NOTES_MARK));
});

test("v2 group turn sees the transcript and forbids forced consensus", () => {
  const cast = ["anna", "bernie", "pepper"].map(R);
  const p = groupTurn({ speaker: cast[1], cast, setting: "the Communal Garden", time: "Afternoon", situation: "A shared plot is overgrown.",
    transcript: [{ speaker: "Anna", text: "Whose weeds are these, exactly?" }], passages: [], turn: 1, maxTurns: 12 });
  assert.ok(p.includes("Anna: Whose weeds are these, exactly?"));
  assert.ok(p.includes("never force agreement"));
  assert.ok(p.includes("Write only Bernie's next line"));
});

test("all nine residents have a distinct voice", () => {
  const v = WORLD.residents.map((r) => r.voice.rhythm);
  assert.equal(new Set(v).size, 9);
  assert.ok(summarize(WORLD.residents.map((r) => r.voice.strong_opinions.join(" "))).meanPairwiseOverlap < 0.15);
});
