# omh_delegate — HANDOFF

**You are picking up `omh_delegate` work mid-stream. Read this file. It is
the only thing you need to recontextualize.**

---

## Where we are right now

- **Two branches in flight, both pushed:**
  - `forge/omh-delegate-hardening` — convention work + Bug 2 fix +
    this entire ralplan debate record.
  - `forge/omh-delegate-v0` — the wrapper itself (~340 LOC, 7 tests,
    doc page). 171/171 tests passing. **Branched off `forge/omh-delegate-hardening`.**
  - Neither is merged to `main` yet. Land them in that order when you're ready.

- **Design status: CONSENSUS REACHED** via 2-round Planner/Architect/Critic
  debate (ralplan applied to itself). Both reviewers APPROVED Round 2.
  The reasoning is preserved in this directory — see "Reference shelf"
  below — but you do not need to re-read it to advance the work.

- **Code status: v0 SHIPPED.** Pure subagent-persists wrapper around
  `delegate_task`. No rescue branch. Fully tested in isolation against
  a mock subagent.

- **What's missing: real-world data.** v0 has never been called against
  a real subagent. The next step is a measurement that gates the v1
  design.

---

## Your single next task: dogfood + measure (the C0 microbenchmark)

The whole reason v0 is small is so we measure how often subagents obey
the brutal-prose contract *before* committing to building a rescue
branch. That measurement is called **C0**.

### Step 1 — Migrate one ralplan phase to use omh_delegate

