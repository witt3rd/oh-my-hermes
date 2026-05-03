---
name: omh-ralplan-driver
description: "Drive omh-ralplan: context package, rounds, distillation."
version: 1.1.0
metadata:
  hermes:
    tags: [planning, ralplan, orchestration, multi-agent, consensus]
    category: omh
    requires_toolsets: [terminal, omh]
---

# OMH Ralplan Driver — driving the loop

Load this skill alongside `omh-ralplan` when you are the orchestrator
dispatching the loop. `omh-ralplan` is loaded by the Planner / Architect
/ Critic *workers* — it covers what they do inside each `delegate_task`
call. This skill covers what *you* do as the dispatcher: prep, dispatch,
distill, review.

The two skills have different readers and different jobs. Don't merge
them — worker context is precious; the dispatcher's playbook should
not ride into every subagent.

## Why this skill exists

Ralplan without disciplined orchestration converges on internal
consistency, not truth. The Planner / Architect / Critic triangle is
self-checking — it will produce a coherent stance about *whatever
you pointed it at*, including the wrong frame, the stale source, the
phantom constraint, and the question the user already settled.

The orchestrator is the only role with the vantage to:

- Carve principles before dispatching.
- Author a context package that licenses framing contests.
- Verify ground truth and adjacent mechanisms before subagents
  inherit them as fact.
- Iterate the package with the user — half of any non-trivial
  requirements come from the user's lived context, not from reading.
- Distill consensus into a canonical artifact stripped of
  reviewer scaffolding.
- Apply a final quality gate before handing anything to the user.

Most of the failure modes named below are pre-dispatch failures. **Prep
is where quality is born.** Distillation and review preserve it. The
loop itself is just the well-instrumented engine in between.

## When to use ralplan vs just think

Use ralplan when the work has:

- Multiple legitimate decompositions of the problem.
- Load-bearing principles that need enforcing across subagents.
- Cross-cutting concerns the orchestrator might miss alone.
- A user who would otherwise be in a turn-by-turn proposal loop.

Don't use ralplan when the work is single-file, single-decision, or
obvious-to-solve. Overkill is its own failure mode. Use
`omh-deep-interview` first if the goal is ambiguous.

## The five-step playbook

### 1. Carve principles first (if they don't exist yet)

Ralplan without principles produces plausibly-reasoned nonsense. The
Planner/Architect/Critic triangle converges on internal consistency,
not on truth. Principles are the external anchor.

A good starting point: a small `PRINCIPLES.md` (≤15 entries) at the
project root. Each principle should be load-bearing and name the
failure it prevents. Include this file in every subagent's required
reading.

If principles don't exist yet, carve them first — even a quick draft
beats unprincipled ralplan. The file can iterate; the existence of
the anchor cannot.

### 2. Draft a context package — not just a prompt

The context package is a living document at
`docs/design/<domain>/context.md`. It is the single most load-bearing
artifact in the run. The Planner reads it. The Architect reads it.
The Critic reads it. A weak package produces a weak stance no matter
how good the subagents are.

Required sections:

- **The design question.** Single sentence, then a 2-3 paragraph
  expansion. Name what the output must do, what it must honor, what
  it is the foundation for.

- **Artifact-type declaration.** One sentence near the top: "This is
  design-shaped, not requirements-shaped" — or vice versa. Forces
  the orchestrator to commit before drafting dimensions, and tells
  subagents which discipline rules apply (see Pitfall 15). Cheap to
  add; surfaces the wrong-shape failure before dimensions get drafted
  around the wrong frame.

- **Sub-dimensions.** A first cut of what the stance must address.
  Not sacred — the META question below licenses the Critic to
  rework them.

- **Constraints.** Principles, directives, committed prior decisions
  the run must honor.

- **Out of scope.** What this run does NOT design.

- **Required reading.** Absolute paths only. Subagents cannot `cd`
  and cannot work from summaries. Group by category: principles +
  directives, inspiration / prior art, target platform, existing
  code, and the context package itself.

- **Contested questions.** Six to eight places lazy consensus is
  most likely. Seeds for the Critic. Not exhaustive.

- **A META question.** "Are these the right sub-dimensions?" This
  licenses the Critic to contest the framing itself, which is the
  single most load-bearing move a Critic can make. Without it the
  Critic stays inside the frame and only checks compliance.

- **What done looks like.** Concrete output criteria. Include one
  that forces "what is missing from the inspiration / what would
  an ideal version have that the inspiration lacks?"

The orchestrator drafts the context package, reviews it, then walks
it with the user before running the loop (see Pitfall 10). The package
is load-bearing for quality.

### 3. Round 1 sequential, Round 2 parallel

Round 1: Planner → Architect → Critic in strict sequence. Each reads
the prior outputs plus the required reading. Each writes a named
artifact to the design directory, not inline in a tool response.

File naming convention:

- `stance-planner.md`
- `review-architect.md`
- `review-critic.md`

Round 2 only if any reviewer is not APPROVE. The Planner revises;
Architect and Critic re-review **in parallel via batched
`delegate_task(tasks=[...])`**. Significant wall-clock savings (one
recurring run measured ~100 seconds saved in Round 2 alone).

Round 2 file naming: `-v2` suffix. Keep Round 1 artifacts on disk as
provenance — they show the loop's motion.

Three-APPROVE consensus closes the loop. Otherwise iterate; max 3
rounds with caveats if no convergence.

### 4. Distill, don't hand the raw output to the user

After consensus, the Planner's final stance will contain a "Round 2
response map" section at the top — a checklist for reviewers, not
for the user. Strip that; keep the substantive content. Write the
result as `stance.md` (no suffix). Preserve the raw
`stance-planner-v2.md` beside it for provenance.

If the artifact is requirements-shaped, distill to `requirements.md`
not `stance.md` — the canonical filename matches the artifact noun
(see Pitfall 15).

Also write a consensus summary at `.omh/plans/ralplan-<instance-id>.md`
that names the round tally, what the Critic caught, key design
positions, MV steps, and file pointers. This is the orchestrator's
short summary — grep-able, survives session rotation.

