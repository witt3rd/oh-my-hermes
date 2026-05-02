---
name: omh-ralph-executor
description: Executing a single omh-ralph task as the executor (not the dispatcher). The orchestrator hands you a tightly-scoped task envelope (files-you-own, files-other-tasks-own, acceptance criteria, TDD instruction, commit metadata, report shape) and expects a single commit + structured report back. Sibling-of-record to omh-ralph-driver (orchestration), omh-ralplan-driver (planning), omh-triage-driver (triage). Load when a turn opens with `[omh-role:executor]`, when an `omh-ralph` parent run dispatches a task to you, when the task envelope specifies "Files this task owns" + "DO NOT modify (sibling tasks own these)", when authoring the report-back the orchestrator will parse, or when reviewing whether your in-progress execution is still inside its lane. Carries the file-scope rigidity discipline, the stash-verify-against-HEAD move for isolating sibling-task failures from your own, the commit-author override pattern, and the structured-report shape the orchestrator depends on.
version: 1.0.0
metadata:
  hermes:
    tags: [omh, ralph, executor, multi-agent, kanban-adjacent]
    related_skills: [omh-ralplan-driver, omh-ralph-driver, omh-triage-driver]
---

# omh-ralph executor — discipline

You are seeing this skill because an omh-ralph dispatcher (orchestrator) handed you a task envelope. You are the *executor*, not the dispatcher. Your job is narrow:

1. Do exactly the task the envelope specifies, no more.
2. Stay inside the file scope the envelope declares.
3. Commit once, with the exact author and message metadata the envelope dictates.
4. Report back in the shape the orchestrator expects.

The dispatcher trusts your report. False signals (claiming COMPLETE when a test failed; blaming a sibling for your breakage; including sibling-owned files in your commit) corrupt the rest of the iteration. Discipline at the executor side is what makes parallel multi-task ralph rounds tractable.

## The task envelope contract

The orchestrator gives you, at minimum:
- **Project root + branch** (where to work, which branch to commit on)
- **Commit author** (e.g. `<being-name> <being-email> (orchestrator-specified)`)
- **Files this task owns** (the only files you may stage)
- **DO NOT modify** (sibling tasks own these — read-only for you)
- **Acceptance criteria** (the bar the orchestrator will verify against)
- **TDD instruction** (whether to write failing tests first)
- **Commit metadata** (exact `git add` invocation and exact commit message body)
- **Output expected** (the report shape)

If any of these are missing or contradictory, ask the orchestrator before writing — don't infer your way through a missing constraint.

## Lifecycle

### 1. Orient

- Read the envelope twice. Note files-you-own AND files-others-own.
- Verify branch + HEAD match what the envelope says: `git status && git log -1 --oneline`.
- Read the required-reading list. The envelope tells you what design context matters.
- Read the files-others-own only if you need them for context — never modify.

### 2. TDD when instructed

The envelope often says: "Author failing tests FIRST. Run. Watch them fail with real assertion errors."

This is not optional when stated. Sequence:
1. Write the test file (or extend an existing one).
2. Run it: `uv run pytest <path> -q`.
3. Confirm RED with real assertion errors (not collection errors, not import failures).
4. THEN modify the implementation.
5. Run the new tests. Confirm GREEN.
6. Run the full suite. Confirm no regressions.

Going green-first (writing the implementation before the test) defeats the orchestrator's audit signal — they wanted to see real test-driven evidence in the commit, not after-the-fact tests rationalized to pass.

### 3. Stay in your file scope

When implementing, you may need to *read* sibling-owned files for context. You may not *modify* them. If you find yourself needing to modify a sibling-owned file to make your task work, that's a coordination signal — `BLOCKED` back to the orchestrator with the specific cross-task dependency, don't silently bleed.

### 4. Run the full suite

Even when you only added narrow tests, run the full suite per the envelope's instruction. The orchestrator wants regression confirmation.

### 5. Sibling-task isolation: the stash-verify move

This is the most-non-trivial executor discipline.

**Scenario:** you finish your work, run the full suite, and one or more failures appear in files outside your owned set. Three reflexes are all wrong:

- **Wrong reflex A** — panic and fail loud as if you broke them.
- **Wrong reflex B** — assume they're sibling-owned without verification and report COMPLETE.
- **Wrong reflex C** — fix them yourself ("just one line, easy") — bleeds into sibling lane.

**Right move:** verify ownership empirically before reporting.

```bash
# 1. Stash your work (keeps the failing-suite state preserved as "your tree minus your work")
git stash

# 2. Run the same failing test against pristine HEAD
uv run pytest <failing-test-path> -q

# 3a. If pristine PASSES → the failure is yours. Pop, fix, retry.
# 3b. If pristine FAILS → the failure is pre-existing or sibling-induced. Pop and continue.
git stash pop
```

