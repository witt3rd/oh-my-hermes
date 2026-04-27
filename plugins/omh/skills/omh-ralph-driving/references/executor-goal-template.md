# Executor goal template

Used as the `goal` field in `delegate_task` for an executor subagent
implementing one task in a ralph iteration. Adapt the variables. Keep
the structure — every section earns its place because the subagent has
NO memory of prior iterations, prior tasks, prior conversations.

```
[omh-role:executor] Task <N> — <one-line task title from the plan>

## Project root + branch

- Repo: <absolute path>
- Branch: <branch name>
- Commit author: <Name <email>>

All paths below are absolute. Subagents do not have `cd`-awareness.

## The task

<Full title + description from the ralph plan, verbatim. Do not
paraphrase — the verifier will grade against the plan, and any drift
between this dispatch and the plan becomes a strike.>

## Acceptance criteria

<Verbatim from the ralph plan. If the plan named a specific test
function (e.g. `test_provision_writes_v1_lineage`), the executor MUST
implement THAT test, not a paraphrase. Drift here = spec-misread
strike (P5).>

## Files this task owns

Modify:
- <absolute path>
- <absolute path>

Create:
- <absolute path>

## DO NOT modify (sibling tasks own these)

- <absolute path> — owned by Task <M> (running in parallel this iteration)
- <absolute path> — owned by Task <K> (running in parallel this iteration)

If you need a function from a sibling-owned file that does not yet
exist, fall back to inline implementation that matches the sibling's
expected signature (named in `## Required reading` below). The two
commits will converge cleanly when both land.

## Prior state (what exists going into this iteration)

Iterations completed: <N-1>

Tasks completed and what they produced:
- Task <M>: <one-line outcome + key files created/modified>
- Task <K>: <...>

Helpers / libraries now available to import:
- `<module path>` exposes `<function/class>(<signature>)` — <one-line use>
- ...

## Forward-encoded learnings (P4 — relevant to THIS task)

From prior iterations:
- <gotcha or convention the executor must honor; cite the iteration
  it was learned in if useful>
- ...

