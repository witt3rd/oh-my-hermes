# Deep Interview Spec: OMH Hermes Plugin (v1)

## Metadata
- Interview ID: di-plugin-20260407
- Rounds: 4
- Final Ambiguity Score: 17.5%
- Type: brownfield
- Generated: 2026-04-07
- Threshold: 20%
- Status: PASSED

## Clarity Breakdown

| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.87 | 0.35 | 0.305 |
| Constraint Clarity | 0.80 | 0.25 | 0.200 |
| Success Criteria | 0.80 | 0.25 | 0.200 |
| Context Clarity | 0.80 | 0.15 | 0.120 |
| **Total Clarity** | | | **0.825** |
| **Ambiguity** | | | **17.5%** |

## Goal

Build a Hermes plugin at `plugin/` in this repo that registers 2 tools
(`omh_state`, `omh_gather_evidence`) and 2 hooks (`pre_llm_call`,
`on_session_end`), eliminating state management and evidence gathering
boilerplate from OMH skills. v2 skills require the plugin; v1 skills
archived in `skills/legacy/`.

## Constraints

- Plugin source lives in `plugin/` within this repo (alongside `skills/` and `docs/`)
- 2 tools only: `omh_state` + `omh_gather_evidence` — `omh_delegate` descoped (confirmed `delegate_task` is an agent-loop tool inaccessible from plugin dispatch path)
- v2 skills **require** the plugin — no graceful fallback, no dual-version maintenance
- v1 skills archived to `skills/legacy/` for users who don't install the plugin
- Target: ~350 lines of Python
- State in `.omh/state/`, config in `plugin/config.yaml` (installed to `~/.hermes/plugins/omh/config.yaml`)
- `omh_gather_evidence` commands must match a configurable allowlist (safety rail)

## Non-Goals

- `omh_delegate` (role-aware delegation wrapper) — blocked by hermes-agent architecture; revisit in v2
- Model tier routing — `delegate_task` has no per-call model param
- `/omh` slash commands — useful but not required for v1
- Refactoring all 4 skills — v1 targets omh-ralph as the reference refactor; others follow

## Acceptance Criteria

- [ ] `hermes` starts without errors and shows `omh` in plugin list
- [ ] `omh_state(action="write", mode="ralph", data={...})` creates `.omh/state/ralph-state.json` with `_meta` envelope
- [ ] `omh_state(action="read", mode="ralph")` returns data without `_meta`, plus `exists`, `stale`, `age_seconds`
- [ ] `omh_state(action="cancel", mode="ralph")` sets `cancel_requested: true` in state file
- [ ] `omh_state(action="cancel_check", mode="ralph")` returns `{cancelled: true}` within 30s TTL
- [ ] `omh_gather_evidence(commands=["npm test"])` runs and returns structured results
- [ ] `omh_gather_evidence(commands=["rm -rf /"])` returns error (not in allowlist)
- [ ] `pre_llm_call` injects full mode context on first turn when OMH modes active
- [ ] `pre_llm_call` injects brief reminder on subsequent turns
- [ ] `on_session_end` writes `_interrupted_at` to active state files
- [ ] `python -m pytest plugin/tests/ -v` passes
- [ ] omh-ralph SKILL.md updated to use `omh_state` and `omh_gather_evidence`; skill is ~25% shorter
- [ ] v1 skills moved to `skills/legacy/` with a README note

## Assumptions Exposed & Resolved

| Assumption | Challenge | Resolution |
|------------|-----------|------------|
| omh_delegate is buildable | Does delegate_task work from plugin tools? | Confirmed NO — agent-loop tool, inaccessible via registry.dispatch. Descoped. |
| Plugin lives at ~/.hermes/plugins/omh/ | Does source go in this repo or outside? | Source in `plugin/` in this repo; installed/symlinked to hermes plugins dir. |
| v2 skills need fallback mode | Should skills work without plugin? | No fallback — v2 skills require plugin. v1 archived in skills/legacy/. |

## Technical Context

**Codebase:** 4 existing skills (omh-ralph, omh-autopilot, omh-ralplan, omh-deep-interview),
all markdown-only. No Python yet. State lives in `.omh/`, plans in `.omh/plans/`,
specs in `.omh/specs/`.

**Hermes plugin API (confirmed):**
- `ctx.register_tool(name, schema, handler)` — registers tool
- `ctx.register_hook(event_name, callback)` — subscribes to lifecycle events
- `pre_llm_call` returns `{"context": "..."}` to inject into user message (confirmed wired in run_agent.py)
- Plugin tools dispatched via `registry.dispatch()` — no agent reference available

**hermes-agent constraint (confirmed from source):**
- `model_tools.py`: `_AGENT_LOOP_TOOLS = {"todo", "memory", "session_search", "delegate_task"}`
- `delegate_task` intercepted before `registry.dispatch`; requires `parent_agent` kwarg
- `handle_function_call()` has no `parent_agent` param — plugin tools cannot call delegate_task

**Existing consensus plan:** `.omh/plans/ralplan-plugin-consensus.md` (updated with confirmed findings)

## Ontology (Key Entities)

| Entity | Type | Fields | Relationships |
|--------|------|--------|---------------|
| Plugin | core domain | name=omh, tools, hooks, config_path, source_path=plugin/ | provides Tools, provides Hooks, installed into hermes-agent |
| Tool | core domain | name, schema, handler, allowlist (evidence only) | registered by Plugin, called by Skills |
| Hook | core domain | name, timing, return_contract | registered by Plugin, called by hermes-agent |
| Skill | core domain | name, SKILL.md, version (v1/v2) | v2 Skills require Plugin; v1 Skills archived to skills/legacy/ |
| hermes-agent | external system | plugins_dir, registry, agent_loop, delegate_task | loads Plugin; Skills run inside hermes-agent |

## Ontology Convergence

| Round | Entity Count | New | Changed | Stable | Stability Ratio |
|-------|-------------|-----|---------|--------|----------------|
| 1 | 5 | 5 | - | - | N/A |
| 2 | 5 | 0 | 0 | 5 | 100% |
| 3 | 5 | 0 | 0 | 5 | 100% |
| 4 | 5 | 0 | 0 | 5 | 100% |

Domain model converged at Round 2 and held through all subsequent rounds.

## Interview Transcript

<details>
<summary>Full Q&A (4 rounds)</summary>

### Round 1
**Q:** What is the status of the hermes-agent PR required for omh_delegate (parent_agent passthrough)?
**A:** User asked "What is omh_delegate? Can we avoid it?" — revealed unfamiliarity with delegation tool
**Ambiguity:** ~30% (Goal: 0.70, Constraints: 0.55, Criteria: 0.65, Context: 0.75)

### Round 2
**Q:** Is omh_delegate worth building given the PR dependency? (with explanation of what it does)
**A:** User asked for source evidence before deciding → led to source analysis of model_tools.py and developer docs
**Ambiguity:** ~27% (Goal: 0.82, Constraints: 0.65, Criteria: 0.65, Context: 0.80)

### Round 3
**Q:** Where should the plugin source code live?
**A:** "In this repo under plugin/"
**Ambiguity:** ~23% (Goal: 0.85, Constraints: 0.75, Criteria: 0.65, Context: 0.80)

### Round 4
**Q:** Should v2 skills require the plugin or fall back gracefully?
**A:** "Require the plugin (Recommended)"
**Ambiguity:** 17.5% ✅ (Goal: 0.87, Constraints: 0.80, Criteria: 0.80, Context: 0.80)

</details>
