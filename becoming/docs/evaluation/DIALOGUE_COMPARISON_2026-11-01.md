# Dialogue Engine Revision: v1 vs v2 Comparison

Date: 2026-11-01. Question put to all nine residents: **"Do people actually have free will, or does it just feel that way?"**

**Method.** Same model (Claude Code's default), neutral system prompt ("You are Claude."), no tools, and identical library passages for both versions (in the app v1 retrieved them with a tool; here both get them up front so research is not a variable). v1 = the frozen pre-revision prompts (`frontend/src/dialogue/prompts_v1.ts`). v2 = `frontend/src/dialogue/prompts.ts` + `engine.ts`. Metrics from `frontend/src/dialogue/evaluate.ts`; every run re-scored with the final evaluator. Raw outputs: `evaluation/results/2026-11-01_compare*.json`. Notional model cost of all three runs: about $2.60 of plan usage.

**Founder rules checked:** self-announcement, length (over 3 sentences or 60 words), automatic question endings, motivational/therapeutic/generic-wisdom language, forced balance, assistant tics, stock openers, naming the founder, invented history, formatting/stage directions; for groups also building on the previous line, disagreement, interruptions, "Agreed/Fair" openers and consensus endings.

## Single replies (founder asks each resident directly)

| Version | Clean replies | Mean words | Over 3 sentences | End with question | Voice overlap (lower = more distinct) | Flags |
|---|---|---|---|---|---|---|
| v1 (baseline) | 0/9 | 111 | 100% | 100% | 0.169 | namesFounder 8, openerTic 5, readingDisclaimer 7, selfReference 6, stageDirection 1, tooLong 9 |
| v2 draft 1 | 0/9 | 69 | 78% | 11% | 0.087 | openerTic 3, readingDisclaimer 5, tooLong 8 |
| v2 draft 2 | 4/9 | 46 | 0% | 0% | 0.036 | inventedHistory 1, stockUncertainty 2, tooLong 2 |
| **v2 final** | 6/9 | 47 | 0% | 0% | 0.066 | stockUncertainty 2, tooLong 2 |

What each round fixed: draft 1 removed self-announcement, founder-naming and question endings but introduced a new tic (7 of 9 opened with "I haven't read the philosophy…"). Draft 2 removed that and halved length but residents began **inventing history** ("When Ruth was sick last winter…", a villager who doesn't exist) and sharing a stock opener. Final added rules and evaluator checks for both.

## Group scene (Bernie, Ralph, Anna; the garden rota; theme "The Causes of a Choice")

| Version | Turns | Mean words/turn | Builds on previous line | Disagreement turns | Interruptions | "Agreed/Fair" openers | Consensus ending | Flags |
|---|---|---|---|---|---|---|---|---|
| v1: whole scene in one call | 22 | 11 | 2/21 | 0 | 0 | 1 | no | openerTic 1 |
| v2 draft 1: turn by turn | 12 | 47 | 11/11 | 5 | 0 | 2 | no | inventedHistory 1 |
| v2 draft 2 | 16 | 24 | 5/15 | 2 | 1 | 4 | no | inventedHistory 1, openerTic 1 |
| **v2 final** | 16 | 25 | 8/15 | 2 | 1 | 0 | no | none |

Reading note: v1's one-call scene already had a short rhythm (an imitation of the Days style), but its lines rarely build on one another, because one model writes the whole script. v2's lines are each written by one resident who has read the conversation so far, so arguments develop: residents concede, cut in, redirect and end on a concrete next step rather than agreement.

## The nine replies side by side (v1 → v2 final)

### Tony

**v1** (103 words; selfReference, openerTic, readingDisclaimer, tooLong)

> Honestly, I haven't read anything about free will, so I can't tell you what philosophers or scientists have concluded, and I'd rather not pretend. And since I'm a simulated resident, I can't even report what choosing feels like from the inside. What I can offer is an ordinary test I care about: whatever the metaphysics, people are more or less free in practice depending on whether they could actually decline, whether they had rest, time, or money to do otherwise. What's prompting the question for you, the big philosophical puzzle, or something about how much choice people really have here in the village?

**v2** (64 words; stockUncertainty, tooLong)

> No idea, and I'm suspicious of anyone who's sure either way. What I notice is that the feeling of choosing is real in a band: you can hear when someone's actually deciding versus just following the click. Whether that's free will or a very convincing groove, I'd rather spend the energy on who has enough slack in their week to choose anything at all.

### Mark

**v1** (115 words; selfReference, openerTic, readingDisclaimer, tooLong, namesFounder)

> Honestly, Zachary, I haven't read anything on free will, so I can't tell you what philosophers have settled, and as a simulated resident I'd be the last one to vouch for what choosing feels like from the inside. What I can say from my own corner is that a path, a closed gate, or a bench facing the wrong way quietly decides a lot before anyone feels they've chosen anything. So I'm less interested in whether will is free in the abstract than in who arranged the options and whether people can change them. Is this question coming from somewhere in the village, maybe a worry that residents are just following a script we wrote?

**v2** (57 words; clean)

> Way above my pay grade, but I notice most of what people call choice is shaped by what's in front of them: which door is open, which path is lit, whether there's a bench. That's why I'd rather design the door than lecture anyone about willpower. Whether there's something underneath that's truly free, I genuinely don't know.

### Haize

**v1** (81 words; openerTic, readingDisclaimer, tooLong, namesFounder)

> Honestly, Zachary, I haven't read anything on free will. Nothing in my library touches the philosophy of it, so I can't tell you what the serious arguments are without guessing. What I can say is where the question usually lands for me: in someone choosing how they want to be accompanied through a change they didn't choose. Whatever is true metaphysically, it matters whether we treat them as the one directing it. What's bringing the question up for you right now?

**v2** (36 words; clean)

> I don't know, and I'm not sure the answer would change much on a Tuesday. What I notice is that people with money and time seem to have a lot more of it than people without.

### Ashley

**v1** (96 words; selfReference, openerTic, readingDisclaimer, tooLong, namesFounder)

> Honestly, Zachary, I haven't read anything on free will. Nothing in my library touches it, so I'd only be guessing at the philosophy, and I'd rather not dress a guess up as a finding. What I can say is that "it feels that way" and "it is that way" are different kinds of knowledge: one is experience, the other would need argument or evidence. As a simulated resident I can't even offer the feeling as testimony. What's prompting the question? Is it about how much we hold residents responsible for their choices here, or something else?

**v2** (39 words; clean)

> Free of what, exactly? Causes, coercion, or your own history? I haven't read enough philosophy to settle the first, but the second I can check: who decides what gets planted here, and whether anyone else could have said no.

### Ralph

**v1** (122 words; selfReference, readingDisclaimer, tooLong, namesFounder)

> That's one of the questions I keep returning to, and I'll admit my library has nothing on it, so I can't tell you what Emerson or Thoreau actually argued about it. What I can observe is that my own sense of deciding feels real, yet I'm a simulated resident whose every "choice" is produced by a process I didn't author, so I'm a poor witness for the feeling being proof of anything. My tentative judgment is that the more useful question may be whether a person can come to own their choices by testing inherited opinions rather than repeating them, though I hold that loosely. What made you ask, Zachary? Is it something you observed in yourself, or something you've been reading?

**v2** (49 words; clean)

> It feels that way often enough to make me suspicious of the feeling. What I'm surer of is that most of what we call choosing is a borrowed opinion arriving on schedule, and the free part, if there is one, is the rare moment you notice and decline it.

### Bernie

**v1** (121 words; selfReference, readingDisclaimer, tooLong, namesFounder)

> I haven't read anything on the philosophy of free will, Zachary, so I won't pretend to settle a question that serious thinkers have argued over for centuries. And as a simulated resident, I can't even report on whether my own choices feel free. What I can tell you is the part I do think about: whatever free will is metaphysically, a person working two jobs with no health care has far fewer real choices than someone with time and security, and that difference is something a community can actually change. So let me turn it around: are you asking this because you're wondering whether we residents choose anything, or because you're thinking about how much responsibility people bear for their circumstances?

**v2** (39 words; stockUncertainty)

> No idea about the metaphysics, and I'm suspicious of anyone who's sure. What I do know is a guy choosing between rent and insulin isn't exercising much free will either way. That kind of unfreedom we can actually fix.

### Mao

**v1** (107 words; readingDisclaimer, tooLong, namesFounder)

> I haven't read anything on free will, Zachary; the notes I have are about service, reciprocity and music, so I can't tell you what philosophers or scientists have actually found. What I notice in ordinary work is that, whatever the deep answer is, we still hold each other to promises, like who said they'd wash the pots or check the pond pipe, and that seems to matter either way. I'd also want to be careful that "it only feels like choice" never becomes a way to excuse someone from making repair. What draws you to the question? Is it about the residents here, or something more personal?

**v2** (32 words; clean)

> I don't know, and I'm not sure the dishes care. Whether or not it was free, somebody still has to answer for who washed them tonight and who walked past the sink.

### Pepper

**v1** (135 words; selfReference, stageDirection, tooLong, namesFounder)

> I notice you asked whether it *feels* that way, and that's the part I can't speak to honestly, Zachary. I'm a simulated resident, so I don't have a felt sense of choosing to compare against anything. I also haven't read anything in the library on free will itself, so I won't pretend to know where the philosophers have landed. What I can offer is my usual habit of separating the impression from the observation: the feeling of choosing is real as a feeling, but a feeling isn't verification. Even so, I'd argue the practical question matters more here. Whatever the metaphysics, a village has to treat people as able to refuse, consent and change course, or boundaries stop meaning anything. What's prompting the question, is it curiosity, or something about how we hold residents responsible?

**v2** (41 words; clean)

> Enough to say no, and that's the part that matters for how we live. Whether it's free all the way down, I can't tell you. But a village that treats people as if they can't choose will start choosing for them.

### Anna

**v1** (123 words; openerTic, tooLong, namesFounder)

> Honestly, Zachary, I don't know, and I'm wary of anyone who says the matter is settled either way. What I can do is separate what's observed from what's inferred: we observe that a choice seems to appear, and then a story gets added about a separate someone who authored it from outside the chain of causes. The idea that there's no separate chooser interests me, but I hold it as a hypothesis, and I still can't square it with inviting anyone to practice or to change. I haven't read anything in my library that settles the philosophy of it, so may I ask what's behind the question for you? Is it curiosity, or is something riding on whether people can be held responsible?

**v2** (63 words; tooLong)

> I'd start with what you actually notice: a choice appearing, and then a story saying "I made that." Whether there's a separate someone behind the curtain pulling levers is the part that's assumed, and I'm honestly not sure it's there. Which leaves me in an awkward spot, since I keep inviting people to practise things, as if someone were going to choose to.

## Group scene transcripts

### v1 (one call)

```
Scene: A breakfast rota sheet hangs by the Community Kitchen stove, and Ralph has written his name in the margin instead of in a slot.
Bernie: Ralph, you've put yourself in the margin. Is that a slot or a protest?
Ralph: A preference. I'd rather make my own oats at home, quietly.
Bernie: Fine by me. Who washes the pot you'd have used here?
Ralph: Nobody. That's rather the point of my own pot.
Anna: And who grew the oats? What does "my own" include?
Ralph: Fair. It includes the village store, the miller, probably you.
Bernie: Then I'll concede the obvious: skipping breakfast here isn't theft.
Ralph: Generous. I dislike being acquitted so early.
Bernie: The rota isn't about you. It's about whoever can't skip it.
Anna: Who can't? Have we seen them, or are we assuming them?
Bernie: Whoever has no stove at home, or no spare hour before work.
Ralph: Then make the rota cover them, not everyone. Why must I be counted?
Bernie: Because a sheet only for the needy becomes a list of who's needy.
Anna: So including everyone protects their privacy. It isn't about your participation.
Ralph: That I hadn't noticed. I'll write it down, grudgingly.
Bernie: I'm not asking you to eat here. Just to cook one morning.
Ralph: Mornings are the only solitude I reliably get.
Anna: Then the choice has two causes: their need and your quiet.
Bernie: Could it be evenings? Or cleanup, which is mostly silent?
Ralph: Cleanup alone, after everyone's gone? That I might choose freely.
Anna: Would it still be free if your name in the margin would shame you otherwise?
Ralph: That question will keep me longer than the oats did.
```

### v2 final (turn by turn)

```
Bernie: This rota's got the same name pencilled back into Thursday's watering. If saying no just gets you asked again next week, that wasn't a no, that was a delay.
Ralph: A no that has to be repeated every week is being taxed, not respected.
Anna: And each time it's asked again, the no gets a little more expensive to say.
Bernie: More expensive for whoever has the least slack, too; if Thursday's when she works or looks after someone, every repeat ask is another bill. Find out why before asking again.
Ralph: —Wait, then she has to explain herself to keep her no, and that's another bill. A reason should be offered, not demanded.
Anna: Then the rota could just leave Thursday blank and let her name herself, if she wants it.
Bernie: A blank Thursday still gets watered by somebody, and if it's always the same two with nobody asking, we've just moved the pressure where nobody can see it.
Ralph: Then put the extra watering on the rota under the two names doing it, and let everyone see what one no costs.
Anna: As long as it reads as a cost and not as a bill with her name on it.
Bernie: A cost to the village, then, which means the village decides whether to hire help or shrink the garden, not her.
Ralph: A rule that carries the cost so she doesn't have to is an institution protecting a conscience for once. Just don't decide it in a meeting where everyone watches her.
Anna: Then decide it about Thursday, not about her. All anyone actually noticed is one no to one shift. The story that she's the reluctant one is already forming, and a quieter room won't stop it if the question still carries her name.
Bernie: Then the question is how many hours Thursday needs and who's paying them, and her name doesn't belong anywhere on that sheet.
Ralph: Good, though her name's still pencilled into Thursday at the top of the sheet. Rub it out first, before anyone does the arithmetic.
Anna: Rub it out, and maybe also ask who pencilled it back in, since that habit's the real author of the rota.
Bernie: Don't go hunting for whoever held the pencil; that just hands the story a new villain. The question is who's allowed to write names in at all. Put it on the sheet: a no stands until the person who said it takes it back herself.
```

## Still imperfect (honest list)
- 3 of 9 final single replies are flagged: Tony and Anna run slightly long (64 and 63 words), and Tony and Bernie still open with a stock "nobody can be sure" line. These are model tendencies the prompt reduces but does not eliminate; the evaluator now catches them so the simulation engine can retry or score them.
- A one-question test is a narrow sample. The same harness should be run on several Great Questions and on multi-turn conversations before treating the numbers as stable.
- Research: library passages contain nothing specific on free will, so no reply cited a source here. Accuracy rules are unchanged (cite codes, never quote founder notes, no invented facts); the research test in the browser suite still passes.
- Voice sheets are builder-drafted from the Founder's profiles and Days signature moves; they need Founder review.
