---
name: omh-ralph
description: >
  Verified execution loop: picks the next task from a plan, delegates to an executor
  subagent, verifies completion with fresh evidence, and updates state. One task per
  invocation — the caller re-invokes until all tasks pass. Enforces the Iron Law:
  every change must be verified through builds, tests, and independent review.
version: 2.0.0
tags: [execution, verification, persistence, iron-law, loop]
category: omh
metadata:
  hermes:
    requires_toolsets: [terminal, omh]
---

# OMH Ralph — Verified Execution

## When to Use

- You have a plan (from omh-ralplan or manual) and need verified execution
- The user says: "ralph", "don't stop", "until done", "must complete", "keep going"
- You need guaranteed verification — not just "looks done" but evidence-backed completion
- Multi-step implementation where each task must be independently verified

## When NOT to Use

- No plan or spec exists (use omh-deep-interview and/or omh-ralplan first)
- Trivial single-file changes (just do them directly)
- The user explicitly wants to skip verification

## Prerequisites

- The `omh` plugin must be installed (`~/.hermes/plugins/omh/`)
- A plan with tasks and acceptance criteria (from ralplan, manual, or inline)

## Architecture: One Task Per Invocation

Each ralph invocation does ONE unit of work and exits. The caller re-invokes.
This eliminates context window exhaustion — each invocation starts fresh.

```
Invocation N:    read state → pick task → execute → verify → update → EXIT
Invocation N+1:  read state → pick next → execute → verify → update → EXIT
Final:           all pass → architect review → complete → EXIT
```

## Procedure

### Step 1: Read State

```
state = omh_state(action="read", mode="ralph")
```

- **Not found** (`state.exists = false`): Fresh start → go to Step 2
- **Active** (`state.data.active = true`): Normal → go to Step 3
- **Complete** (`state.data.phase = "complete"`): Report completion, offer fresh start
- **Blocked** (`state.data.phase = "blocked"`): Report blockers, ask if resolved
- **Cancelled** (`state.data.phase = "cancelled"`): Report cancellation, offer resume

Check cancel signal:
```
cancel = omh_state(action="cancel_check", mode="ralph")
```
If `cancel.cancelled = true`: set phase="cancelled", exit.

Check staleness: if `state.stale = true`, warn the user and offer fresh start or continue.

Increment `iteration`. If over `max_iterations` (default 100): set phase="blocked", exit.

### Step 2: Planning Gate

Ralph MUST NOT execute without a plan. Check sources in order:

1. `omh_state(action="check", mode="ralph-tasks")` — already parsed? Resume at Step 3
2. `.omh/plans/ralplan-*.md` or `.omh/plans/consensus-*.md` — parse into tasks
3. `.omh/plans/ralph-plan.md` — parse into tasks
4. Nothing → refuse: "No plan found. Run `omh-ralplan` first, or provide tasks inline."

**Parse plan into tasks:** Extract numbered tasks with titles, descriptions, acceptance criteria. Reject generic criteria. Enforce atomicity. Extract dependencies.

Write tasks:
```
omh_state(action="write", mode="ralph-tasks", data={"source_plan": "...", "tasks": [...]})
```

Create ralph state:
```
omh_state(action="write", mode="ralph", data={
    "active": true, "phase": "execute", "iteration": 0,
    "max_iterations": 100, "task_prompt": "...",
    "completed_task_learnings": [], "error_history": []
})
```

### Step 3: Pick Next Task

```
tasks = omh_state(action="read", mode="ralph-tasks")
```

1. If ALL tasks have `passes: true` → Step 7 (Final Review)
2. Find eligible: `passes=false` AND dependencies met
3. No eligible but incomplete remain → deadlock, set phase="blocked", exit
4. Pick by priority. If 2-3 independent tasks eligible → batch via `delegate_task(tasks=[...])` (max 3 concurrent)

### Step 4: Execute

Load role prompt from `omh-ralplan/references/role-executor.md`. Pass the FULL text in delegate_task context — subagents can't load skill files.

