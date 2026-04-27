# Architect final review template

Used as the `goal` field in `delegate_task` for the Step 7 final
architect review — the merge gate at the end of a ralph run, after
all tasks have `passes: true`. This is the orchestrator's last gate
before handing the user a PR-ready branch.

This is NOT the per-iteration verifier (that's `verifier-goal-template.md`).
The architect reviews the full implementation HOLISTICALLY — across
all tasks, against the original plan/stance, with attention to seams
the per-task verifiers couldn't see.

```
[omh-role:architect] Final review of <domain> ralph run for merge readiness.

## Project root + branch

- Repo: <absolute path>
- Branch: <branch name>
- Tasks completed: <N> (all `passes: true` in ralph-tasks state)
- Iterations: <M>
- Strikes encountered: <K> (categorized: <X test-infra, Y spec-misread,
  Z impl-bug>)

## Required reading

The original design (read first):
- <absolute path to stance.md or design doc>
- <absolute path to PRINCIPLES.md or directives>

The plan that was executed:
- <absolute path to .omh/plans/ralph-plan.md or ralplan-<slug>.md>

The implementation (the full diff range):
- `git log --oneline <base>..<head>` — N implementation commits
- For each commit, `git show <sha>` (the architect should walk the
  diff range, not just check tip-of-tree)

The orchestrator's iteration log (if present):
- <absolute path to .omh/logs/ralph-progress.md or domain equivalent>

Per-task state:
- `.omh/state/ralph-tasks--<instance_id>.json` for verifier verdicts +
  forward-encoded learnings.

## Your job

Review the FULL implementation against the original plan/stance. Per-
task verifiers already graded each task in isolation — your job is
the cross-task / cross-iteration view they could not have. Specifically:

1. **Architectural fidelity.** Did the implementation honor the design
   stance? Are load-bearing positions visible in the code, or only in
   prose? Cite stance sections.

2. **Principle alignment.** Do the principles fire in the mechanics,
   or only in comments? A principle that's documented but not
   enforced by code is a principle-derivation without teeth.

3. **MV slice readiness.** Can the user actually run this tonight?
   Walk the user-facing entry points; trace one realistic invocation
   end-to-end. Anything missing?

4. **Architectural seams.** Anything rough that wasn't explicitly
   deferred in the stance? Is the rough edge documented (RELEASES.yaml,
   issue tracker, or stance "Open questions" section)?

5. **Commit hygiene.** Walk `git log --oneline <range>`. Each commit
   should map to one task; commit messages should cite plan task IDs.
   If P9 commit-absorption happened (sibling files swept via
   `git add -A`), flag it as foldable.

6. **Test affordance gaps.** Per-task verifiers checked the per-task
   tests. Are there integration / cross-task tests the plan named
   that didn't get implemented? Are there integration cases that
   should exist but weren't named?

7. **Discovered tasks.** If any tasks landed mid-run with
   `discovered: true`, were they completed? Are there unsurfaced
   discoveries (gaps the architect sees that the per-task verifiers
   missed)?

8. **Documentation surface.** Did user-facing docs (README, AGENT.md,
   CONTRIBUTING.md, etc.) get updated to reflect the new mechanism?
   A merged feature with stale README is a half-merge.

## Specific things to verify (orchestrator-named)

- <Stance-flagged "must verify at end" items the orchestrator wants
  the architect to confirm>
- <Specific principle-firing checks the orchestrator suspects might
  be prose-only>
- <Cross-task invariants only visible at the end>

## Output expected

Produce a ~1500-3000 word architect review at:
`<absolute path to <orchestrator>-architect-review.md>`

This is a separate artifact from the orchestrator's own iteration
review (`<orchestrator>-review.md`). Both ride; they have different
authors and different jobs.

Structure:

- **Verdict:** APPROVE / APPROVE_WITH_PROVISO / REQUEST_CHANGES
- **One-paragraph summary:** what the run produced + whether it ships.
- **Architectural fidelity:** does code match stance? cite.
- **Principle alignment:** which principles fire in mechanics; which
  are prose-only.
- **MV slice readiness:** end-to-end trace of one realistic invocation;
  what's missing or rough.
- **Architectural seams:** rough edges; for each, foldable / deferred-
  with-issue / blocking.
- **Commit hygiene:** clean / fuzzy with names / blocked.
- **Test affordance gaps:** named gaps + recommended adds.
- **Provisos (if APPROVE_WITH_PROVISO):** numbered list, each with:
  what / why fold-not-block / where to add it.
- **Discovered tasks (if REQUEST_CHANGES):** new tasks the architect
  surfaces, in `discovered: true` shape, ready for the orchestrator to
  add to ralph-tasks state.
- **What this run proved about the plan:** any plan-shape feedback
  worth folding into future ralplan/ralph runs.
```

## The three verdicts

### APPROVE

Seal-of-merge. The branch is ready for PR. No follow-ups required
before merge. The architect-review still ships as a record of the
review, but the PR can land.

When to issue: stance honored, principles fire in mechanics, MV slice
walks cleanly end-to-end, commit hygiene clean, no architectural seams
left rough without explicit deferral.

### APPROVE_WITH_PROVISO

Small foldable items must land before merge — typically 1-3 of:
- A missed README/CONTRIBUTING/AGENT.md update.
- A commit-history rebase to fix P9 absorption.
- A missing test affordance the plan named but didn't enforce.
- A small edge-case fix the verifier missed in isolation.

Each proviso is named explicitly with what / where / why. The
orchestrator folds them as a follow-up commit (or an interactive
rebase for history fixes), then merges.

When NOT to issue: if the proviso would require >1 hour of work or
re-opens a load-bearing decision, that's REQUEST_CHANGES, not a
proviso. Provisos are foldable; if it's not foldable, don't fold it.

### REQUEST_CHANGES

Something cannot ship as-is. The architect surfaces:

- New tasks (in `discovered: true` shape) the orchestrator adds to
  ralph-tasks state.
- A specific failing case that the test suite missed.
- An architectural drift between stance and implementation that
  must be reconciled before merge.

The ralph loop resumes with these tasks; the architect re-reviews on
the next Step 7 cycle.

## Key things to include EVERY time

- **The diff range** — `<base>..<head>` walked commit-by-commit, not
  just tip-of-tree inspection. Cross-task seams are only visible
  across commits.
- **End-to-end MV-slice trace** — pick one realistic user invocation,
  walk it through the code, name what's missing. Per-task verifiers
  can't catch end-to-end gaps.
- **Principle-firing audit** — for each load-bearing principle from
  the stance, is it enforced by code or only documented in prose?
- **Commit hygiene check** — walk `git log --oneline <range>`; flag
  P9 absorptions for foldable rebase.
- **Documentation surface check** — README / AGENT.md / etc. updated
  to match the merged feature. Stale docs = half-merge.

## On verdict calibration

A perfect APPROVE on a multi-task run is rare. APPROVE_WITH_PROVISO
is the common outcome — small things slip past per-task verifiers
that the architect catches at altitude. Don't avoid APPROVE_WITH_PROVISO
to seem decisive; the proviso is what makes the architect's seat
worth occupying.

REQUEST_CHANGES at Step 7 is uncommon but real. If the run drifted
architecturally and per-task verifiers didn't catch it (because each
task in isolation looked fine), this is the gate that catches it.
Don't soften REQUEST_CHANGES into APPROVE_WITH_PROVISO when the
problem is structural — provisos are foldable; structural drift is
not.

