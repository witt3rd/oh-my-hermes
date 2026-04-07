# OMH Hermes Plugin — Implementation Plan

Generated: 2026-04-07
Based on: plugin-proposal.md (v2), omc-plugin-infrastructure.md, omc-tools-analysis.md,
hermes-agent plugins.py, registry.py, delegate_tool.py, AGENTS.md

---

## Summary

Build the OMH plugin as a real Python plugin at `~/.hermes/plugins/omh/` that
registers 8 MCP-style tools and 3 lifecycle hooks via the Hermes PluginContext
API. The plugin provides: (1) session-scoped state management with atomic writes
and metadata envelopes, (2) role-aware delegation that auto-loads role prompts
and routes to model tiers, (3) evidence gathering that runs build/test/lint and
returns structured results, (4) a cancel-check mechanism, and (5) session hooks
for mode awareness and clean interruption handling. The plugin targets ~850 lines
of Python for the core, uses the existing `delegate_task` tool internally, stores
state in `.omh/state/`, and reads configuration from
`~/.hermes/plugins/omh/config.yaml`. All tools return JSON strings per the
Hermes handler contract. The plugin requires no changes to hermes-agent itself.

---

## Architecture

```
~/.hermes/plugins/omh/
├── plugin.yaml           # Manifest (name, version, provides_tools, provides_hooks)
├── __init__.py           # register(ctx: PluginContext) — wires everything
├── config.yaml           # Role mappings, model tier config, role_prompts_dir
├── omh_config.py         # Config loader (reads config.yaml, merges defaults)
├── omh_state.py          # State engine (atomic write, meta envelope, session scoping)
├── tools/
│   ├── __init__.py
│   ├── state_tools.py    # omh_state_read/write/clear/check/list (5 tools)
│   ├── delegate_tool.py  # omh_delegate (1 tool)
│   ├── evidence_tool.py  # omh_gather_evidence (1 tool)
│   └── cancel_tool.py    # omh_cancel_check (1 tool)
└── hooks/
    ├── __init__.py
    ├── session_hooks.py  # on_session_start, on_session_end
    └── llm_hooks.py      # pre_llm_call (mode awareness injection)
```

### Key Hermes API Surface Used

From `hermes_cli/plugins.py`:
- `PluginContext.register_tool(name, toolset, schema, handler, ...)` — delegates to `tools.registry.registry.register()`
- `PluginContext.register_hook(hook_name, callback)` — valid hooks: `pre_tool_call`, `post_tool_call`, `pre_llm_call`, `post_llm_call`, `on_session_start`, `on_session_end`

From `tools/registry.py`:
- Handlers must return `str` (JSON-encoded)
- Handlers receive `(args: dict, **kwargs)` where kwargs may include `task_id`, `parent_agent`
- Schema format: `{"name": str, "description": str, "parameters": {"type": "object", "properties": {...}, "required": [...]}}`

From `tools/delegate_tool.py`:
- `delegate_task(goal, context, toolsets, tasks, max_iterations, acp_command, acp_args, parent_agent)` — the underlying function
- Can be called directly from Python (not just via tool dispatch)

---

## Tasks

### Task 1: Plugin Scaffold

**Description:** Create the directory structure, `plugin.yaml` manifest, and
`__init__.py` with the `register(ctx)` entry point. The register function
should import and call registration functions from each tool module and hook
module. Include `config.yaml` with sensible defaults.

**Files:**
- `~/.hermes/plugins/omh/plugin.yaml`
- `~/.hermes/plugins/omh/__init__.py`
- `~/.hermes/plugins/omh/config.yaml`
- `~/.hermes/plugins/omh/tools/__init__.py`
- `~/.hermes/plugins/omh/hooks/__init__.py`

**Dependencies:** None

**Complexity:** Low (~80 lines)

**Acceptance Criteria:**
- `hermes` starts without errors and shows `omh` in plugin list
- `hermes tools` shows the `omh` toolset (even if tools do nothing yet)
- `plugin.yaml` declares `name: omh`, lists `provides_tools` and `provides_hooks`
- `register(ctx)` calls `ctx.register_tool()` for each tool and `ctx.register_hook()` for each hook
- All imports are lazy (tool modules imported inside register, not at top level)