```
delegate_task(
    goal="Implement: {task.title}\n{task.description}\n\nAcceptance Criteria:\n{task.acceptance_criteria}",
    context="{executor role prompt}\n\n---\nProject Context: {tech stack}\n
    Previous Feedback: {verifier rejection if retry}\n
    Learnings: {state.data.completed_task_learnings}"
)
```

Parse response: COMPLETE → Step 5, PARTIAL → Step 5, BLOCKED → record and skip.

### Step 5: Verify

**Part A — Gather evidence:**
```
evidence = omh_gather_evidence(commands=["npm run build", "npm test", "npm run lint"])
```
Adjust commands to match the project's toolchain.

**Part B — Delegate to verifier:**

Load role prompt from `omh-ralplan/references/role-verifier.md`.

```
delegate_task(
    goal="Verify acceptance criteria:\n{task.title}\n{task.acceptance_criteria}\n\nExecutor Report:\n{executor_report}",
    context="{verifier role prompt}\n\n---\nFresh Evidence:\n{evidence.results}\n\nFiles Modified: {changed files}"
)
```

Parse response:
- **APPROVE**: mark task passed, record learnings:
  ```
  state.data.completed_task_learnings.append({
      "task_id": "T-001", "summary": "...", "files_changed": [...], "gotchas": "..."
  })
  ```
- **FAIL/REQUEST_CHANGES**: record verdict, construct error fingerprint, check 3-strike (Step 6)

### Step 6: Error Handling

**3-Strike:** After failure, construct fingerprint: `{task_id, category, error_key}`. Error key = extracted error code (e.g., `TS2345`) or first 200 chars normalized. If 3 matching fingerprints on same task → mark task blocked, continue to next.

If ALL remaining tasks blocked → set active=false, phase="blocked", report.

**Cancel:** If user says "stop"/"cancel"/"abort":
```
omh_state(action="cancel", mode="ralph", reason="user request")
```
Set phase="cancelled", exit.

### Step 7: Final Review

When all tasks pass, gather evidence and delegate to architect:

```
evidence = omh_gather_evidence(commands=["npm run build", "npm test"])
```

Load `omh-ralplan/references/role-architect.md`. Architect is READ-ONLY.

```
delegate_task(
    goal="Review complete implementation:\n{plan summary}\n{all tasks + learnings}",
    context="{architect role prompt}\n\n---\nFresh Evidence:\n{evidence.results}\nAll Files Changed: {aggregate list}"
)
```

- **APPROVE**: cleanup and complete:
  ```
  omh_state(action="clear", mode="ralph")
  omh_state(action="clear", mode="ralph-tasks")
  ```
  Keep `.omh/logs/ralph-progress.md`. Report completion.
- **REQUEST_CHANGES**: add discovered tasks, set phase="execute", exit for next invocation.

### Step 8: Update State and Exit

After every step, save state:
```
omh_state(action="write", mode="ralph", data={...updated state...})
```
The `omh_state` tool handles atomic writes automatically. Exit cleanly.

## State Management

All state operations use `omh_state` tool — atomic writes, meta envelope, and staleness detection are handled automatically. See `references/state-schema.md` for field definitions.

## Sentinel Convention

Other skills detect ralph status via:
```
omh_state(action="check", mode="ralph")
→ {exists, active, phase, stale, age_seconds}
```

## Pitfalls

- **Never skip the planning gate.** No plan = no execution.
- **Never trust executor claims without verifier evidence.** Use `omh_gather_evidence` to get fresh output before the verifier delegation.
- **Don't run commands inside verifier delegation.** Verifier is READ-ONLY. Gather evidence first with `omh_gather_evidence`.
- **Don't conflate verifier and architect.** Verifier = per-task evidence check. Architect = holistic design review. Different roles, different phases.
- **Respect the 3-strike rule.** Same error 3 times → task is blocked. Surface the issue.
- **Feed learnings forward.** Include `completed_task_learnings` in every executor delegation.