If pristine HEAD passes the test but your tree fails, the failure is yours — don't pop with a half-fix; investigate. If pristine HEAD also fails the test, you've proven the failure is sibling-task or pre-existing, and you can report COMPLETE with an honest "1 sibling-task failure I confirmed isn't mine" note for the orchestrator.

The orchestrator is running multiple tasks in parallel. Without this verification you cannot honestly distinguish "I broke it" from "they broke it" from "it was already broken." Every executor that skips this move corrupts the iteration's signal.

See `references/sibling-isolation-pattern.md` for the canonical narrated example.

### 6. Commit with envelope-specified author

The envelope dictates the author. Don't trust the host's git config — override per-commit:

```bash
git -c user.name='<being-name>' -c user.email='<being-email>' commit -m "..."
```

Without `-c`, you commit as whatever `~/.gitconfig` says (often `user@hostname` or a different identity). The orchestrator expects a specific author for downstream attribution.

### 7. Stage explicitly, never `-A`

The envelope says: `git add <file1> <file2> <file3>`. Do exactly that. Do not `git add -A`, `git add .`, or `git add -u`. Sibling-task work in the working tree (other dispatchers running in parallel, or just operator notes) must not enter your commit.

After staging, run `git status` and confirm:
- Only owned files appear under "Changes to be committed"
- Sibling-owned files (if modified by a parallel task) appear under "Changes not staged" or "Untracked"
- If a sibling-owned file appears staged, you violated the envelope — `git reset HEAD <file>` and start over.

### 8. Report back in the orchestrator's expected shape

Typical shape:

```
Status: COMPLETE / BLOCKED / PARTIAL
Commit: <full sha>
Files touched: <list with one-line description each>
Tests added/passing: <count + key names>
Anything you swept up by accident: <or "nothing">
Learnings worth forwarding: <brief bullets>
Open questions: <or "none">
```

Honesty over performance. If you skipped a step or hit a sibling-failure you couldn't isolate, name it. The orchestrator triages it; you don't.

## Pitfalls

**Treating sibling-task failure as your problem.** You did not break what you did not touch. Verify with the stash move, then report.

**Touching the orchestrator's plan file.** `.omh/plans/ralph-plan.md` (or wherever the round's plan lives) is the orchestrator's surface, not the executor's. Don't edit it. If `git status` shows it modified, that's the orchestrator's writes — don't include it in your commit.

**Renaming the commit message.** The envelope's commit message is exact. Don't shorten the title, drop the `task-N:` prefix, drop `Refs:`, or rephrase the body. Downstream tooling (release notes, plan reconciliation) parses these.

**Author override forgotten.** Without `-c user.name -c user.email` your commit goes out under the host's default identity. Some orchestrators reject commits with the wrong author and recycle the task.

**Skipping the full-suite run** because "my narrow tests pass." The envelope asks for full-suite confirmation precisely so the orchestrator knows you didn't regress something distant. Skipping that step is the executor lying about coverage.

**Tightening a primitive's semantics breaks tests in neutral territory.** When your task hardens a shared helper (e.g., `delete_file` becomes ancestor-aware, a function that previously accepted any input now validates), the full-suite run may surface failures in test files that are neither in your "Files this task owns" list nor in the "DO NOT modify (sibling tasks own)" list — they're neutral territory the envelope didn't enumerate because nobody anticipated the seam. Three options:

- *Leave broken* — wrong; full suite must pass per envelope.
- *BLOCKED back to orchestrator* — wrong if the fix is a one-line fixture update obviously caused by your semantic change (e.g., a test of `delete_file_happy` that now needs a seeded MANIFEST entry to keep firing the clean-unlink path). That's not a coordination problem; it's the same change rippling into its own test surface.
- *Fix the minimal seam and flag it in the commit body* — right. Stage the fixture file alongside your owned files, keep the diff truly minimal (one line if possible), and call it out explicitly in the commit body so the orchestrator (and reviewers) can see it: e.g., "Also: seeded MANIFEST in test_X (test_Y.py) to match new ancestor-aware semantics — without an ancestor entry, v12 delete_file routes to conflicts rather than unlinking." Then mention it in the report's "Anything you swept up by accident" field.

The distinction from "touching sibling-owned files" is intent: sibling-owned files belong to a parallel task with its own commit author and its own envelope. Neutral test files that your primitive change shifts the meaning of are *yours to fix* because no one else's envelope will ever reach them. Skipping this fix and shipping a red suite to the orchestrator is the worse failure mode.

**`migration-coverage:` rule (project-specific but common in janus repos).** Some envelopes invoke a commit-msg hook (`bin/check-migration-coverage`) that fails the commit if you touched plugin source or templates without either a sibling migration or an explicit `migration-coverage: <reason>` line in the body. The envelope tells you which form to use; if it includes `migration-coverage:` in the spec'd commit body, ship it as-is — that line is load-bearing.

