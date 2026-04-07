# OMHA Ralph — Implementation Plan v2

**Date:** 2026-04-07
**Status:** Draft v2 — Revised per Architect + Critic consensus feedback
**Supersedes:** omha-ralph-implementation-plan.md (v1)

---

## Summary

OMHA Ralph is a persistence execution skill for Hermes Agent that executes
tasks from a plan and verifies completion through independent reviewers.

### Architectural Change from v1: One-Task-Per-Invocation

v1 proposed an in-session loop that iterates through all tasks. Both
reviewers identified context window exhaustion as the #1 unaddressed risk.
The Critic proposed an alternative: **one task per invocation**, where ralph
does a single unit of work and exits, relying on the caller (autopilot,
cron, or the user) to re-invoke.

**This plan adopts the one-task-per-invocation pattern.** Justification:

1. **Context exhaustion eliminated.** Each invocation starts fresh. No
   accumulated context from prior tasks.
2. **Faithful to OMC.** OMC ralph relies on a stop hook (persistent-mode.cjs)
   that Hermes cannot replicate. Rather than simulating it with weaker prompt
   instructions, we lean into Hermes' strength: state files + re-invocation.
   The state files carry all context between invocations.
3. **Simpler to reason about.** Each invocation is: read state → pick task →
   execute → verify → update state → done. No loop management, no phase
   tracking within a single session.
4. **Composable.** Autopilot can invoke ralph N times, or the user can run
   ralph repeatedly, or a cron job can drive it.

The execution model per invocation:

```
1. Read .omha/state/ralph-state.json and ralph-tasks.json
2. Check for cancel signal → abort if present
3. Pick next task (highest priority, passes=false)
4. Delegate to executor subagent (single task)
5. Executor self-verifies before reporting COMPLETE
6. Orchestrator runs build/tests for fresh evidence
7. Delegate to verifier subagent (evidence-based check)
8. If verifier approves → mark task passed, record learnings
9. If verifier rejects → record failure, increment error count
10. Update state files (atomic write)
11. END — caller re-invokes for next task
```

When all tasks pass, ralph performs a final architectural review on the
next invocation and marks the plan complete.

### OMC Mapping

| OMC Component | OMHA Equivalent |
|---|---|
| persistent-mode.cjs stop hook | State files + re-invocation by caller |
| prd.json story tracking | ralph-tasks.json |
| ralph-state.json | ralph-state.json (with session_id, awaiting_confirmation) |
| progress.txt | ralph-progress.md |
| Executor agent (Sonnet) | delegate_task with role-executor.md |
| Architect agent (Opus, read-only) | delegate_task with role-architect.md (analysis only) |
| Verifier agent (Sonnet) | delegate_task with role-verifier.md (evidence checking) |
| ultrawork parallel execution | Parallel delegate_task (max 3 concurrent) |
| 3-strike circuit breaker | Error fingerprinting with structured matching |
| cancel signal | .omha/state/ralph-cancel.json |
| Deslop pass | **Deferred** — see Divergence D5 |

### Explicit OMC Divergences

