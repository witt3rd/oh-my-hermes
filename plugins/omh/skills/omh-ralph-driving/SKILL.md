---
name: omh-ralph-driving
description: >
  How to drive an omh-ralph run well as the dispatcher — plan-shape,
  iteration cadence, parallel batching, evidence gathering, verifier
  discipline, and commit hygiene across many iterations. The
  iron-law of one-task-per-invocation is in omh-ralph itself; this
  skill covers what the orchestrator does between invocations to
  keep the loop moving cleanly: picking parallel-safe batches,
  honoring "DO NOT modify <shared file>" discipline, distinguishing
  executor strikes (test-infra vs spec-misread vs real bug),
  Step-7 final architect review, and committing the loop to the
  user's branch.
version: 1.0.0
metadata:
  hermes:
    tags: [execution, ralph, orchestration, multi-agent, parallel, verification]
    category: omh
    requires_toolsets: [terminal, omh]
---

# OMH Ralph Driving — orchestrator's playbook for verified execution

Load this skill alongside `omh-ralph` when you are the orchestrator
dispatching the loop. `omh-ralph` is loaded by the role-tagged
*workers* (executor / verifier / architect) — it covers the iron-law
discipline inside each task's `delegate_task` call. This skill covers
what *you* do as the dispatcher: plan-shape, iteration cadence,
parallel batching, evidence gathering, verifier dispatch, strike
handling, commit hygiene, and the final architect gate.

The two skills have different readers and different jobs. Don't merge
them — worker context is precious; the dispatcher's playbook should
not ride into every subagent.

This skill is the ralph-side counterpart to `omh-ralplan-orchestration`
(which is the dispatcher playbook for ralplan, the design loop). The
relationship is consistent: each method has a worker-side skill (used
inside delegate_task) and a driver-side skill (used by the orchestrator
between dispatches).

## When to use ralph vs just write the code

Use ralph when:

- You have a plan with 5+ independently-acceptable tasks (from
  `omh-ralplan` or hand-authored).
- Quality-via-verification matters more than wall-clock — each task's
  output must be evidence-graded before the next builds on it.
- You want clean checkpoints across many work units (no context bloat).
- Some tasks are independent and can run in parallel batches.

Don't use ralph when:

- The work is single-step or trivially obvious to write directly.
- No plan exists yet — run `omh-ralplan` (or for an obvious goal,
  `omh-deep-interview` first) before invoking ralph.
- The user wants to skip verification (unusual; usually means the
  work is small enough to do directly).

## The arc of a ralph run

```
iter 1: pick eligible tasks → dispatch executors (parallel where safe)
        → gather evidence → dispatch verifiers (parallel) → mark passes/fails
        → update state → release lock → exit

iter 2: re-invoke. Read state. Pick next batch. Same cycle.

...

iter N: all tasks pass → Step 7 final architect review → mark complete.
```

The orchestrator's job between iterations: pick the right batch, write
the right context for each executor, gather the right evidence, parse
the verifier verdicts, and decide whether to retry or move on.

## The five-step playbook

### 1. Read the plan; verify it is ralph-shaped

A ralph plan is a list of numbered tasks, each with:

- A clear title.
- A description tight enough that an executor with no prior context
  can implement it.
- **Acceptance criteria that are testable.** Generic criteria like
  "implementation is complete" are rejected by ralph's planning gate.
- Dependencies (which other tasks must be done first).
- Files-touched (for parallel-batch planning — see step 3).

If the plan came from `omh-ralplan`, it is design-shaped, not ralph-shaped. The stance's "MV slice" section is your starting point; you may need to translate it to ralph's task format. Author `.omh/plans/ralph-plan.md` (or `.omh/plans/ralplan-<slug>.md` if it derives from a specific ralplan instance) with proper task structure.

The plan does not need every task pre-authored to the same depth — it can grow. Ralph's planning gate parses what's there at first invocation; new tasks discovered during execution land via the `discovered: true` flag in state.

### 2. Pick the right batch for each iteration

Each ralph iteration does ONE unit of work. A "unit" can be:

- One task (when the next eligible task is alone, or has shared file
  footprint with other eligibles)
- A batch of 2-4 tasks (when independents are eligible and have
  disjoint touch sets)

**Eligibility** = `passes: false` AND all dependencies met.

**Disjoint touch sets** = the tasks do not modify the same files. Read
the plan's "Files to modify/create" lists. If two eligible tasks both
touch `bin/janus-new-being`, they are NOT parallel-safe — one owns
the modification. If one touches `migrations/lib.py` and another
touches `bin/_lineage.py`, they are parallel-safe.