**"Redaction-marker" strikes from a verifier are display-layer artifacts more often than implementation bugs.** When a verifier (or your own grep/read_file) reports that a specific source line contains a literal redaction sigil — `***`, `<redacted>`, `xxx`, `REDACTED`, `…` — at a position where the source clearly should interpolate a variable (f-string `{var}`, template `${var}`, `%s`-style format), DO NOT trust the rendering. The display layer between the file on disk and what your tool prints can mangle curly-brace interpolation markers, control characters, or rare unicode into mask-shaped strings. A v12 ralph run lost a full retry iteration to exactly this: `f"https://x-access-token:{token}@"` rendered as `f"https://x-access-token:***@"` in `read_file` and `grep` output, the verifier struck IMPLEMENTATION-BUG correctly given what it saw, and the executor's fix-up commit became test-only because the bytes were correct from the original commit forward.

Discipline (before retrying or patching):

1. Run byte-level confirmation: `od -c <file> | sed -n '<line-start>,<line-end>p'` OR `python3 -c "import sys; print(repr(open(sys.argv[1],'rb').read().splitlines()[<idx>]))" <file>` OR `git show HEAD:<file> | sed -n '<line>p' | od -c`.
2. If the bytes contain `{var}` / `${var}` / `%s` / actual interpolation tokens, the implementation is sound and the strike is a false positive — report the false positive to the orchestrator, do not retry the implementation, and add a regression test that pins the byte-level invariant (so future verifiers can't be deceived by display drift).
3. If the bytes contain the literal mask-sigil (`***`, etc.), the strike is real — proceed with the fix.

The `scripts/verify-redaction-marker.sh` helper automates the byte-level check in one invocation. Run it before dispatching a retry on any IMPLEMENTATION-BUG strike whose evidence cites a mask-shaped substitution.

The failure mode is generalizable beyond ralph: any agent loop where one agent verifies another's code by reading rendered output is vulnerable. Architect-final-review (`docs/design/<rel>/forge-architect-review.md`) should also confirm any verifier-strike-categorized "redaction" or "stub-substitution" finding at byte level before treating it as ground truth.

See `references/sibling-executor-preemption.md` for the narrated v12 incident and `scripts/verify-redaction-marker.sh` for the helper.

**Sibling-executor pre-emption on retries (same-lane, not cross-lane).** Distinct from the sibling-task-in-different-lane case above. When a strike-N retry of the *same* task is dispatched, the orchestrator may have already fanned out a parallel executor for the same task envelope — or a previous executor may have partially landed work that wasn't yet committed when your retry started. Diagnostic: the patch tool's response will include a `_warning` field like `"<file> was modified by sibling subagent 'sa-X' but this agent never read it"`. That warning is load-bearing — STOP and reconcile state before patching further. Concretely:

1. Check `git diff <parent-sha> -- <file>` against the commit the envelope says you should be parented at. If the diff is empty, the fix is already in the tree (sibling already landed it on disk) — your work is now test-only, and the commit body should say so.
2. Don't trust terminal-rendered `grep` output as authoritative when something feels wrong. Drop to byte-level (`od -c`, `python3 -c "open(p,'rb').read()..."`) or `git show HEAD:<file>` to confirm what's actually on disk.
3. If a sibling actually committed the same fix while you were working, the orchestrator will reconcile — report COMPLETE with an honest "sibling executor 'sa-X' had already applied the implementation diff before this retry started; my commit is test-only; provenance preserved in commit body" note.

The root failure mode this prevents: chasing a phantom bug for many tool calls because a stale-looking grep makes you believe the fix isn't there when it is. See `references/sibling-executor-preemption.md` for a narrated example.

**Running `--from-file` end-to-end tests when the test envs need `hermes` on PATH.** If the executor runs in a profile or container without `hermes`, those tests skip silently (typical pattern: `@pytest.mark.skipif(not _hermes_available(), ...)`). Don't mistake a skip for a pass; check the suite summary explicitly.

## Adjacent skills

- **omh-ralplan-driver** — the planning side of OMH (designing the ralph plan the dispatcher then runs).
- **omh-ralph-driver** — the orchestration side that hands you envelopes.
- **omh-triage-driver** — the triage variant.
- **kanban-worker** — Hermes Kanban executor discipline. Distinct system (Kanban dispatcher, not omh-ralph) but the worker discipline shape rhymes — file scope, structured handoff, retry-aware.
- **github-pr-workflow** — when the round culminates in a PR, the dispatcher (not you) typically opens it; you ship commits the dispatcher will gather.

## See also

- `references/sibling-isolation-pattern.md` — canonical narrated example of the stash-verify move from a real iteration.
- `references/sibling-executor-preemption.md` — narrated example of same-lane sibling-executor pre-emption on a strike-N retry, and the byte-level verification path when terminal grep output is misleading.
- `scripts/verify-redaction-marker.sh` — one-shot byte-level confirmation for "literal redaction marker" strikes (display-layer-artifact false-positive detector). Run before retrying any IMPLEMENTATION-BUG strike whose evidence cites a mask-shaped substitution (`***`, `<redacted>`, etc.) at a specific line.
