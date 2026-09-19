# OMH Plugin (v2)

The optional Hermes plugin at `plugins/omh/` adds custom tools and lifecycle
hooks that eliminate infrastructure plumbing from skill prose. Skills work
without it; the plugin reduces boilerplate and enables token-efficient role
injection.

Install to `~/.hermes/plugins/omh/`. Requires Python 3.10+ and `pyyaml`.

## Role Prompts

Shared role prompts give subagents precise behavioral instructions. The catalog
is the source of truth — `plugins/omh/references/role-*.md`, enumerated at
runtime by `get_role_catalog()`:

| Role | Purpose | Used By |
|------|---------|---------|
| **Planner** | Task decomposition, sequencing, risk flags | ralplan |
| **Architect** | Structural review, boundary clarity, long-term maintainability | ralplan, ralph (final review) |
| **Critic** | Adversarial challenge, assumption testing, stress testing | ralplan |
| **Executor** | Code implementation, test-first, minimal changes | ralph |
| **Verifier** | Evidence-based completion checking, read-only, pass/fail | ralph |
| **Analyst** | Requirements extraction, hidden constraints, acceptance criteria | deep-interview, autopilot |
| **Security Reviewer** | Vulnerabilities, trust boundaries, injection vectors | autopilot (validation phase) |
| **Test Engineer** | Test strategy, coverage, edge cases, flaky test hardening | autopilot (QA phase) |
| **Code Reviewer** | Diff review, conventions, holistic quality | autopilot (validation phase) |
| **Debugger** | Root cause analysis, hypothesis testing, minimal targeted fixes | ralph (error diagnosis) |

Source files: `plugins/omh/references/role-{name}.md`.

## How Role Injection Works

With the v2 plugin installed, skills use `[omh-role:NAME]` markers in the
`delegate_task` goal string instead of embedding role prompt text inline:

```python
delegate_task(
    goal="[omh-role:executor] Implement the following task:\n\n<task>...",
    context="<project context only>"
)
```

The Hermes `pre_llm_call` hook fires at the start of each subagent session,
detects the marker in `user_message` (which equals the `goal` string), loads
the matching role file from `plugins/omh/references/role-{name}.md`, and
injects it into the subagent's system prompt via `{"context": ...}`. The role
text never passes through the parent agent's context window.

A `pre_tool_call` hook validates `[omh-role:NAME]` markers before the subagent
starts, warning immediately on unknown role names (fail-fast for typos).

**Fallback:** `omh_state(action="load_role", role="NAME")` returns the role
prompt as a string for skills that need it explicitly.

**Debug mode:** Set `OMH_DEBUG=1` (env var) or `debug: true` in `config.yaml`
to see injection events:

```
[OMH DEBUG] pre_tool_call: delegate_task with role 'executor' detected
[OMH DEBUG] pre_llm_call: injecting role 'executor' into subagent system prompt
```

## Components

| Component | What It Does | Status |
|-----------|-------------|--------|
| `omh_state` tool (13 actions) | Atomic read/write/check/cancel for `.omh/` state files; `load_role` action for explicit role loading | Shipped |
| `omh_gather_evidence` tool | Runs build/test/lint commands from an allowlist, captures + truncates output | Shipped |
| `pre_llm_call` hook | Detects `[omh-role:NAME]` in subagent `user_message`; injects matching role prompt into system context | Shipped |
| `pre_tool_call` hook | Validates `[omh-role:NAME]` markers in `delegate_task` goals before subagents start; warns on unknown roles | Shipped |
| `on_session_end` hook | Writes `_interrupted_at` to active mode state on unexpected exit | Shipped |
| Model tier routing | Maps roles to Haiku/Sonnet/Opus via config | Roadmap |

The key architectural insight for role injection: `delegate_task` passes
`goal` as `user_message` to the subagent's `run_conversation()`. The
`pre_llm_call` hook receives this as `user_message` on `is_first_turn=True`,
making it the natural injection point — no new Hermes primitives required.

## v1 vs v2 Skill Prose

Skills express intent instead of mechanism. Compare delegation between the
two versions:

```markdown
# v1 skill prose (verbose — role text inlined, state loaded manually)
Load the executor role from ~/.hermes/skills/omh-ralplan/references/role-executor.md
and pass it in the context field of delegate_task alongside the task definition...

# v2 skill prose (concise — hook handles injection)
delegate_task(goal="[omh-role:executor] Implement: {task}", context="{project context}")
```

## Development

```bash
pip install -e ".[dev]"
python -m pytest plugins/omh/tests/
```