Pick the simplest target: `plugins/omh/skills/omh-ralplan/SKILL.md`,
the **planner role only** of round 1. Edit the SKILL prose so that
instead of saying "use `delegate_task` with goal/context/toolsets", it
says "use `omh_delegate(role='planner', mode='ralplan',
phase='round1-planner', round=1, goal=..., context=..., toolsets=...)`".

The wrapper handles path computation, breadcrumbs, and verification.
The skill no longer needs to spell out `<<<EXPECTED_OUTPUT_PATH>>>`
contracts in prose — `omh_delegate` injects that itself.

### Step 2 — Run ralplan against ≥3 toy specs

Pick three small problems (a refactor decision, a small feature design,
a tool-choice debate — whatever's around). Run `omh-ralplan` against
each. Each run dispatches multiple subagents (planner, architect,
critic, possibly multiple rounds). Target **≥20 total dispatches**
across the runs.

### Step 3 — Tally the results

Each dispatch leaves two breadcrumb files under
`.omh/state/dispatched/`:
- `{id}.dispatched.json` — written before dispatch
- `{id}.completed.json` — written after; contains `file_present`,
  `contract_satisfied`, `recovered_by_wrapper`, `raw_return`, `error`.

Iterate over the completed breadcrumbs. For each:
- Aggregate: count `file_present == True` rate.
- **Per-role / per-failure-mode breakdown** (Critic W-R2-1): a 92%
  aggregate that hides one role at 60% is a different story than 92%
  evenly. Bin by `role` (planner / architect / critic) and, for
  failures, classify the `raw_return` by hand into:
  `{drift, double-write, refusal, paraphrase, acknowledgment, other}`.

Write the tally to a new file:
**`.omh/research/ralplan-omh-delegate/c0-contract-obedience.md`**

Include sample size, methodology (what counts as "obeyed"), aggregate
rate, per-role rates, failure-mode histogram, and 3–5 representative
raw_return excerpts.

### Step 4 — Apply the pre-locked threshold rule

Thresholds were locked *before* measurement to prevent motivated
reasoning:

| Aggregate `file_present` rate | Decision |
|------------------------------|----------|
| **≥95%** across ≥20 dispatches | Skip the rescue branch entirely. v1 = v1.A only. The wrapper stays pure subagent-persists permanently. (CI-1 option a wins.) |
| **80–95%** | v1 adds the rescue branch in **loud-only** form: sentinel-marker required (`<<<RESULT>>>...<<<END_RESULT>>>`), `ok` becomes `"degraded"` (string), file gets `<!-- CONTRACT VIOLATED -->` header. (v1.B.) |
| **<80%** | Stop. The rescue branch is the wrong fix; the contract prose is the right fix. Rewrite the contract block in `omh_delegate.py` and re-measure. |

Write your decision and reasoning to a new file:
**`.omh/research/ralplan-omh-delegate/v1-decision.md`**

### Step 5 — Execute v1

The full v1 task list is in `round2-planner.md` §4. Headline:

**v1.A — always (regardless of C0):**
- Extract `omh_io.py` from inlined helpers (atomic_write_text,
  resolve_under_project, discover_project_root). Refactor `omh_state`
  and `evidence_tool` to use them.
- Add batch dispatch (`tasks=[...]`) with per-task breadcrumbs.
- Register as a Hermes tool (`tools/delegate_tool.py` shim) so skills
  can call it as a tool, not just a Python import.
- Migrate remaining ralplan phases (R1+R2 architect/critic, post-R2
  reconciliation), `omh-ralph`, `omh-autopilot`. Audit
  `omh-deep-interview`.
- E1 expanded test suite (≥10 more unit tests).
- Update `docs/omh-delegate.md` and write a migration guide.

**v1.B — only if C0 said 80–95%:**
- Sentinel-marker rescue branch (per round2-planner.md §4 v1.B).
- Reactivate OQ1 investigation (`delegate_task`'s actual return shape,
  partially answered: `{"results": [{"summary": <subagent-string>,
  ...}], ...}` — see `omh_delegate.py` and the v0 commit).

**v1.C — only if C0 said ≥95%:**
- Nothing. The rescue-branch design lives in the historical record but
  never ships.

---

## Quick orientation if you've never seen this code

- **The wrapper:** `plugins/omh/omh_delegate.py`. Read the docstring at
  the top — it's the design summary in 30 lines.
- **The tests:** `plugins/omh/tests/test_omh_delegate.py`. Read the
  happy-path test first (it's the first one — that's deliberate, M6).
- **The public-facing doc:** `docs/omh-delegate.md`. Includes the
  v0/v1/v2 roadmap and the "Known limitations" list with explicit
  deferrals.
- **Run the tests:** `cd /home/dt/src/witt3rd/oh-my-hermes && uv run
  --with pytest python -m pytest plugins/omh/tests/ -q`. Should print
  `171 passed`.

---

## Decisions already locked (do NOT re-litigate without strong cause)

These are settled. If you find yourself wanting to relitigate one,
there is a high probability that either (a) the original argument
applies and you should re-read the relevant artifact, or (b) you have
discovered something genuinely new — in which case write a new
research note explaining what changed.

- **No rescue branch in v0.** Loud failure beats silent rescue.
  Re-opening this requires C0 data showing <95% obedience.
- **Append-only breadcrumbs.** Never RMW a breadcrumb. Completion
  data goes in a sibling file. Eliminates a class of races.
- **Three-boolean status** (`file_present` / `contract_satisfied` /
  `recovered_by_wrapper`). Always present. Even when v0 makes two of
  them trivially constant. Forward-compat with v1.B.
- **`ok_strict = (ok is True)`.** Ships in v0 even though identical
  to `ok` today. Future `ok="degraded"` would silently pass naïve
  truthy checks; `ok_strict` is the migration-safe accessor.
- **Walk-up `.omh/` discovery** for project root (mirrors `git`).
  Hermes does not `chdir` during dispatch (verified by source grep —
  this was the load-bearing OQ-D).
- **`goal_sha256` + `goal_bytes` only** in breadcrumbs — no preview.
  Avoids leaking secrets that bleed into goal text.
- **Pre-locked C0 thresholds** (≥95% / 80–95% / <80%). Locked before
  measurement to prevent motivated reasoning. Don't change them after
  seeing the data.

---

## Approval conditions still owed

- **AC-1 (already shipped in v0):** `ok_strict` field. ✓
- **AC-2 (already shipped in v0):** Cross-fs `os.replace` deferral
  documented in `docs/omh-delegate.md` §"Known limitations". ✓

If you ship v1.B, AC-1 becomes *active* — callers must use
`ok_strict` instead of `ok` for hard pass/fail checks. Update the
migration guide accordingly.

---

## Reference shelf (read only if you need to)

If you need to challenge a settled decision or understand *why*
something is the way it is, the full debate record is here:

- `00-spec.md` — original spec, including the failure modes (FM1, FM2)
  the wrapper exists to address.
- `01-project-context.md` — context bundle for fresh subagents.
- `round1-planner.md` — original maximalist plan (~22 tasks, 4 tracks).
  **Superseded.** Read only for historical context.
- `round1-architect.md` — REQUEST_CHANGES with C1–C5 and M1–M7.
- `round1-critic.md` — REQUEST_CHANGES aggressive: CI-1 (drop the
  rescue), CI-2 (measure first), CI-3 (bootstrap is evidence prose
  works), CI-4 (no v0 exists), CI-5 (classifier undecidable),
  W1–W6 (concurrency, secrets, silent degrade, root discovery,
  operability, cross-fs).
- `round2-planner.md` — **the ship-ready plan**. §3 = v0 (already
  built). §4 = v1. §5 = v2. §6 = updated risks/OQs.
- `round2-architect.md` — APPROVE with notes (N1–N4).
- `round2-critic.md` — APPROVE with conditions (AC-1, AC-2) and
  warnings (W-R2-1 through W-R2-4).
- `CONSENSUS.md` — verdict trail and the approval conditions in one
  place.

You don't need to read any of these to advance the work. They are
here so that *if* a question comes up — "why did we decide X?" — the
answer is a `grep` away.

---

## TL;DR of TL;DRs

> **Migrate one ralplan phase to call `omh_delegate`. Run it against
> 3 toy specs (≥20 total dispatches). Tally the results into
> `c0-contract-obedience.md`. Apply the threshold rule. Write the
> decision into `v1-decision.md`. Then build v1.A (always) plus
> v1.B if and only if the threshold says so.**

The wrapper exists. The tests pass. The plan is settled. What's
missing is the data.

— Forge ⚒️, 2026-04-20 (handoff written for future self)
