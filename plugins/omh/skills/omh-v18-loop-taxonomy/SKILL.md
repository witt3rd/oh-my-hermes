---
name: omh-v18-loop-taxonomy
description: "Saturate loop kind taxonomy: six typed loop kinds, per-kind specs, turn results, terminal states. OMH v18 skill→kind mapping."
version: 1.0.0
author: Forge ⚒️
license: MIT
metadata:
  hermes:
    tags: [omh, saturate, loops, loop-kinds, taxonomy, types]
    category: omh
---

# OMH v18 Loop Taxonomy

The loop taxonomy lives in Saturate and OMH maps to it. Every OMH skill is
an instance of a Saturate loop kind. The kind determines iteration semantics,
turn result types, terminal states, and spec schema.

**Source of truth:** `~/src/witt3rd/saturate/ARCHITECTURE.md` (Loop Taxonomy section)
**OMH architecture:** `~/src/witt3rd/oh-my-hermes/docs/v18/architecture.md`

---

## The Six Loop Kinds

```python
class MetricOptimizationKind(LoopKind): pass  # hypothesis → measure → keep/revert
class ConsensusKind(LoopKind):          pass  # agents deliberate until agreement
class TaskExecutionKind(LoopKind):      pass  # tasks executed until plan verified
class InformationSeekingKind(LoopKind): pass  # search until gaps close
class ClarificationKind(LoopKind):
    HUMAN_GATED: ClassVar[bool] = True        # ONLY human complete() ends this
class SelectionKind(LoopKind):          pass  # spawn N candidates, keep top-k, repeat
```

Plus structural (non-loop) kinds: `BatchKind` (fan-out/synthesize), `OnceKind` (single execution).

---

## OMH Skill → Loop Kind Mapping

| OMH Skill | Saturate LoopKind | Notes |
|-----------|-------------------|-------|
| `omh-ralplan` | `ConsensusKind` | Planner/Architect/Critic until AllApprove |
| `omh-ralph` | `TaskExecutionKind` | Tasks executed until plan verified complete |
| `omh-autopilot` | `TaskExecutionKind` | Multi-phase pipeline |
| `omh-deep-research` | `InformationSeekingKind` | Search until gaps close |
| `omh-deep-interview` | `ClarificationKind` (HUMAN_GATED) | NO queue backend |
| `omh-triage` | `BatchKind` | Fan-out, no loop state |
| `omh-autoresearch` (Arc 2) | `MetricOptimizationKind` | Future |
| Future evolutionary | `SelectionKind` | Future |

---

## ClarificationKind.HUMAN_GATED is structural

The scheduler NEVER marks a `ClarificationKind` task terminal. There is no
`should_terminate` overload for it. Only an explicit human `complete()` call
ends it. This is a type property, not configuration.

`omh-deep-interview` does NOT post to the work queue. It manages state via
plain file I/O to `.omh/state/interview--{id}.json`. The sentinel
(`.omh/specs/*-spec.md` with `status: confirmed`) is the output.

---

## Per-Kind Turn Result Algebras (key patterns)

**MetricOptimizationKind:**
```python
Accepted(hypothesis, previous_value, new_value)  # keep + advance baseline
Discarded(hypothesis, reason: Regressed|Crashed|Unchanged)  # revert
# crashed ≠ regressed — crashed does NOT update baseline stats
```

**ConsensusKind:**
```python
RoundComplete(round, verdicts: Dict[Role, Verdict])
ConsensusReached(proposal, rounds)
# Terminal: ConsensusTerminalReached | Deadlocked | Blocked | Cancelled
```

**TaskExecutionKind:**
```python
TaskPassed(task_id, learning)
TaskFailed(task_id, error_fingerprint)
AllTasksPassed(summary)
# Terminal: PlanComplete | PlanBlocked | Exhausted | Cancelled
```

**InformationSeekingKind:**
```python
FindingsAdded(new_findings, remaining_gaps)
Sufficient(findings)
# Terminal: InformationSufficient | InformationExhausted | Cancelled
```

**ClarificationKind (HUMAN_GATED):**
```python
CoverageUpdated(dimension, new_level)
HumanConfirmed(spec)  # only terminal — no automatic predicate
```

---

## The Four-Operation Queue Interface

OMH v18 plugin exposes `omh_queue` with these operations:

```
post(mode, instance_id, kind, name, ...)    → task_id
claim(mode, instance_id)                    → ClaimResult{status: claimed|not_found|running}
release(mode, instance_id)                  → None  # CRITICAL: resets RUNNING→PENDING on clean exit
write_state(mode, instance_id, state)       → None  # updates last_heartbeat
cancel(mode, instance_id)                   → None  # sets cancel_requested=1
complete(mode, instance_id, terminal_state) → None  # marks terminal
status(mode, instance_id)                   → dict|None  # read-only
```

**`release()` is critical for ralph/autopilot:** Each driver iteration exits
cleanly after `write_state()`. Without `release()`, the next `claim()` waits
300s for crash-recovery timeout. With `release()`, reclaim is immediate.

**Three backends, detected at runtime:**
1. OMH internal queue (always — zero config, embedded SQLite)
2. Kanban (if `omh_backend: "kanban"` in config)
3. Saturate (if `SATURATE_URL` set — v18.2+)

---

## When this fires

Load when:
- Working on any OMH v18+ skill and need to know which loop kind applies
- Designing a new OMH skill and need to declare its loop kind
- Working on Saturate integration and need the OMH side of the interface
- Debugging queue behavior — especially `claim()` returning `running` vs `not_found`

⚒️