**plugin.yaml shape:**
```yaml
name: omh
version: "0.1.0"
description: "Oh My Hermes — infrastructure layer for OMH skills"
author: "witt3rd"
provides_tools:
  - omh_state_read
  - omh_state_write
  - omh_state_clear
  - omh_state_check
  - omh_state_list
  - omh_delegate
  - omh_gather_evidence
  - omh_cancel_check
provides_hooks:
  - on_session_start
  - on_session_end
  - pre_llm_call
```

---

### Task 2: Config Loader

**Description:** Implement `omh_config.py` that reads
`~/.hermes/plugins/omh/config.yaml`, merges with hardcoded defaults, and
exposes a `get_config()` function. Config includes role mappings (role name →
category + tier), model tier → model mapping, and the role prompts directory
path.

**Files:**
- `~/.hermes/plugins/omh/omh_config.py`
- `~/.hermes/plugins/omh/config.yaml` (default content)

**Dependencies:** Task 1

**Complexity:** Low (~60 lines)

**Acceptance Criteria:**
- `get_config()` returns a dict with `roles`, `model_routing.tiers`, `role_prompts_dir`
- Missing config.yaml returns all defaults (no crash)
- Malformed YAML logs a warning and returns defaults
- Config is cached after first load (module-level singleton)

**Default config.yaml:**
```yaml
role_prompts_dir: ~/.hermes/skills/omh-ralplan/references
model_routing:
  enabled: true
  tiers:
    low: null       # use agent's default model
    medium: null
    high: null
roles:
  executor:          {category: implementation, tier: medium}
  verifier:          {category: review,         tier: medium}
  architect:         {category: analysis,       tier: high}
  planner:           {category: planning,       tier: high}
  critic:            {category: analysis,       tier: high}
  analyst:           {category: analysis,       tier: high}
  security-reviewer: {category: review,         tier: high}
  code-reviewer:     {category: review,         tier: high}
  test-engineer:     {category: testing,        tier: medium}
  debugger:          {category: analysis,       tier: medium}
state_dir: .omh/state
staleness_hours: 2
cancel_ttl_seconds: 30
```

---

### Task 3: State Engine

**Description:** Implement `omh_state.py` — the core state management engine.
This is a pure Python module (no tool registration) that provides functions
for reading, writing, clearing, and checking state files. All state files
live under `.omh/state/` relative to the project root (cwd). Writes are
atomic (write-to-temp + os.replace). Every write wraps data in a `_meta`
envelope with timestamp, mode, and session_id.

**Files:**
- `~/.hermes/plugins/omh/omh_state.py`

**Dependencies:** Task 2 (for config: staleness_hours, state_dir)

**Complexity:** Medium (~200 lines)

**Functions:**
```python
def state_read(mode: str, session_id: str = None) -> dict:
    """Read .omh/state/{mode}-state.json. Returns {exists, data, stale, session_match}."""

def state_write(mode: str, data: dict, session_id: str = None) -> dict:
    """Atomic write with _meta envelope. Returns {success, path}."""

def state_clear(mode: str, session_id: str = None) -> dict:
    """Delete state file. Returns {cleared, path}."""

def state_check(mode: str, session_id: str = None) -> dict:
    """Quick status: {exists, active, stale, session_match, phase, age_seconds}."""

def state_list_active() -> dict:
    """List all modes with active state. Returns {modes: [{mode, active, phase, age}]}."""

def _atomic_write(path: Path, data: dict) -> None:
    """Write to .tmp.{uuid} then os.replace(). fsync before rename."""

def _wrap_meta(mode: str, data: dict, session_id: str = None) -> dict:
    """Add _meta: {written_at, mode, session_id} envelope."""

def _is_stale(meta: dict, max_hours: float) -> bool:
    """Check if _meta.written_at is older than max_hours."""
```

