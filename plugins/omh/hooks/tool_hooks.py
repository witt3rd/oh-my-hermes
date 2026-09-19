"""
pre_tool_call hook — validate [omh-role:NAME] markers in delegate_task calls.

Intercepts delegate_task tool calls in the parent session and warns when an
[omh-role:NAME] marker references an unknown role. This is defense-in-depth:
the hook catches typos at delegation time (fail-fast) before the subagent starts.

Non-blocking by design. A pre_tool_call callback's only honoured returns are
{"action": "block"|"approve"|"modify"} (see hermes_cli/plugins.py::
_get_pre_tool_call_directive_details); every other shape is silently ignored, so
a warning cannot ride the return value. This hook logs instead of returning, and
the pre_llm_call hook in the subagent session handles role prompt injection.

Hermes delivers this hook as ``tool_name=..., args={...}``.
"""

import logging

logger = logging.getLogger(__name__)


def _goal_strings(args: dict) -> list[str]:
    """Every goal string in a delegate_task call.

    Covers both documented call shapes: single (``goal=``) and batch
    (``tasks=[{"goal": ...}, ...]``).
    """
    goals: list[str] = []
    goal = args.get("goal")
    if isinstance(goal, str) and goal:
        goals.append(goal)
    tasks = args.get("tasks")
    if isinstance(tasks, list):
        for task in tasks:
            if isinstance(task, dict):
                task_goal = task.get("goal")
                if isinstance(task_goal, str) and task_goal:
                    goals.append(task_goal)
    return goals


def pre_tool_call(**kwargs) -> None:
    """Warn (log-only) on unknown [omh-role:NAME] markers in delegate_task goals."""
    if kwargs.get("tool_name") != "delegate_task":
        return None

    args = kwargs.get("args")
    if not isinstance(args, dict):
        return None

    goals = _goal_strings(args)
    if not goals:
        return None

    from ..omh_roles import debug_print, extract_role_marker, get_role_catalog

    catalog = get_role_catalog()
    available = ", ".join(sorted(catalog.keys())) or "(none)"

    for goal in goals:
        role_name = extract_role_marker(goal)
        if role_name is None:
            continue
        debug_print(f"pre_tool_call: delegate_task with role '{role_name}' detected")
        if role_name not in catalog:
            debug_print(
                f"pre_tool_call: unknown role '{role_name}' in delegate_task — "
                f"warning only (non-blocking). Available: {available}"
            )
            logger.warning(
                "omh pre_tool_call: unknown role '%s' in delegate_task goal. "
                "Available: %s",
                role_name,
                available,
            )

    return None
