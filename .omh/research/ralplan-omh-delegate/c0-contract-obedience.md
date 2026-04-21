# C0 — Contract Obedience Microbenchmark (initial sample)

**Date:** 2026-04-21
**Sample size:** 3 dispatches (omh-deep-research Round 2)
**Subagent model:** claude-opus-4.7
**Wrapper version:** omh_delegate v0 (pure subagent-persists, no rescue)

## Methodology

Each Round 2 dispatch (Planner, Architect, Critic) routed through omh_delegate.
Wrapper computed expected_output_path, injected the brutal-prose
`<<<EXPECTED_OUTPUT_PATH>>>` contract appended to the goal, dispatched, and
verified `Path(expected_output_path).is_file()` after return.

A dispatch counts as **contract-obedient** iff `file_present == True` AND the
subagent's `summary` (return value) was exactly the path string with no
paraphrase or wrapping.

## Results

| # | Role      | id (truncated)                                        | file_present | contract_satisfied | bytes  | summary == path? |
|---|-----------|-------------------------------------------------------|--------------|--------------------|--------|------------------|
| 1 | planner   | deep-research-design-planner-r2-...-7bfc              | ✓            | ✓                  | 26,376 | ✓                |
| 2 | architect | deep-research-design-architect-r2-...-ae55            | ✓            | ✓                  | 7,951  | ✓                |
| 3 | critic    | deep-research-design-critic-r2-...-d05f               | ✓            | ✓                  | 9,259  | ✓                |

**Aggregate:** 3/3 = 100% file_present. 3/3 = 100% summary-equals-path.

## Sample size caveat

n=3 is far below the C0 threshold-decision sample size of ≥20. This sample
is **not sufficient** to apply the pre-locked threshold rule. It is consistent
with the ≥95% bucket but doesn't establish it.

## Per-role observations

All three roles obeyed the contract exactly. Each subagent:
- Read the goal+context files in full first (deliberate read-then-write).
- Wrote exactly one write_file call to exactly the expected path.
- Returned only the path string as the final summary.

No paraphrase, no double-write, no acknowledgment-instead-of-path, no drift.

## Failure-mode histogram

Empty (no failures in this sample). Categories pre-defined for future tallies:
`{drift, double-write, refusal, paraphrase, acknowledgment, other}`.

## Bugs surfaced by dogfooding (NOT in C0 contract obedience — these are
infrastructure issues found WHILE running the benchmark)

### Bug D1 (CRITICAL) — `omh_delegate` import target doesn't exist

`omh_delegate.py` line 207:
    from tools.delegate_tool import delegate_task as delegate_fn

There is no `tools/` package in the repo. v0 cannot dispatch in-process when
called as a Python function. This was deferred to v1 ("Register as a Hermes
tool") in `round2-planner.md` §4 v1.A, but the v0 docstring claims a working
`delegate_fn`-injection-or-default and the unit tests exercise only the
injection path — masking the import failure.

**Resolution path:** the wrapper conceptually splits into two halves
(`prepare()` returns dispatch metadata + augmented goal; `finalize()` writes
the completion breadcrumb after the agent dispatches via the real Hermes tool).
Manual driver at `/tmp/omh_delegate_manual.py` exercised this split during
Round 2 and worked cleanly. **v1 should formalize prepare/finalize as the
public API** and demote the all-in-one `omh_delegate(...)` call to "Python
callers only" status, or remove it.

### Bug D2 (minor) — README only describes the all-in-one form

`docs/omh-delegate.md` describes `omh_delegate(...)` as the public API with
no mention of the prepare/finalize split. Doc needs to track the v1 reality.

### Bug D3 (observation, not bug) — opus-4.7 obedience is high

Three-for-three contract obedience on opus-4.7 with this contract template
suggests the v1.B rescue branch may genuinely be unnecessary if the production
fleet is opus-4.7+. Need to retest on weaker models before locking the
≥95% conclusion.

## Recommendations

1. Land Bug D1 as a v1 issue. The prepare/finalize split is the right shape.
2. Run ≥17 more dispatches (target n=20+) before applying threshold rule.
3. Include at least one weaker-model dispatch in the next batch (sonnet,
   haiku) — homogeneous opus-4.7 sample isn't representative.
4. Add at least one adversarial test: a goal whose natural completion shape
   (e.g., "answer this question") strongly conflicts with the path-only
   return contract.

⚒️ Forge — 2026-04-21