**Acceptance Criteria:**
- `state_write("ralph", {"iteration": 1, "active": True})` creates `.omh/state/ralph-state.json` with `_meta` envelope
- `state_read("ralph")` returns data WITHOUT `_meta` (stripped), plus `exists=True`
- Concurrent writes don't corrupt (atomic rename)
- Stale detection works (>2h by default)
- `state_clear` removes the file and returns confirmation
- `state_list_active` finds all `*-state.json` files with `active: true`
- `.omh/state/` directory auto-created on first write
- All functions handle missing files gracefully (no crashes)

---

### Task 4: State Tools (5 tools)

**Description:** Register the 5 state tools via `ctx.register_tool()`. Each
tool is a thin wrapper around the state engine functions from Task 3. Tools
handle argument parsing and JSON serialization.

**Files:**
- `~/.hermes/plugins/omh/tools/state_tools.py`

**Dependencies:** Task 1 (scaffold), Task 3 (state engine)

**Complexity:** Low-Medium (~100 lines)

**Tool Schemas:**
```python
# omh_state_read
{
    "name": "omh_state_read",
    "description": "Read OMH mode state. Returns parsed state data with staleness and session info.",
    "parameters": {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "description": "Mode name: ralph, autopilot, ralplan, deep-interview, etc."
            }
        },
        "required": ["mode"]
    }
}

# omh_state_write
{
    "name": "omh_state_write",
    "description": "Write OMH mode state atomically. Wraps data with metadata envelope.",
    "parameters": {
        "type": "object",
        "properties": {
            "mode": {"type": "string", "description": "Mode name"},
            "data": {"type": "object", "description": "State data to write (arbitrary JSON)"}
        },
        "required": ["mode", "data"]
    }
}

# omh_state_clear — params: mode (required)
# omh_state_check — params: mode (required)
# omh_state_list  — params: none
```

**Acceptance Criteria:**
- All 5 tools appear in `hermes tools` under the `omh` toolset
- Agent can call `omh_state_write(mode="ralph", data={...})` and it creates the file
- Agent can call `omh_state_read(mode="ralph")` and get the data back
- All tools return JSON strings (handler contract)
- Error cases return `{"error": "..."}` not Python exceptions

---

### Task 5: Evidence Gathering Tool

**Description:** Register `omh_gather_evidence` — runs a list of shell
commands, captures output, truncates to a limit, and returns structured
results. Uses `subprocess.run()` internally (NOT the Hermes terminal tool —
this runs directly in the plugin's process context for simplicity and because
it needs structured output).

**Files:**
- `~/.hermes/plugins/omh/tools/evidence_tool.py`

**Dependencies:** Task 1 (scaffold)

**Complexity:** Low (~100 lines)

**Tool Schema:**
```python
{
    "name": "omh_gather_evidence",
    "description": (
        "Run build/test/lint commands and collect evidence for verification. "
        "Returns structured results with exit codes, truncated output, and an "
        "all_pass summary. Use this before sending results to a verifier."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "commands": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Shell commands to run (e.g. ['npm run build', 'npm test', 'npm run lint'])"
            },
            "truncate": {
                "type": "integer",
                "description": "Max chars to keep per command output (default: 2000). Keeps the LAST N chars."
            },
            "workdir": {
                "type": "string",
                "description": "Working directory for commands (default: cwd)"
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout per command in seconds (default: 120)"
            }
        },
        "required": ["commands"]
    }
}
```

**Handler logic:**
```python
def gather_evidence(args, **kwargs):
    commands = args["commands"]
    truncate = args.get("truncate", 2000)
    workdir = args.get("workdir", None)
    timeout = args.get("timeout", 120)
    results = []
    for cmd in commands:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              cwd=workdir, timeout=timeout)
        output = (proc.stdout + proc.stderr)[-truncate:]
        results.append({
            "command": cmd,
            "exit_code": proc.returncode,
            "output": output,
            "truncated": len(proc.stdout + proc.stderr) > truncate,
            "passed": proc.returncode == 0
        })
    return json.dumps({
        "results": results,
        "all_pass": all(r["passed"] for r in results),
        "summary": f"{sum(1 for r in results if r['passed'])}/{len(results)} passed"
    })
```