Example shapes (drop the ones that don't apply):
- TEST-INFRA: <pattern that bit a previous executor; e.g. "never use
  `hash(content) & 0xffff` for tmpdir naming — randomized + small
  modulus = collision risk">
- NAMING: <project convention; e.g. "bin/* scripts use uv shebang and
  no .py suffix">
- REUSE: <existing helper; e.g. "classify() in bin/_lineage.py ships
  the criterion — reuse it; don't duplicate the taxonomy">
- HISTORY: <git discipline; e.g. "use `git rm -r` not `rm -rf` to
  preserve history when removing tracked files">

## Required reading (open these files; do not work from summaries)

Canonical design:
- <absolute path to stance.md or design doc> — read first
- <absolute path to PRINCIPLES.md or directives>

Adjacent siblings to pattern-match against:
- <absolute path to similar in-tree file the new code should resemble>

Prior tasks' outputs you will build on or import from:
- <absolute path>

## TDD instruction (every executor dispatch, every time)

1. Author the failing test FIRST. Run it. Watch it fail with the
   expected error (not an import error or syntax error — a real
   assertion failure that names what's missing).
2. Implement the production code.
3. Run the test. Watch it pass.
4. Run the full project suite (the orchestrator will run evidence-
   gathering separately, but you should run it locally too). Confirm
   no regressions.
5. Commit (see `## Commit metadata` below).

Do NOT skip step 1. A passing test that was authored after the
implementation is not a TDD-grade test; the verifier may catch this
as test-after coding and request changes.

## Commit metadata

- Stage explicitly: `git add <each file from "Files this task owns">`.
  Do NOT `git add -A`. Sibling tasks may have uncommitted files in
  the working tree (see P9 in `omh-ralph-driving` SKILL.md).
- Run `git status` before commit. If sibling task files are present
  and unstaged, do NOT include them. If they're staged from a prior
  step in your own work, that's fine.
- Commit message shape:
  ```
  <task-id>: <one-line summary>

  <Optional 2-4 line body explaining what changed and why, citing
  acceptance criteria or test names where useful.>

  Refs: <plan path or task ID>
  ```
- Branch: stay on `<branch name>` from the project root + branch
  section. Do not create a new branch.
- Author identity: <commit author from above>.

## What "done" looks like for this task

1. Failing test authored and committed (or in same commit as impl —
   project's choice; default = same commit).
2. Implementation passes the test.
3. Full project suite passes (no regressions).
4. Commit lands on <branch name> with the message shape above.
5. The files listed under `## Files this task owns` are the only
   files touched. Sibling-owned files are unchanged.

## Output expected back to the orchestrator

A report with:
- **Status:** COMPLETE / BLOCKED / PARTIAL
- **Commit:** <sha>
- **Files touched:** <list>
- **Tests added/passing:** <list>
- **Anything you swept up by accident:** <files that ended up in your
  commit that weren't in the "Files this task owns" list — be honest;
  the architect's Step 7 commit-hygiene check needs this signal>
- **Learnings worth forwarding:** <gotchas or conventions worth
  encoding into future executors' P4 sections>
- **Open questions:** <if any — surface, don't paper over>
```

## Key things to include EVERY time

- **Absolute paths.** Subagents have no `cd`-awareness.
- **The task description verbatim from the plan.** Paraphrase = drift
  = spec-misread strike.
- **Acceptance criteria verbatim from the plan,** especially exact
  test function names where the plan named them.
- **DO NOT modify <list>.** Critical under parallel batches. Without
  it, parallel executors race on shared files (P3).
- **Forward-encoded learnings (P4).** Each iteration produces gotchas;
  the next iteration's executors do NOT see them unless you encode.
- **Explicit `git add` (not `-A`).** P9 commit-hygiene discipline.
- **TDD instruction.** Make it explicit every time, even if the
  executor "should know."

## Variations

- **Retry after REQUEST_CHANGES (test-infra strike):** add at top:
  ```
  ## Prior strike: TEST-INFRA

  Prior verifier feedback: <verbatim>. The test itself was buggy
  (e.g., `<specific issue>`). Fix the test; the implementation may
  already be correct. Re-run; if impl + new test still fail,
  diagnose impl.
  ```
- **Retry after REQUEST_CHANGES (spec-misread strike):** emphasize the
  acceptance-criteria section with what was misread:
  ```
  ## Prior strike: SPEC-MISREAD

  Prior verifier feedback: <verbatim>. The implementation diverged
  from the acceptance criteria as follows: <named drift>. Re-read
  the criteria; implement what they specify, not what feels natural.
  ```
- **Retry after REQUEST_CHANGES (implementation-bug strike):** name the
  failing case explicitly:
  ```
  ## Prior strike: IMPLEMENTATION-BUG

  Prior verifier feedback: <verbatim>. Failing case: <specific
  input/scenario>. Add a test that reproduces this case, then fix.
  ```
- **First-of-batch (no prior state):** drop the "Prior state" section
  or use it for the project's pre-ralph baseline (e.g., "fresh branch
  from main; no ralph tasks completed yet").
- **Solo task (no parallel siblings):** drop "DO NOT modify" — but
  KEEP the explicit `git add` discipline. P9 still applies if the
  working tree has untracked files from earlier orchestrator work.

## On strike categories (P5 cross-reference)

Verifier returns one of three REQUEST_CHANGES shapes:

1. **TEST-INFRA** — test buggy, impl may be fine. Fix the test.
2. **SPEC-MISREAD** — impl diverged from criteria. Re-read, redo.
3. **IMPLEMENTATION-BUG** — impl has a real defect. Reproduce + fix.

Tag the retry dispatch with the category (see Variations above) so
the executor knows where to focus. The 3-strike circuit breaker fires
on the same `(category, error_key)` repeating — mixing categories
masks real bugs (or vice versa).
