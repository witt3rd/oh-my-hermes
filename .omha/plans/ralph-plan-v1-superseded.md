# OMHA Ralph — Implementation Plan

**Date:** 2026-04-07
**Status:** Draft — Pending consensus review

---

## Summary

OMHA Ralph is a persistence loop skill for Hermes Agent that executes tasks
from a plan and verifies completion through an independent reviewer. It
translates OMC's ralph pattern (persistent-mode.cjs stop hook + prd.json story
tracking + ultrawork parallel execution + architect verification) into
Hermes-native primitives: strong prompt instructions for persistence,
.omha/state/ files for resumability, delegate_task for parallel execution
(max 3 concurrent), and role-based verification separation.

The skill sits in the OMHA pipeline between ralplan (planning) and autopilot
(full lifecycle): it receives a plan with numbered tasks and acceptance
criteria, executes them one at a time through an executor subagent, verifies
each through an independent architect subagent, and loops until all tasks
pass or a circuit breaker triggers. Unlike OMC ralph which relies on a
Node.js stop hook to mechanically prevent session exit, OMHA ralph uses
skill instructions and state files — the agent is instructed to never
consider itself done until all tasks are verified, and state files allow
resumption if the session does end.

The implementation is 7 tasks: state schema, planning gate, core loop
skeleton, executor delegation, architect verification, 3-strike circuit
breaker, and resumability. A final integration task wires it into the
omha-autopilot pipeline.

---

## Tasks

### Task 1: Define State Schema and File Layout
**Complexity:** Small
**Dependencies:** None
**Description:**
Define the ralph-state.json schema and task-tracking schema. OMC uses two
separate files: ralph-state.json (loop metadata) and prd.json (story
tracking). OMHA should use:

- `.omha/state/ralph-state.json` — loop state (iteration, phase, errors)
- `.omha/state/ralph-tasks.json` — task list with acceptance criteria and
  pass/fail status (equivalent of prd.json but sourced from ralplan output)
- `.omha/logs/ralph-progress.md` — append-only log (equivalent of progress.txt)

Schema for ralph-state.json (adapted from OMC reference lines 606-618):
```json
{
  "active": true,
  "iteration": 1,
  "max_iterations": 20,
  "phase": "execute|verify|review|complete",
  "task_prompt": "original task text",
  "current_task_id": "T-001",
  "started_at": "ISO-8601",
  "last_updated_at": "ISO-8601",
  "files_modified": [],
  "error_history": []
}
```

Schema for ralph-tasks.json (adapted from OMC prd.json, lines 666-681):
```json
{
  "source_plan": ".omha/plans/ralplan-consensus-*.md",
  "tasks": [
    {
      "id": "T-001",
      "title": "Task title",
      "description": "What to implement",
      "acceptance_criteria": ["Specific testable criterion"],
      "passes": false,
      "priority": 1,
      "executor_report": null,
      "architect_verdict": null,
      "error_count": 0
    }
  ]
}
```

**Acceptance Criteria:**
- [ ] State schema documented in SKILL.md references/state-schema.md
- [ ] Both JSON schemas have every field documented with type and purpose
- [ ] Error history schema supports 3-strike detection (error message + task ID + iteration)
- [ ] Schema supports resumability: any field needed to resume is present

---

### Task 2: Implement Planning Gate
**Complexity:** Small
**Dependencies:** Task 1
**Description:**
OMC ralph Step 1 (lines 79-96) requires a PRD before any code runs. OMHA
ralph must enforce the same gate: refuse to execute without a plan containing
tasks and acceptance criteria.

The planning gate checks for:
1. A ralplan consensus plan at `.omha/plans/ralplan-*.md` or
   `.omha/plans/consensus-*.md`
2. OR a manually provided plan at `.omha/plans/ralph-plan.md`
3. OR task items already parsed into `.omha/state/ralph-tasks.json`

If no plan exists, ralph MUST NOT proceed. It should:
- Tell the user to run omha-ralplan first
- OR offer to parse an inline task list into ralph-tasks.json (simple mode)