**Acceptance Criteria:**
- `omh_gather_evidence(commands=["echo hello", "false"])` returns 2 results, first passes, second fails, `all_pass=false`
- Output truncation works (keeps tail)
- Timeout kills long-running commands without hanging
- `workdir` parameter changes cwd for all commands
- Returns JSON string

---

### Task 6: Cancel Check Tool

**Description:** Register `omh_cancel_check` — checks for a cancel signal
file with TTL validation. Skills call this in their loop iterations to detect
user-requested cancellation.

**Files:**
- `~/.hermes/plugins/omh/tools/cancel_tool.py`

**Dependencies:** Task 1, Task 2 (config for cancel_ttl_seconds)

**Complexity:** Low (~40 lines)

**Tool Schema:**
```python
{
    "name": "omh_cancel_check",
    "description": "Check if a cancel signal has been requested for an OMH mode. Returns cancelled=true if a valid (non-expired) cancel signal exists.",
    "parameters": {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "description": "Mode to check (default: 'ralph')"
            }
        },
        "required": []
    }
}
```

**Handler logic:**
- Read `.omh/state/{mode}-cancel.json`
- If exists and `_meta.written_at` is within `cancel_ttl_seconds` (default 30s): return `{cancelled: true, reason, requested_at}`
- If expired: delete the file, return `{cancelled: false, reason: "expired"}`
- If missing: return `{cancelled: false}`

**Acceptance Criteria:**
- Returns `cancelled: false` when no signal exists
- Returns `cancelled: true` when fresh signal exists
- Expired signals (>30s) are cleaned up and return false
- Creating a cancel signal: `omh_state_write(mode="ralph-cancel", data={reason: "user request"})` (uses the state engine)

---

### Task 7: Delegate Tool

**Description:** Register `omh_delegate` — the high-level delegation tool
that wraps Hermes's `delegate_task`. It auto-loads role prompts, constructs
context from components, and resolves model tiers from config. Internally
it calls `delegate_task()` from `tools/delegate_tool.py` (the function, not
the tool dispatch).

**Files:**
- `~/.hermes/plugins/omh/tools/delegate_tool.py`

**Dependencies:** Task 1, Task 2 (config for roles + model routing)

**Complexity:** Medium-High (~250 lines)

**Tool Schema:**
```python
{
    "name": "omh_delegate",
    "description": (
        "Delegate work to a role-specific subagent. Automatically loads the role "
        "prompt, routes to the appropriate model tier, and constructs context from "
        "components. Much simpler than raw delegate_task — just specify the role "
        "and goal."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "role": {
                "type": "string",
                "description": "Role name: executor, verifier, architect, planner, critic, analyst, security-reviewer, code-reviewer, test-engineer, debugger"
            },
            "goal": {
                "type": "string",
                "description": "What the subagent should accomplish"
            },
            "task_context": {
                "type": "string",
                "description": "Project-specific context (tech stack, conventions, relevant file paths)"
            },
            "learnings": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Learnings from previously completed tasks"
            },
            "previous_feedback": {
                "type": "string",
                "description": "Feedback from a prior rejection (for retry attempts)"
            },
            "model_override": {
                "type": "string",
                "description": "Explicit model to use, bypassing tier routing (e.g. 'anthropic/claude-opus-4')"
            },
            "toolsets": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Toolsets for the subagent (default: ['terminal', 'file', 'web'])"
            },
            "max_iterations": {
                "type": "integer",
                "description": "Max iterations for the subagent (default: 50)"
            }
        },
        "required": ["role", "goal"]
    }
}
```