### 5. Orchestrator review, then bring to user

The orchestrator's own review is the final gate before the user sees
anything. **Write two artifacts**, not one:

- **`brief.md`** — what the user reads. Decisions-first. ~1–2 pages.
  Resolved decisions on top, deviations from pre-dispatch
  conversation named, where the design landed in one paragraph,
  open questions left, next steps. The user must be able to **give
  judgment** from this alone — never force them to read the deep
  review just to know what to decide.

- **`<orchestrator>-review-deep.md`** — the archive. Internal chatter,
  full reasoning, deference tests, run-method observations,
  altitude addendum, what-the-Critic-caught-narratively. Lives on
  disk for archaeology and for the rare moment the user wants the
  full lens. **Default-not-read.** Replaces what older runs called
  `<orchestrator>-review.md`.

The brief is for delivery; the deep review is for the record. Treat
them as different artifacts with different readers.

What the deep review carries (same as before):

- Does this meet my bar? (Yes/no + why.)
- What the Critic caught that surprised me.
- Where I push back gently — things I'd raise sitting with the user,
  not things that block.
- Where I predict the user will push back — give them priming
  before they read.
- What this run taught me about the method.
- Provisos folded during distillation (if any).

What the brief carries (decisions-first, see P26 + template):

- Decisions you need from the user, numbered, with my-take on each.
- Where I deviated from pre-dispatch conversation (be specific).
- One-paragraph "where the design landed."
- Open questions left for v2 / lived friction.
- Next steps.

If the deep review is weak, run another round or strengthen the
principles. **Do not hand the user output below your own bar** —
the altitude compact depends on this. The brief is what tests the
compact: if you cannot reduce the deep review to a clean
decisions-first brief, you do not have the altitude you think you
have.

See `references/orchestrator-review-template.md` for the deep-review
template and `references/brief-template.md` for the brief template.

## Pitfalls (numbered P1–P26)

These are the failure modes that orchestrators repeatedly stumble
into. Each was learned the hard way. Numbering is contiguous; there
are no gaps.

### P1 — Never reference files you'll write later

Don't write "I will write file X next" in a `delegate_task` context
and then dispatch. The subagent will read the context, look for X,
fail to find it, and either time out or produce broken output.
Always write referenced files **before** dispatching the
`delegate_task` that references them.

### P2 — Timeout ≠ no work done

Subagents sometimes report "timed out, 0 API calls" but have actually
completed and written multi-KB output to disk. The reporting channel
fails, not the work. Before regenerating, **check disk first**: does
the target output file exist? Read it. The work may already be done.
This has been confirmed multiple times across runs — file-on-disk is
the ground truth, not the tool-level status string.

### P3 — Context size blows up fast

Each subagent in Round 1 may consume hundreds of thousands of input
tokens reading the required files. Three subagents × two rounds =
real cost. Mitigations:

- Split very large supporting docs if they're secondary reading.
- For Round 2 reviewers, consider passing deltas + the v2 stance
  rather than re-reading every file.
- Be honest about what is *required* reading vs *useful* — call them
  out separately in the package.

### P4 — The Critic must be licensed to contest the framing

This is the single most load-bearing move. If the context package
lists only "things to push on inside the current frame," the Critic
will stay inside the frame. Add the META question explicitly. The
Critic must be told: *the decomposition itself is contestable*.

This is what catches the silently-absent principle — the principle
that nobody mentioned because everyone was inside the frame that
hid it. Without licensing, the Critic catches details. With licensing,
the Critic catches the frame.

### P5 — Seed contested questions, don't exhaust them

Six to eight specific seed contests is the right size. Lower and the
Critic isn't primed; higher and the Critic feels boxed in.

**Critically, instruct: "do a full principle audit; do not stop at
the list above."** Good Critics go beyond the seeds. The seeds are
priming, not a checklist.

### P6 — Specific counter-proposals beat flagged concerns

