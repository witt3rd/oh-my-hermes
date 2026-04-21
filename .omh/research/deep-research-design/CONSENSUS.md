# Consensus Plan — omh-deep-research

**Status:** APPROVED Round 2 (both reviewers).
**Date:** 2026-04-21
**Process:** omh-ralplan, two rounds.

## Verdict trail

| Round | Phase     | Verdict           | File                                                   |
|-------|-----------|-------------------|--------------------------------------------------------|
| R1    | planner   | strawman          | (preserved in ~/src/witt3rd/oh-my-hermes-state/)       |
| R1    | architect | REQUEST_CHANGES   | (preserved in ~/src/witt3rd/oh-my-hermes-state/)       |
| R1    | critic    | REQUEST_CHANGES   | (preserved in ~/src/witt3rd/oh-my-hermes-state/)       |
| R2    | planner   | revised plan      | `planner-r2-20260421T043258Z.md`                       |
| R2    | architect | **APPROVE**       | `architect-r2-20260421T043657Z.md`                     |
| R2    | critic    | **APPROVE** (no new critical issues) | `critic-r2-20260421T043657Z.md`     |

Both reviewers explicitly verified all Round-1 conditions were addressed. Critic
ran an adversarial pass for new issues introduced by R2 changes and found none
of critical severity ("NO NEW CRITICAL ISSUES" — verbatim).

## The plan

The ship-ready plan lives in `planner-r2-20260421T043258Z.md`. Twelve tasks
(T1–T12, T9b dropped). Five-phase decomposition. Three new roles
(`research-researcher`, `research-synthesist`, `research-verifier`). Boundary
rule: parent owns filesystem, parent inlines findings into delegations,
subagents return text only. 3-strike retry on verify retained, exercised by
T12 (both arms: retry-then-pass and 3-strike-then-blocked).

## Round 1 → Round 2 resolution map

See the changelog at the bottom of `planner-r2-...md` for the full mapping;
both reviewers confirmed it matches the actual task bodies.

## Cosmetic nits raised by Critic R2 (non-blocking)

Critic flagged a small number of cosmetic items (slug rule wording, log
format consistency) — none gate approval. Capture them when implementing
T1–T12 if you want; they're not in the consensus contract.

## Implementation entry point

When you (future Forge or Donald) want to build this skill: read
`planner-r2-...md` task by task. T1 is roles, T2-T3 are skill prose,
T4-T9 are phase implementations, T10-T12 are tests. Each task has
`acceptance` and `verify_cmd` fields. Build in order.

⚒️ Forge — 2026-04-21