## Worked review examples

### APPROVE_WITH_PROVISO (typical)

> Verdict: APPROVE_WITH_PROVISO
>
> The 13-task janus-migration ralph run honored the stance: lineage
> capture lands at `bin/janus-new-being`, `classify()` ships taxonomy-
> as-criterion (P-reuse), the v1→v2 migrations machinery exists at
> `migrations/lib.py:hash_equals_ancestor`. MV slice walks cleanly:
> a fresh `janus-new-being --with-gh` provision writes
> `.janus/version` + `seed-history/v1/MANIFEST` with content hashes,
> verified by `test_provision_writes_v1_lineage_and_gh_config`.
>
> Two foldable provisos:
>
> 1. **Commit-hygiene rebase.** task-11's commit absorbed ~60% of
>    task-12's intended-commit content via `git add -A` (executor
>    swept untracked __init__.py + RELEASES.yaml mid-edit). Tests are
>    green; deliverables correct. Interactive rebase splits the two
>    commits along their `files:` field boundaries before PR.
> 2. **migrations/README.md missing.** The plan named the v2-
>    migrations directory but no README.md was added describing the
>    on-disk layout. Add a 30-line README before merge.

### REQUEST_CHANGES (uncommon, structural)

> Verdict: REQUEST_CHANGES
>
> Per-task verifiers each APPROVE-d their tasks. The cross-task seam
> they couldn't see: task-4 writes the MANIFEST in `<profile>/.janus/
> seed-history/v1/MANIFEST` but task-8's `hash_equals_ancestor()`
> reads from `<profile>/.janus/MANIFEST` (no seed-history/v1/ prefix).
> Both tests pass in isolation (task-4 reads its own write; task-8 has
> a fixture that writes to its own location). Realistic invocation
> fails: `janus-update` provisioned via task-4 cannot be diffed by the
> task-8 helper because the paths don't match.
>
> Discovered task:
>
> ```
> task-14 (discovered: true):
>   title: Reconcile MANIFEST path between janus-new-being and
>          migrations/lib.py:hash_equals_ancestor
>   files: bin/janus-new-being, migrations/lib.py, integration test
>   acceptance: test_provision_then_compare_manifest_e2e passes
>          (provisions a profile, then calls hash_equals_ancestor
>          on the same path; both must agree)
>   priority: 1
> ```
>
> Resume the loop with task-14; re-review at next Step 7.