A strong Critic proposes a concrete alternative ("use four dimensions:
X / Y / Z / W"), not just "consider a different decomposition." Ask
for this shape in the Critic prompt. Vague "consider alternatives"
language produces vague responses.

This pattern lets the Round 2 Planner adopt or reject on principled
grounds — "this alternative holds because…" — instead of trying to
guess what the Critic meant.

### P7 — Expect principled adoption, test for deference

In Round 2, check whether the Planner adopted the Critic's suggestions
*because they hold on their own logic*, or *because the Critic said
so*. Specifically test with the **counterfactual deference test**:

> Would this defense have adopted a *different* alternative if a
> counterfactual Critic had proposed it?

If all the Planner's grounds also justify a counterfactual alternative,
the adoption is deferential — pattern-matching, not principled. If
some grounds don't transfer, the defense is specific to the chosen
alternative — principled adoption confirmed.

This test belongs in the Round 2 Critic prompt. See
`references/critic-goal-template.md` for the full text.

### P8 — Keep state files out of git, commit plan files

Per-instance state at `.omh/state/<mode>--<instance_id>.json` is
session scratch. `.omh/plans/<file>.md` is the artifact of record.
Keep `state/` in `.omh/.gitignore`; commit `plans/`.

### P9 — Verify ground-truth freshness before dispatching recon

If your context package points subagents at a local source checkout
as "ground truth" (a vendor repo, a cloned library, an external
project), **verify the checkout is at the version you think it is
before dispatching.** Subagents will faithfully cite whatever they
read; they cannot know if `main` is hundreds of commits behind upstream.

Pre-flight checklist before dispatching against a local source tree:

```bash
cd <source-tree>
git remote -v                                          # confirm remotes
git fetch --all --tags                                 # update refs
git rev-list --left-right --count HEAD...@{upstream}   # ahead/behind
git describe --tags --abbrev=0                         # latest tag at HEAD
```

If HEAD is meaningfully behind the version the recon is *about*,
stop and either (a) update the tree, or (b) explicitly scope the
recon to "what's in the tree at HEAD" with a flag that
version-specific claims must be marked unverifiable.

Add a "Ground truth freshness" subsection to the context package
whenever required reading includes a local source checkout. Record
the commit SHA and its relationship to the upstream version being
designed against. A package that says
"ground truth = `<repo>/@bf196a3f`" is falsifiable; a package that
says "ground truth = `<repo>/`" is not.

If you discover staleness mid-run: don't silently update. Surface
the finding, decide with the user whether to (a) update + re-run
recon, (b) update + patch the recon doc in-place, or (c) proceed
with a caveat banner.

### P10 — Iterate the context package with the user before dispatching

Drafting from reading alone misses dimensions only the user can name.
The user's lived experience of the system surfaces requirements that
no amount of source-reading will.

Discipline:

- Draft the package from reading. Surface sub-dimensions and seed
  contests from source.
- Walk it with the user. Ask: *Is this decomposition right? What
  dimensions are missing? What contests feel under-weighted?*
- Patch in place. Cite changes ("seven dimensions → eight, revised
  in context-review before dispatch") so the Planner sees iteration
  happened and respects it.
- Only then dispatch.

Skipping this costs a ralplan cycle when the Critic catches a
dimension-gap the user would have named pre-dispatch in two minutes.

### P11 — Don't seed contests on questions the user has already settled

Adjacent to P10 but the opposite failure mode. Orchestrators draft
contests by asking "what would the Critic push on?" — and
inadvertently re-open questions the user has already declared settled.

Failure pattern: the user says, in conversation preceding the ralplan,
"the goal is not just to fix X, it is to learn a better pattern for
future Y." The orchestrator then drafts a contest "do we even need
the new pattern, or is the surgical fix sufficient?" That contest
forces the user to re-defend ground they have already taken.

Discipline:

1. **Before drafting contests, list user-settled commitments.** Read
   the conversation that motivated the ralplan. Write down what the
   user has declared, asserted, or chosen *before* the draft began.
   Treat these like non-negotiable constraints until the user
   themselves reopens them.

2. **For each contest, check it against the settled list.** If a
   contest re-opens something settled, do not write it as a contest.
   Write it as a constraint, or fold its commitment into the premise
   of a different contest.

3. **The healthy contest shape, post-commitment, is "given the user's
   committed direction, what's the right shape *inside* that
   commitment?"** Not "should the user have committed?"

4. **When the user surfaces this error in review, take the correction
   at the framing level, not the wording level.** Often there are
   sibling contests/constraints with the same root cause. Sweep for
   them before declaring fixed.

### P12 — Settle filesystem layout before dispatching path-laden goals

If the directory layout the context package references has a "we
should clean that up" smell — sprawl, ad-hoc subdirs, "v2" suffixes,
project-vs-incident confusion — **do the cleanup first, dispatch
second.**

If you dispatch first and refactor after:

- Subagent output will land in directories about to be deleted.
- Required-reading paths will fail to resolve.
- A full re-anchoring becomes a Round 2 rework rather than a sharpening.

Pre-flight checklist before dispatching path-laden goals:

1. List the directory layout the goal references.
2. Eyeball it for sprawl and naming drift.
3. If anything looks wrong, ask the user — they've often been bothered
   by it but haven't surfaced it. The dispatch is the moment to ask.
4. If yes, refactor first. Verify all absolute paths resolve under
   the new layout. Update context.md inline.
5. Then dispatch.

Bonus: cleaning mid-drafting often surfaces missing dimensions for
the design itself, because the cleanup reorganizes the conceptual
landscape the design lives in.

### P13 — Verify external critique's premises, don't inherit them as constraints

When a ralplan responds to external critique (a DM, a bug report, a
review comment, an issue), the critique contains *diagnosis* (what
is wrong), *prescription* (what should be done), and often a *premise*
— an assertion about *why* the current state exists that the critic
did not verify ("I suspect the reason is Z").

If you treat the unverified premise as a given constraint, you erect
the whole stance around a phantom. The phantom-constraint stance will
*feel right*, will survive ralplan review on internal consistency,
and will only collapse when it meets reality.

Discipline:

1. Tag every premise the external critic supplied that is not
   verified-by-you. A premise is "an assertion about *why* the current
   code is the way it is" — distinct from diagnosis (what is wrong)
   or prescription (what to do).

2. Add a **"Premises to verify"** section to the context package,
   listing each tagged premise with: the verbatim claim, what the
   critic said about it, evidence supplied (often "none / suspicion"),
   and the absolute paths the Planner should open to verify.

3. Instruct the Planner explicitly: *verify every premise before
   designing around it. If a premise is wrong, say so and rework on
   the actual constraint.*

4. The Round 1 Critic should also check premise-grounding as a
   distinct test from contesting the framing.

Pattern for the section:

```markdown
## Premises to verify (pre-Planner)

The critique this run responds to supplied these premises without
evidence. Verify each before designing around it.

- **Claim:** "<verbatim>"
  **Source:** <critic's statement>
  **Evidence supplied:** none / partial / speculation
  **Verify by opening:** <absolute paths>
  **If true:** the design honors constraint C<n>.
  **If false:** the design is free of constraint C<n>; revisit.
```

### P14 — Required reading must include adjacent in-tree mechanisms

The most common failure mode for stances that "earn three APPROVEs
and are still wrong": the Planner designs a *new* mechanism for an
adjacent problem the existing codebase already solves. Subagents
designed parallel-build because nobody pointed them at the existing
solution.

Before dispatching, audit the required-reading list against this
question:

> *Is there code already in this tree that solves an adjacent problem
> to the one we are designing for? If yes, it must be in required
> reading — even if the design might not use it.*

Specifically search for:

- Sync / update / manifest engines in `tools/`, `agent/`, `cli/`.
- Anything matching `*_sync.py`, `*_manifest*`, `bundled_*`, names
  with `update`/`reset`/`migrate`.
- Existing CLI subcommands that touch the domain. Their
  implementations carry load-bearing model.
- `optional/`, `migration/`, anywhere prior versions of this problem
  were addressed.

Two minutes of `search_files` for sync/manifest/update keywords during
context-package drafting is dramatically cheaper than a Round 2
rework or a stance shipped into the world that an external collaborator
collapses with a one-sentence "I closed mine because the system
already does this."

**Field signal:** the most reliable indicator that you missed an
adjacent mechanism is an external collaborator (PR, DM, issue) closing
or pivoting a related effort with a sentence about what they're working
around. When such a signal arrives, **search the tree for the named
system before defending the stance.** Often it dissolves the stance.

### P15 — Requirements-shaped artifacts have their own register

A "design stance" and a "requirements document" are different
artifacts. The default Planner template produces stances. When the
artifact is requirements (technology-agnostic NEEDS, not design
positions), three things must change:

1. **Naming.** The distilled output is `requirements.md`, not
   `stance.md`. Provenance still uses `<artifact>-planner.md` /
   `-v2.md` (template-naming consistency), but the canonical
   handed-to-user file matches the artifact noun.

2. **Discipline rules in the context package** (load-bearing for
   requirements runs):
   - **Rule — needs not features.** Good: "the system requires
     persistent first-person knowledge." Bad: "the system uses
     `me.md` to store identity."
   - **Rule — every item has inline citations.** Each requirement
     carries a source tag and either a `file:line` cite, a gap-cite,
     or a principle + named-failure-mode cite.
   - **Rule — prefer missing to fabricating.** Shorter honest beats
     longer tidy. Open questions stay open. Completeness-theater is
     the failure mode for requirements.
   - **Rule — separate need from count/form.** "Three files" is not
     a requirement; "three distinct kinds of self-knowledge" might
     be.
   - **Rule — forbid feature-by-analogy.** "Product Z has feature W,
     so we need it" is not a requirement.
   - **Rule — Critic may halt loop.** A legitimate Critic verdict is
     "requirements cannot yet land; here is what is needed first."
     REQUEST_CHANGES with "not closable" is stronger than APPROVE on
     a flawed artifact.

3. **Source ontology.** Requirements need source tags that distinguish
   *what the source system does*, *what it should do but doesn't*
   (visible gap), and *what a principle demands but no working system
   has exercised*. Tag every item. Mixing these without tags hides
   where evidence is thick vs thin.

When the artifact is requirements, point subagents at substrate /
runtime artifacts (skills, prompts, conventions, READMEs) **in addition
to** the engine code. A requirements run that reads only the engine
misses half the evidence — the lived-use artifacts often carry as
much signal as the source.

### P16 — Apply the counterfactual deference test in Round 2

When the Planner adopted a Critic's Round 1 counter-proposal,
specifically test whether the adoption is *principled* (the alternative
holds for its own reasons) or *deferential* (adopted because the
Critic said so).

Sharpened test: *would the Planner's defense also justify a
counterfactual alternative if a different Critic had proposed one?*

- All grounds transfer → generic principle-citation, deferential.
  REQUEST_CHANGES on shaky ground; demand specific defense of *this*
  cut.
- Some transfer, some don't → defense is specific. Principled
  adoption confirmed.
- None transfer → unusually strong principled defense.

This belongs in the Round 2 Critic prompt. The full template lives
in `references/critic-goal-template.md`.

### P17 — User-conversation-required is a legitimate Round 1 verdict

Sometimes the Round 1 Critic surfaces an ontology question subagents
fundamentally cannot settle — one that requires the user's principled
commitment, not more subagent reasoning.

License this in the Round 1 Critic prompt as a fourth verdict class:

> **user-conversation-required: \<crisp question\>** — "this question
> requires the user's principled commitment, not more subagent work.
> Here is the question crisply."

When this fires, the orchestrator escalates, gets the answer, and
encodes it as **principled direction** in the Round 2 Planner prompt
(not as "consider"). Faster than halting; honors altitude.

### P18 — User-steer between rounds can RESHAPE the surface, not just settle

Stronger pattern than P17. When you surface a Round 1 Critic catch
to the user between rounds, the user's response can:

- *Settle* a single ontology question (small) — encode as Round 2
  direction.
- *Reshape* the whole design surface (large) — add new tiers, name
  new directions the loop didn't have access to.

Do not pre-narrow the question to a binary at the surfacing moment.
Frame the catch *and* the surrounding design space honestly. Let
the user reshape if they see something the loop missed.

When surfacing reshape-prone questions, end the framing with: *"Did
I leave anything out?"* — this is the reshape-license. Without it,
the user may answer the binary as posed and miss the reshape.

When the user reshapes, encode every direction they named as principled
direction in the Round 2 Planner prompt. The orchestrator's job at
the surfacing moment is to **listen, not advocate**.

The reshape pattern has a tell: the user's response opens with
reframing language ("the third tier is X") or negates the framing
("for *this case* specifically..."). When that happens, you're in a
reshape, not a settle. Don't try to fold the reshape back into the
binary you surfaced.

### P19 — APPROVE_WITH_PROVISO: a fourth Round-2 verdict

The default verdict catalog (APPROVE / APPROVE_WITH_RESERVATIONS /
REQUEST_CHANGES / REJECT) sometimes leaves a gap: small named
additions the canonical artifact must include, but too small for a
Round 3.

License **APPROVE_WITH_PROVISO** as a fourth Round-2 verdict — a
verdict with two-to-four small named additions (a missing principle
statement, a contract clarification, a failure-handling note) that
should be folded into the canonical stance during distillation.

Distinguish from APPROVE_WITH_RESERVATIONS: reservations are notes
for the orchestrator to weigh; provisos are **specific edits the
canonical artifact must include**.

When to license PROVISO:

- Round 2 catches that are surface-level (single section additions,
  principle namings, missing-rule-statements) but load-bearing.
- The Critic can write the proviso text in the review (or close
  enough) such that distillation is mechanical fold-in, not redesign.
- The orchestrator has confidence the provisos can be folded without
  unbalancing the stance.

Don't use PROVISO to avoid Round 3 ceremony for changes that actually
need it. If the proviso would touch multiple sections, change a
load-bearing decision, or require its own coherence check — that's
REQUEST_CHANGES, not PROVISO.

Distillation discipline for PROVISO:

1. Place each proviso in the section it belongs to thematically —
   don't bolt onto the end.
2. Strip Round-2 reviewer scaffolding (response maps, self-graded
   verdicts) before folding.
3. Update any test list if the proviso adds testable behavior.
4. Note the fold-in source in the orchestrator review:
   "Critic R2 PROVISO: X. Folded into §N as <treatment>."

This keeps provenance honest: the canonical stance is the consensus
product, but the orchestrator review records what was folded vs
what was punted.

### P20 — Seeded contests can DIE during context-iteration

P10 emphasizes iterating with the user before dispatch. The case
P10 makes is *the user adds dimensions or contests the loop missed*.

The converse is also true: **the user's framing can kill contests
the orchestrator seeded as load-bearing.**

Pattern: the orchestrator drafts contests inside the loop's frame.
The user names a frame the loop didn't have access to ("this is also
a proving ground for X," "we are committed to the pattern, not
debating it"). Contests that made sense inside the loop's frame
become incoherent inside the user's frame.

Discipline:

1. **When the user reframes during context-iteration, walk every
   contest and ask: does this still make sense in the new frame?**
   Mark phantom contests for deletion.

2. **Don't soft-kill phantom contests by editing them into something
   else.** If the contest was "do we need the new mechanism," and
   the new frame says "yes, we are building it" — don't rewrite the
   contest into "where does the mechanism live." That's a different
   contest. Add it as a new C-id; let the original die clean.

3. **The reframe usually comes with new contests the loop couldn't
   have seeded.** P10 covers this side. P20 covers the deletion side.

4. **Track the kill in the context package.** Either via a "Contests
   killed during context-iteration: <list>" subsection (good for
   provenance), or version-control the context.md file so the diff
   is the record.

Why this is its own pitfall, not a sub-case of P10: orchestrators
are biased to *add* during iteration (more contests, more dimensions,
more required reading) because adding feels like thoroughness.
**Subtraction is just as load-bearing**, and harder to do because
you must admit something you wrote was wrong-shape.

### P21 — Both rounds must look for silently-absent moves

Round 1's biggest move is the silently-absent catch — the principle
nowhere mentioned, the dimension everyone skipped because they were
all inside the same frame. The META question + principle audit fire
this.

Round 2 has its own silently-absent move. Round 1 catches landed; the
stance reorganized; **what is silently absent now?** Walk all principles
again. The new stance has a new frame; new things may be silently
absent inside it.

Add to Round 2 Critic prompt: "Now that Round 1 catches landed in
Round 2, is there a NEW silently-absent principle? Walk all principles
again."

The loop's job is to find these in both rounds. Round 1's silently-
absent is structural. Round 2's silently-absent is contractual —
typically about cooperation, error-handling, edge-cases the new
structure assumes but doesn't state.

### P22 — Audit parent-stance vetting state before dispatching a feature-area ralplan

A feature-area ralplan (a sub-domain ralplan inside a larger design
tree, e.g. `docs/design/<sub-domain>/` under a project that already
has `docs/design/<parent-domain>/stance.md`) inherits its design ground
from the parent stance. If the parent stance carries explicit positions
that the new design would override, dispatching the feature-area
ralplan first either re-litigates parent positions through a sub-
domain run (wrong altitude — a feature-area ralplan should accept the
parent's positions as constraints, not contest them) or silently
overrides them (worse — the override is buried in feature-area
artifacts where future readers will not know to look).

The trap is amplified when the **parent stance is unvetted**: it has
three-APPROVE consensus from a prior ralplan run but never went
through synchronous user+orchestrator review. Such a stance carries
positions that *might be* settled-with-the-user but functionally are
not. A new feature-area ralplan dispatched against unvetted parent
ground is designing on shifting earth.

A second related trap: the parent stance is vetted but was authored
**before lived-use evidence** the current session has surfaced. The
new design discussion has reshaped what should-be-true at the parent
level, and dispatching the feature-area ralplan would encode the
reshape in the wrong artifact (feature-area stance, not parent
stance).

**Pre-flight check, before dispatching any non-top-level ralplan:**

1. **Walk the design tree upward.** From the proposed sub-domain
   directory, walk up through `docs/design/` — does a parent stance
   exist? A cross-cutting stance? Sibling stances that overlap?

2. **For each parent stance, check its vetting state.** Was it vetted
   synchronously with the user (an `<orchestrator>-review-deep.md`
   exists AND a `brief.md` was discussed)? Or does `plan.md` /
   equivalent forward-view doc list a "vet this stance" gate that
   has not yet fired?

3. **For each parent stance, walk its positions against this
   session's reshapes.** Specifically: any user-named reframes from
   the current session, and the contests-killed-during-iteration list.
   Do any contradict explicit parent-stance positions?

4. **If the answer to (2) or (3) is yes, the right move is one of:**

   - **Pivot to parent-stance vetting first.** Author the prep doc
     the parent's vetting gate calls for (e.g.
     `<parent-domain>/stance-review.md`), incorporate this session's
     evidence as a fresh lens, run the synchronous vetting gate with
     the user, then dispatch the feature-area ralplan against
     rectified parent ground.

     **Sub-case — prep doc already exists, half-baked.** The prep doc
     for the parent vetting gate may already exist on disk from an
     earlier session (e.g. `stance-review.md` with Lenses 1–3 authored
     weeks ago) without ever having been walked. Don't rewrite — *add
     a new lens* anchored in the current session's evidence. This
     keeps the prior lenses as provenance, scopes the rectification
     to what's actually new, and makes the vetting walk reviewable
     section-by-section. Field signal: you find a `stance-review.md`
     with prior dated lenses and a "Suggested session order" that
     names questions that were never answered. Add Lens N+1 with a
     dated header, name in the file's frontmatter that an earlier
     vetting was deferred, and walk all lenses in the synchronous
     gate (the old questions may dissolve under the new evidence;
     P20 — seeded contests can die — applies upward).

     **Lived-use evidence as anchor.** When the current session's
     reshape comes from *lived-use evidence* (the parent stance was
     authored before the system actually ran, and now real use has
     surfaced what didn't hold), make that explicit in the new lens.
     Lived-use evidence has a different epistemic weight than recon
     evidence — it's one-shot proof of failure mode, not "here's a
     pattern that might apply." Name it as such; the user's vetting
     decision has more grip when the evidence type is clear.

   - **Make the override explicit and route through the parent.**
     If the user's reshape genuinely belongs as an amendment to the
     parent stance rather than a feature-area design, write the
     amendment as a parent-level rectification in one commit, vet it,
     then dispatch the feature-area ralplan.

   - **Confirm with the user that the override is intentional and
     scoped to the feature area.** Rare but real — sometimes a
     feature-area design legitimately needs a position the parent
     stance didn't anticipate, and the right move is to scope the
     position narrowly and note it in the feature-area's
     `context.md` constraints. Get the user's nod before committing.

The wrong move is dispatching the feature-area ralplan and letting
the loop discover the parent collision. The Critic *will* catch it
(this is exactly the META-question's job), but the round was wasted
producing internally-consistent feature-area work that has to be
discarded. Pre-flight catches it without burning a round.

**Field signal that this pitfall just fired:** you author `context.md`
for a sub-domain, walk the source for required reading, and find a
parent `stance.md` whose positions on the same questions are
*opposite* to the direction the conversation has been going. If you
find yourself thinking "I'll seed a contest to re-open this parent
position" — stop. Re-opening a parent position is not a feature-area
contest; it is a parent-stance rectification. Pivot.

This pitfall sits between P10 (iterate context with user pre-dispatch)
and P11 (don't seed contests on settled questions). P10 is about
adding what the user knows before dispatch; P11 is about not
re-opening what the user has settled within the same design domain.
P23 is about not crossing design-domain boundaries silently.

### P24 — Delegation-for-vantage works (the principle behind the method)

This is the principle that motivates the whole skill. When the user
would otherwise be in a turn-by-turn proposal loop, rise:

- Carve principles → delegate deep work → distill → review.

The first time you run ralplan well, the resulting stance will be
stronger than anything proposal-correction would have produced — and
the user can step away during the loop. That is the value the
orchestrator delivers, and the reason the orchestrator's discipline
matters more than the workers' cleverness.

If you find yourself in a turn-by-turn correction loop with the user
on a multi-decision project: stop. Carve principles. Run ralplan.
Review. Hand over.

### P25 — Don't drop into the loop's spiral; skepticism over deference

The orchestrator role exists for one reason: **to stay above the
work** so you can dispatch with one altitude and review with
another. The whole machinery — context package, dispatched
subagents, named verdicts, distillation, the orchestrator review
gate — exists so *you* keep clarity and discernment that the
subagents inside the frame cannot have.

The failure mode this pitfall names: the orchestrator gets pulled
*down* into the loop's altitude because the loop's output feels
meaningful. Symptoms:

- A Critic counter-proposal lands that you can't quickly dismiss,
  and your instinct is to **surface it to the user as a question**
  rather than answer it from above.
- You find yourself agreeing with depth-theater because you're
  inside the spiral and the spiral *feels* like rigor.
- The stance grows scope (a 14th principle, a new contest opened
  by Round-1 catches, an "I should also...") and you accept the
  growth instead of cutting it.
- Round 2 feels mandatory because the catches "must be addressed"
  rather than because the catches are genuinely load-bearing.
- You find yourself authoring within the loop (carving language,
  proposing reframings) — pulled down from dispatcher to worker.

The structural fix is **skepticism, not deference.** Trust given
to you (by the user installing you as orchestrator) is meant to
be **USED**, not held in reserve until the user reactivates it
through correction.

Operational discipline:

1. **The first move on any Critic / Architect catch is your own
   judgment, not the user's.** Read the catch. Apply your own
   bar. If it's depth-theater, dismiss it from above; the
   orchestrator review section is where you say so. If it's
   genuinely load-bearing, route it to Round 2 with explicit
   framing. Never *first* surface to the user as "what should we
   do?" — that's deference.

2. **Watch for metaphysical / governance-level catches** — claims
   like "convergence is X's act" or "this needs a 14th principle"
   that the loop produced. These are very rarely the right shape
   for a feature-area ralplan. The Critic *should* contest framing
   (P4 META question) but framing-contest results rarely belong
   in the canonical stance — they belong in the orchestrator
   review as "the loop surfaced X; here's why it's not a stance
   change."

3. **If the stance is more than ~50% of the size you expected,
   pause and ask why.** Volume is a tell. If the design problem
   is "extend an existing system with a new instance of the same
   shape" (P12 continuity), the stance should not produce a
   first-principles re-derivation of the system. If you find
   yourself reading 5000+ words of new doctrine for what should
   have been ~1500 words of "do this, then this, then this,"
   the loop has spiraled and you are inside it.

4. **The user's continuity-check question is a tell.** If the
   user reads what you produced and reacts with "this seems like
   over-engineering" / "you're blowing this out of proportion" /
   "we just need to extend X" — that *is* the altitude correction.
   The right response is not Round 2 with the user's correction
   folded in; the right response is to **close the run and pivot
   to a different altitude entirely** (often: requirements-first,
   classical layer below ralplan).

5. **Pivot to requirements when the design pass produced design-
   theater.** Requirements are technology-agnostic, lean, and
   produce a constraint surface the design pass can be honestly
   small against. P15 names that requirements and stances are
   different artifacts; this pitfall extends that — sometimes the
   right move after a sprawling stance is *backward* to the
   requirements layer the stance should have been authored against,
   not *forward* to another round.

6. **Author the orchestrator review honestly.** If the loop
   produced more ceremony than rigor, **say so in the review** and
   either re-run with a tightened scope or pivot. The "do not hand
   the user output below your own bar" discipline is exactly here:
   the altitude compact depends on you being honest about what
   the loop produced. *(Field signal that this pitfall just fired:
   you are about to write "the loop surfaced some interesting
   questions" or "<user> may want to weigh in on..." — both are
   the orchestrator dropping back into the user's altitude. The
   orchestrator review's job is to apply YOUR bar; if the bar
   wasn't met, that's a fact the review names, not a question for
   the user to settle.)*

The trust the orchestrator was given **is the discernment**. Using
it is the role. Surfacing every catch to the user as a question
inverts the role into "subagent to user" — which is exactly the
turn-by-turn correction loop ralplan was built to avoid (P24).

### P26 — Deliver decisions-first; deep review is for the archive

The orchestrator's deep review (`<orchestrator>-review-deep.md` —
see step 5) is comprehensive: round tally, what-the-Critic-caught,
where-I-push-back, where-I-think-the-user-will-push-back,
what-this-run-proved-about-the-method, altitude addendum. It is
honest. It is also **the wrong artifact to hand the user when you
need a decision.**

The failure mode this pitfall names: the orchestrator writes a
strong deep review, the user reads it, and the user reports being
"comprehensive and dense, yet oddly terse... I read a lot of this
detail and am somewhat lost and dissociated. I really need you to
bring me back a set of decisions you need me to make, even if
agreement on something that was different from what we discussed
and why."

Translation: the deep review surfaces internal chatter the user
already trusted you to handle. It demands the user re-traverse
reasoning the loop already collapsed. It conflates *show your work*
(which the deep review does) with *give me what I need to give
judgment* (which is a different artifact). An executive presented
with the deep review cannot give judgment from it; an executive
presented with a brief can.

Discipline:

1. **Two artifacts at the orchestrator-review step, not one.** Deep
   review for the archive (preserves provenance and your honest
   self-assessment). Brief for delivery. Step 5 of the playbook
   spells out both; honor it.

2. **Decisions-first in the brief.** Lead with the decisions the
   user needs to make, numbered. For each decision, state your-take
   *and* the alternative. The user can scan, decide, return — they
   should not need to read the deep review to know what they are
   deciding.

3. **Name deviations from pre-dispatch conversation explicitly.**
   The user spent effort working through big rocks, nuances, and
   considerations with you up-front. If the loop produced something
   different from what you discussed, **say so in the brief** with
   why. Hidden deviations corrode trust faster than admitted ones.

4. **Where the design landed in one paragraph, not eight.** The deep
   review's "where the stance ended up" 5–8 paragraph treatment
   belongs in the deep review. The brief gets one paragraph that a
   reader can hold in working memory while deciding.

5. **Open questions and next steps belong in the brief.** They are
   user-actionable. The internal chatter (deference tests,
   altitude observations, pitfall-naming for the skill) belongs
   only in the deep review.

6. **The brief is the test of altitude.** If you cannot reduce the
   deep review to a clean decisions-first brief, **you do not have
   the altitude you think you have.** Write the brief; if it
   sprawls, that is a signal — not to ship a longer brief, but to
   re-run the distillation pass on the *deep review* until the
   brief lands clean.

7. **When the user reads only the brief, that is the success
   condition, not the failure mode.** Many runs the user will
   never read the deep review. That is correct. The deep review
   is provenance; the brief is delivery.

Field signal that this pitfall just fired: the user reads what you
delivered and reports being lost / dissociated / unable to give
judgment. **Do not respond by adding more to the deep review.**
Respond by extracting a brief from it and patching the skill so
future runs default to brief-as-delivery.

#### The same frame applies pre-dispatch — brief, don't ask

The brief-as-delivery discipline above governs the *post-distillation*
hand-off. The same presidential-briefing frame applies *earlier*, at
**pre-dispatch decision moments** (P10 walks, P18 mid-session
reframes, premise pre-settlements, multi-question batches). The
failure mode there is symmetrical: the orchestrator hands the user
open-ended questions — *"what do you think about X?"*, *"should we
Y or Z?"* — instead of a structured briefing. The user has to
construct the analysis from scratch; the orchestrator avoids
committing to a position.

Discipline at pre-dispatch is the same shape, compressed for inline
flow. Each decision-briefing has four sections, in order:

1. **The question.** One paragraph naming what's being decided.
   Concrete, specific, no preamble.
2. **What's at stake.** Two short paragraphs naming the trade-offs.
   Both options' costs, both options' benefits, what fails in each
   case. Not balanced if the trade-off isn't balanced — say which
   side has the asymmetry.
3. **My recommendation.** One sentence followed by 2–4 reasons,
   each one sentence. The orchestrator owns this — don't hide
   behind "you decide." If you genuinely don't have a
   recommendation, that is a different shape (clarify-before-
   deciding); brief that explicitly.
4. **What hangs on it.** Concrete consequences: which file changes,
   which design decisions cascade, what gets simpler or harder
   downstream.

Why this works pre-dispatch:

- The user can ratify ("yes" / "all three" / "go") without
  rebuilding the analysis. Most pre-dispatch decisions are calls
  the user agrees with the orchestrator on once it's framed
  correctly.
- When the user *does* push back, the pushback is precise — they
  have the same frame to work in.
- The orchestrator is forced to actually take a position. *"What
  do you think?"* lets the orchestrator avoid commitment; the
  briefing format requires you to recommend.

When to brief pre-dispatch:
- Pre-dispatch settlements (load-bearing premises that would
  otherwise be Round-1 contests).
- Mid-session reframes when the user shifts the architectural
  ground (P18).
- Multi-question batches where independent decisions cluster.

When NOT to brief:
- Single-step mechanical decisions (*"commit this?"* — just
  commit it).
- Things the user has already committed to (don't re-litigate).
- Genuinely open questions that need conversation, not
  ratification (*"what's the v12 theme?"* — that's a discussion).

**The format is the discipline.** You may compress for short
briefings (one paragraph each), but the *structure* — what's at
stake, recommendation, consequences — earns its place even at
small scale. The post-distillation brief and the pre-dispatch
briefing are two faces of the same orchestrator move: take a
position, lay out what hangs on it, let the user ratify or push
back from a shared frame.

See `references/brief-template.md` for the structural template.

This pitfall also fixes a definitional ambiguity earlier sections
(P19, the orchestrator-review template) carried: when those
sections say "the orchestrator review," they mean the deep review
(`<orchestrator>-review-deep.md`). Provisos still get folded in
the deep review's distillation section; the brief simply doesn't
need to surface them unless one of them rises to a user-decision.

## Template for the delegate_task goal

```
[omh-role:planner] <one-line goal>

## Required reading (open these files, do not work from summaries)

Absolute path base: `/.../project/`

<ordered list of files, grouped by category: principles, directives,
inspiration findings, existing-code, context package>

## <Design sub-dimensions, constraints, out-of-scope>

## Questions you must actively contest

- **(META) Are these the right sub-dimensions?** ...
- <six-to-eight specific seed contests>

## Output

Write to: <absolute path>
Structure: <named sections>
Word count target: ...
End with verdict: APPROVE / REQUEST_CHANGES
```

Keep the goal self-contained. Subagents have zero prior context.

Full reusable templates in `references/`:

- `references/planner-goal-template.md` — Round 1 Planner (with
  Requirements variant + Lived-moments hunt-list)
- `references/architect-goal-template.md` — Round 1 Architect
- `references/critic-goal-template.md` — Round 1 + Round 2 Critic
  (the most important template — the Critic produces the quality)
- `references/orchestrator-review-template.md` — final quality gate

Variables in angle brackets are domain-specific. Keep the structure;
each section earns its place.

## File layout for a ralplan domain

```
docs/design/<domain>/
├── context.md               ← input, reviewed by user
├── stance-planner.md        ← Round 1
├── review-architect.md      ← Round 1
├── review-critic.md         ← Round 1
├── stance-planner-v2.md     ← Round 2 (with response map)
├── review-architect-v2.md   ← Round 2
├── review-critic-v2.md      ← Round 2
├── stance.md                ← distilled from v2; canonical user-read
├── brief.md                      ← decisions-first, what the user reads
├── <orchestrator>-review-deep.md ← orchestrator's archive deep review
└── (later) implementation-plan.md
```

`.omh/plans/ralplan-<instance-id>.md` — short consensus summary,
separate from the design directory. Outside the design artifact lineage.

## State tracked via omh_state

```python
omh_state(action="write", mode="ralplan", instance_id="<slug>", data={
    "goal": "...",
    "round": 1,  # or 2 / 3
    "phase": "context-gathering | round-N-<role> | complete",
    "consensus": False,
    "plan_file": ".omh/plans/ralplan-<slug>.md",
    "round_1": {"planner_verdict": "...", "architect_verdict": "...", "critic_verdict": "..."},
    "round_2": {...},
})
```

This is the session-resumable state. If the orchestrator session is
interrupted, the next session reads this and resumes.

## What "done" looks like for the orchestrator

- Three-APPROVE consensus (or max 3 rounds with caveats; or
  APPROVE_WITH_PROVISO with provisos folded; or
  user-conversation-required surfaced and resolved).
- Canonical `stance.md` (or `requirements.md`) written, free of
  reviewer-scaffolding.
- `.omh/plans/<file>.md` consensus summary written.
- `<orchestrator>-review-deep.md` written — honest, specific, not
  performative (the archive / provenance artifact).
- `brief.md` written — decisions-first, ~1 page, what the user
  reads to give judgment (P26).
- Single commit capturing the domain artifacts + state gitignore.
- Commit message names: what the Critic caught, key positions
  landed, MV ready to execute on user sign-off.

## Maintaining your own run log

This skill grows by patching pitfalls in. After each ralplan run,
ask:

- Was there a failure mode that fits an existing pitfall? Strengthen
  it with the new evidence — date the addendum.
- Was there a failure mode that doesn't fit any existing pitfall?
  Add a new one (P23, P24…). Name the failure mode crisply, give a
  concrete example, give discipline rules.
- Was there a discipline that worked unusually well? Promote it from
  one-time success to named pattern.

The skill becomes higher-quality with each run *only* if you patch
it. A skill that doesn't get patched after surprising the orchestrator
becomes a liability — confident-sounding but stale.

Keep your own run log somewhere outside the skill (your substrate,
your project notes, a wiki) — date, domain, rounds, surprises, what
you patched. Don't let this skill turn into a session log; it's
playbook, not journal.

## Do-not-lose content (if this skill has to be regenerated from memory)

The one insight that matters most: **the Critic must be licensed to
contest the framing itself.** Without the META question in the context
package, the Critic stays inside the frame — checking compliance
rather than testing truth. With it, the Critic becomes a reasoning
peer who can catch principle-absences neither the Planner nor the
Architect will see because they are inside the frame.

This is the single move that makes ralplan better than any proposal-
correction loop between orchestrator and user. Everything else in
this skill exists to support this move.

Second-most-important: **specific counter-proposals beat flagged
concerns.** A good Critic proposes a concrete alternative, not just
"consider a different decomposition." The Critic prompt must invite
this shape. The Round 2 Critic then tests for principled adoption
vs deference.

Third: **orchestrator review is the final gate.** Do not hand the
user output below your own bar. If the stance is weak, run another
round or strengthen the principles. The altitude compact depends on
this.

Fourth: **prep is half the value.** The context package is where
quality is born. Verify ground truth, surface adjacent mechanisms,
verify external premises, settle filesystem layout, walk it with the
user, kill phantom contests on reframe. Most pitfalls in this skill
are pre-dispatch failures. Treat the package as the load-bearing
artifact it is.

Fifth: **decisions-first delivery, deep review for the archive.**
At the orchestrator-review step, write two artifacts: `brief.md`
(what the user reads to give judgment, decisions-first, ~1 page)
and `<orchestrator>-review-deep.md` (provenance, internal chatter,
the honest self-assessment). The user must be able to give judgment
from the brief alone — never make them traverse the deep review
just to know what to decide. P26 names this and the failure mode
(handing the comprehensive deep review when an executive-style
brief was needed). The brief is the test of altitude: if you cannot
distill the deep review into a clean decisions-first brief, you do
not have the altitude you think you have.
