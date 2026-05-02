# Brief template

Used as `brief.md` at the orchestrator-review step (step 5 of the
playbook). The brief is **what the user reads to give judgment**;
the deep review (`<orchestrator>-review-deep.md`) is the archive.

The brief must let an executive scan, decide, and return — without
ever needing to read the deep review.

See P26 for why this artifact exists separately from the deep
review, and the failure mode it prevents.

## Length

~1–2 pages typical. ~400–800 words. If under 200, you skipped
something the user actually needs to decide. If over 1500, you are
shipping the deep review with a different filename — re-distill.

## Structure

```markdown
# Brief — <domain> ralplan

**For:** <user>
**From:** <orchestrator>
**Date:** <date>
**Deep version:** `<orchestrator>-review-deep.md` (archive — internal chatter, full reasoning, deference tests, etc.)
**Canonical artifacts:** `stance.md`, `<companion-artifact-1>.md`, ...

---

## What this is

<2–4 sentences. Round tally compressed. The headline outcome of the run.
What was avoided, what was caught, what landed.>

## Decisions you need from me

<Numbered list. Each decision:
1. **<Decision name>** — <one-sentence framing of the choice>.
   <My take + the alternative.>
>

(If decisions were already resolved in conversation before this brief
was written, retitle this section "Decisions you needed to make
(resolved)" and list how each was settled. Treat it as a record so
the user can sanity-check.)

## Where we deviated from pre-dispatch conversation

<Be specific. Name each place the loop produced something different
from what you and the user worked through up-front, and why.

If there are no deviations, say so explicitly: "All positions align
with what we worked through pre-dispatch." This is a load-bearing
sentence — it tells the user nothing is hiding.>

## What changed since the deep review (if applicable)

<Only present if user feedback after the deep review drove patches
to the canonical artifacts. List concrete changes:
- File X: <change>
- File Y: <change>

If the brief is being delivered fresh after distillation with no
post-deep-review changes, omit this section.>

## Where the design landed (one paragraph)

<Single paragraph, ~80–150 words. The shape of the design at a level
the user can hold in working memory. Names the load-bearing positions
without enumerating every dimension.>

## Open questions left for v2 / lived friction

<Bullets, ~3–6 items. Things that are NOT decided here, that the user
should know are deferred. Distinguish "deferred to v2" from "owed
follow-up" if that matters.>

## Next steps

<Numbered list, ~3–5 items. What happens after the user signs off.
Who owns each. The sequence.>

⚒️  (or your signature)
```

## What makes a brief honest vs performative

**Honest:**
- Decisions stated as decisions, with the alternative named so the
  user can weigh
- Deviations from pre-dispatch conversation explicit, with cause
- One paragraph for the design shape, not five
- Open questions named even when uncomfortable
- Concrete next steps with ownership

**Performative:**
- "Comprehensive consensus reached" language without naming what
  the user must decide
- Hidden deviations (the loop went somewhere different and you hope
  the user doesn't notice)
- Five paragraphs on "where the stance ended up" because you
  couldn't compress
- Open questions buried in the deep review only
- "Ready for your read" with no decisions named — the user reads,
  finds nothing actionable, and disengages

## The deviation discipline

The most load-bearing section is **"Where we deviated from pre-dispatch
conversation."** The user spent real cognitive effort working through
the design with you before dispatch. Hidden deviations corrode trust
the fastest. Surface them, name why, let the user push back. They
will respect the deviation if you named it; they will be hurt if
they discover it.

If there were no deviations, say "All positions align with what we
worked through pre-dispatch" explicitly. The absence-of-deviation
sentence is itself load-bearing — it tells the user nothing is
hiding.

## The decision-stating discipline

Every decision in the "Decisions you need from me" section must
include:

- **What's at stake** — one sentence framing the choice.
- **My take** — your recommendation, named clearly.
- **The alternative** — what saying no looks like, so the user can
  weigh.

Bad: "We need to decide on the trigger model."
Good: "**Trigger model.** LLM call on every synthesis trigger, or
deterministic-at-periodic with LLM only at session-start/shockwave?
*My take: LLM-everywhere v1, telemetry watches the cost, fall back if
it bites.* The architecture supports either; this is a v1 budget
choice, not a structural one."

The user can read the bad version and have no idea what to decide.
The user can read the good version and decide in 20 seconds.

## When to include "Decisions you needed to make (resolved)"

If the brief is being written *after* a conversation where decisions
were already settled, retitle the section and list how each was
resolved. This is a record-of-record for the user to sanity-check
that you heard correctly. It is not redundant; it is verification.

## One discipline: write the brief before the deep review when possible

Counter-intuitively: the brief is harder to write than the deep
review. The deep review is a discharge — you write what you saw.
The brief is a distillation — you write what the user must see.

If you cannot write a clean brief, you do not have the altitude you
think you have. Run another distillation pass on the deep review
until the brief lands clean.

When time permits, draft the brief first. The decisions-first
discipline forces you to identify what's actually at stake. The
deep review then writes itself as the supporting record.
