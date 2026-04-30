# Triage doc template

Structure for the dated round doc written under
`<host-repo>/docs/triage/YYYY-MM-DD-<descriptor>.md`.

Adapt to the host project's existing docs style. The 2026-04-29
janus rewrite (`witt3rd/janus:docs/triage/2026-04-29-issue-triage.md`)
is the canonical structural example.

---

```markdown
# <Repo> open-issue triage — YYYY-MM-DD

Carved by <author> at <user>'s request via `omh-triage` (v0.1).
Ground-truth anchored to repo HEAD `<commit-ref>`.

## Headline finding

<N filed → X stale, Y recast, Z still-live.>
<What's changed since the last pass.>

## Run shape

- Inventory: <N open at start>
- Roles dispatched: <Maintainer, Skeptic>
- Conflicts surfaced: <count, each named>
- Time wall-clock: <duration>

## Cluster-by-cluster vet

<Per-cluster table: # / status / action.>

## Verdicts

### Closures (<N>)

<Table: issue # / title / Maintainer verdict / pointer-comment summary.>

### Recasts (<N>)

<Table: issue # / title / body-surgery spec.>

### Live (<N>)

<Brief table: issue # / why it earned its slot per Skeptic.>

### Conflicts escalated to user (<N>)

<For each: Maintainer says X for reason A; Skeptic says Y for reason B;
recommended resolution; user's decision.>

## Project board updates

<What moved on the project: target version reassignments, cluster
changes, status updates.>

## Tidying moves applied

<Labels added, cross-links posted, label-creation done.>

## What this pass did not do

<Deferred to next round, with reasoning.>

## Lessons surfaced

<L1, L2, ... — what this round taught about the discipline. Candidates
for folding into PROCESS.md or omh-triage SKILL.md after rounds 2+
confirm them.>

## Methodology note

<What this pass anchored against; what the next pass should learn.>

⚒️ <author>
- YYYY-MM-DD: <round descriptor>
```
