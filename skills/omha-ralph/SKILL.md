---
name: omha-ralph
description: >
  Verified execution loop: picks the next task from a plan, delegates to an executor
  subagent, verifies completion with fresh evidence, and updates state. One task per
  invocation — the caller re-invokes until all tasks pass. Enforces the Iron Law:
  every change must be verified through builds, tests, and independent review.
version: 1.0.0
tags: [execution, verification, persistence, iron-law, loop]
category: omha
metadata:
  hermes:
    requires_toolsets: [terminal]
---

# OMHA Ralph — Verified Execution

## When to Use

- You have a plan (from omha-ralplan or manual) and need verified execution
- The user says: "ralph", "don't stop", "until done", "must complete", "keep going"
- You need guaranteed verification — not just "looks done" but evidence-backed completion
- Multi-step implementation where each task must be independently verified

## When NOT to Use

- No plan or spec exists (use omha-deep-interview and/or omha-ralplan first)
- Trivial single-file changes (just do them directly)
- The user explicitly wants to skip verification

## Prerequisites

- A plan with tasks and acceptance criteria. Sources (checked in order):
  1. `.omha/state/ralph-tasks.json` (already parsed — resume)
  2. `.omha/plans/ralplan-*.md` or `.omha/plans/consensus-*.md` (ralplan output)
  3. `.omha/plans/ralph-plan.md` (manually provided)
- If no plan exists: refuse to start, tell the user to run omha-ralplan first
  - **Simple mode fallback**: if the user provides inline tasks, parse them into ralph-tasks.json

## Architecture: One Task Per Invocation

Each ralph invocation does ONE unit of work and exits. The caller (autopilot, the user,
or a cron job) re-invokes for the next task. This eliminates context window exhaustion
and makes every invocation a clean checkpoint.

```
Invocation N:  read state → pick task → execute → verify → update state → EXIT
Invocation N+1: read state → pick next task → execute → verify → update state → EXIT
...
Final invocation: all tasks pass → architect review → mark complete → EXIT
```

## Procedure

### Step 1: Read State

1. Check for `.omha/state/ralph-state.json`
   - **Not found**: This is a fresh start. Go to Step 2 (Planning Gate).
   - **Found, `active=true`**: Normal operation. Go to Step 3.
   - **Found, `active=false`, `phase="complete"`**: Report completion. Ask if user wants a fresh start.
   - **Found, `active=false`, `phase="blocked"`**: Report what's blocked and why. Ask if issues are resolved.
   - **Found, `active=false`, `phase="cancelled"`**: Report cancellation. Check if `.omha/state/ralph-cancel.json` still exists — if removed, offer to resume.

2. Check for cancel signal: `.omha/state/ralph-cancel.json`
   - If present and within 30-second TTL: set `phase="cancelled"`, preserve state, exit.
   - If present but stale (>30s): delete it, continue.

3. Check staleness: if `last_updated_at` is more than 2 hours ago, warn the user:
   "Ralph state is {N} hours old. The project may have changed. Continue from checkpoint or fresh start?"

4. Increment `iteration`. If `iteration > max_iterations` (default 100): set `phase="blocked"`, report "Max iterations reached", exit.

### Step 2: Planning Gate

Ralph MUST NOT execute without a plan. Check sources in order:

1. `.omha/state/ralph-tasks.json` — already parsed, skip to Step 3
2. `.omha/plans/ralplan-*.md` — parse into ralph-tasks.json
3. `.omha/plans/ralph-plan.md` — parse into ralph-tasks.json
4. Nothing found → tell user: "No plan found. Run `omha-ralplan` first, or provide tasks inline."

**Plan parsing rules:**
- Extract numbered tasks with titles, descriptions, and acceptance criteria
- **Reject** generic criteria like "implementation is complete" — criteria must be testable
- **Enforce atomicity**: split multi-part tasks into separate entries
- Extract dependencies from explicit task references
- Assign priorities based on dependency ordering (no-dependency tasks first)
- Set all tasks to `passes: false`, `discovered: false`

