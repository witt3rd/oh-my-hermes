"""
Oh My Hermes (OMH) Plugin — Infrastructure layer for OMH orchestration skills.

Provides:
  - omh_state tool: atomic state management for .omh/ directory
  - omh_gather_evidence tool: run build/test/lint with safety allowlist
  - on_session_end hook: preserve state on interruption
  - pre_llm_call hook: inject mode awareness context
"""

import json
import logging

logger = logging.getLogger(__name__)


# ── Tool Schemas ─────────────────────────────────────────────────────────

OMH_STATE_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["read", "write", "clear", "check", "list", "cancel", "cancel_check"],
            "description": (
                "Action to perform. "
                "'read': full state data for a mode. "
                "'write': atomically write state (with _meta envelope). "
                "'clear': delete a mode's state file. "
                "'check': quick status (exists/active/phase/stale). "
                "'list': all active OMH modes. "
                "'cancel': set cancel signal on a mode. "
                "'cancel_check': check if cancel signal is pending (30s TTL)."
            ),
        },
        "mode": {
            "type": "string",
            "description": "Mode name (e.g., 'ralph', 'autopilot', 'interview'). Required for all actions except 'list'.",
        },
        "data": {
            "type": "object",
            "description": "State data to write. Required for 'write' action. Must be a JSON object.",
        },
        "reason": {
            "type": "string",
            "description": "Cancel reason. Used with 'cancel' action.",
        },
    },
    "required": ["action"],
}

OMH_EVIDENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "commands": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Shell commands to run (e.g., ['npm run build', 'npm test', 'npm run lint']). "
                "Must match the configured allowlist. Max 10 commands."
            ),
        },
        "workdir": {
            "type": "string",
            "description": "Working directory. Defaults to current directory.",
        },
        "truncate": {
            "type": "integer",
            "description": "Max chars per command output (keeps the tail). Default: 2000.",
        },
    },
    "required": ["commands"],
}


# ── Tool Handlers ────────────────────────────────────────────────────────

def _handle_omh_state(args: dict, **kwargs) -> str:
    """Dispatch omh_state actions to the state engine."""
    from .state_engine import (
        state_read, state_write, state_clear, state_check,
        state_list_active, cancel_set, cancel_check,
    )

    action = args.get("action")
    mode = args.get("mode")

    if action == "list":
        return json.dumps(state_list_active())

    if not mode:
        return json.dumps({"error": "mode is required for all actions except 'list'"})

    if action == "read":
        return json.dumps(state_read(mode))
    elif action == "write":
        data = args.get("data")
        if data is None:
            return json.dumps({"error": "data is required for 'write' action"})
        return json.dumps(state_write(mode, data))
    elif action == "clear":
        return json.dumps(state_clear(mode))
    elif action == "check":
        return json.dumps(state_check(mode))
    elif action == "cancel":
        reason = args.get("reason", "user request")
        return json.dumps(cancel_set(mode, reason=reason))
    elif action == "cancel_check":
        return json.dumps(cancel_check(mode))
    else:
        return json.dumps({"error": f"Unknown action: {action}"})


def _handle_omh_gather_evidence(args: dict, **kwargs) -> str:
    """Run build/test/lint commands and capture output."""
    from .evidence import gather_evidence

    commands = args.get("commands", [])
    if not commands:
        return json.dumps({"error": "commands list is required"})

    workdir = args.get("workdir")
    truncate = args.get("truncate")

    result = gather_evidence(commands, workdir=workdir, truncate=truncate)
    return json.dumps(result)


# ── Hooks ────────────────────────────────────────────────────────────────

# Cache for pre_llm_call performance (avoid filesystem reads every turn)
_active_modes_cache = {"modes": [], "checked_at": 0}
_CACHE_TTL = 5.0  # seconds


def _hook_on_session_end(**kwargs) -> None:
    """Ensure OMH state is cleanly saved when session ends."""
    from .state_engine import state_list_active, state_read, state_write
    import time

    try:
        active = state_list_active()
        for mode_info in active.get("modes", []):
            mode = mode_info["mode"]
            result = state_read(mode)
            if result["exists"] and result["data"]:
                data = result["data"]
                data.pop("_meta", None)
                data["_interrupted_at"] = time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                )
                state_write(mode, data)
                logger.info(
                    "OMH: saved interrupted state for mode '%s' (phase: %s)",
                    mode, mode_info.get("phase"),
                )
    except Exception as e:
        logger.warning("OMH on_session_end hook failed: %s", e)


def _hook_pre_llm_call(**kwargs) -> dict:
    """Inject mode-awareness context when OMH modes are active."""
    import time
    from .state_engine import state_list_active

    now = time.time()

    # Fast path: check cache
    if now - _active_modes_cache["checked_at"] < _CACHE_TTL:
        modes = _active_modes_cache["modes"]
    else:
        # Check filesystem — but fast path if .omh/state/ doesn't exist
        from pathlib import Path
        state_dir = Path.cwd() / ".omh" / "state"
        if not state_dir.exists():
            _active_modes_cache["modes"] = []
            _active_modes_cache["checked_at"] = now
            return {}

        try:
            active = state_list_active()
            modes = active.get("modes", [])
        except Exception:
            modes = []
        _active_modes_cache["modes"] = modes
        _active_modes_cache["checked_at"] = now

    if not modes:
        return {}

    # Build context injection
    parts = ["[OMH] Active orchestration modes detected:"]
    for m in modes:
        phase = m.get("phase", "unknown")
        iteration = m.get("iteration")
        iter_str = f", iteration {iteration}" if iteration else ""
        parts.append(f"  - {m['mode']}: phase={phase}{iter_str}")
    parts.append("Read .omh/state/ files for full context. Use omh_state tool for state management.")

    is_first = kwargs.get("is_first_turn", False)
    if is_first:
        parts.append("This appears to be a new session resuming an active OMH mode.")

    return {"context": "\n".join(parts)}


# ── Plugin Registration ──────────────────────────────────────────────────

def register(ctx):
    """Called by Hermes plugin system on load."""
    logger.info("OMH plugin v0.1.0 registering...")

    # Register tools
    ctx.register_tool(
        name="omh_state",
        toolset="omh",
        schema=OMH_STATE_SCHEMA,
        handler=_handle_omh_state,
        description=(
            "Manage OMH orchestration state (.omh/state/ directory). "
            "Actions: read, write, clear, check, list, cancel, cancel_check. "
            "Use for ralph/autopilot/interview state persistence."
        ),
        emoji="📋",
    )

    ctx.register_tool(
        name="omh_gather_evidence",
        toolset="omh",
        schema=OMH_EVIDENCE_SCHEMA,
        handler=_handle_omh_gather_evidence,
        description=(
            "Run build/test/lint commands and capture output for verification. "
            "Commands must match the configured allowlist. "
            "Output is truncated to 2000 chars (configurable). "
            "Use during ralph verification and autopilot QA phases."
        ),
        emoji="🔍",
    )

    # Register hooks
    ctx.register_hook("on_session_end", _hook_on_session_end)
    ctx.register_hook("pre_llm_call", _hook_pre_llm_call)

    logger.info("OMH plugin registered: 2 tools, 2 hooks")
