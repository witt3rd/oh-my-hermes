# OMH Hermes Plugin — Implementation Plan (v2)

Generated: 2026-04-07
Revision: v2 — addresses reviewer blockers from Architect + Critic
Based on: omh-plugin-plan.md (v1), hermes-agent source analysis

---

## Changes from v1

| # | Issue | Resolution |
|---|-------|------------|
| 1 | **parent_agent not available to plugin tools** (showstopper) | Requires 1-line hermes-agent PR; fallback via thread-local stash documented |
| 2 | **Cancel filename mismatch** | Cancel integrated into omh_state; uses `{mode}-state.json` with `cancel_requested` field |
| 3 | **Model routing may not work** | Descoped from v1; delegate_task has no model param; document as future work |
| 4 | **8 tools → 3 tools** (Critic simplicity test) | Adopted: omh_state, omh_delegate, omh_gather_evidence |
| 5 | **omh_gather_evidence bypasses safety rails** | Command allowlist + configurable approval |
| 6 | **on_session_start return values ignored** | Context injection moved to pre_llm_call with is_first_turn check |
| 7 | **session_id dead code** | Removed from v1; no session scoping in v1 |
| 8 | **schema_version missing** | Added to _meta envelope |

---

## Summary

Build the OMH plugin as a Python plugin at `~/.hermes/plugins/omh/` that
registers **3 MCP-style tools** and **2 lifecycle hooks** via the Hermes
PluginContext API. The plugin provides: (1) unified state management with
atomic writes, metadata envelopes, and cancel signaling, (2) role-aware
delegation that auto-loads role prompts, (3) evidence gathering with a
command allowlist, and (4) session hooks for mode awareness and clean
interruption. Target: **~500 lines** of Python. State stored in
`.omh/state/`, config in `~/.hermes/plugins/omh/config.yaml`.

