# Verifier goal template

Used as the `goal` field in `delegate_task` for a verifier subagent
grading one completed task. Verifiers run in parallel — batch them via
`delegate_task(tasks=[...])` after `omh_gather_evidence` produces real
test output.

The verifier MUST grade against the plan's acceptance criteria, not
the executor's interpretation of them. The orchestrator runs evidence
(P6); the verifier reads it. Without this, you have two layers of
executor self-reporting.

```
[omh-role:verifier] Verify Task <N> — <one-line task title>

## Project root + branch

- Repo: <absolute path>
- Branch: <branch name>
- Commit under review: <sha from executor's report>

## The task as specified

<Full task title + description from the ralph plan, verbatim. Same
text the executor saw. If the executor saw a paraphrase and you grade
against the original, you'll catch spec-misread; if you grade against
the executor's paraphrase, you won't.>

## Acceptance criteria (from the plan, verbatim)

<Verbatim from the ralph plan. If the plan named exact test functions,
the verifier checks those exact tests exist and pass.>

## Evidence (from `omh_gather_evidence`, run by the orchestrator)

The orchestrator ran the project's actual test/build/lint commands
BEFORE dispatching you. Real output:

```
<paste the structured evidence object from omh_gather_evidence:
results, all_pass, summary>
```

Do NOT re-run evidence yourself. The orchestrator-runs-evidence pattern
exists so verifiers see ground truth, not executor claims. If you
think evidence is incomplete (e.g., wrong test scope, missing
project), say so in your verdict — don't paper over by re-running.

## Files to inspect

The executor reported touching:
- <absolute path>
- <absolute path>

Read each. Check that:
- The implementation matches the acceptance criteria (not the
  executor's prose interpretation).
- The tests authored are the tests the plan named.
- Sibling-owned files (listed below) were NOT modified.
- Commit boundary is clean (no sibling files swept in via `git add -A`).

## Sibling-owned files (must be untouched)

- <absolute path> — owned by Task <M>
- <absolute path> — owned by Task <K>

If the commit modified any of these, that's a P3 violation (parallel
boundary breach) AND/OR a P9 violation (commit-hygiene). Flag it.

## Specific load-bearing checks (beyond "tests pass")

These are the things the orchestrator wants explicitly verified —
checks that go past the test suite into reading the code:

- <Named check 1; e.g., "verify the mismatched-flag check happens
  BEFORE any filesystem writes — if not, partial-flag invocations
  corrupt state">
- <Named check 2; e.g., "verify the function uses
  `bin/_lineage.classify()` rather than reimplementing the
  taxonomy">
- <Named check N>

## Strike categorization (if returning REQUEST_CHANGES)

If the implementation does not meet acceptance criteria, categorize
the strike for the orchestrator:

1. **TEST-INFRA** — the test itself is buggy (fixture race, hash
   collision in tmpdir naming, runner config issue). Implementation
   may be correct.
2. **SPEC-MISREAD** — the executor implemented something different
   from the acceptance criteria. Cite the specific drift.
3. **IMPLEMENTATION-BUG** — the executor implemented the right thing
   but it has a real defect. Name the failing case (input/scenario).

The 3-strike circuit breaker fires on the same `(category, error_key)`
repeating. Tagging correctly prevents test-infra strikes from masking
real bugs.

## Output expected back to the orchestrator

A verdict with:

- **Verdict:** APPROVE / REQUEST_CHANGES
- **Acceptance criteria compliance:** for each criterion, PASS / FAIL
  with a one-line citation (test name + result, or file:line + observed
  behavior).
- **Load-bearing checks:** for each, PASS / FAIL with citation.
- **Sibling boundary:** CLEAN / VIOLATED (name the violations).
- **Commit hygiene:** CLEAN / FUZZY (name absorbed-but-out-of-scope
  files).
- **Strike category (if REQUEST_CHANGES):** TEST-INFRA / SPEC-MISREAD
  / IMPLEMENTATION-BUG.
- **Error key (if REQUEST_CHANGES):** short stable handle the
  orchestrator can use to detect repetition (e.g.,
  `hash-collision-in-tmpdir-naming`, `mismatched-flag-write-before-check`).
- **Specific feedback:** what the executor needs to do differently on
  retry. Be concrete; vague feedback produces vague retries.
```

## Key things to include EVERY time

- **The acceptance criteria verbatim from the plan,** not the
  executor's report. Verifier's job is to grade against the spec.
- **Real evidence output** from `omh_gather_evidence`. Without it,
  verifier reads only the executor's claims.
- **Sibling-owned file list.** Without it, the verifier can't catch
  P3 (parallel boundary) violations.
- **Specific load-bearing checks.** "Tests pass" is necessary but not
  sufficient — the orchestrator names the deeper checks.
- **Strike-category instruction.** Without categorization, the
  3-strike breaker fires wrong.

## Variations

- **Re-verify after retry:** add at top:
  ```
  ## Prior verdict: REQUEST_CHANGES — <category>

  Prior feedback: <verbatim>. Confirm whether the retry addresses
  this specific feedback. If yes → APPROVE. If partial → still
  REQUEST_CHANGES with what remains.
  ```
- **Solo task (no parallel siblings):** drop the "Sibling-owned" and
  "Sibling boundary" sections. KEEP the commit-hygiene check — the
  working tree may have untracked files from prior orchestrator work.
- **Test-infra-suspected verifier:** the orchestrator may already
  suspect a test-infra issue. Tell the verifier:
  ```
  ## Test-infra hypothesis

  The orchestrator suspects this failure may be test-infra rather
  than implementation. Specifically: <hypothesis>. Confirm or refute
  before grading the implementation.
  ```

## On the verifier's altitude

The verifier is NOT an executor. Do not try to "fix" what you find;
report it. The orchestrator decides retry-vs-advance based on your
verdict + strike category. A verifier who patches things they find
wrong has collapsed the loop's separation-of-concerns and produces
unreviewed code.

## Worked verdict example (APPROVE shape)

```
**Verdict:** APPROVE

**Acceptance criteria compliance:**
- `test_provision_writes_v1_lineage` — PASS (test_janus_new_being_lineage.py:42)
- MANIFEST contains content hashes for SOUL.md and template tree —
  PASS (verified at .janus/seed-history/v1/MANIFEST:1-12)
- gh_config written when --with-gh — PASS (test_janus_new_being_lineage.py:78)

**Load-bearing checks:**
- Mismatched-flag check happens before fs writes — PASS
  (bin/janus-new-being:142, write at :158)
- Reuses bin/_lineage.classify() — PASS (bin/janus-new-being:131)

**Sibling boundary:** CLEAN
**Commit hygiene:** CLEAN

No follow-ups.
```

## Worked verdict example (REQUEST_CHANGES shape)

```
**Verdict:** REQUEST_CHANGES

**Acceptance criteria compliance:**
- `test_mismatched_flags_no_partial_writes` — FAIL
  (test_janus_new_being_lineage.py:104, AssertionError: profile dir
  contains partial state after mismatched-flag invocation)

**Strike category:** IMPLEMENTATION-BUG
**Error key:** mismatched-flag-write-before-check

**Specific feedback:**
The mismatched-flag check at bin/janus-new-being:142 happens AFTER
the first filesystem write at :128 (the SOUL.md template render).
Move the check to before any write — the acceptance criterion
requires partial-flag invocations to leave the filesystem
unchanged. Test at :104 reproduces.

**Sibling boundary:** CLEAN
**Commit hygiene:** CLEAN
```