If a plan exists but ralph-tasks.json doesn't, ralph parses the plan's
numbered tasks into the task JSON schema. Each task must have at least one
specific acceptance criterion (OMC pattern: reject generic criteria like
"implementation is complete" per lines 85-86).

**Acceptance Criteria:**
- [ ] Ralph refuses to start without a plan or task list
- [ ] Error message tells user exactly what to do (run ralplan or provide tasks)
- [ ] Plan parsing extracts task titles, descriptions, and acceptance criteria
- [ ] Generic/vague acceptance criteria are flagged with a warning
- [ ] Simple mode: user can provide inline tasks as a fallback

---

### Task 3: Core Loop Skeleton
**Complexity:** Medium
**Dependencies:** Task 1, Task 2
**Description:**
Implement the main ralph loop as skill instructions. This is the heart of
the skill — the prompt text that keeps the agent iterating.

The loop follows OMC ralph Steps 2-6 (lines 91-115) adapted for Hermes:

```
LOOP START:
  1. Read ralph-state.json and ralph-tasks.json
  2. Pick next task: highest priority with passes=false (Step 2)
  3. Set phase="execute", update current_task_id
  4. Delegate to executor subagent (Step 3) → Task 4
  5. Set phase="verify"
  6. Run build + test commands directly (Step 4)
  7. Delegate to architect subagent for review (Step 4) → Task 5
  8. If architect approves AND builds/tests pass:
     - Set task.passes=true
     - Append to ralph-progress.md
     - Set phase="execute" for next task
  9. If architect rejects OR builds/tests fail:
     - Increment task.error_count
     - Record error in error_history
     - Check 3-strike rule → Task 6
     - If not struck out: loop back to step 3 with feedback
 10. If all tasks pass: set phase="review" for final verification
 11. Final architect review of all changes (Step 7)
 12. If approved: set active=false, delete state files, DONE
 13. If rejected: loop back with rejection feedback
LOOP END
```

