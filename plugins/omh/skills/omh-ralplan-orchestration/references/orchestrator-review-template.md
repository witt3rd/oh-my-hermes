# Orchestrator deep-review template

Used when writing the orchestrator's deep review (e.g.
`<orchestrator>-review-deep.md`) — the honest assessment of the
ralplan output that lives in the archive.

**This is NOT what the user reads to give judgment.** That is the
brief (`brief.md`, see `brief-template.md`). The deep review is
the provenance: full reasoning, deference tests, internal chatter,
altitude observations. It captures *what you saw*; the brief
captures *what the user must see*. See P26 for why these are two
artifacts, not one.

This is the final quality gate. If what you write here feels weak,
the stance is not ready. Run another round, strengthen principles,
or fix the context package. **Then** distill the brief from the
deep review.

```markdown
# <Orchestrator>'s deep review of the <domain> ralplan output

**For:** archive (and the user, if they want the full lens).
**Brief delivered separately:** `brief.md` (decisions-first, ~1 page).
**From:** <orchestrator>
**Date:** <date>
**Stance file:** <path to stance.md>

---

## Does it meet my bar? Yes/No.

<One paragraph. If no, say why and what would make it yes.>

## What happened in the run

<Round tally. What the Critic caught that nobody else did. Concrete
naming of the moves that made the output good.>

## Where the stance ended up

<5-8 paragraphs. The dimensions, the load-bearing positions, what
was retired, the MV first shape. Enough that someone reading only
this review (skipping stance.md) understands the shape.>

## Where I push back, gently

<4-6 items. Things you would raise when sitting together with the
user, but not things you would block on. Be specific, be
constructive.>

## Where I think the user will push back

<Your prediction of the user's questions before they see the stance.
This lets them walk in with priming. Be honest; if you don't know,
say so.>

## What this run proved about the method

<What worked. What would be tuned next run. What infrastructure
failures to debug separately (and where the handoff note lives).>

## Provisos folded during distillation (if any)

<If the Round 2 Critic returned APPROVE_WITH_PROVISO, list each
proviso here with a note on where it landed in the canonical stance.
Format:
- "Critic R2 PROVISO: <text>. Folded into §<section> as <treatment>."

This keeps provenance honest: the stance is the consensus product,
but this review records what was folded vs what was punted.>

## Summary for the archive

<5-bullet summary. End with the brief's location:
"Brief delivered at brief.md.">

---

## Addendum: altitude

<If relevant: what this run demonstrates about the delegation-for-
vantage method itself. The first time a ralplan run goes well, the
addendum is often: "the stance is stronger than any proposal-correction
loop would have been, and the principles-as-guardrails worked." Note
when this fires; it's the value the orchestrator exists to deliver.>
```

## What makes a deep review honest vs performative

**Honest:**
- Names specific things the Critic caught that the orchestrator
  would have missed
- Names specific pushbacks the orchestrator has, with specific
  alternatives or the concession that they are not block-worthy
- Predicts user objections before they are raised
- Admits what the run taught the orchestrator about their own gaps

**Performative:**
- "Everything looks great" language
- Praise of the subagents without specifics
- No pushbacks (a perfect stance is almost always an unread stance)
- "I would have said the same thing" (you would not have, or the
  ralplan run was unnecessary)

## Length

~1500-3000 words typical. If under 1000, you didn't engage deeply.
If over 5000, you are re-writing the stance; stop.

## One discipline: read the stance twice before writing the deep review

First pass: does it meet the done-criteria in context.md?
Second pass: what would a skeptical user ask first?

The deep review is written against the second-pass mental state, not
the first. Compliance-checking is the Architect's job; the
orchestrator's deep review is about whether the work is *good*.

## After the deep review: write the brief

The deep review is for the archive. The brief
(`references/brief-template.md`) is for the user. Do not skip the
brief — handing the user the deep review when they need a decision
is the P26 failure.

If you cannot reduce the deep review to a clean decisions-first
brief, you do not have the altitude you think you have. Re-distill
the deep review until the brief lands clean.