**Handler logic (pseudocode):**
```python
def omh_delegate(args, **kwargs):
    config = get_config()
    role = args["role"]
    goal = args["goal"]

    # 1. Load role prompt
    role_prompt = _load_role_prompt(role, config["role_prompts_dir"])

    # 2. Resolve model from tier
    role_config = config["roles"].get(role, {"tier": "medium"})
    model = args.get("model_override") or config["model_routing"]["tiers"].get(role_config["tier"])

    # 3. Build context
    context_parts = []
    if role_prompt:
        context_parts.append(f"# Role: {role.title()}\n\n{role_prompt}")
    if args.get("task_context"):
        context_parts.append(f"## Project Context\n\n{args['task_context']}")
    if args.get("learnings"):
        context_parts.append(f"## Learnings from Prior Tasks\n\n" +
                             "\n".join(f"- {l}" for l in args["learnings"]))
    if args.get("previous_feedback"):
        context_parts.append(f"## Previous Rejection Feedback\n\n{args['previous_feedback']}")
    context = "\n\n---\n\n".join(context_parts)

    # 4. Call delegate_task (import the function directly)
    from tools.delegate_tool import delegate_task
    result = delegate_task(
        goal=goal,
        context=context,
        toolsets=args.get("toolsets"),
        max_iterations=args.get("max_iterations"),
        parent_agent=kwargs.get("parent_agent"),
    )
    return result  # already a JSON string from delegate_task
```

**Acceptance Criteria:**
- `omh_delegate(role="executor", goal="Implement feature X")` successfully spawns a subagent
- Role prompt auto-loaded from configured directory (falls back gracefully if missing)
- Model tier routing works: `high` role gets configured model (or default if null)
- Context string includes role prompt + task_context + learnings + feedback when provided
- Unknown roles fall back to tier=medium with a warning
- Returns the delegate_task result (JSON string with subagent output)
- Works with `model_override` to bypass tier routing

---

### Task 8: Session Hooks

**Description:** Implement the three lifecycle hooks that provide mode
awareness and clean interruption handling.

**Files:**
- `~/.hermes/plugins/omh/hooks/session_hooks.py`
- `~/.hermes/plugins/omh/hooks/llm_hooks.py`

**Dependencies:** Task 1, Task 3 (state engine)

**Complexity:** Medium (~130 lines)

**Hook: on_session_start**
```python
def on_session_start(**kwargs):
    """Check for active OMH modes and return awareness context."""
    active = state_list_active()
    if not active["modes"]:
        return None
    # Build awareness message
    lines = ["[OMH] Active modes detected:"]
    for m in active["modes"]:
        lines.append(f"  - {m['mode']}: phase={m.get('phase', '?')}, age={m.get('age_seconds', '?')}s")
    lines.append("Read the relevant state with omh_state_read() to continue.")
    return {"context": "\n".join(lines)}
```

**Hook: on_session_end**
```python
def on_session_end(**kwargs):
    """Ensure active OMH modes have clean state on interruption."""
    active = state_list_active()
    if not active["modes"]:
        return None
    for m in active["modes"]:
        # Read current state and mark interruption point
        current = state_read(m["mode"])
        if current.get("exists") and current.get("data", {}).get("active"):
            data = current["data"]
            data["_interrupted_at"] = datetime.utcnow().isoformat() + "Z"
            state_write(m["mode"], data)
    logger.info("OMH: Saved interruption state for %d active modes", len(active["modes"]))
```

**Hook: pre_llm_call**
```python
def pre_llm_call(**kwargs):
    """If an OMH mode is active, inject a brief reminder."""
    active = state_list_active()
    if not active["modes"]:
        return None
    # Only inject for the highest-priority active mode
    mode = active["modes"][0]
    phase = mode.get("phase", "unknown")
    iteration = mode.get("iteration", "?")
    reminder = (
        f"[OMH] You are in {mode['mode']} mode (phase: {phase}, "
        f"iteration: {iteration}). Do not stop until the workflow is complete "
        f"or you hit a cancel signal. Check omh_cancel_check() if unsure."
    )
    return {"context": reminder}
```

**Acceptance Criteria:**
- `on_session_start` returns context string when active modes exist, None otherwise
- `on_session_end` updates state files with `_interrupted_at` timestamp
- `pre_llm_call` returns a brief context injection for active modes
- All hooks are exception-safe (Hermes wraps them in try/except, but we should also be defensive)
- Hooks don't crash when `.omh/state/` directory doesn't exist
- `pre_llm_call` return format: `{"context": "..."}` or plain string (both accepted by Hermes)

