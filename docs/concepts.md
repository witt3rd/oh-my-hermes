# OMH Concepts

How the four skills work and how they compose. For installation and the
top-level pitch, see the project [README](../README.md).

## How They Compose

```
omh-deep-interview  →  confirmed spec (.omh/specs/)
        ↓
omh-ralplan         →  consensus plan (.omh/plans/)
        ↓
omh-autopilot       →  detects existing spec/plan, skips completed phases
        ↓ (internally uses)
omh-ralph           →  one-task-per-invocation until verified complete
```

Each skill works standalone. Autopilot composes them into a pipeline but any
skill can be used independently:

- **Just need a plan?** → `omh-ralplan`
- **Vague idea?** → `omh-deep-interview` → `omh-ralplan`
- **Have a plan, need execution?** → `omh-ralph`
- **End-to-end?** → `omh-autopilot`

## Consensus Planning (Ralplan)

Three perspectives debate until they agree:

```
Planner drafts a plan
    → Architect reviews for structural soundness
    → Critic challenges assumptions adversarially
    → If not all APPROVE: Planner revises, loop back (max 3 rounds)
    → Consensus reached: plan written to .omh/plans/
```

This catches blind spots that a single agent misses. The Critic's job is to
break the plan — if it survives, it's stronger for it.

## Requirements Interview (Deep Interview)

A Socratic conversation that gates on user-confirmed readiness, not automated
scoring:

- Asks one targeted question per round, focused on the weakest dimension
- Tracks coverage across four dimensions: Goal, Constraints, Success
  Criteria, Existing Context
- Uses coarse bins (HIGH/MEDIUM/LOW/CLEAR) as heuristics, never as exit gates
- The user always decides when they're done — scoring never auto-terminates
- Outputs a confirmed spec that downstream skills consume

Design decisions made during consensus review:

- Coarse bins over float scores (LLM self-assessment lacks decimal precision)
- User-confirmed exit over threshold-gated exit (the user is the authority)
- Ask about brownfield, don't auto-detect (respects user knowledge)
- Adaptive questioning over named challenge modes (simpler, same effect)

## Verified Execution (Ralph)

One-task-per-invocation persistence:

```
Read state → Pick next task → Execute (delegate_task with executor role)
    → Verify (orchestrator runs builds/tests, then delegate_task with verifier role)
    → Update state → Exit
    → Caller re-invokes for next task
```

Key mechanisms:

- **Planning gate**: Won't execute without a spec or plan with acceptance
  criteria
- **Separation of concerns**: Executor writes code, verifier checks evidence
  (read-only), architect reviews holistically
- **3-strike circuit breaker**: Same error fingerprint 3 times → stop and
  surface the fundamental issue
- **Cancel signal**: `cancel_requested` in the mode's own state file, with a
  30-second TTL for
  clean abort
- **Learnings forward**: Completed task discoveries feed into subsequent
  executor context
- **Parallel-first**: Independent tasks batch up to 3 concurrent subagents

## Full Pipeline (Autopilot)

Composes all skills into phases, detecting existing artifacts to skip
completed work:

```
Phase 0: Requirements  → deep-interview (skip if .omh/specs/ has confirmed spec)
Phase 1: Planning      → ralplan consensus (skip if .omh/plans/ has approved plan)
Phase 2: Execution     → ralph persistence loop
Phase 3: QA            → build + test cycling
Phase 4: Validation    → parallel review (architect + security + code reviewer)
Phase 5: Cleanup       → delete state files, report summary
```

## State Convention

State and artifacts live in `.omh/` within the project directory. See the
[`.omh/` README](../.omh/README.md) for the directory layout, what's tracked
vs. ignored, and the rationale.