| ID | OMC Pattern | OMHA Choice | Justification |
|---|---|---|---|
| D1 | Stop hook mechanically prevents exit | State files + re-invocation | Hermes has no stop hook. State files are the persistence mechanism. |
| D2 | max_iterations=100, auto-extends by 10 | max_iterations=100, configurable, hard cap | OMC auto-extends because the hook can enforce it. Without a hook, a hard cap prevents runaway. |
| D3 | Tiered model routing (Haiku/Sonnet/Opus) | Single model (user's configured model) | Hermes delegate_task doesn't support model selection. Document as limitation. |
| D4 | 6 concurrent child agents | 3 concurrent subagents | Hermes constraint (architecture.md line 61). |
| D5 | Mandatory deslop pass (ai-slop-cleaner) | Deferred to omha-autopilot | Ralph's scope is execute+verify. Code quality passes belong in the full pipeline. Per task brief: "optional, not built-in." |
| D6 | Session-scoped state dirs (.omc/state/sessions/{id}/) | Flat .omha/state/ with session_id field | Hermes uses a simpler state layout. session_id in the JSON prevents cross-contamination. |

---

## Tasks

### Task 1: Define State Schema and File Layout
**Complexity:** Small
**Dependencies:** None
**Description:**
Define the ralph-state.json schema, task-tracking schema, and cancel signal.
Aligns with OMC state fields (reference lines 606-618) with all required
fields present.

File layout:
- `.omha/state/ralph-state.json` — loop state
- `.omha/state/ralph-tasks.json` — task list with acceptance criteria
- `.omha/state/ralph-cancel.json` — cancel signal (Addresses: Architect C1, Critic C4)
- `.omha/logs/ralph-progress.md` — append-only log with learnings

Schema for ralph-state.json:
```json
{
  "active": true,
  "session_id": "uuid-of-creating-session",
  "iteration": 1,
  "max_iterations": 100,
  "phase": "execute|verify|final-review|complete|blocked|cancelled",
  "task_prompt": "original task text",
  "current_task_id": "T-001",
  "started_at": "ISO-8601",
  "last_updated_at": "ISO-8601",
  "project_path": "/path/to/project",
  "awaiting_confirmation": false,
  "awaiting_confirmation_set_at": null,
  "files_modified": [],
  "error_history": [],
  "completed_task_learnings": []
}
```

**New fields vs v1 (addressing Architect C3, Critic C1):**
- `session_id` — Matches OMC pattern (reference line 613). Prevents stale
  state cross-contamination. On resume, ralph checks session_id against
  current session. Mismatched session_id triggers a staleness warning.
- `awaiting_confirmation` + `awaiting_confirmation_set_at` — Matches OMC
  pattern (reference lines 444-448). 2-minute TTL. When ralph needs user
  input, it sets this flag and exits. Re-invocation checks the flag.
- `completed_task_learnings` — Array of {task_id, summary, files_changed,
  gotchas} from completed tasks. Fed into subsequent executor contexts.
  (Addresses: Architect M6)

Schema for ralph-tasks.json:
```json
{
  "source_plan": ".omha/plans/ralplan-consensus-*.md",
  "tasks": [
    {
      "id": "T-001",
      "title": "Task title",
      "description": "What to implement — one atomic unit of work",
      "acceptance_criteria": ["Specific testable criterion"],
      "passes": false,
      "priority": 1,
      "dependencies": ["T-000"],
      "executor_report": null,
      "verifier_verdict": null,
      "error_count": 0,
      "error_fingerprints": [],
      "discovered": false
    }
  ]
}
```

**New fields vs v1:**
- `dependencies` — Enables parallel execution independence detection
  (Addresses: Critic W1)
- `error_fingerprints` — Structured error identity, not just raw messages
  (Addresses: Architect C6, Critic W2)
- `discovered` — Marks tasks added dynamically during execution
  (Addresses: Architect C5)
- `verifier_verdict` — Renamed from architect_verdict to reflect role
  separation (Addresses: Architect C4, Critic C3)

Schema for ralph-cancel.json (Addresses: Architect C1, Critic C4):
```json
{
  "requested_at": "ISO-8601",
  "requested_by": "user|circuit-breaker|context-limit",
  "reason": "User requested cancellation"
}
```
Cancel signal has a 30-second TTL (OMC pattern, reference line 361).
Ralph checks for this file at the start of each invocation.

**Task atomicity rule (Addresses: Architect M4):**
Each task in ralph-tasks.json MUST be one atomic unit of work. During plan
parsing, multi-part tasks are split. A task is atomic if: it touches a
bounded set of files, has testable acceptance criteria, and can be
independently verified.

**Acceptance Criteria:**
- [ ] State schema documented in SKILL.md references/state-schema.md
- [ ] All JSON schemas have every field documented with type and purpose
- [ ] session_id, awaiting_confirmation present and documented
- [ ] Error fingerprint schema supports structured matching (not just prefix)
- [ ] Cancel signal schema with TTL documented
- [ ] Schema supports resumability: any field needed to resume is present

---

### Task 2: Implement Planning Gate
**Complexity:** Small
**Dependencies:** Task 1
**Description:**
OMC ralph Step 1 (reference lines 79-96) requires a PRD before any code
runs. OMHA ralph must enforce the same gate.

The planning gate checks for:
1. A ralplan consensus plan at `.omha/plans/ralplan-*.md` or
   `.omha/plans/consensus-*.md`
2. OR a manually provided plan at `.omha/plans/ralph-plan.md`
3. OR task items already parsed into `.omha/state/ralph-tasks.json`

If no plan exists, ralph MUST NOT proceed. It should:
- Tell the user to run omha-ralplan first
- OR offer to parse an inline task list into ralph-tasks.json (simple mode)

Plan parsing rules:
- Extract numbered tasks with titles, descriptions, acceptance criteria
- Reject generic criteria like "implementation is complete" (OMC lines 84-86)
- **Enforce task atomicity:** split multi-part tasks into separate entries
  (Addresses: Architect M4)
- Assign dependencies based on explicit references between tasks
- Set `discovered: false` for all initial tasks

**Acceptance Criteria:**
- [ ] Ralph refuses to start without a plan or task list
- [ ] Error message tells user exactly what to do
- [ ] Plan parsing extracts tasks with acceptance criteria
- [ ] Generic/vague acceptance criteria flagged with warning
- [ ] Multi-part tasks split into atomic units
- [ ] Dependencies extracted and recorded
- [ ] Simple mode: user can provide inline tasks as fallback

---

### Task 3: One-Task-Per-Invocation Core Logic
**Complexity:** Medium
**Dependencies:** Task 1, Task 2
**Description:**
Implement the core ralph invocation logic. This replaces v1's in-session
loop with the one-task-per-invocation pattern.

Each invocation follows this sequence:

```
ON INVOCATION:
  1. Read ralph-state.json
     - If not found: run Planning Gate (Task 2), create state, proceed
     - If found and active=false, phase="complete": report completion
     - If found and active=false, phase="blocked": report blocker
     - If found and active=false, phase="cancelled": report cancellation
  2. Check cancel signal (.omha/state/ralph-cancel.json)
     - If present and within TTL: set phase="cancelled", exit
  3. Check staleness: last_updated_at > 2 hours ago
     - Warn user, offer fresh start (Addresses: Architect M3 — staleness
       is resume-time only, checked at the START of each invocation)
  4. Check session_id — if mismatch, warn about cross-session state
  5. Increment iteration, check max_iterations (default 100)
     - If exceeded: set phase="blocked", exit with message
  6. Read ralph-tasks.json
  7. If ALL tasks have passes=true: go to FINAL REVIEW
  8. Pick next task: highest priority with passes=false and dependencies met
     - If no task is eligible (all blocked by dependencies): report deadlock
  9. Set current_task_id, update state (atomic write)
 10. EXECUTE: Delegate to executor subagent → Task 4
 11. VERIFY: Run build/tests, delegate to verifier → Task 5
 12. Process result:
     - Approved: set task.passes=true, record learnings in
       completed_task_learnings, append to ralph-progress.md
     - Rejected: increment error_count, record error fingerprint,
       check 3-strike → Task 6
 13. Update state files (atomic write)
 14. EXIT — caller re-invokes for next task

FINAL REVIEW (when all tasks pass):
  1. Set phase="final-review"
  2. Delegate to architect subagent for holistic review
     (Addresses: Architect C4 — architect does analysis, not evidence checking)
  3. If approved: set active=false, phase="complete", delete state files
     (keep ralph-progress.md)
  4. If rejected: create new discovered tasks from rejection feedback
     (Addresses: Architect C5 — dynamic task discovery)
  5. EXIT
```

**State file convention (Addresses: Critic W7):**
Ralph uses files (not conversation state) because:
- Files survive session boundaries (conversation state does not)
- Files are inspectable by the user (cat ralph-state.json)
- Files enable the one-task-per-invocation pattern
- Files allow other skills (autopilot) to read ralph's progress

**Atomic file writes (Addresses: Architect M1):**
All state file writes use atomic write-to-temp-then-rename pattern
(OMC Pattern 8, reference lines 462-469):
```
write to ralph-state.json.tmp
rename ralph-state.json.tmp → ralph-state.json
```
This prevents corrupt state on crash or context-limit exit.

**Progressive urgency (Addresses: Architect M2):**
Not applicable in one-task-per-invocation — each invocation is a fresh
context, so there is no within-session urgency escalation. However, the
iteration count in ralph-progress.md serves as a signal to the user/caller
about how many invocations have been spent.

**Acceptance Criteria:**
- [ ] Single invocation does one task and exits
- [ ] State file read/write at invocation boundaries
- [ ] Cancel signal checked before any work
- [ ] Staleness check at invocation start
- [ ] Session_id validation at invocation start
- [ ] Final review triggered when all tasks pass
- [ ] Dynamic task creation from final review rejection
- [ ] Atomic file writes for all state updates
- [ ] Clean exit — no loop, no persistence instructions needed

---

### Task 4: Executor Delegation
**Complexity:** Medium
**Dependencies:** Task 1, Task 3
**Description:**
Implement the executor subagent delegation. Each task is sent to an executor
via delegate_task.

The delegation must include:
1. The executor role prompt (from omha-ralplan/references/role-executor.md)
2. The specific task description and acceptance criteria
3. Project context (tech stack, conventions, relevant file paths)
4. Previous iteration feedback (if this is a retry after verifier rejection)
5. **Learnings from completed tasks** (Addresses: Architect M6)
   — Include completed_task_learnings from ralph-state.json so the executor
   benefits from discoveries made during prior tasks

**Self-verification before reporting COMPLETE (Addresses: Architect M5):**
The executor prompt must instruct the subagent to verify its own work
before reporting COMPLETE:
- Run any inline tests it can
- Check that acceptance criteria are met from its perspective
- Report status as COMPLETE only if self-check passes
- Report PARTIAL if some criteria unverified
- Report BLOCKED if stuck

Executor output format:
- Status: COMPLETE, BLOCKED, or PARTIAL
- Changes: files created/modified
- Self-Verification: what was checked, results
- Issues: problems encountered
- Notes: for reviewer attention

**Parallel execution (Addresses: Critic W1, W4):**

OMC default is parallel-first (Pattern 11, reference line 751). OMHA
adopts parallel-first with explicit independence detection:

Independence rule: two tasks are independent if and only if:
1. Neither lists the other (or the other's outputs) in its dependencies
2. Their file footprints don't overlap (determined from task descriptions)

When multiple independent tasks are eligible:
- Batch up to 3 concurrent delegate_task calls (Hermes limit)
- Each gets its own task, own context, own learnings feed
- Collect all results before proceeding to verification
- If independence is uncertain (file footprint unclear), fall back to
  sequential (safe default)

**OMC divergence:** OMC fires up to 6 agents simultaneously (reference
line 755). Hermes caps at 3 (architecture.md line 61).

**Acceptance Criteria:**
- [ ] Executor receives role prompt + task spec + project context
- [ ] Executor receives learnings from prior completed tasks
- [ ] Retry includes previous verifier feedback in context
- [ ] Executor self-verifies before reporting COMPLETE
- [ ] Parallel execution batches up to 3 independent tasks
- [ ] Independence detection uses dependency graph + file footprint
- [ ] Sequential fallback when independence is uncertain
- [ ] Executor output parsed and stored in task.executor_report

---

### Task 5: Verification — Verifier + Architect Separation
**Complexity:** Medium
**Dependencies:** Task 1, Task 3
**Description:**
Implement verification as TWO distinct roles (Addresses: Architect C4,
Critic C3). OMC has three agents at levels 2-3: executor (writes code),
architect (analyzes/diagnoses, read-only), verifier (checks evidence).
v1 conflated architect and verifier.

**Verifier Agent (per-task verification):**
The verifier checks whether a specific task's acceptance criteria are met
with fresh evidence. Maps to OMC verifier agent (reference lines 544-574).

Verifier delegation includes:
1. role-verifier.md prompt (NEW — must be created)
2. The task's acceptance criteria
3. The executor's completion report
4. Fresh build/test output (run by orchestrator BEFORE delegating)
5. List of files modified

Verifier output format (from OMC reference lines 566-574):
- Verdict: PASS or FAIL (with confidence: high/medium/low)
- Evidence: table of checks performed with commands and output
- Acceptance Criteria: table mapping each criterion to VERIFIED/PARTIAL/MISSING
- Gaps: any uncovered areas
- Recommendation: APPROVE, REQUEST_CHANGES, or NEEDS_MORE_EVIDENCE

Verifier rules (from OMC reference lines 554-558):
- READ-ONLY — cannot modify files
- No approval without fresh evidence
- Reject on: "should/probably/seems to", no test output, claims without results
- Run commands if possible, don't trust claims

On APPROVE: task.passes = true, task.verifier_verdict = full report
On REQUEST_CHANGES: task.verifier_verdict = report with concerns, loop back
On FAIL: task.verifier_verdict = report with failures, loop back

**Architect Agent (final review only):**
The architect performs holistic review when ALL tasks pass. This is the
Step 7 review (OMC reference lines 117-129). The architect evaluates:
- Functional completeness against the original plan
- Architectural coherence across all changes
- Integration issues between separately-implemented tasks
- Scope completeness (no scope reduction)

Architect is READ-ONLY (OMC reference line 520-521).

Architect output:
- Verdict: APPROVE or REQUEST_CHANGES
- Strengths: what's correct
- Concerns: specific issues (with file:line references)
- Missing: gaps not addressed
- New Tasks: if REQUEST_CHANGES, specific tasks to create

**Acceptance Criteria:**
- [ ] Verifier and architect are separate delegations with distinct prompts
- [ ] Verifier runs per-task, architect runs once at final review
- [ ] Verifier receives fresh build/test output as evidence
- [ ] Verifier rejects claims without evidence
- [ ] Architect reviews holistically against original plan
- [ ] Both are READ-ONLY (cannot modify files)
- [ ] role-verifier.md prompt created in references/

---

### Task 6: Error Handling — 3-Strike + Cancel + Circuit Breakers
**Complexity:** Medium
**Dependencies:** Task 1, Task 3
**Description:**
Implement error handling, cancellation, and circuit breakers.

**3-Strike Rule (OMC reference lines 149-153, 298-299):**

Structured error fingerprinting (Addresses: Architect C6, Critic W2):

v1 used "first 100 chars of normalized error" which would false-match on
common errors like "Build failed" or "Test failed". v2 uses structured
fingerprinting:

```json
{
  "task_id": "T-001",
  "iteration": 5,
  "category": "build|test|lint|runtime|timeout|unknown",
  "error_key": "normalized identifying string",
  "raw_error": "full error text (truncated to 500 chars)",
  "timestamp": "ISO-8601"
}
```

Error matching logic:
1. Same task_id (errors on different tasks never match)
2. Same category
3. error_key similarity — the error_key is constructed by:
   a. Strip timestamps, absolute paths, line numbers, PIDs
   b. Extract the error type/code (e.g., "TS2345", "ENOENT", "AssertionError")
   c. If an error code exists, that IS the key
   d. If no error code, use first 200 chars of normalized message
4. Two fingerprints match if task_id + category + error_key are equal

When 3-strike triggers:
1. Set task status to blocked (not the whole plan)
2. Record the error pattern and all 3 attempt summaries
3. Skip to next eligible task (Addresses: Architect C5 partially)
4. If ALL remaining tasks are blocked: set active=false, phase="blocked"
5. Write clear message explaining what's blocked and why

**Cancel/Abort Mechanism (Addresses: Architect C1, Critic C4):**

The user can cancel ralph by:
1. Creating `.omha/state/ralph-cancel.json` with `requested_by: "user"`
2. Or: ralph skill prompt instructs the agent that if the user says "stop",
   "cancel", or "abort", write the cancel file and exit
3. Or: autopilot/caller writes the cancel file

On cancel detection:
1. Set phase="cancelled" in ralph-state.json
2. DO NOT delete state files (allow resume later)
3. Report: "Ralph cancelled at iteration N, task [id]. State preserved
   for resume. Delete .omha/state/ralph-cancel.json and re-invoke to continue."

**Circuit Breakers:**

| Breaker | Threshold | Action |
|---|---|---|
| Max iterations | 100 (configurable via max_iterations) | Set phase="blocked", exit |
| Staleness | >2 hours since last_updated_at | Warn on next invocation, offer fresh start |
| All tasks blocked | Every remaining task has 3-strike | Set phase="blocked", exit with full report |
| Cancel signal | ralph-cancel.json within TTL | Set phase="cancelled", exit |

max_iterations defaults to 100 (matching OMC, reference line 609).
(Addresses: Architect C7, Critic W3). Unlike OMC which auto-extends,
OMHA uses a hard cap because there is no stop hook to enforce extension.
Users can set a higher value in ralph-state.json before invocation.

**Acceptance Criteria:**
- [ ] Error fingerprinting uses structured matching (category + error_key)
- [ ] 3-strike blocks individual tasks, not entire plan
- [ ] Cancel signal file detected and honored
- [ ] User "stop"/"cancel"/"abort" creates cancel file
- [ ] Max iterations enforced (default 100, configurable)
- [ ] Staleness detected on invocation (>2h)
- [ ] All-blocked state properly reported

---

### Task 7: Resumability and State Recovery
**Complexity:** Medium
**Dependencies:** Tasks 1-6
**Description:**
Implement resume-from-checkpoint. In the one-task-per-invocation model,
every invocation is effectively a "resume" — it reads state and continues.
This task handles the edge cases.

Resume scenarios:

| State Found | active | phase | Action |
|---|---|---|---|
| No state file | - | - | Fresh start: run Planning Gate |
| State exists | true | execute/verify | Normal: pick next task, continue |
| State exists | true | final-review | Re-run final review |
| State exists | false | complete | Report completion, offer fresh start |
| State exists | false | blocked | Report blockers, ask if resolved |
| State exists | false | cancelled | Report cancellation, check for cancel file removal |

**Session ID handling (Addresses: Architect C3, Critic C1):**
- On fresh start: generate a UUID and store as session_id
- On resume: compare stored session_id with current session
- If different session: warn "Resuming ralph state from a different session.
  State was last updated at [time]." — proceed anyway (not a hard block,
  since one-task-per-invocation expects different sessions)
- session_id prevents a DIFFERENT ralph plan's state from being read
  (e.g., if the user runs ralph in two different project directories)

**Staleness (Addresses: Architect M3):**
Staleness is checked ONLY at invocation time (not continuously). The 2-hour
threshold means: if the last state update was >2 hours ago, the project
state may have changed externally. Ralph warns and offers a choice:
- Continue from checkpoint (risky if files changed)
- Fresh start (re-run planning gate, re-assess all tasks)

**Dynamic task discovery on resume (Addresses: Architect C5):**
Tasks are NOT immutable. New tasks can be added to ralph-tasks.json:
1. By the final architect review (REQUEST_CHANGES creates new tasks)
2. By the executor reporting BLOCKED with "needs prerequisite task X"
3. By the user manually editing ralph-tasks.json between invocations

Discovered tasks have `discovered: true` and are inserted at the
appropriate priority level.

**State cleanup on completion (OMC Pattern 12, reference lines 757-760):**
- Delete ralph-state.json
- Delete ralph-tasks.json
- Delete ralph-cancel.json (if exists)
- Keep ralph-progress.md (audit trail)

**Acceptance Criteria:**
- [ ] Every invocation reads state and determines correct action
- [ ] Session_id generated on fresh start, checked on resume
- [ ] Staleness warning at >2h with choice to continue or restart
- [ ] Blocked state allows retry after user confirms fix
- [ ] Cancelled state detects cancel file removal for resume
- [ ] Dynamic tasks can be added between invocations
- [ ] State files deleted on completion, progress log preserved

---

### Task 8: Create role-verifier.md Prompt
**Complexity:** Small
**Dependencies:** Task 5
**Description:**
Create the verifier role prompt based on OMC's verifier agent
(reference lines 544-574). This prompt goes in
omha-ralplan/references/role-verifier.md alongside the existing
role-architect.md and role-executor.md.

The verifier is distinct from the architect:
- **Verifier:** "Did this specific task meet its acceptance criteria?
  Show me the evidence."
- **Architect:** "Does the overall system design hold together?
  Are there architectural concerns?"

The prompt must encode:
- Evidence-first principle (no approval without fresh output)
- Red flag detection ("should", "probably", "seems to")
- Structured output format (verdict, evidence table, criteria mapping)
- READ-ONLY constraint
- Investigation protocol: DEFINE → EXECUTE → GAP ANALYSIS → VERDICT

**Acceptance Criteria:**
- [ ] role-verifier.md created in omha-ralplan/references/
- [ ] Clearly distinct from role-architect.md
- [ ] Evidence-first principle encoded
- [ ] Structured output format specified
- [ ] READ-ONLY constraint explicit

---

### Task 9: Write the SKILL.md
**Complexity:** Large
**Dependencies:** Tasks 1-8 (all design decisions must be final)
**Description:**
Write the complete SKILL.md file. This is the actual deliverable — the
skill instructions that Hermes loads and follows.

The SKILL.md must include:
1. Frontmatter (name, description, version, tags, metadata)
2. When to Use section (trigger conditions)
3. Prerequisites section (planning gate)
4. One-Task-Per-Invocation Protocol (numbered steps)
5. Executor Delegation section (what to include, parallel rules, learnings feed)
6. Verifier section (per-task, evidence-based)
7. Architect section (final review only)
8. Cancel/Abort section
9. 3-Strike Rule section (with structured fingerprinting)
10. Resumability section
11. Iron Law checklist (adapted from OMC's 12-item checklist, reference lines 156-169)
12. State Schema reference (inline or linked)
13. OMC Divergences section (explicit list of what differs and why)

Reference files to create:
- references/state-schema.md — JSON schemas
- references/iron-law-checklist.md — verification checklist
- templates/ralph-tasks-example.json — example task file

Key tone: the SKILL.md is instructions, not documentation. Every sentence
is a rule ("you MUST"), a condition ("IF x THEN y"), or a reference
("read file X for schema").

**The SKILL.md must NOT contain loop/persistence language.** Since we use
one-task-per-invocation, there is no "never stop" instruction. Instead:
"Complete one task, update state, and exit. The caller will re-invoke you."

**Acceptance Criteria:**
- [ ] SKILL.md replaces the stub completely
- [ ] All 8 previous tasks' designs reflected in instructions
- [ ] One-task-per-invocation protocol is clear
- [ ] No loop/persistence language (no "never stop")
- [ ] Cancel/abort mechanism documented
- [ ] Verifier and architect roles clearly separated
- [ ] Iron Law checklist adapted for Hermes
- [ ] OMC divergences section present
- [ ] Reference files created alongside SKILL.md
- [ ] Valid YAML frontmatter

---

## Risks

### R1: Caller Must Re-invoke (No Mechanical Persistence)
**Severity:** High
**Mitigation:** This is the fundamental trade-off of one-task-per-invocation.
Accepted because: (a) autopilot will be the primary caller and handles
re-invocation, (b) users can use cron or a simple "while ralph says not done,
invoke ralph" wrapper, (c) state files make each invocation stateless and
safe. The alternative (in-session loop) has the worse risk of context
exhaustion killing a mid-task execution.

### R2: delegate_task Subagents Can't Run Terminal Commands
**Severity:** Medium
**Mitigation:** Orchestrator runs builds and tests. Subagents (executor,
verifier, architect) only reason about code and produce reports. Executor
writes code via file tools; ralph runs verification commands.
(Confirmed: architecture.md line 64.)

### R3: 3-Agent Concurrency Limit Constrains Parallel Execution
**Severity:** Low
**Mitigation:** Most invocations work on one task (execute + verify = 2
subagent calls, serial). Parallelism applies when multiple independent
tasks are eligible. 3 concurrent is sufficient. OMC's 6-agent ultrawork
is rarely fully utilized in practice.

### R4: Error Fingerprinting May Still Have Edge Cases
**Severity:** Medium
**Mitigation:** Structured fingerprinting (category + error_key) is much
better than v1's "first 100 chars" but won't be perfect. The error_key
extraction logic (error codes > normalized message) handles the most common
cases. Edge case: genuinely different errors with similar messages. Ship
and iterate — the 3-strike blocks one task, not the whole plan.

### R5: Learnings Feed May Grow Large
**Severity:** Low
**Mitigation:** completed_task_learnings is summarized (not raw output).
Each entry is ~100-200 chars. For a 20-task plan, that's ~4KB — well within
delegate_task context limits. If it grows too large, truncate to the 10
most recent learnings.

### R6: Git Integration Absent (Addresses: Critic W5)
**Severity:** Medium
**Mitigation:** Ralph does not auto-commit or provide git rollback. The
user can commit between ralph invocations manually. Autopilot may add git
integration. For now, ralph's progress log and task-by-task execution
provide logical rollback points (re-run a task to redo its changes).
This is a deliberate simplicity choice — git integration adds complexity
for uncertain value at this stage.

---

## Open Questions

### Q1: Should ralph support running WITHOUT ralplan (ad-hoc mode)?
**Recommendation:** Yes. The planning gate accepts either a ralplan output
or a manually provided task list. "Tasks must exist" is the gate, not
"ralplan must have run."

### Q2: Should the executor subagent write code directly?
**Recommendation:** Yes. Executor uses file tools (read_file, write_file,
patch). Ralph runs build/test commands. This is confirmed by architecture.md
line 64.

### Q3: How does ralph handle tasks that require user interaction?
**Recommendation:** Set awaiting_confirmation=true, exit. On next
invocation, check if the user has provided input (e.g., updated task
description, set awaiting_confirmation=false). The one-task-per-invocation
model makes this natural — ralph just exits and the user re-invokes
after providing input.

### Q4: Should ralph commit to git after each task?
**Recommendation:** Not by default. Optional via user instruction in
the plan. See Risk R6.

### Q5: Should ralph detect parallel independence automatically?
**Recommendation:** Use the dependency graph from ralph-tasks.json as the
primary signal. If dependencies field is empty/absent, conservatively
assume sequential. The executor prompt should flag any discovered
dependencies for future tasks.

### Q6: How should autopilot invoke ralph repeatedly?
**Recommendation:** This is autopilot's problem, not ralph's. Ralph is
a single-invocation skill. Autopilot can: (a) use a while-loop in its
prompt instructions, (b) check ralph-state.json after each invocation,
(c) re-invoke until phase="complete". Details deferred to omha-autopilot
implementation plan.

---

## Dependency Graph

```
Task 1 (State Schema)
  ├──→ Task 2 (Planning Gate)
  ├──→ Task 3 (Core Logic) ──→ Task 4 (Executor)
  │                         ──→ Task 5 (Verification)
  │                         ──→ Task 6 (Error Handling)
  ├──→ Task 7 (Resumability) ← depends on Tasks 1-6
  └──→ Task 8 (Verifier Prompt) ← depends on Task 5 design
       └──→ Task 9 (SKILL.md) ← depends on all
```

Tasks 4, 5, 6 can be built in parallel once Task 3 is complete.
Task 8 can be built in parallel with Tasks 4/6.
Task 9 must be last.

---

## Estimated Total Effort

| Task | Complexity | Description |
|------|-----------|-------------|
| 1. State Schema | Small | Define schemas, document all fields |
| 2. Planning Gate | Small | Parsing logic + error messages + atomicity enforcement |
| 3. Core Logic | Medium | One-task-per-invocation protocol, atomic writes |
| 4. Executor Delegation | Medium | delegate_task integration, parallel rules, learnings feed |
| 5. Verification | Medium | Verifier + architect separation, evidence gathering |
| 6. Error Handling | Medium | 3-strike with structured fingerprinting, cancel, circuit breakers |
| 7. Resumability | Medium | State recovery, session_id, dynamic tasks |
| 8. Verifier Prompt | Small | role-verifier.md creation |
| 9. SKILL.md | Large | Complete skill instructions + reference files |

---

## Feedback Resolution Tracking

### Architect Feedback — All Addressed

| ID | Issue | Resolution |
|---|---|---|
| C1 | No cancel/abort | Cancel signal file + cancel detection in Task 6 |
| C2 | Context window growth | One-task-per-invocation eliminates this entirely |
| C3 | No session_id | Added to state schema in Task 1 |
| C4 | Architect role overloaded | Split into verifier (per-task) + architect (final review) in Task 5 |
| C5 | No dynamic task discovery | Tasks mutable via final review, executor blocking, user edit in Task 7 |
| C6 | Error fingerprinting crude | Structured fingerprinting with category + error_key in Task 6 |
| C7 | max_iterations 20 too low | Default 100, configurable, hard cap in Task 6 |
| M1 | Atomic file writes | Write-to-temp-then-rename in Task 3 |
| M2 | Progressive urgency | N/A in one-task-per-invocation (no within-session urgency) |
| M3 | Staleness clarification | Explicitly resume-time only, documented in Task 3 |
| M4 | Task atomicity | Enforced during plan parsing in Task 2 |
| M5 | Executor self-verification | Added to executor prompt in Task 4 |
| M6 | Feed learnings forward | completed_task_learnings in state, fed to executor in Task 4 |

### Critic Feedback — All Addressed

| ID | Issue | Resolution |
|---|---|---|
| C1 | State schema diverges | session_id + awaiting_confirmation added, divergences documented |
| C2 | Context window exhaustion | One-task-per-invocation eliminates this |
| C3 | Missing verifier agent | Separate verifier created in Task 5 + Task 8 |
| C4 | No cancel/abort | Cancel mechanism in Task 6 |
| W1 | Parallel execution hand-waved | Independence detection via dependency graph in Task 4 |
| W2 | Error fingerprinting will fail | Structured fingerprinting in Task 6 |
| W3 | max_iterations 20 too low | Default 100 |
| W4 | Sequential-first wrong default | Parallel-first adopted in Task 4 |
| W5 | No git integration | Documented as deliberate omission in Risk R6 |
| W6 | Deslop omission not documented | Documented as Divergence D5 |
| W7 | Files vs conversation state | Explained in Task 3 state file convention section |
