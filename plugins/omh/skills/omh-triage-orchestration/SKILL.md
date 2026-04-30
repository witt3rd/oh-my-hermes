---
name: omh-triage-orchestration
description: "Dispatcher's playbook for omh-triage runs (when to invoke, how to drive)"
version: 0.1.0
metadata:
  hermes:
    tags: [triage, orchestration, dispatcher, multi-agent]
    category: omh
    requires_toolsets: [terminal, omh, delegation]
---

# OMH Triage Orchestration — Driving a Triage Run

> **v0.1 status:** Like the worker skill (`omh-triage`), this dispatcher's playbook is deliberately small. Pitfalls accumulate through lived rounds. The `omh-ralplan-orchestration` skill is the structural model — that one shipped to 25 numbered pitfalls only after multiple real runs surfaced each failure mode. This one starts at T1–T6 and grows.

## When You Are the Orchestrator

You are the orchestrator if you are dispatching `omh-triage` against a backlog and intending to land verdicts (closures, recasts, version targeting) on real issues.

You are not the orchestrator if you are running `omh-triage` as an experiment to see what the skill produces (no execution intent). For experiments, skip the user sign-off gate and just observe — but mark the run as exploratory in any output doc.

## Pre-flight Discipline

Before invoking `omh-triage`:

### Audit the backlog state

1. **Issue count.** If <10 open issues, you probably don't need triage; just decide manually. If >100 open issues, the backlog has rotted; do a manual first-pass cull before invoking.
2. **Time since last grooming.** If <2 weeks AND no major refactor landed, may not be worth a round.
3. **Project board state** (if any). Cards in "Won't ship" / staging columns should be drained by a triage round, not left to accumulate.
4. **Recent migrations or refactors.** This is the load-bearing pre-flight check — *what surfaces have moved since issues were filed?* If the answer is "many," triage is high-leverage. If the answer is "none," triage is low-leverage.

### Audit the **trigger**

What's the actual reason for this run?

- "About to cut version vN+1, want to know what's in scope" → triage will inform version-cut planning. Output should target the project's version field.
- "Just shipped a major migration, several issues may be stale" → triage is a cleanup pass. Output is mostly closures.
- "Backlog feels heavy, want to prune" → Skeptic's pressure dominates; Maintainer is supporting. Frame the goal accordingly.
- "Periodic hygiene, no specific motivator" → low-priority; consider deferring until a triggering reason exists.

The trigger shapes how you weight the role outputs. A cleanup-pass run weights Maintainer; a pruning run weights Skeptic.

### Audit the host project's discipline

Does the host project have:
- A `docs/triage/PROCESS.md` documenting two-mode discipline (quick-file vs grooming)?
- A GitHub Project with target-version + cluster fields?
- A prior triage doc to delta against?

If not, propose authoring these first — `omh-triage` produces dated docs and project-board updates; if there's no infrastructure to write them into, the output evaporates.

## The dispatcher's job during the run

### During Phase 0 (context gathering)

You author the context package, not a subagent. The package shapes both subagents' work; getting it wrong wastes both passes.

The package must include:
- Repo HEAD ref (the anchor for Maintainer's vetting)
- List of recent migrations / refactors with brief description (so Maintainer doesn't re-derive)
- Issue count + label distribution + age distribution
- Prior triage doc summary (if any), specifically: what verdicts landed, what was deferred
- The trigger framing (cleanup vs pruning vs hygiene)

If the package is over ~1000 words, it's bloated. ~500 is the target.

### During Phase 1 (role passes)

Maintainer first; Skeptic only on Maintainer's live + recast output. Don't run them parallel-from-scratch — the Skeptic needs Maintainer's verdicts to know what to review.

Watch for these failure modes (each becomes a numbered pitfall as it's lived):

- **T1 — Maintainer claims "stale" without a commit ref.** Reject and request anchor. "Done in a recent migration" is not a valid anchor; "Done in v6 (commit `c49abbf`)" is.
- **T2 — Skeptic reviews stale issues.** A waste-of-pass. The skill body says skip them, but if the dispatcher passes the wrong inventory to Skeptic, this happens.
- **T3 — Subagent produces a flat narrative instead of per-issue blocks.** The skill's output format is structured for a reason — distillation depends on per-issue parsing. Reject and request structured output.

### During Phase 2 (distillation)

You — the orchestrator — produce the resolution table per the skill's verdict-combination matrix. Conflicts go to user, not auto-resolved. Be specific about *which* issues are conflicts; "there are some conflicts" is not enough.

If the round produced **no conflicts**, that's worth noting. Either the role pressures are well-aligned this round (good) or the roles haven't pressed hard enough (bad). After several rounds with zero conflicts, it's time to add a third role.

### During Phase 3 (execution)

User-gated. Execute closures, recasts, board updates. Use the `/tmp/closeN.md` + shell-loop idiom for the actual close commands (not `terminal()` from `execute_code` — multi-paragraph quoted bodies fail silently there; learned in janus round 1).

After execution, write the round doc. The doc names what you did, what you deferred, and what the round *taught* — lessons that may want to fold back into PROCESS.md or this skill if subsequent rounds confirm them.

## Pitfalls (v0.1)

### T1 — Skipping ground-truth pre-flight

The dispatcher's biggest leverage is Phase 0. A run with bad ground truth produces stale verdicts that look authoritative because they came from a multi-role consensus. The discipline: spend 10 minutes mapping recent migrations *before* dispatching anyone.

### T2 — Authoring the triage doc before the run

Don't write your verdicts into the doc and then run `omh-triage` to "validate" them. The roles' job is to surface what the dispatcher missed; if the dispatcher already decided, the roles are theater. Write the doc *from* the run output, not *toward* it.

### T3 — Letting the run grow scope

A grooming round has a defined scope: the open issues at the time of the run. If a role surfaces "we should also redesign X" — that's a separate ralplan, not part of triage. Note it in the round doc's "deferred" section; don't try to handle it in-loop.

### T4 — Treating the close pile as low-attention

Closures are durable. A wrongly-closed issue is much harder to recover than a wrongly-kept one. Read every pointer-comment before posting, even when the role's verdict feels clear. The Maintainer's "stale" verdict is your verdict to ratify, not to rubber-stamp.

### T5 — Conflicts presented as questions, not as decisions

When the roles disagree, your distillation should produce a **specific decision question for the user** — not a generic "there's some disagreement on these N issues." Frame each conflict as: "Maintainer says X for reason A; Skeptic says Y for reason B; my recommendation is Z." Then ask. (See `omh-ralplan-orchestration` P25 — skepticism over deference.)

### T6 — Running too often

Grooming is not a daily activity. If you find yourself dispatching `omh-triage` weekly, the underlying problem is more issues are filed than the team is willing to act on; the fix is upstream (better filing discipline, smaller backlog, fewer new issues), not more triage.

## Templates

- `plugins/omh/skills/omh-triage/references/triage-doc-template.md` — structure for the round doc
- `plugins/omh/skills/omh-triage/references/orchestrator-review-template.md` — pre-execution review by you

## Pairs With

- `omh-triage` — the worker skill
- `omh-ralplan-orchestration` — the structural model this followed
- The host project's `docs/triage/PROCESS.md` if one exists (defines the two-mode quick-file/grooming discipline that triage runs *within*)