**Edge case — shared imports.** Even if files are disjoint, if Task A
authors a helper that Task B imports, you may need Task A to land first.
Surface this in dependency declarations during plan-authoring; if you
miss it, the executor for B will surface the dependency mid-task.

**Right batch size.** 2-4 tasks. Five+ in one batch overloads
orchestrator parsing of executor reports + verifier dispatch in your
own context window.

### 3. Dispatch executors with rich context

Each executor gets a fresh subagent. Subagents have NO memory of
prior iterations, prior conversations, prior tasks. Encode everything
they need in the dispatch context.

The executor dispatch context must contain:

- **Project root + branch.** Paths absolute, not relative.
- **Prior state.** What tasks completed in earlier iterations, what
  files now exist, what helpers/libraries are available to import.
- **Learnings from prior tasks** that are relevant to this one. Pull
  forward gotchas, naming conventions, architectural choices that
  the executor needs to honor.
- **The task itself.** Full title, description, acceptance criteria.
- **Required reading.** Absolute paths to the canonical design,
  prior tasks' outputs, similar siblings to pattern-match against.
- **TDD instruction.** Failing test first, watch it fail, implement,
  watch it pass, run full suite, commit. Make this explicit in
  EVERY executor dispatch.
- **Commit metadata.** Author identity, commit message shape, branch.
- **DO NOT modify <list>.** Critically important under parallel
  batches. See P3 below.

Use the `[omh-role:executor]` marker in the goal — the OMH plugin
auto-injects the executor role prompt via its `pre_llm_call` hook.
Don't inline role text manually.

A full template for the executor `goal` field — including TDD
instructions, sibling-aware DO-NOT-modify discipline, commit metadata,
and retry variations for each strike category — is at
`references/executor-goal-template.md`. Adapt the variables; keep the
structure.

### 4. Gather evidence with `omh_gather_evidence` BEFORE dispatching verifiers

After all executors complete, run the project's actual test/build/lint
commands via `omh_gather_evidence`. This produces a structured
`{results, all_pass, summary}` object the verifier can grade against.

**Critical:** the verifier does NOT run evidence themselves. Gathering
happens at the orchestrator level so you can verify executor claims
match reality before the verifier reads them.

**Allowlist gotcha.** `omh_gather_evidence` enforces a token-prefix
allowlist (`~/.hermes/plugins/omh/config.yaml` →
`evidence_tool.allowlist_prefixes`). Common project test commands like
`uv run --with pytest --with pyyaml -m pytest` do NOT match
`uv run pytest` because `--with` breaks the prefix. Either:

- Use the matching prefix: `uv run pytest <args>` (preferred — keep
  pytest as a project dev dep so `--with pytest` is unnecessary).
- Add a custom prefix to the OMH config.
- Wrap with a project-local script.

If gather_evidence rejects your command, the symptom is `exit_code: -1,
output: "Command not in allowlist"`. Re-form the command before
dispatching the verifier.

### 5. Dispatch verifiers in parallel (batched per task)

For each completed task, dispatch a verifier subagent with:

- `[omh-role:verifier]` marker (auto-injects the verifier role prompt).
- The task's acceptance criteria (so they grade against the spec, not
  the executor's interpretation of it).
- The full evidence output (the verifier MUST see real test results,
  not paraphrased success claims).