Key persistence instruction (replacing OMC's persistent-mode.cjs):
The skill prompt must include strong language like:
"You are in ralph persistence mode. You MUST NOT consider your work done
until ALL tasks in ralph-tasks.json have passes=true AND the final architect
review has approved. After each task completion, immediately proceed to the
next. Do not ask for permission between tasks. Do not summarize and stop.
If you feel the urge to stop, read ralph-tasks.json — if any task has
passes=false, you are not done."

This replaces OMC's mechanical stop hook (lines 364-370) with instructional
persistence. The trade-off is acknowledged: prompt-based persistence is
weaker than mechanical enforcement. State files provide the safety net.

**Acceptance Criteria:**
- [ ] Loop picks tasks in priority order
- [ ] Loop transitions through phases: execute → verify → (next task or review)
- [ ] State file updated at every phase transition
- [ ] Progress log appended after each completed task
- [ ] Persistence instructions are clear and emphatic
- [ ] Loop terminates cleanly when all tasks pass + final review approves

---

### Task 4: Executor Delegation
**Complexity:** Medium
**Dependencies:** Task 1, Task 3
**Description:**
Implement the executor subagent delegation. Each task is sent to an executor
via delegate_task with the role-executor.md prompt as context.

The delegation must include:
1. The executor role prompt (from omha-ralplan/references/role-executor.md)
2. The specific task description and acceptance criteria
3. Project context (tech stack, conventions, relevant file paths)
4. Previous iteration feedback (if this is a retry after architect rejection)

OMC uses tiered routing (Haiku/Sonnet/Opus per lines 96-98). OMHA simplifies:
all executor work uses the default model. The orchestrator (ralph itself)
handles complex reasoning; executors just implement.

For tasks that can be parallelized (independent tasks with no shared files):
batch up to 3 concurrent delegate_task calls (Hermes limit). This maps to
OMC's ultrawork pattern (lines 180-206) but capped at 3 instead of 6.

Parallel execution rules:
- Only tasks with no file-level dependency can run in parallel
- If unsure about independence, run sequentially (safe default)
- Each parallel executor gets its own task from ralph-tasks.json

Executor output format (per role-executor.md lines 22-28):
- Status: COMPLETE, BLOCKED, or PARTIAL
- Changes: files created/modified
- Tests: what was tested, results
- Issues: problems encountered
- Notes: for reviewer attention

**Acceptance Criteria:**
- [ ] Executor receives role prompt + task spec + project context
- [ ] Retry includes previous architect feedback in context
- [ ] Parallel execution batches up to 3 independent tasks
- [ ] Sequential fallback when independence is uncertain
- [ ] Executor output parsed and stored in task.executor_report

---

### Task 5: Architect Verification
**Complexity:** Medium
**Dependencies:** Task 1, Task 3
**Description:**
Implement the independent architect verification. After executor completes,
an architect subagent reviews the changes. This maps to OMC ralph Step 4
(lines 101-105) and the architect agent (lines 515-542).

Critical: the architect is READ-ONLY. In OMC, Write/Edit tools are
disallowed (line 521). In Hermes delegate_task, the subagent context should
explicitly state: "You are reviewing code. You MUST NOT modify any files.
Your job is to read, analyze, and produce a verdict."

The architect delegation includes:
1. The architect role prompt (from omha-ralplan/references/role-architect.md)
2. The task's acceptance criteria
3. The executor's completion report
4. The list of files modified
5. Build/test output (fresh — run before delegating)

Architect output format (per role-architect.md lines 20-27):
- Verdict: APPROVE, REQUEST_CHANGES, or REJECT
- Strengths: what's correct
- Concerns: specific issues with suggested fixes
- Missing: gaps not addressed

On APPROVE: task.passes = true, task.architect_verdict = "APPROVE"
On REQUEST_CHANGES: task.architect_verdict includes concerns, loop back
On REJECT: task.architect_verdict includes rejection reason, loop back

Verification must include fresh evidence (OMC verifier pattern, lines 556-558):
- Run tests and capture output BEFORE sending to architect
- Architect sees real test results, not claims
- Build output included verbatim

**Acceptance Criteria:**
- [ ] Architect receives read-only instructions (cannot modify files)
- [ ] Architect receives fresh build/test output as evidence
- [ ] Architect reviews against specific acceptance criteria (not vague)
- [ ] Verdict parsed and stored in task.architect_verdict
- [ ] APPROVE/REQUEST_CHANGES/REJECT flow correctly controls loop

---

### Task 6: 3-Strike Circuit Breaker
**Complexity:** Small
**Dependencies:** Task 1, Task 3
**Description:**
Implement the 3-strike rule from OMC (lines 149-153, 298-299). If the same
error recurs 3 times on the same task, ralph STOPS and surfaces it to the
user as a fundamental problem.

Error matching logic:
- Normalize error messages (strip timestamps, line numbers, paths)
- Compare normalized errors across iterations for the same task
- "Same error" = similar root cause, not exact string match
  (use first 100 chars of normalized error as fingerprint)

When 3-strike triggers:
1. Set ralph-state.json active=false
2. Set phase="blocked"
3. Write clear message: "RALPH STOPPED: Task [id] has failed 3 times with
   the same error. This appears to be a fundamental issue requiring human
   intervention. Error: [description]. Attempts: [list of what was tried]."
4. Do NOT delete state files (allow resume after user fixes the blocker)

Additional circuit breakers (from OMC Pattern 4, lines 709-717):
- Max iterations: default 20 (OMC uses 100 but extends; we cap firmly)
- Staleness: if ralph-state.json last_updated_at > 2 hours ago, treat as
  stale on resume (offer fresh start)

**Acceptance Criteria:**
- [ ] Same error on same task 3 times → ralph stops
- [ ] Error matching uses normalized fingerprints, not exact strings
- [ ] Stop message includes error description and attempt history
- [ ] State preserved for resumability (not deleted)
- [ ] Max iteration cap enforced (default 20)
- [ ] Stale state detected on resume (>2h)

---

### Task 7: Resumability
**Complexity:** Medium
**Dependencies:** Tasks 1-6
**Description:**
Implement resume-from-checkpoint. When ralph is invoked and finds existing
state files, it offers to resume rather than start over. This maps to OMC's
session state recovery (lines 580-596) and the architecture doc's state
convention (lines 54-55).

Resume logic:
1. On invocation, check for `.omha/state/ralph-state.json`
2. If exists and active=true:
   a. Check staleness (>2h → warn, offer fresh start)
   b. If not stale: "Found ralph state at iteration N, task [id],
      phase [phase]. Resuming..."
   c. Read ralph-tasks.json to find current position
   d. Continue from last recorded phase
3. If exists and active=false, phase="blocked":
   a. "Ralph was blocked on task [id]. Has the issue been resolved?"
   b. If yes: reset error_count for that task, set active=true, resume
   c. If no: stay stopped
4. If exists and active=false, phase="complete":
   a. "Ralph completed previously. Start fresh? [y/n]"

State cleanup on successful completion (OMC Pattern 12, lines 757-760):
- Delete ralph-state.json
- Delete ralph-tasks.json
- Keep ralph-progress.md (it's the audit trail)

**Acceptance Criteria:**
- [ ] Existing active state triggers resume flow
- [ ] Stale state (>2h) gets warning
- [ ] Blocked state allows retry after user confirms fix
- [ ] Completed state offers fresh start
- [ ] State files deleted on success, progress log preserved
- [ ] Resume picks up at correct task and phase

---

### Task 8: Write the SKILL.md
**Complexity:** Large
**Dependencies:** Tasks 1-7 (all design decisions must be final)
**Description:**
Write the complete SKILL.md file that replaces the current stub. This is the
actual deliverable — the skill instructions that Hermes loads and follows.

The SKILL.md must include:
1. Frontmatter (name, description, version, tags, metadata)
2. When to Use section (trigger conditions)
3. Prerequisites section (planning gate)
4. Core Loop section (the full ralph protocol as numbered steps)
5. Executor Delegation section (what to include, parallel rules)
6. Architect Verification section (read-only, evidence-based)
7. 3-Strike Rule section
8. Resumability section
9. Iron Law checklist (adapted from OMC's 12-item checklist, lines 156-169)
10. Persistence Instructions section (the strong prompt language)
11. State Schema reference (inline or linked)

The skill should also include reference files:
- references/state-schema.md — JSON schemas
- references/iron-law-checklist.md — verification checklist
- templates/ralph-tasks-example.json — example task file

Key tone: the SKILL.md must be authoritative and action-oriented. It's not
documentation — it's instructions the agent follows. Every sentence should
either be a rule ("you MUST"), a condition ("IF x THEN y"), or a reference
("read file X for schema").

**Acceptance Criteria:**
- [ ] SKILL.md replaces the stub completely
- [ ] All 7 previous tasks' designs are reflected in the instructions
- [ ] Persistence language is strong and unambiguous
- [ ] Iron Law checklist adapted for Hermes (no OMC-specific items)
- [ ] Reference files created alongside SKILL.md
- [ ] Skill loads correctly (frontmatter valid YAML)
- [ ] A developer reading only SKILL.md understands the full ralph protocol

---

## Risks

### R1: Prompt-Based Persistence is Fundamentally Weaker Than Mechanical Hooks
**Severity:** High
**Mitigation:** Accept this limitation. OMC's persistent-mode.cjs mechanically
blocks stop attempts (lines 364-370). Hermes has no equivalent. We rely on:
(a) strong instructions, (b) state files for resume, (c) user awareness that
ralph may need re-invocation. The state-based resumability in Task 7 is the
real safety net — if ralph stops, it can pick up where it left off.

### R2: delegate_task Subagents Can't Run Terminal Commands
**Severity:** Medium
**Mitigation:** The orchestrator (ralph itself) runs builds and tests
directly. Subagents (executor, architect) only reason about code and produce
reports. The executor's role prompt says to write code and report changes;
ralph then runs the verification commands. This differs from OMC where
executor agents have full tool access.
**Update after reading architecture.md:** Line 64 says "Subagents lack
execute_code — children reason step-by-step, can't batch." This confirms
the approach: orchestrator runs commands, subagents reason.

### R3: 3-Agent Concurrency Limit Constrains Parallel Execution
**Severity:** Low
**Mitigation:** Most ralph iterations are sequential anyway (implement → verify
→ next). Parallelism only applies when multiple independent tasks exist.
3 concurrent is sufficient for the common case. OMC's 6-agent ultrawork
is rarely fully utilized in practice.

### R4: Error Fingerprinting for 3-Strike May Be Too Loose or Too Strict
**Severity:** Medium
**Mitigation:** Start with simple prefix matching (first 100 chars normalized).
If too many false positives, increase to 200 chars. If too many false
negatives, add semantic similarity. Ship simple, iterate based on usage.

### R5: Plan Parsing May Fail on Non-Standard Plan Formats
**Severity:** Low
**Mitigation:** Define a clear expected format (numbered tasks with acceptance
criteria). If parsing fails, ralph asks the user to provide tasks in the
expected format or manually create ralph-tasks.json.

---

## Open Questions

### Q1: Should ralph support running WITHOUT ralplan (ad-hoc mode)?
OMC ralph supports --no-prd for legacy mode (line 66). Should omha-ralph
allow a user to just say "ralph: implement X" without a formal plan?
**Recommendation:** Yes, with a simple mode where the user provides an inline
task list. The planning gate should be "tasks must exist" not "ralplan must
have run." This makes ralph usable standalone while still encouraging the
full pipeline.

### Q2: Should the executor subagent write code directly or return instructions?
If subagents can't run terminal commands (Risk R2), can they still write files?
delegate_task subagents in Hermes have access to tools (read_file, write_file,
patch, etc.) but not terminal. The executor should write code directly using
these tools, and ralph runs the build/test commands.
**Recommendation:** Executor writes code via tools. Ralph runs verification.

### Q3: How does ralph handle tasks that require user interaction mid-loop?
OMC stops on "fundamental blockers requiring user input" (line 149). Should
ralph pause and wait, or mark the task blocked and skip to the next?
**Recommendation:** Mark blocked, skip to next independent task. When all
remaining tasks are blocked, stop and surface all blockers at once.

### Q4: Should ralph commit to git after each task?
OMC's Huntley variant commits after each story (lobehub ref line 170). This
provides rollback points. But it clutters git history.
**Recommendation:** Optional. Default to no auto-commit. If the user's plan
says to commit, ralph honors it. Ralph's progress log provides the audit
trail instead.

### Q5: Deslop pass — include or defer?
OMC has a mandatory deslop pass (lines 131-139) that cleans AI-generated
slop from code. The task brief says "optional, not built-in."
**Recommendation:** Defer to omha-autopilot. Ralph's scope is
execute+verify. Code quality passes belong in the full pipeline.

### Q6: What model should the architect verification use?
OMC uses Opus for architect (line 518). Hermes delegate_task doesn't specify
model — it uses whatever the parent session's model is.
**Recommendation:** Document that ralph works best with a strong model but
don't hard-code model selection. Let the user control this via their Hermes
config.

---

## Dependency Graph

```
Task 1 (State Schema)
  ├──→ Task 2 (Planning Gate)
  ├──→ Task 3 (Core Loop) ──→ Task 4 (Executor)
  │                        ──→ Task 5 (Architect)
  │                        ──→ Task 6 (3-Strike)
  └──→ Task 7 (Resumability) ← depends on Tasks 1-6
       └──→ Task 8 (SKILL.md) ← depends on all
```

Tasks 4, 5, 6 can be built in parallel once Task 3 is complete.
Task 8 must be last (it documents the final design).

---

## Estimated Total Effort

| Task | Complexity | Estimated Work |
|------|-----------|---------------|
| 1. State Schema | Small | Define schemas, write reference doc |
| 2. Planning Gate | Small | Parsing logic + error messages |
| 3. Core Loop | Medium | Main skill instructions, phase transitions |
| 4. Executor Delegation | Medium | delegate_task integration, parallel rules |
| 5. Architect Verification | Medium | Read-only review delegation, evidence gathering |
| 6. 3-Strike | Small | Error tracking + matching logic |
| 7. Resumability | Medium | State recovery + stale detection |
| 8. SKILL.md | Large | Complete skill file + references |

All tasks are "skill file writing" — no code to compile or deploy. The
deliverable is SKILL.md + reference files that Hermes loads as instructions.