**IMPORTANT:** The plugin requires a small hermes-agent PR (Issue #1 below)
to enable delegation from plugin tools. The plan includes a thread-local
fallback if the PR is not yet merged, but the PR is the correct fix.

---

## Critical Issue #1: parent_agent Access

### The Problem

`delegate_task()` requires `parent_agent` (returns error JSON without it).
The agent loop in `run_agent.py` special-cases `delegate_task` at line 6108:

```python
elif function_name == "delegate_task":
    return _delegate_task(..., parent_agent=self)
```

All other tools go through `handle_function_call()` → `registry.dispatch()`,
which passes only `task_id=` and `user_task=` as kwargs. Plugin tools
registered via `ctx.register_tool()` go through `registry.dispatch()` and
therefore **never receive parent_agent**.

### The Solution: hermes-agent PR (Option D — proper refactor)

The cleanest fix: add `parent_agent` to `handle_function_call()` kwargs and
pass it through `registry.dispatch()`. This is a ~5-line change in two files:

**model_tools.py** — add param to handle_function_call:
```python
def handle_function_call(
    function_name, function_args, task_id=None,
    tool_call_id=None, session_id=None, user_task=None,
    enabled_tools=None,
    parent_agent=None,          # NEW
) -> str:
    ...
    result = registry.dispatch(
        function_name, function_args,
        task_id=task_id, user_task=user_task,
        parent_agent=parent_agent,      # NEW
    )
```

**run_agent.py** — remove the special-case, pass parent_agent to the
generic handler:
```python
# Remove the elif function_name == "delegate_task" branch
# Change the else branch to:
return handle_function_call(
    function_name, function_args, effective_task_id,
    tool_call_id=tool_call_id,
    session_id=self.session_id or "",
    enabled_tools=list(self.valid_tool_names) if self.valid_tool_names else None,
    parent_agent=self,          # NEW — all tools get it; most ignore it
)
```

Also remove `delegate_task` from `_AGENT_LOOP_TOOLS` in model_tools.py
(line 364), since it no longer needs special-casing.

**Impact:** Zero breaking changes. Existing tool handlers accept `**kwargs`
and will silently ignore `parent_agent`. Only tools that opt into it (like
omh_delegate) use it.

### Fallback: Thread-Local Stash (if PR not merged)

If the PR is blocked, use a thread-local to stash the agent reference:

```python
# omh/_agent_stash.py
import threading
_local = threading.local()

def stash_agent(agent):
    _local.agent = agent

def get_agent():
    return getattr(_local, 'agent', None)
```

Inject via the `pre_llm_call` hook (which receives `conversation_history`
from the agent loop — but NOT the agent itself). Actually, no hook receives
the agent reference either.

**Better fallback:** Use `pre_tool_call` hook. In `model_tools.py` line 501,
pre_tool_call is called with `tool_name=, args=, task_id=, session_id=,
tool_call_id=`. Still no parent_agent.

**Realistic fallback:** Monkey-patch at plugin load time:

```python
# In register(ctx):
import run_agent
_original = run_agent.AIAgent._execute_single_tool_call
def _patched(self, *args, **kwargs):
    _local.agent = self
    return _original(self, *args, **kwargs)
run_agent.AIAgent._execute_single_tool_call = _patched
```

This is fragile and version-dependent. **The PR is strongly preferred.**

### Recommendation

Submit the hermes-agent PR as a prerequisite. It's clean, backwards-compatible,
and benefits all plugins. The omh_delegate tool should check for parent_agent
in kwargs and return a clear error message if missing (rather than cryptically
failing):

```python
def omh_delegate(args, **kwargs):
    parent_agent = kwargs.get("parent_agent")
    if not parent_agent:
        return json.dumps({
            "error": "omh_delegate requires parent_agent. "
            "Ensure hermes-agent >= X.Y.Z (PR #NNN)."
        })
```

---

## Architecture

```
~/.hermes/plugins/omh/
├── plugin.yaml           # Manifest
├── __init__.py           # register(ctx: PluginContext)
├── config.yaml           # Role mappings, role_prompts_dir
├── omh_config.py         # Config loader
├── omh_state.py          # State engine (atomic write, meta, cancel)
├── tools/
│   ├── __init__.py
│   ├── state_tool.py     # omh_state (1 unified tool)
│   ├── delegate_tool.py  # omh_delegate (1 tool)
│   └── evidence_tool.py  # omh_gather_evidence (1 tool)
├── hooks/
│   ├── __init__.py
│   └── llm_hooks.py      # pre_llm_call (mode awareness + first-turn injection)
│   └── session_hooks.py  # on_session_end (interruption state)
└── tests/
    ├── test_state.py
    ├── test_evidence.py
    ├── test_delegate.py
    └── test_hooks.py
```

### Tools (3 total)

| Tool | Description |
|------|-------------|
| `omh_state` | Unified state: action=read\|write\|clear\|check\|list\|cancel |
| `omh_delegate` | Role-aware delegation wrapping delegate_task |
| `omh_gather_evidence` | Run build/test/lint with allowlist + structured results |

### Hooks (2 total)

| Hook | Purpose |
|------|---------|
| `pre_llm_call` | First-turn: inject active mode awareness. Every turn: inject mode reminder |
| `on_session_end` | Mark active modes with `_interrupted_at` timestamp |

Note: `on_session_start` is NOT used for context injection (return values
from it are not consumed by the agent loop for context). We use `pre_llm_call`
with `is_first_turn` check instead, which IS wired for context injection
(run_agent.py lines 7144-7163).

---

## Tasks

### Task 0: hermes-agent PR (prerequisite)

**Description:** Submit PR to hermes-agent to pass parent_agent through
handle_function_call → registry.dispatch. See "Critical Issue #1" above.

**Files changed:**
- `model_tools.py` — add parent_agent param to handle_function_call, pass to dispatch
- `run_agent.py` — remove delegate_task special-case from _execute_single_tool_call, pass parent_agent=self to handle_function_call

**Complexity:** Low (~10 lines changed)

**Acceptance Criteria:**
- delegate_task still works exactly as before (regression test)
- Plugin tools registered via ctx.register_tool receive parent_agent in kwargs
- No breaking changes to existing tool handlers

---

### Task 1: Plugin Scaffold

**Description:** Create directory structure, `plugin.yaml` manifest, and
`__init__.py` with the `register(ctx)` entry point.

**Files:**
- `~/.hermes/plugins/omh/plugin.yaml`
- `~/.hermes/plugins/omh/__init__.py`
- `~/.hermes/plugins/omh/config.yaml`
- `~/.hermes/plugins/omh/tools/__init__.py`
- `~/.hermes/plugins/omh/hooks/__init__.py`

**Dependencies:** None

**Complexity:** Low (~60 lines)

**Acceptance Criteria:**
- `hermes` starts without errors and shows `omh` in plugin list
- `hermes tools` shows the `omh` toolset
- `register(ctx)` calls `ctx.register_tool()` for 3 tools and `ctx.register_hook()` for 2 hooks
- All imports are lazy (inside register, not at top level)

**plugin.yaml:**
```yaml
name: omh
version: "0.1.0"
description: "Oh My Hermes — infrastructure layer for OMH skills"
author: "witt3rd"
provides_tools:
  - omh_state
  - omh_delegate
  - omh_gather_evidence
provides_hooks:
  - pre_llm_call
  - on_session_end
```

---

### Task 2: Config Loader

**Description:** Implement `omh_config.py` — reads config.yaml, merges with
defaults, exposes `get_config()`.

**Files:**
- `~/.hermes/plugins/omh/omh_config.py`
- `~/.hermes/plugins/omh/config.yaml`

**Dependencies:** Task 1

**Complexity:** Low (~50 lines)

**Acceptance Criteria:**
- `get_config()` returns dict with roles, role_prompts_dir, evidence_allowlist
- Missing/malformed config returns defaults (no crash)
- Config cached after first load (module-level singleton)

**Default config.yaml:**
```yaml
role_prompts_dir: ~/.hermes/skills/omh-ralplan/references

roles:
  executor:          {category: implementation}
  verifier:          {category: review}
  architect:         {category: analysis}
  planner:           {category: planning}
  critic:            {category: analysis}
  analyst:           {category: analysis}
  security-reviewer: {category: review}
  code-reviewer:     {category: review}
  test-engineer:     {category: testing}
  debugger:          {category: analysis}

state_dir: .omh/state
staleness_hours: 2
cancel_ttl_seconds: 30

evidence:
  # Commands matching these prefixes are allowed without approval
  allowlist_prefixes:
    - "npm "
    - "npx "
    - "yarn "
    - "pnpm "
    - "cargo "
    - "make "
    - "python -m pytest"
    - "python -m mypy"
    - "go test"
    - "go build"
    - "go vet"
    - "ruff "
    - "black --check"
    - "eslint "
    - "tsc "
    - "grep "
    - "wc "
    - "cat "
    - "head "
    - "tail "
  max_commands: 10
  default_timeout: 120
  default_truncate: 2000
```

Note: model_routing removed from config (descoped from v1 — see Issue #3).

---

### Task 3: State Engine

**Description:** Implement `omh_state.py` — the core state management engine.
All state files live under `.omh/state/` relative to cwd. Writes are atomic
(write-to-temp + os.replace). Every write wraps data in a `_meta` envelope
with timestamp, mode, and schema_version. Cancel is implemented as a field
in state data, not a separate file.

**Files:**
- `~/.hermes/plugins/omh/omh_state.py`

**Dependencies:** Task 2

**Complexity:** Medium (~180 lines)

**Functions:**
```python
def state_read(mode: str) -> dict:
    """Read .omh/state/{mode}-state.json.
    Returns {exists, data, stale, age_seconds}.
    Data returned WITHOUT _meta (stripped)."""

def state_write(mode: str, data: dict) -> dict:
    """Atomic write with _meta envelope.
    Returns {success, path}."""

def state_clear(mode: str) -> dict:
    """Delete state file. Returns {cleared, path}."""

def state_check(mode: str) -> dict:
    """Quick status: {exists, active, stale, phase, age_seconds}."""

def state_list_active() -> dict:
    """List all modes with active state.
    Returns {modes: [{mode, active, phase, age_seconds}]}."""

def state_cancel(mode: str, reason: str = "user request") -> dict:
    """Set cancel_requested=True in the mode's state file.
    Returns {success, mode}. If no active state, writes a
    minimal cancel-only state."""

def state_check_cancel(mode: str) -> dict:
    """Check if cancel_requested is set and within TTL.
    Returns {cancelled, reason, requested_at}.
    Clears expired cancel signals."""

def _atomic_write(path: Path, data: dict) -> None:
    """Write to .tmp.{uuid} then os.replace(). fsync before rename."""

def _wrap_meta(mode: str, data: dict) -> dict:
    """Add _meta: {written_at, mode, schema_version: 1} envelope."""

def _is_stale(meta: dict, max_hours: float) -> bool:
    """Check if _meta.written_at is older than max_hours."""
```

**Key design decisions:**
- No session_id scoping in v1 (removed dead code)
- Cancel signal is `cancel_requested: true` + `cancel_reason` + `cancel_at`
  fields in the mode's own state file, not a separate file. This eliminates
  the filename mismatch bug from v1.
- `_meta.schema_version: 1` added to all writes for future migration
- `state_list_active()` has 5s TTL cache for pre_llm_call performance

**Acceptance Criteria:**
- `state_write("ralph", {"iteration": 1, "active": True})` creates `.omh/state/ralph-state.json` with `_meta`
- `state_read("ralph")` returns data WITHOUT `_meta`, plus `exists=True`
- `state_cancel("ralph")` sets cancel fields in ralph-state.json
- `state_check_cancel("ralph")` returns `{cancelled: true}` if within TTL
- Concurrent writes don't corrupt (atomic rename)
- Stale detection works (>2h by default)
- `.omh/state/` auto-created on first write
- All functions handle missing files gracefully

---

### Task 4: Unified State Tool

**Description:** Register the single `omh_state` tool that handles all state
operations via an `action` parameter. Replaces the 5 separate state tools +
cancel tool from v1.

**Files:**
- `~/.hermes/plugins/omh/tools/state_tool.py`

**Dependencies:** Task 1, Task 3

**Complexity:** Low (~80 lines)

**Tool Schema:**
```python
{
    "name": "omh_state",
    "description": (
        "Manage OMH workflow state. Actions: read, write, clear, check, "
        "list, cancel, cancel_check. State is stored in .omh/state/ "
        "relative to the project root."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "write", "clear", "check", "list",
                         "cancel", "cancel_check"],
                "description": "Operation to perform"
            },
            "mode": {
                "type": "string",
                "description": "Mode name: ralph, autopilot, ralplan, etc. "
                               "Required for all actions except 'list'."
            },
            "data": {
                "type": "object",
                "description": "State data to write (for action=write only)"
            },
            "reason": {
                "type": "string",
                "description": "Cancel reason (for action=cancel only)"
            }
        },
        "required": ["action"]
    }
}
```

**Handler logic:**
```python
def omh_state_handler(args, **kwargs):
    action = args["action"]
    mode = args.get("mode", "")

    if action == "list":
        return json.dumps(state_list_active())
    if not mode:
        return json.dumps({"error": "mode is required for this action"})

    dispatch = {
        "read":         lambda: state_read(mode),
        "write":        lambda: state_write(mode, args.get("data", {})),
        "clear":        lambda: state_clear(mode),
        "check":        lambda: state_check(mode),
        "cancel":       lambda: state_cancel(mode, args.get("reason", "user request")),
        "cancel_check": lambda: state_check_cancel(mode),
    }
    fn = dispatch.get(action)
    if not fn:
        return json.dumps({"error": f"Unknown action: {action}"})
    return json.dumps(fn())
```

**Acceptance Criteria:**
- `omh_state(action="write", mode="ralph", data={...})` creates state file
- `omh_state(action="read", mode="ralph")` returns the data
- `omh_state(action="cancel", mode="ralph")` sets cancel signal
- `omh_state(action="cancel_check", mode="ralph")` detects cancel
- `omh_state(action="list")` shows all active modes
- All actions return JSON strings
- Error cases return `{"error": "..."}` not Python exceptions

---

### Task 5: Evidence Gathering Tool

**Description:** Register `omh_gather_evidence` with a command allowlist
to avoid bypassing Hermes safety rails.

**Files:**
- `~/.hermes/plugins/omh/tools/evidence_tool.py`

**Dependencies:** Task 1, Task 2 (for config: allowlist)

**Complexity:** Low (~90 lines)

**Tool Schema:**
```python
{
    "name": "omh_gather_evidence",
    "description": (
        "Run build/test/lint commands and collect evidence for verification. "
        "Commands must match the configured allowlist (build tools, test "
        "runners, linters). Returns structured results with exit codes, "
        "truncated output, and an all_pass summary."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "commands": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Shell commands to run (must match allowlist)"
            },
            "truncate": {
                "type": "integer",
                "description": "Max chars per command output (default: 2000, keeps tail)"
            },
            "workdir": {
                "type": "string",
                "description": "Working directory (default: cwd)"
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
    config = get_config()
    commands = args["commands"]
    allowlist = config.get("evidence", {}).get("allowlist_prefixes", [])
    max_cmds = config.get("evidence", {}).get("max_commands", 10)
    truncate = args.get("truncate", config.get("evidence", {}).get("default_truncate", 2000))
    timeout = args.get("timeout", config.get("evidence", {}).get("default_timeout", 120))
    workdir = args.get("workdir")

    if len(commands) > max_cmds:
        return json.dumps({"error": f"Too many commands ({len(commands)} > {max_cmds})"})

    # Validate commands against allowlist
    rejected = []
    for cmd in commands:
        cmd_stripped = cmd.strip()
        if not any(cmd_stripped.startswith(prefix) for prefix in allowlist):
            rejected.append(cmd_stripped)
    if rejected:
        return json.dumps({
            "error": "Commands not in allowlist",
            "rejected": rejected,
            "hint": "Add prefixes to config.yaml evidence.allowlist_prefixes"
        })

    results = []
    for cmd in commands:
        try:
            proc = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                cwd=workdir, timeout=timeout
            )
            output = (proc.stdout + proc.stderr)[-truncate:]
            results.append({
                "command": cmd,
                "exit_code": proc.returncode,
                "output": output,
                "truncated": len(proc.stdout + proc.stderr) > truncate,
                "passed": proc.returncode == 0
            })
        except subprocess.TimeoutExpired:
            results.append({
                "command": cmd, "exit_code": -1,
                "output": f"TIMEOUT after {timeout}s",
                "truncated": False, "passed": False
            })

    return json.dumps({
        "results": results,
        "all_pass": all(r["passed"] for r in results),
        "summary": f"{sum(1 for r in results if r['passed'])}/{len(results)} passed"
    })
```

**Acceptance Criteria:**
- `omh_gather_evidence(commands=["npm test"])` succeeds (matches allowlist)
- `omh_gather_evidence(commands=["rm -rf /"])` returns error (not in allowlist)
- Output truncation works (keeps tail)
- Timeout kills long-running commands
- `workdir` parameter works
- Returns JSON string
- Max command count enforced

---

### Task 6: Delegate Tool

**Description:** Register `omh_delegate` — wraps delegate_task with
role-aware prompt loading and context assembly. Requires parent_agent
from kwargs (hermes-agent PR prerequisite).

**Files:**
- `~/.hermes/plugins/omh/tools/delegate_tool.py`

**Dependencies:** Task 0 (PR), Task 1, Task 2

**Complexity:** Medium (~150 lines)

**Tool Schema:**
```python
{
    "name": "omh_delegate",
    "description": (
        "Delegate work to a role-specific subagent. Automatically loads "
        "the role prompt and constructs context. Simpler than raw "
        "delegate_task — just specify the role and goal."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "role": {
                "type": "string",
                "description": "Role: executor, verifier, architect, planner, "
                               "critic, analyst, security-reviewer, code-reviewer, "
                               "test-engineer, debugger"
            },
            "goal": {
                "type": "string",
                "description": "What the subagent should accomplish"
            },
            "task_context": {
                "type": "string",
                "description": "Project context (tech stack, conventions, paths)"
            },
            "learnings": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Learnings from prior tasks"
            },
            "previous_feedback": {
                "type": "string",
                "description": "Feedback from a prior rejection"
            },
            "toolsets": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Toolsets for subagent (default: terminal, file, web)"
            },
            "max_iterations": {
                "type": "integer",
                "description": "Max iterations (default: 50)"
            }
        },
        "required": ["role", "goal"]
    }
}
```

Note: `model_override` removed from v1. The delegate_task() function
signature (line 510-518 of delegate_tool.py) does NOT accept a model
parameter. Model selection is controlled by hermes-agent's delegation
config (`~/.hermes/config.yaml` delegation.provider/model), not per-call.
This can be revisited in v2 if delegate_task gains model routing.

**Handler logic:**
```python
def omh_delegate(args, **kwargs):
    # 1. Check parent_agent
    parent_agent = kwargs.get("parent_agent")
    if not parent_agent:
        return json.dumps({
            "error": "omh_delegate requires parent_agent in kwargs. "
            "Ensure hermes-agent includes the parent_agent-passthrough PR."
        })

    config = get_config()
    role = args["role"]
    goal = args["goal"]

    # 2. Load role prompt
    role_prompt = _load_role_prompt(role, config["role_prompts_dir"])

    # 3. Build context
    context_parts = []
    if role_prompt:
        context_parts.append(f"# Role: {role.title()}\n\n{role_prompt}")
    if args.get("task_context"):
        context_parts.append(f"## Project Context\n\n{args['task_context']}")
    if args.get("learnings"):
        context_parts.append(
            "## Learnings from Prior Tasks\n\n" +
            "\n".join(f"- {l}" for l in args["learnings"])
        )
    if args.get("previous_feedback"):
        context_parts.append(
            f"## Previous Rejection Feedback\n\n{args['previous_feedback']}"
        )
    context = "\n\n---\n\n".join(context_parts)

    # 4. Call delegate_task
    from tools.delegate_tool import delegate_task
    return delegate_task(
        goal=goal,
        context=context,
        toolsets=args.get("toolsets"),
        max_iterations=args.get("max_iterations"),
        parent_agent=parent_agent,
    )
```

**Acceptance Criteria:**
- `omh_delegate(role="executor", goal="Implement X")` spawns subagent
- Role prompt auto-loaded (graceful fallback if missing)
- Context string includes all provided components
- Unknown roles fall back with warning
- Returns delegate_task result (JSON string)
- Clear error if parent_agent missing

---

### Task 7: Hooks

**Description:** Implement lifecycle hooks for mode awareness and
interruption handling.

**Files:**
- `~/.hermes/plugins/omh/hooks/llm_hooks.py`
- `~/.hermes/plugins/omh/hooks/session_hooks.py`

**Dependencies:** Task 1, Task 3

**Complexity:** Low-Medium (~80 lines)

**Hook: pre_llm_call** (replaces both on_session_start and pre_llm_call from v1)

The agent loop passes `is_first_turn` to pre_llm_call (confirmed at
run_agent.py line 7152). Return values are consumed as context injection
(lines 7156-7163). This is the correct hook for both first-turn awareness
AND ongoing mode reminders.

```python
def pre_llm_call(**kwargs):
    """Inject OMH mode awareness into the conversation."""
    active = state_list_active()  # cached with 5s TTL
    if not active["modes"]:
        return None

    is_first_turn = kwargs.get("is_first_turn", False)

    if is_first_turn:
        # Full awareness: list all active modes with details
        lines = ["[OMH] Active modes detected:"]
        for m in active["modes"]:
            lines.append(
                f"  - {m['mode']}: phase={m.get('phase', '?')}, "
                f"age={m.get('age_seconds', '?')}s"
            )
        lines.append("Read the relevant state with omh_state(action='read') to continue.")
        return {"context": "\n".join(lines)}
    else:
        # Brief reminder for ongoing turns
        mode = active["modes"][0]
        return {"context": (
            f"[OMH] Active: {mode['mode']} "
            f"(phase: {mode.get('phase', '?')}, "
            f"iteration: {mode.get('iteration', '?')}). "
            f"Check omh_state(action='cancel_check') if unsure whether to continue."
        )}
```

**Hook: on_session_end**
```python
def on_session_end(**kwargs):
    """Mark active modes with interruption timestamp."""
    active = state_list_active()
    if not active["modes"]:
        return None
    for m in active["modes"]:
        current = state_read(m["mode"])
        if current.get("exists") and current.get("data", {}).get("active"):
            data = current["data"]
            data["_interrupted_at"] = datetime.utcnow().isoformat() + "Z"
            state_write(m["mode"], data)
    logger.info("OMH: Saved interruption state for %d active modes",
                len(active["modes"]))
```

**Acceptance Criteria:**
- `pre_llm_call` returns full context on first turn when modes active
- `pre_llm_call` returns brief reminder on subsequent turns
- `pre_llm_call` returns None when no active modes
- `on_session_end` writes `_interrupted_at` to active state files
- All hooks exception-safe and handle missing `.omh/state/` directory
- `state_list_active()` cache prevents filesystem I/O on every LLM call

---

### Task 8: Test Suite

**Description:** Tests verifiable without a full Hermes session.

**Files:**
- `~/.hermes/plugins/omh/tests/test_state.py`
- `~/.hermes/plugins/omh/tests/test_evidence.py`
- `~/.hermes/plugins/omh/tests/test_delegate.py`
- `~/.hermes/plugins/omh/tests/test_hooks.py`

**Dependencies:** Tasks 1-7

**Complexity:** Medium (~180 lines)

**Acceptance Criteria:**
- `test_state.py`: round-trip write/read/clear, atomic safety, staleness, meta envelope with schema_version, cancel signal lifecycle
- `test_evidence.py`: allowlist enforcement, multi-command, truncation, timeout, max_commands
- `test_delegate.py`: role prompt loading, context assembly (mock delegate_task)
- `test_hooks.py`: pre_llm_call first-turn vs subsequent, on_session_end interruption state
- All tests use tmp_path (no real filesystem side effects)
- Tests pass with `python -m pytest ~/.hermes/plugins/omh/tests/ -v`

---

### Task 9: Skill Refactoring (omh-ralph)

**Description:** Refactor omh-ralph to use the 3 plugin tools.

**Dependencies:** Tasks 1-7

**Complexity:** Medium

**Acceptance Criteria:**
- State: `omh_state(action="read", mode="ralph")` replaces manual JSON
- Delegation: `omh_delegate(role="executor", ...)` replaces manual prompt assembly
- Evidence: `omh_gather_evidence(commands=[...])` replaces manual subprocess
- Cancel: `omh_state(action="cancel_check", mode="ralph")` replaces manual file reads
- Skill is ~40% shorter
- Works in a real Hermes session with plugin installed

---

## Descoped from v1

### Model Routing (was in v1 config)

`delegate_task()` signature (delegate_tool.py lines 510-518):
```python
def delegate_task(
    goal=None, context=None, toolsets=None, tasks=None,
    max_iterations=None, acp_command=None, acp_args=None,
    parent_agent=None,
) -> str:
```

There is no `model` parameter. Model selection is resolved internally via
`_resolve_delegation_credentials()` which reads from `~/.hermes/config.yaml`
delegation section. Per-call model routing would require either:
- A delegate_task enhancement to accept model override
- Setting config before each call (race condition in concurrent scenarios)

**Decision:** Descope from v1. Users configure delegation model globally in
`~/.hermes/config.yaml`. Revisit if delegate_task gains per-call model support.

### Session ID Scoping

Removed entirely from v1. Single-user CLI doesn't need it. Can be added
in v2 if multi-session isolation becomes necessary.

### /omh Slash Command

Useful (`/omh status`, `/omh cancel ralph`) but not required for v1.
Recommend as Task 10 post-launch.

---

## Risks

### R1: hermes-agent PR acceptance (CRITICAL)
**Risk:** The PR to pass parent_agent through handle_function_call may be
rejected or delayed.
**Mitigation:** The PR is minimal and backwards-compatible. If blocked,
the thread-local monkey-patch fallback works but is fragile. Without either
fix, omh_delegate cannot function — the plugin would ship with only
omh_state and omh_gather_evidence (still useful for skill simplification).

### R2: delegate_task import path
**Risk:** `tools.delegate_tool` may not be importable from plugin context.
**Mitigation:** Plugin's `__init__.py` runs inside hermes-agent process.
Test early (Task 6). Fallback: `sys.modules` lookup.

### R3: pre_llm_call performance
**Risk:** `state_list_active()` does filesystem I/O on every LLM call.
**Mitigation:** 5-second TTL cache. If `.omh/state/` doesn't exist, return
immediately with no I/O.

### R4: Evidence allowlist too restrictive
**Risk:** Users need commands not in default allowlist.
**Mitigation:** Allowlist is configurable in config.yaml. Document how to
extend it. Consider adding `evidence.allow_all: true` escape hatch for
advanced users.

### R5: Atomic write on NFS/Windows
**Risk:** `os.replace()` not guaranteed atomic on all filesystems.
**Mitigation:** Document Linux/macOS local filesystem requirement.

---

## Dependency Graph

```
Task 0 (hermes-agent PR) ─────────────────────────┐
                                                    v
Task 1 (Scaffold)                            Task 6 (Delegate)
  ├─> Task 2 (Config)
  │     ├─> Task 3 (State Engine)
  │     │     └─> Task 4 (State Tool)
  │     └─> Task 5 (Evidence Tool)
  └─> Task 7 (Hooks) ← depends on Task 3
        └─> Task 8 (Tests) ← depends on all above
              └─> Task 9 (Skill Refactor)
```

**Critical path:** 0 → 1 → 2 → 3 → 4 → 7 → 8 → 9
**Parallelizable:** Tasks 4, 5, 6 can be built in parallel after Task 2+3
(Task 6 also needs Task 0)

---

## Estimated Timeline

| Day | Tasks | Milestone |
|-----|-------|-----------|
| 1   | 0, 1, 2, 3 | PR submitted, plugin loads, state engine complete |
| 2   | 4, 5, 6 | All 3 tools registered and functional |
| 3   | 7, 8   | Hooks + test suite |
| 4   | 9      | omh-ralph refactored and working |

---

## Appendix: _meta Envelope Schema

```json
{
  "_meta": {
    "written_at": "2026-04-07T10:15:30.123456Z",
    "mode": "ralph",
    "schema_version": 1
  },
  "active": true,
  "phase": "execute",
  "iteration": 3,
  "cancel_requested": false,
  "cancel_reason": null,
  "cancel_at": null
}
```

When returned by `state_read`, `_meta` is stripped. The `stale` and
`age_seconds` fields are computed from `_meta.written_at` at read time.
