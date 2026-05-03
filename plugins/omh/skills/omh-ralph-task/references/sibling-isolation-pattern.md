# sibling-isolation pattern — canonical example

Drawn from janus-plugin-v12 / 2026-05-01 ralph round, Task 3 (profile-template namespace rectification, framework: → plugin:). Task 1 (migrations/lib.py edits) was running in parallel — same repo, different files, same iteration.

## Setup

The envelope specified:

```
Files this task owns
Modify:
- profile-template/substrate/profile.yaml.j2
- bin/janus-new-being
- bin/tests/test_janus_new_being.py

DO NOT modify (sibling tasks own these)
- migrations/lib.py — Task 1
- migrations/tests/test_lib.py — Task 1
```

Prior state: 361 tests pass on v12 HEAD (`80317eb`).

## What happened

Task 3 work landed clean — TDD red-then-green on the new tests, file scope respected. Ran the full suite per envelope instruction:

```
$ uv run pytest -q
...
1 failed, 374 passed in 9.56s
=================================== FAILURES ===================================
____________________________ test_delete_file_happy ____________________________
migrations/tests/test_lib_helpers.py:217: AssertionError
```

The failure was in `migrations/tests/test_lib_helpers.py` — neighbor file to `migrations/tests/test_lib.py` (which the envelope flagged as Task-1-owned) and a test against `migrations/lib.py` (also Task-1-owned).

## The wrong moves (didn't take)

- **Panic** — "I broke 1 test, status PARTIAL" — false. I did not modify migrations/lib.py.
- **Assume sibling** — "Status COMPLETE; failure is Task 1's, not mine" — possibly false. The envelope said "all 361 existing tests continue to pass," and 374 - 1 = 373 ≠ 361, but `test_lib_helpers.py` is a TEST file; the test count grew because Task 1 added new tests AND Task 1 broke one existing test. Without verification I'd be reporting an assumption as a fact.
- **Fix it** — open `migrations/lib.py` and patch — explicit envelope violation; that's Task 1's lane.

## The right move — stash verify

```bash
$ git stash
Saved working directory and index state WIP on v12: 80317eb v12 fold: ...

$ uv run pytest migrations/tests/test_lib_helpers.py::test_delete_file_happy -q
.                                                                        [100%]
1 passed in 0.01s

$ git stash pop
Dropped refs/stash@{0} (...)
```

Pristine HEAD (`80317eb`) PASSES the test. My tree (with Task 1's working-tree edits to `migrations/lib.py`) FAILS the test.

But — crucially — the failure surfaced via Task 1's edits to migrations/lib.py, NOT via my edits to profile-template / janus-new-being / bin/tests. The stash also stashed Task 1's working-tree changes (since they were unstaged-modified-files in the same working tree). When pristine = HEAD passes and tree-with-only-Task-1-work fails, that's proof the breakage came in via Task 1.

After `git stash pop`, the failure returns. I committed only my owned files. Reported COMPLETE with this isolation note in the report:

> Full suite: 374 passed, 1 failed. The single failure (`migrations/tests/test_lib_helpers.py::test_delete_file_happy`) is in Task 1's territory (migrations/lib.py), confirmed by stashing my changes and seeing the test pass against pristine HEAD. Failure is from Task 1's parallel in-progress modifications to migrations/lib.py — not in my scope.

## Why this matters

The orchestrator parses report-back and decides: re-dispatch this task (if status was PARTIAL/BLOCKED/failures-mine), advance the round (if COMPLETE), or escalate (if a sibling broke a thing my task touches). False signals here corrupt the iteration:

- Reporting COMPLETE without verification → orchestrator might miss that Task 1 actually broke something
- Reporting PARTIAL without verification → orchestrator re-dispatches you for nothing, wasted compute
- Fixing it yourself → corrupts Task 1's work, breaks the parallel-task isolation contract

Verification cost: 3 commands, ~5 seconds. Cheap diagnostic for what it protects.

## When stash doesn't work cleanly

Edge cases where the stash-verify pattern needs adaptation:

- **Untracked files matter to the test.** `git stash -u` to include them. Common when the failing test imports a new module a sibling added.
- **Stash contains conflicting paths.** If both you and the sibling touched the same file (envelope violation by one of you), stash pop will conflict. Resolve by re-reading the envelope — one of you is out of bounds.
- **Test depends on installed-state, not just source.** Re-run after `uv pip install -e .` or equivalent if the failure is import-shape rather than logic.

## Don't be precious about the shape

The pattern is: separate-the-trees → run-the-test-against-each → name-which-tree-owns-the-failure. `git stash` is the cheap implementation; `git worktree add` against pristine HEAD is heavier but cleaner when stash is unsafe. The discipline is the verification, not the specific git incantation.