- File paths to inspect.
- Specific load-bearing checks that go beyond "tests pass" (e.g.,
  "verify the mismatched-flag check happens BEFORE any filesystem
  writes — if not, partial-flag invocations corrupt state").

Verifiers run in parallel via batched `delegate_task(tasks=[...])` —
same wall-clock savings as Round 2 ralplan reviewers.

The verifier returns one of:

- **APPROVE** / PASS — task's `passes` flag becomes `true`.
- **REQUEST_CHANGES** / FAIL — record verdict, retry executor with the
  feedback. Track strikes (see P5 below).

A full template for the verifier `goal` field — including the
acceptance-criteria-verbatim discipline, evidence-paste shape, sibling
boundary checks, strike categorization, and worked verdict examples —
is at `references/verifier-goal-template.md`.

## Pitfalls (P1–P10)

These are the failure modes that ralph dispatchers stumble into.
Numbered for cross-reference; gaps reserved for future additions.

### P1 — Plan must be ralph-shaped, not design-shaped

`omh-ralplan` produces a `stance.md` — a design document. Ralph
needs a task list with testable acceptance criteria.

If you point ralph at a stance directly, the planning gate either
parses it weakly (extracting whatever numbered sections look
task-shaped) or refuses outright. Translate the stance's MV slice
into a proper ralph plan first.

The translation is mechanical:

- Stance MV-slice items → ralph tasks (one item per task).
- Stance test affordances → task acceptance criteria (verbatim where
  the stance named them).
- Stance "depends on" prose → task `dependencies:` field.
- Stance file paths → task `files:` list (for parallel-batch
  planning).

Author the ralph plan as `.omh/plans/ralph-plan.md` or
`.omh/plans/ralplan-<slug>.md`. Ralph's planning gate finds either.

**Worked translation example (from the 2026-04-27 janus run).** The
stance's "MV slice plan" section listed 13 work items spread across
NOW (~3.5h, lineage capture before next provision) / NEXT (+72h, the
update tool) / DEFERRED (later releases). The ralph plan landed each
item as a task with this shape:

```markdown
### Task 4 — bin/janus-new-being: version stamp + seed-history snapshot

**Files to modify:**
- `bin/janus-new-being`

**Files to create:**
- `bin/tests/test_janus_new_being_lineage.py`

**Description:**
Patch `bin/janus-new-being` provisioning logic to write lineage data
per the stance's NOW slice item 2. After successful provisioning,
write `<profile>/.janus/version`, snapshot rendered template + plugin
tree to `<profile>/.janus/seed-history/v1/` via post-write disk-read,
compute MANIFEST with content hashes per file...

**Acceptance criteria (verbatim from stance test affordance):**

    def test_provision_writes_v1_lineage(tmp_path):
        profile = tmp_path / "alice-janus"
        # ... provision invocation ...
        assert (profile / ".janus" / "version").read_text().strip() == "v1"
        seed = profile / ".janus" / "seed-history" / "v1"
        assert (seed / "SOUL.md").exists()
        ...

**Dependencies:** none (Task 5 extends, but doesn't conflict)
```

The translation discipline that made this work:

1. **Verbatim acceptance criteria from the stance.** Where the stance
   said `test_provision_writes_v1_lineage_and_gh_config` passes, the
   ralph plan used that exact test name. This makes the executor
   write the test the stance specified, and the verifier grade
   against the stance's own contract — no drift through paraphrase.

2. **Files-touched are explicit.** Each task's `files:` lists exactly
   what gets created and modified. This is what enables parallel-
   batch planning later (P2): the orchestrator can read the lists
   and check disjoint touch sets without re-deriving them from the
   description prose.

3. **Dependencies are inferred from shared concrete artifacts, not
   just prose.** The stance said the MANIFEST shape was authored in
   Task 4; Task 8 (lib.py with `hash_equals_ancestor`) needs to read
   that format. So Task 8's `dependencies: [task-4]` was inferred from
   the shared file format, not from a "Task 8 must come after Task 4"
   sentence.

4. **NOW/NEXT/DEFERRED gets folded into priority ordering.** All
   NOW-slice tasks get `priority: 1` or `priority: 2` (with
   priority-2 reserved for ones that gate later parallel batches).
   NEXT gets 3-5. DEFERRED items don't appear as ralph tasks at all
   — they're not part of this run's work envelope.

5. **Test affordance section per task gets expanded to full pytest
   function signatures.** The stance often listed test names with
   brief shape; the ralph task gives the executor the exact function
   names + behavior so they don't have to re-derive them.

**The translation is its own load-bearing step.** Doing it sloppy
produces a sloppy run no matter how disciplined the orchestration is
afterward. The ralph plan IS the contract executors implement and
verifiers grade against; if it's vague, the loop produces vague work.

Budget 30-60 minutes for the translation on a 10+ task plan. The
output is the file ralph's planning gate parses; you'll never look at
the stance directly again during the run.

### P2 — Identify parallel-safe batches before dispatching, not during

Walk all eligible tasks (`passes: false` + deps met) at the start of
each iteration. For each pair, check disjoint-touch-set. Mark the
parallel-safe set; dispatch them in one batched `delegate_task`.

If you wait until after dispatching one task to consider whether
others could have run in parallel, you've forfeited the wall-clock
savings for that iteration. The right-time-to-decide is at the start
of the iteration, when you're already reading state.

Right batch size is 2-4. Two if dependencies are tight; four if
multiple independents stack. Five-plus overloads the orchestrator's
own context with executor reports + parallel verifier dispatches.

### P3 — "DO NOT modify <shared file>" must be explicit in parallel dispatch contexts

When dispatching parallel executors, only ONE task owns each shared
file. The other executors must import (read-only) but not modify it.

Encode this explicitly in each executor's dispatch context:

> DO NOT modify migrations/lib.py during this task — Task X owns that
> change. Import what you need; if a function isn't there yet, fall
> back to inline implementation that matches Task X's expected
> signature so they converge cleanly when both commits land.

Without this instruction, parallel executors race on the shared file
and produce conflicting commits. With it, they respect the boundary
and commit only their own work.

The instruction should also tell each executor to **unstage sibling
tasks' files before commit**. Otherwise `git add -A` sweeps in
neighbors' uncommitted work — see P9.

### P4 — Encode forward-learnings in each executor dispatch

Each iteration produces learnings (gotchas, naming conventions,
patterns that worked, patterns that failed). The next iteration's
executors do NOT see these unless you encode them.

Maintain a per-iteration learnings list in the ralph state's
`completed_task_learnings` field, and include the relevant subset in
each subsequent executor's dispatch context.

Examples worth encoding forward:

- "TEST-INFRA: never use `hash(content) & 0xffff` for tmpdir naming
  — randomized + small modulus = collision risk."
- "Use `git rm -r` (not `rm -rf`) to preserve git history when
  removing tracked files."
- "bin/janus-new-being uses uv shebang, no .py suffix; new bin/*
  scripts should follow the same pattern."
- "The classify() function in bin/_lineage.py ships the criterion
  (path-prefix patterns + Class-B exact set), not enumeration. Reuse
  it; don't duplicate the taxonomy."

These compress and ride forward via the dispatch context. The
omh-ralph state's `completed_task_learnings` is the canonical store.

### P5 — Distinguish executor strikes by category

When the verifier returns REQUEST_CHANGES, the cause is one of:

1. **Test-infra** — the test itself is buggy (e.g., a `hash() & 0xffff`
   path collision, a fixture race, a test runner config issue). The
   implementation may be correct; only the test needs fixing.

2. **Spec-misread** — the executor implemented something different
   from what the acceptance criteria asked for. Implementation needs
   correction.

3. **Implementation bug** — the executor implemented the right thing
   but it has a real defect (logic error, edge case missed, security
   issue).

These three categories take different fixes. Test-infra retries
should touch only the test file. Spec-misread retries need fresh
context emphasizing what the spec actually requires. Implementation-
bug retries need the failing case named explicitly.

Tag the strike category in the error fingerprint when updating state:

```python
"error_fingerprints": [
    {"category": "test-infra", "error_key": "hash-collision-in-tmpdir-naming", "round": 1},
    ...
]
```

The 3-strike circuit breaker (per `omh-ralph` Step 6) fires when the
same `(category, error_key)` repeats three times. Tagging by category
prevents test-infra strikes from masking real bugs (or vice versa).

### P6 — Verifiers must read real evidence, not executor claims

Always run `omh_gather_evidence` before dispatching verifiers.
Include the evidence output in the verifier's dispatch context.

If you skip evidence-gathering, the verifier reads only the executor's
report ("Status: COMPLETE; 5 tests pass; commit X") and has no
ground truth to grade against. Executor reports are sometimes wrong
— either the executor genuinely missed something, or a test passed
for the wrong reason (e.g., a path-collision crashing before the
load-bearing assertion ran — see this skill's worked example).

The orchestrator-runs-evidence pattern is what makes ralph
verification trustworthy.

### P7 — Final architect review (Step 7) is the merge gate

When all tasks pass, ralph's Step 7 dispatches an architect to review
the full implementation against the original plan/stance.

The architect reviews HOLISTICALLY:

- Architectural fidelity (did the implementation honor the design?)
- Principle alignment (do load-bearing principles fire in mechanics,
  not just appear in prose?)
- MV slice readiness (can the user actually run this tonight?)
- Architectural seams (anything rough vs explicitly deferred?)
- Commit hygiene (is the git history clean enough to merge?)
- Test affordance gaps

This is the orchestrator's final gate before handing the user a
PR-ready branch. The architect can return:

- **APPROVE** — seal-of-merge.
- **APPROVE_WITH_PROVISO** — small foldable additions before merge
  (typically 1-3 named items).
- **REQUEST_CHANGES** — something cannot ship; new tasks added with
  `discovered: true`.

Author the architect's review as `<orchestrator>-architect-review.md`
in the design directory (the orchestrator's own iteration-level review
is `<orchestrator>-review.md`; the architect-review is a separate
artifact).

A full template for the architect-final-review `goal` field — including
the diff-range walk, end-to-end MV-slice trace, principle-firing audit,
commit-hygiene check, verdict calibration guidance, and worked review
examples (APPROVE_WITH_PROVISO and REQUEST_CHANGES) — is at
`references/architect-final-review-template.md`.

### P8 — Update state at every action; release lock at every exit

Per `omh-ralph` Step 0/Step 8: state files at
`.omh/state/ralph--<instance_id>.json` and
`.omh/state/ralph-tasks--<instance_id>.json` track the run. Lock at
`.omh/state/ralph--<instance_id>.lock` prevents concurrent sessions
racing on the same plan.

Discipline:

- Acquire the lock at iteration start (Step 0).
- Update state after every executor completion, every verifier
  verdict, every task transition.
- Release the lock at every exit point — success, blocked, cancel,
  max-iterations, exception. Wrap the iteration body so unlock fires
  even on error.

Do NOT leave stale locks. If a lock is held by a dead process, the
next ralph invocation will surface it via `held_by` — offer to cancel
+ retry, don't silently steal.

### P9 — Commit hygiene under parallel writes

Three executors writing to the same branch in one orchestrator turn
will see *partial* state from each other (whatever has been committed)
but NOT each other's uncommitted work. If one executor uses
`git add -A` to stage their commit, they may sweep in sibling
executors' files that are still in-flight.

Discipline for parallel-executor dispatch:

1. **Tell each executor to `git add` their specific files explicitly**,
   not `git add -A`. Names match the task's `files:` field.

2. **Tell each executor to check `git status` before commit**: if
   sibling tasks' files are present and unstaged, do NOT include them.
   Common sibling files: untracked __init__.py stubs, untracked test
   files, RELEASES.yaml mid-edit.

3. **Accept that absorption sometimes happens anyway.** When it does,
   the failure is recoverable: an interactive rebase squashes the
   over-broad commit with the missing one, OR a follow-up history-note
   commit explains the boundary.

4. **Surface the absorption in iteration logs.** If you notice an
   executor reported "swept in pre-existing untracked files," flag it
   for the architect's commit-hygiene check at Step 7.

This pattern was learned the hard way: in one run, task-11's commit
absorbed ~60% of task-12's intended-commit content via `git add -A`.
Tests stayed green; deliverables were correct; commit boundaries were
fuzzy. Architect flagged it as a foldable proviso.

### P10 — Resume vs restart matters for plugin/tool changes

If the user makes plugin or toolset changes between iterations
(adding a tool, enabling a plugin, modifying config.yaml), tools do
NOT register live in the current session. They register at agent
**boot**.

If the user says "I changed the config, can you use the new tool now?":

- The session needs a full restart, not just a Resume button click
  (some chat UIs reuse the same agent process across "Resume").
- Verify by checking your function schema — if the new tool isn't
  there, the boot didn't happen.
- The fastest way to know is `omh_state(action="check", ...)` if
  it's an OMH-related plugin — if the tool errors with
  "function not found," the plugin isn't loaded.

See sibling skill `enabling-hermes-plugin-in-profile` for the full
plugin-install diagnostic ladder if tools genuinely don't surface
after restart.

## State management cheat sheet

```python
# Step 0: check + lock
omh_state(action="cancel_check", mode="ralph", instance_id=instance_id)
lock = omh_state(action="lock", mode="ralph", lock_key=instance_id,
                  session_id=session_id, holder_note="...")

# Step 1: read state (or trigger planning gate)
state = omh_state(action="read", mode="ralph", instance_id=instance_id)
tasks = omh_state(action="read", mode="ralph-tasks", instance_id=instance_id)

# Step 2: planning gate (only on first invocation)
omh_state(action="write", mode="ralph-tasks", instance_id=instance_id, data={
    "tasks": [{"id": "task-1", "title": "...", "description": "...",
               "acceptance_criteria": "...", "priority": 1,
               "dependencies": [], "passes": False, "files": [...]}, ...]
})

# Step 3-5: per-iteration execution
# (delegate_task for executors, omh_gather_evidence, delegate_task for verifiers)

# Step 8: update state, exit
omh_state(action="write", mode="ralph", instance_id=instance_id, data={
    "active": True, "phase": "execute", "iteration": N, ...,
    "completed_task_learnings": [...]
})
omh_state(action="unlock", mode="ralph", lock_key=instance_id, session_id=session_id)
```

## What "done" looks like for the orchestrator

- All tasks have `passes: true` in ralph-tasks state.
- Step 7 final architect review: APPROVE or APPROVE_WITH_PROVISO with
  provisos folded.
- `<orchestrator>-architect-review.md` written.
- `.omh/logs/ralph-progress.md` (or domain-equivalent) names the
  iteration arc, strikes encountered, and key learnings.
- State marked `phase: complete`, `active: false`.
- Lock released.
- The user can open a PR from the branch.

## Worked example (2026-04-27, janus migration)

13-task plan, 5 iterations, 1 strike total, final APPROVE_WITH_PROVISO.

- **iter 1**: 3 independents (RELEASES.yaml, AGENT.md patch, retire
  janus-migration skill) in parallel. All APPROVE.
- **iter 2**: task-4 solo (lineage capture, gates 5/6/8). Strike 1
  was test-infra hash collision. APPROVE on retry.
- **iter 3**: 3 parallel (gh-config, backfill-lineage, lib.py). Each
  task's dispatch said "DO NOT modify bin/_lineage.py — Task X owns
  it." Strike-zero round.
- **iter 4**: 3 parallel (janus-migrate skill, janus-update CLI,
  pytest harness). Strike-zero.
- **iter 5**: 3 parallel (boot-context surface, janus-contribute stub,
  v2 migrations). Strike-zero. **One commit-hygiene issue:** task-11
  absorbed task-12 files via `git add -A`. Tests green; flagged for
  architect review.
- **Step 7**: architect APPROVE_WITH_PROVISO, two foldable items
  (commit-hygiene rebase + missing migrations/README.md).

Total: 0 → 132 tests across 14 implementation commits. The discipline
that made this strike-zero across 4/5 parallel iterations was P3
("DO NOT modify <shared file>") + P4 (forward-learnings encoding) +
P6 (orchestrator-runs-evidence). The one strike was P5 test-infra,
recovered cleanly.

## Maintaining your own run log

Each ralph run that produces new pitfalls or surprising patterns is
worth logging. Keep a short table:

| Date | Domain | Iters | Strikes | Surprises | Patches to this skill |
|------|--------|-------|---------|-----------|------------------------|

Don't let this skill turn into a session log. Log somewhere else
(your substrate, project notes, a wiki). Patch this skill only when
a pitfall is general enough to teach a future orchestrator.

## Related skills

- `omh-ralph` — the worker-side discipline, loaded inside each
  delegate_task. Required reading for the orchestrator (one-off, to
  understand what the workers are doing) but not loaded into worker
  context (they auto-inject role prompts via the plugin).
- `omh-ralplan-orchestration` — the dispatcher playbook for the
  design loop. Use BEFORE ralph if no plan exists yet. Same shape
  (driver-side skill) for a different method (consensus design vs
  verified execution).
- `omh-ralplan` — the worker-side design discipline. Use only inside
  delegate_task with `[omh-role:planner|architect|critic]` markers.
- `enabling-hermes-plugin-in-profile` — sibling skill for the
  plugin-install diagnostic ladder. Cite if a ralph run is blocked
  because OMH tools aren't in the function schema.
- `subagent-driven-development` — the simpler shape for plans without
  the OMH plugin available. Same architectural pattern but without
  state machinery, role injection, or evidence tooling.

## Do-not-lose content

The single most load-bearing insight: **the orchestrator runs evidence,
not the verifier.** Always `omh_gather_evidence` BEFORE dispatching
the verifier. Include real test output in the verifier's context.
This is what makes ralph's verdicts trustworthy; without it, you have
two layers of executor-self-reporting.

Second: **"DO NOT modify <shared file>" is the discipline that makes
parallel batches of 3 work.** Every parallel-executor dispatch must
name what files belong to siblings. Without this, parallel batches
race on shared files and one task's commit absorbs another's work.

Third: **strikes have categories.** Test-infra ≠ spec-misread ≠
implementation-bug. Tag the category; the 3-strike circuit breaker
should fire on the *same* category, not just the same task. Mixing
categories produces false-positive halts (or worse, false-negatives
where a real bug masquerades as test-infra).

Fourth: **the orchestrator's altitude is "between iterations,"**
not inside any one task. The iron-law of one-task-per-invocation
exists so you can stay at altitude — picking batches, encoding
learnings forward, gathering evidence, dispatching verifiers,
deciding retry vs advance. Drop into the work and you become an
executor; the loop's whole value collapses.