Create `ralph-state.json` with a fresh `session_id` (UUID) and `iteration: 0`.

### Step 3: Pick Next Task

Read `.omha/state/ralph-tasks.json`.

1. If ALL tasks have `passes: true` → go to Step 7 (Final Review)
2. Find eligible tasks: `passes=false` AND all dependencies met (dependent tasks have `passes=true`)
3. If no task is eligible but incomplete tasks remain → report dependency deadlock, set `phase="blocked"`, exit
4. Among eligible tasks, pick by priority (lowest number first)

**Parallel execution** (if multiple independent tasks are eligible):
- Two tasks are independent if: neither depends on the other AND their file footprints don't overlap
- If 2-3 independent tasks are eligible: batch them into a single `delegate_task` call (up to 3 concurrent)
- If independence is uncertain: run sequentially (safe default)

### Step 4: Execute

For each selected task, delegate to an executor subagent:

```
delegate_task(
    goal="Implement this task:\n\n{task.title}\n{task.description}\n\nAcceptance Criteria:\n{task.acceptance_criteria}",
    context="{role-executor.md prompt}\n\n---\n\nProject Context:\n{tech stack, conventions, relevant paths}\n\nPrevious Feedback (if retry):\n{verifier's rejection feedback}\n\nLearnings from prior tasks:\n{completed_task_learnings from ralph-state.json}"
)
```

Load the executor role prompt from `omha-ralplan/references/role-executor.md`. Include the FULL prompt text — subagents can't load skill files.

The executor prompt instructs self-verification before reporting COMPLETE:
- Run any inline tests it can
- Check acceptance criteria from its perspective
- Report COMPLETE only if self-check passes, PARTIAL if some criteria unverified, BLOCKED if stuck

Parse the executor's response:
- **COMPLETE**: proceed to Step 5 (Verify)
- **PARTIAL**: proceed to Step 5 anyway (verifier will catch gaps)
- **BLOCKED**: record the blocker. If the executor says a prerequisite task is needed, add it as a discovered task to ralph-tasks.json with `discovered: true`. Skip to state update.

Record `executor_report` on the task.

### Step 5: Verify

Verification has two parts: fresh evidence gathering (you do this) and verifier delegation.

**Part A: Gather fresh evidence (orchestrator responsibility)**

Before delegating to the verifier, YOU (the orchestrator) must gather evidence:
1. Run the project's build command (if applicable)
2. Run the project's test suite (if applicable)
3. Run any linting/type-checking (if applicable)
4. Capture all output

This is critical: the verifier is READ-ONLY. It cannot run commands. You provide the evidence.

**Part B: Delegate to verifier subagent**

```
delegate_task(
    goal="Verify whether this task's acceptance criteria are met:\n\n{task.title}\n{task.acceptance_criteria}\n\nExecutor Report:\n{task.executor_report}",
    context="{role-verifier.md prompt}\n\n---\n\nFresh Build/Test Output:\n{build output}\n{test output}\n{lint output}\n\nFiles Modified:\n{list of changed files}"
)
```

Load the verifier role prompt from `omha-ralplan/references/role-verifier.md`.

Parse the verifier's response:
- **APPROVE / PASS**: Set `task.passes = true`. Record learnings in `completed_task_learnings`:
  ```json
  {"task_id": "T-001", "summary": "what was done", "files_changed": [...], "gotchas": "..."}
  ```
  Append completion entry to `.omha/logs/ralph-progress.md`.
- **REQUEST_CHANGES / FAIL**: Record `verifier_verdict` on the task. Record error fingerprint. Check 3-strike rule (Step 6). The task will be retried on the next invocation with the verifier's feedback included in the executor context.

### Step 6: Error Handling

**3-Strike Circuit Breaker**

After a verification failure, construct an error fingerprint:
- `task_id`: which task failed
- `category`: build / test / lint / runtime / timeout / unknown
- `error_key`: extracted error code (e.g., `TS2345`, `ENOENT`) or first 200 chars of normalized message
- See `references/state-schema.md` for full fingerprint schema