---

### Task 9: Integration Test Suite

**Description:** Write tests that verify the plugin loads correctly in
isolation (mocking the PluginContext) and that each tool produces correct
output. Tests should be runnable standalone (`python -m pytest`) without
starting a full Hermes session.

**Files:**
- `~/.hermes/plugins/omh/tests/__init__.py`
- `~/.hermes/plugins/omh/tests/test_state.py`
- `~/.hermes/plugins/omh/tests/test_evidence.py`
- `~/.hermes/plugins/omh/tests/test_delegate.py`
- `~/.hermes/plugins/omh/tests/test_hooks.py`
- `~/.hermes/plugins/omh/tests/test_registration.py`

**Dependencies:** Tasks 1-8

**Complexity:** Medium (~200 lines)

**Acceptance Criteria:**
- `test_state.py`: round-trip write/read/clear, atomic write safety, staleness detection, meta envelope
- `test_evidence.py`: multi-command execution, truncation, timeout handling, all_pass logic
- `test_delegate.py`: role prompt loading, context assembly, model tier resolution (mock delegate_task)
- `test_hooks.py`: session_start/end/pre_llm with and without active modes
- `test_registration.py`: register(ctx) calls ctx.register_tool 8 times and ctx.register_hook 3 times
- All tests use tmp_path fixtures (no real filesystem side effects)
- Tests pass with `python -m pytest ~/.hermes/plugins/omh/tests/ -v`

---

### Task 10: Skill Refactoring (omh-ralph)

**Description:** Refactor omh-ralph SKILL.md to use plugin tools instead of
manual infrastructure. This is the proof that the plugin works end-to-end.

**Files:**
- `~/.hermes/skills/omh-ralph/SKILL.md` (or wherever it lives)

**Dependencies:** Tasks 1-8 (full plugin)

**Complexity:** Medium (rewriting ~100 lines of infrastructure into ~20 lines of tool calls)

**Acceptance Criteria:**
- State management uses `omh_state_read/write/clear` instead of manual JSON
- Delegation uses `omh_delegate(role="executor", ...)` instead of manual prompt assembly
- Evidence gathering uses `omh_gather_evidence(commands=[...])` instead of manual subprocess
- Cancel checking uses `omh_cancel_check(mode="ralph")` instead of manual file reads
- Skill is ~40% shorter than before
- Skill works correctly in a real Hermes session with the plugin installed

---

## Risks

### R1: delegate_task function import path
**Risk:** The `omh_delegate` tool needs to call `delegate_task()` as a Python
function, but `tools/delegate_tool.py` lives inside the hermes-agent package
and may not be importable from a plugin's module context.
**Mitigation:** Test early (Task 7). If direct import fails, fall back to
calling `registry.dispatch("delegate_task", args)` which is always available.
The plugin's `__init__.py` runs inside the hermes-agent process, so
`tools.delegate_tool` should be importable.

### R2: pre_llm_call injection overhead
**Risk:** The `pre_llm_call` hook runs on EVERY LLM call. If `state_list_active()`
does filesystem I/O each time, it adds latency.
**Mitigation:** Implement a module-level cache with 5s TTL on state_list_active
results (same pattern as OMC). If no `.omh/state/` directory exists, return
immediately with no I/O.

### R3: Atomic write on Windows/NFS
**Risk:** `os.replace()` is atomic on local POSIX filesystems but may not be
on NFS or Windows.
**Mitigation:** Document that the plugin targets Linux/macOS local filesystems.
This is the same limitation as OMC.

### R4: Plugin load order vs tool availability
**Risk:** Plugin tools must be registered before the agent's first tool
discovery pass. If plugins load too late, tools won't appear.
**Mitigation:** Hermes calls `discover_plugins()` during startup before tool
discovery. Verified in the code — `_load_plugin()` calls `register()` which
calls `ctx.register_tool()` synchronously.

