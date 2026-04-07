# Oh My Hermes Agent (OMHA)

Multi-agent orchestration skills for [Hermes Agent](https://github.com/NousResearch/hermes-agent). Inspired by [oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode) (OMC) and its ecosystem of community implementations, rebuilt natively for Hermes primitives.

## What This Is

OMHA brings structured multi-agent workflows to Hermes Agent through composable skills — no code changes, no plugins, no forks. Install individual skills and use them standalone or as a pipeline.

| Skill | What It Does | Status |
|-------|-------------|--------|
| **omha-ralplan** | Consensus planning: Planner → Architect → Critic debate until agreement | Complete |
| **omha-deep-interview** | Socratic requirements interview with coverage tracking | Complete |
| **omha-ralph** | Verified execution: implement → verify → iterate until done | Consensus plan approved |
| **omha-autopilot** | Full pipeline composing all three skills end-to-end | Stub |

## Origin Story

OMC solved a real problem: Claude Code's context window degrades over long sessions, and autonomous agents declare victory prematurely. OMC's answer was lifecycle hooks, 29 specialized agents, and mechanical stop-prevention — all tightly coupled to Claude Code's infrastructure.

OMHA takes the best ideas from OMC and its community variants (Ouroboros, Huntley, Agentic Kit, and others published on the LobeHub Skills Marketplace) and rebuilds them for Hermes Agent using only three primitives:

- **`delegate_task`** — Isolated subagents with role-specific context (fresh context per agent, no history leakage)
- **File-based state** — `.omha/` directory for persistence, handoffs, and resumability
- **Skills** — Markdown instructions the agent follows, in the `agentskills.io` open standard

The key architectural insight came during the ralph consensus process: instead of fighting Hermes's lack of a stop-prevention hook, we lean into the "one-task-per-invocation" pattern — each ralph call does one unit of work, updates state, and exits. The caller re-invokes. This is actually more faithful to Geoffrey Huntley's original ralph concept (`while :; do cat PROMPT.md | claude-code; done`) than OMC's in-session loop.

## Install

```bash
# Add the tap (one-time)
hermes skills tap add witt3rd/omha

# Install individual skills
hermes skills install omha-ralplan
hermes skills install omha-deep-interview
hermes skills install omha-ralph
hermes skills install omha-autopilot
```

Or install manually by copying `skills/<name>/` to `~/.hermes/skills/omha/`.

## How They Compose

```
omha-deep-interview  →  confirmed spec (.omha/specs/)
        ↓
omha-ralplan         →  consensus plan (.omha/plans/)
        ↓
omha-autopilot       →  detects existing spec/plan, skips completed phases
        ↓ (internally uses)
omha-ralph           →  one-task-per-invocation until verified complete
```

Each skill works standalone. Autopilot composes them into a pipeline but any skill can be used independently:

- **Just need a plan?** → `omha-ralplan`
- **Vague idea?** → `omha-deep-interview` → `omha-ralplan`
- **Have a plan, need execution?** → `omha-ralph`
- **End-to-end?** → `omha-autopilot`

## Core Concepts

### Consensus Planning (Ralplan)

Three perspectives debate until they agree:

```
Planner drafts a plan
    → Architect reviews for structural soundness
    → Critic challenges assumptions adversarially
    → If not all APPROVE: Planner revises, loop back (max 3 rounds)
    → Consensus reached: plan written to .omha/plans/
```

This catches blind spots that a single agent misses. The Critic's job is to break the plan — if it survives, it's stronger for it.

### Requirements Interview (Deep Interview)

A Socratic conversation that gates on user-confirmed readiness, not automated scoring:

- Asks one targeted question per round, focused on the weakest dimension
- Tracks coverage across four dimensions: Goal, Constraints, Success Criteria, Existing Context
- Uses coarse bins (HIGH/MEDIUM/LOW/CLEAR) as heuristics, never as exit gates
- The user always decides when they're done — scoring never auto-terminates
- Outputs a confirmed spec that downstream skills consume

Design decisions made during consensus review:
- Coarse bins over float scores (LLM self-assessment lacks decimal precision)
- User-confirmed exit over threshold-gated exit (the user is the authority)
- Ask about brownfield, don't auto-detect (respects user knowledge)
- Adaptive questioning over named challenge modes (simpler, same effect)

### Verified Execution (Ralph)

One-task-per-invocation persistence:

```
Read state → Pick next task → Execute (delegate_task with executor role)
    → Verify (orchestrator runs builds/tests, then delegate_task with verifier role)
    → Update state → Exit
    → Caller re-invokes for next task
```

Key mechanisms:
- **Planning gate**: Won't execute without a spec or plan with acceptance criteria
- **Separation of concerns**: Executor writes code, verifier checks evidence (read-only), architect reviews holistically
- **3-strike circuit breaker**: Same error fingerprint 3 times → stop and surface the fundamental issue
- **Cancel signal**: `.omha/state/ralph-cancel.json` with 30-second TTL for clean abort
- **Learnings forward**: Completed task discoveries feed into subsequent executor context
- **Parallel-first**: Independent tasks batch up to 3 concurrent subagents

### Full Pipeline (Autopilot)

Composes all skills into phases, detecting existing artifacts to skip completed work:

```
Phase 0: Requirements  → deep-interview (skip if .omha/specs/ has confirmed spec)
Phase 1: Planning      → ralplan consensus (skip if .omha/plans/ has approved plan)
Phase 2: Execution     → ralph persistence loop
Phase 3: QA            → build + test cycling
Phase 4: Validation    → parallel review (architect + security + code reviewer)
Phase 5: Cleanup       → delete state files, report summary
```

## Key Adaptations from OMC

| OMC Pattern | OMHA Adaptation | Why |
|---|---|---|
| `spawn_agent` with role prompts | `delegate_task` with role text in context field | Hermes subagents receive goal + context, not separate system prompts |
| `persistent-mode.cjs` (mechanical stop prevention) | One-task-per-invocation + state files | Hermes has no stop hook; state-based resumability is more robust than prompt-based persistence |
| 6 concurrent child agents | 3 concurrent (Hermes `MAX_CONCURRENT_CHILDREN`) | Batch into groups of 3; Phase 4 validation fits exactly |
| Float ambiguity scores (0.0-1.0) with auto-exit gate | Coarse bins (HIGH/MEDIUM/LOW/CLEAR) with user-confirmed exit | LLM self-assessment lacks the precision to justify decimal thresholds |
| PRD user stories (`prd.json`) | Task items from ralplan consensus plans | Equivalent structure, different source |
| `.omc/` state directory | `.omha/` state directory | Same convention, different namespace |
| Haiku/Sonnet/Opus tier routing | Default model with per-subagent override | Hermes delegate_task supports model param but doesn't auto-route |
| Challenge modes (Contrarian/Simplifier/Ontologist) | Single adaptive instruction | Same effect, less ceremony |
| `AskUserQuestion` (clickable UI) | Conversational questions | Hermes is platform-agnostic (CLI, Telegram, etc.) |
| Deslop pass (mandatory in ralph) | Deferred to autopilot | Scope reduction for v1; documented as known gap |

## Role Prompts

Eight shared role prompts give subagents precise behavioral instructions:

| Role | Purpose | Used By |
|------|---------|---------|
| **Planner** | Task decomposition, sequencing, risk flags | ralplan |
| **Architect** | Structural review, boundary clarity, long-term maintainability | ralplan, ralph (final review) |
| **Critic** | Adversarial challenge, assumption testing, stress testing | ralplan |
| **Executor** | Code implementation, test-first, minimal changes | ralph |
| **Verifier** | Evidence-based completion checking, read-only, pass/fail | ralph |
| **Analyst** | Requirements extraction, hidden constraints, acceptance criteria | deep-interview, autopilot |
| **Security Reviewer** | Vulnerabilities, trust boundaries, injection vectors | autopilot (validation phase) |
| **Test Engineer** | Test strategy, coverage, edge cases, flaky test hardening | autopilot (QA phase) |
| **Debugger** | Root cause analysis, hypothesis testing, minimal targeted fixes | ralph (error diagnosis) |

## State Convention

All state lives in `.omha/` within the project directory:

```
.omha/
├── state/                              # Active mode state (JSON)
│   ├── interview-{id}.json             # Active deep-interview session
│   ├── ralph-state.json                # Active ralph session
│   ├── ralph-tasks.json                # Task tracking for ralph
│   ├── ralph-cancel.json               # Cancel signal (30s TTL)
│   └── autopilot-state.json            # Active autopilot session
├── plans/                              # Consensus plans (Markdown, persisted)
│   └── ralplan-{name}-consensus.md
├── specs/                              # Interview specs (Markdown, persisted)
│   └── {project}-spec.md
├── logs/                               # Audit trail
│   ├── interview-{id}.log
│   └── ralph-{id}.log
└── progress/                           # Append-only execution logs
    └── ralph-progress.md
```

State files are deleted on successful completion. Specs and plans persist as artifacts.

## Methodology: Self-Bootstrapping

OMHA was built using its own tools. The first skill implemented was `omha-ralplan` (consensus planning), which was then used to design the remaining skills through multi-agent debate:

1. **omha-deep-interview** — Designed via ralplan consensus (2 rounds: Planner drafted, Critic challenged scoring-as-exit-gate and undefined spec contract, Planner revised, both approved)
2. **omha-ralph** — Designed via ralplan consensus with OMC source + LobeHub references fed to all subagents (2 rounds: both reviewers demanded cancel mechanism, context strategy, and verifier separation; Critic proposed one-task-per-invocation architecture; Planner adopted it; both approved)

Each consensus process produced a plan that was then reviewed against the actual OMC source code and LobeHub marketplace implementations, ensuring OMHA preserves the patterns that matter while adapting to Hermes's architecture.

## Reference Material

The `docs/` directory contains analysis of the source implementations:

| Document | Contents |
|----------|----------|
| `docs/architecture.md` | OMHA composition model, primitives, constraints |
| `docs/omc-ralph-reference.md` | Extracted from actual OMC source: ralph, ultrawork, autopilot, persistent-mode.cjs, agent prompts, 12 design patterns |
| `docs/lobehub-skills-reference.md` | 3 ralph variants, 2 deep-interview implementations, 2 autopilot implementations from the LobeHub marketplace |

## Requirements

- Hermes Agent v0.7.0+
- No additional dependencies, plugins, or code changes

## Hermes Constraints

| Constraint | Impact | How OMHA Handles It |
|---|---|---|
| 3 concurrent subagents | Can't fire 6 parallel agents like OMC | Batch into groups of 3; validation phase fits exactly |
| No recursive delegation | Subagents can't spawn subagents | All orchestration at top level; subagents are leaf workers |
| No stop-prevention hook | Can't mechanically force continuation | One-task-per-invocation + state files for ralph; prompt-based for ralplan |
| Subagents lack `execute_code` | Children reason step-by-step | Orchestrator handles batch operations; subagents use tools directly |
| Subagents lack `memory` | Children can't write to shared memory | State passed via files and delegate_task context |

## Distribution

OMHA is distributed as a GitHub tap for the Hermes Skills Hub:

```
Phase 1 (current): GitHub tap — witt3rd/omha
Phase 2 (planned): PR to NousResearch/hermes-agent optional-skills/
Phase 3 (if needed): pip plugin for mechanical persistence hooks
```

## License

MIT