Add to `task.error_fingerprints`. Check: does this task now have 3 fingerprints with matching `category + error_key`?

If yes (3-strike triggered):
1. Mark the task as blocked (set a `blocked: true` flag or skip it in task selection)
2. Log: "Task {id} blocked: same error ({error_key}) occurred 3 times"
3. Continue to next eligible task on next invocation
4. If ALL remaining tasks are blocked: set `active=false`, `phase="blocked"`, report full blocker summary

**Cancel Detection**

If the user says "stop", "cancel", or "abort" during this invocation:
1. Write `.omha/state/ralph-cancel.json` with `requested_by: "user"`
2. Set `phase="cancelled"` in ralph-state.json
3. Preserve all state for resume
4. Report: "Ralph cancelled at iteration {N}, task {id}. State preserved. Delete ralph-cancel.json and re-invoke to resume."

### Step 7: Final Review

When all tasks have `passes: true`, perform a holistic architectural review.

Delegate to architect subagent:

```
delegate_task(
    goal="Review the complete implementation for architectural soundness.\n\nOriginal Plan:\n{source plan text}\n\nTasks Completed:\n{summary of all tasks + learnings}",
    context="{role-architect.md prompt}\n\n---\n\nFresh Build/Test Output:\n{full build + test output}\n\nFiles Changed Across All Tasks:\n{aggregate file list}"
)
```

Load the architect role prompt from `omha-ralplan/references/role-architect.md`.

The architect is READ-ONLY — it analyzes, it doesn't fix.

Parse the architect's response:
- **APPROVE**: Set `active=false`, `phase="complete"`. Delete state files (ralph-state.json, ralph-tasks.json, ralph-cancel.json). Keep `ralph-progress.md`. Report completion summary.
- **REQUEST_CHANGES**: Create new tasks from the architect's feedback. Add to ralph-tasks.json with `discovered: true`. Set `phase="execute"`. These tasks will be picked up on the next invocation.

### Step 8: Update State and Exit

After every action (execute, verify, error, final review):
1. Update `last_updated_at` to current time
2. Write state files using atomic pattern: write to `.tmp`, then rename
3. Exit cleanly

The caller re-invokes for the next iteration.

## State Management

See `references/state-schema.md` for full schemas.

Key rules:
- **Atomic writes**: All state file writes use write-to-temp-then-rename
- **One active session**: If ralph-state.json exists with `active: true`, this is a resume
- **Session ID**: Generated on fresh start, checked on resume (warning on mismatch, not hard block)
- **Staleness**: >2 hours since last update triggers a warning on next invocation
- **Cleanup**: State files deleted on completion, progress log preserved

## Sentinel Convention

Other skills detect ralph status by checking:
- `.omha/state/ralph-state.json` exists with `active: true` → ralph is in progress
- `.omha/state/ralph-state.json` exists with `phase: "complete"` → ralph finished successfully
- `.omha/logs/ralph-progress.md` exists → ralph has run (check content for outcome)

## Pitfalls

- **Never skip the planning gate.** No plan = no execution. Even for "simple" tasks, parse them into ralph-tasks.json with acceptance criteria.
- **Never trust executor claims without verifier evidence.** The executor says "tests pass" but the verifier must see test output. Self-verification is a first pass, not the final word.
- **Don't run builds/tests inside the verifier delegation.** The verifier is READ-ONLY. The orchestrator (you) gathers evidence BEFORE delegating to the verifier.
- **Don't conflate verifier and architect.** The verifier checks per-task acceptance criteria with evidence. The architect reviews holistic design quality. Different jobs, different prompts, different phases.
- **Respect the 3-strike rule.** If the same error occurs 3 times on the same task, the task is blocked. Don't keep retrying — surface the fundamental issue.
- **Always use atomic writes for state files.** Write to `.tmp`, then rename. A crash mid-write must not corrupt state.
- **Feed learnings forward.** Each executor should know what prior tasks discovered. Include `completed_task_learnings` in every executor delegation context.