### R5: Session ID availability in hooks
**Risk:** Hooks receive `**kwargs` but the specific kwargs available at each
hook point aren't fully documented. `session_id` may or may not be passed.
**Mitigation:** Use `os.environ.get("HERMES_SESSION_ID")` as fallback, or
generate a process-scoped UUID if neither is available. Test empirically
which kwargs each hook receives.

### R6: State file location (cwd-relative)
**Risk:** `.omh/state/` is relative to cwd. In gateway mode, cwd may be the
home directory, not the project directory.
**Mitigation:** Check `TERMINAL_CWD` env var first, then `os.getcwd()`. Document
that OMH skills should be run from the project root.

---

## Open Questions

### Q1: Should the plugin also register a `/omh` slash command?
The plugin supports `ctx.register_cli_command()`. A `/omh status` command could
show active modes, and `/omh cancel <mode>` could write a cancel signal. This
would be ~50 lines and very useful, but is not in the current spec. **Recommend:
yes, add as Task 11 if time permits.**

### Q2: Session scoping — do we need it for v1?
OMC uses session IDs extensively for state isolation. Hermes skills currently
don't have multi-session state conflicts (single-user CLI). Should we implement
session scoping in v1 or keep it simple (global `.omh/state/{mode}-state.json`)?
**Recommend: implement session_id parameter but make it optional. Default to
no session scoping. Add it later if needed.**

### Q3: Should omh_delegate call delegate_task via registry dispatch or direct import?
Direct import (`from tools.delegate_tool import delegate_task`) gives us the
function signature but creates a coupling. Registry dispatch
(`registry.dispatch("delegate_task", args)`) is more decoupled but we lose
`parent_agent` passthrough. **Recommend: direct import — the plugin runs inside
hermes-agent's process, and we need `parent_agent` for workspace resolution.**

### Q4: Config file location — plugin dir vs project dir?
Should `config.yaml` live only in `~/.hermes/plugins/omh/config.yaml` (global),
or should projects be able to override with `.omh/config.yaml` (project-local)?
**Recommend: global only for v1. Project-level overrides add complexity for
marginal benefit.**

### Q5: How does pre_llm_call injection interact with prompt caching?
Hermes AGENTS.md says context injection goes into the user message (not system
prompt) to preserve prompt cache. Our `pre_llm_call` hook returns `{"context": "..."}`
which Hermes injects per the documented contract. But does injecting different
context each turn break caching? **Answer: No — the system prompt is cached,
user message context is ephemeral by design. Confirmed in plugins.py docstring.**

### Q6: Do we need backward-compatible skills (work without plugin)?
The proposal suggests v2 skills require the plugin, with v1 skills in `legacy/`.
**Recommend: yes, require the plugin for v2 skills. Keep v1 skills as-is. The
plugin is a single directory copy — low barrier to install.**

---

## Dependency Graph

```
Task 1 (Scaffold)
  ├─> Task 2 (Config)
  │     ├─> Task 3 (State Engine)
  │     │     └─> Task 4 (State Tools)
  │     ├─> Task 6 (Cancel Tool)
  │     └─> Task 7 (Delegate Tool)
  ├─> Task 5 (Evidence Tool)
  └─> Task 8 (Hooks) ← depends on Task 3
        └─> Task 9 (Tests) ← depends on all above
              └─> Task 10 (Skill Refactor)
```

**Critical path:** 1 → 2 → 3 → 4 → 8 → 9 → 10

**Parallelizable:** Tasks 4, 5, 6, 7 can all be built in parallel after Tasks 2+3.

---

## Estimated Timeline

| Day | Tasks | Milestone |
|-----|-------|-----------|
| 1   | 1, 2, 3 | Plugin loads, config works, state engine complete |
| 2   | 4, 5, 6 | State tools, evidence tool, cancel tool registered |
| 3   | 7, 8   | Delegate tool and hooks complete — full plugin functional |
| 4   | 9      | Test suite passes |
| 5   | 10     | omh-ralph refactored and working with plugin |
