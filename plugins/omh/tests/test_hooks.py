"""Tests for lifecycle hooks — pre_llm_call and on_session_end."""

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import plugins.omh.omh_config as omh_config_module
from plugins.omh.hooks.llm_hooks import pre_llm_call
from plugins.omh.hooks.session_hooks import on_session_end
from plugins.omh.omh_state import state_read, state_write


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    omh_config_module._config_cache = {
        "state_dir": ".omh/state",
        "staleness_hours": 2,
        "cancel_ttl_seconds": 30,
        "evidence": {},
    }
    # Invalidate list cache
    from plugins.omh import omh_state as mod
    mod._list_cache["expires_at"] = 0
    yield
    omh_config_module._config_cache = None
    mod._list_cache["expires_at"] = 0


# ---------------------------------------------------------------------------
# pre_llm_call — no active modes
# ---------------------------------------------------------------------------

def test_pre_llm_call_no_active_modes():
    result = pre_llm_call(is_first_turn=True)
    assert result is None


def test_pre_llm_call_no_active_modes_subsequent():
    result = pre_llm_call(is_first_turn=False)
    assert result is None


# ---------------------------------------------------------------------------
# pre_llm_call — first turn with active modes
# ---------------------------------------------------------------------------

def test_pre_llm_call_first_turn_full_context():
    state_write("ralph", {"active": True, "phase": "execute"})

    from plugins.omh import omh_state as mod
    mod._list_cache["expires_at"] = 0

    result = pre_llm_call(is_first_turn=True)
    assert result is not None
    assert "context" in result
    ctx = result["context"]
    assert "ralph" in ctx
    assert "omh_state" in ctx
    assert "read" in ctx


def test_pre_llm_call_first_turn_lists_all_modes():
    state_write("ralph", {"active": True, "phase": "execute"})
    state_write("autopilot", {"active": True, "phase": "execution"})

    from plugins.omh import omh_state as mod
    mod._list_cache["expires_at"] = 0

    result = pre_llm_call(is_first_turn=True)
    ctx = result["context"]
    assert "ralph" in ctx
    assert "autopilot" in ctx


# ---------------------------------------------------------------------------
# pre_llm_call — subsequent turns (brief reminder)
# ---------------------------------------------------------------------------

def test_pre_llm_call_subsequent_brief():
    state_write("ralph", {"active": True, "phase": "verify"})

    from plugins.omh import omh_state as mod
    mod._list_cache["expires_at"] = 0

    result = pre_llm_call(is_first_turn=False)
    assert result is not None
    ctx = result["context"]
    assert "ralph" in ctx
    assert "cancel_check" in ctx
    # Should be shorter than first-turn (no full listing)
    assert len(ctx) < 300


# ---------------------------------------------------------------------------
# on_session_end — marks active modes with _interrupted_at
# ---------------------------------------------------------------------------

def test_on_session_end_marks_interrupted():
    state_write("ralph", {"active": True, "phase": "execute", "iteration": 3})

    from plugins.omh import omh_state as mod
    mod._list_cache["expires_at"] = 0

    on_session_end()

    result = state_read("ralph")
    assert "_interrupted_at" in result["data"]


def test_on_session_end_ignores_inactive_modes():
    state_write("ralph", {"active": False, "phase": "complete"})

    from plugins.omh import omh_state as mod
    mod._list_cache["expires_at"] = 0

    on_session_end()

    result = state_read("ralph")
    assert "_interrupted_at" not in result["data"]


def test_on_session_end_no_modes_noop():
    # Should not raise, should not create any files
    on_session_end()
    assert not Path(".omh/state").exists() or list(Path(".omh/state").glob("*.json")) == []


# ---------------------------------------------------------------------------
# Exception safety
# ---------------------------------------------------------------------------

def test_pre_llm_call_exception_safe():
    with patch("plugins.omh.hooks.llm_hooks.state_list_active", side_effect=Exception("boom")):
        result = pre_llm_call(is_first_turn=True)
    assert result is None


def test_on_session_end_exception_safe():
    with patch("plugins.omh.hooks.session_hooks.state_list_active", side_effect=Exception("boom")):
        on_session_end()  # must not raise


# ---------------------------------------------------------------------------
# pre_llm_call — role prompt injection via [omh-role:NAME] marker
# ---------------------------------------------------------------------------

def test_pre_llm_call_injects_role_on_first_turn(tmp_path, monkeypatch):
    role_file = tmp_path / "role-executor.md"
    role_file.write_text("You are an executor agent.")
    monkeypatch.setattr("plugins.omh.omh_roles._REFERENCES_DIR", tmp_path)

    result = pre_llm_call(is_first_turn=True, user_message="[omh-role:executor] Do the task")
    assert result is not None
    ctx = result["context"]
    assert "executor" in ctx
    assert "You are an executor agent." in ctx


def test_pre_llm_call_no_marker_unchanged():
    # No marker, no active modes → None
    result = pre_llm_call(is_first_turn=True, user_message="Do the task with no role")
    assert result is None


def test_pre_llm_call_unknown_role_warning(tmp_path, monkeypatch):
    monkeypatch.setattr("plugins.omh.omh_roles._REFERENCES_DIR", tmp_path)

    result = pre_llm_call(is_first_turn=True, user_message="[omh-role:ghost] Do it")
    assert result is not None
    ctx = result["context"]
    assert "WARNING" in ctx
    assert "ghost" in ctx


def test_pre_llm_call_role_plus_active_mode(tmp_path, monkeypatch):
    role_file = tmp_path / "role-verifier.md"
    role_file.write_text("You are a verifier.")
    monkeypatch.setattr("plugins.omh.omh_roles._REFERENCES_DIR", tmp_path)

    state_write("ralph", {"active": True, "phase": "verify"})
    from plugins.omh import omh_state as mod
    mod._list_cache["expires_at"] = 0

    result = pre_llm_call(is_first_turn=True, user_message="[omh-role:verifier] Check the work")
    assert result is not None
    ctx = result["context"]
    assert "You are a verifier." in ctx
    assert "ralph" in ctx


def test_pre_llm_call_subsequent_turn_no_role_injection(tmp_path, monkeypatch):
    role_file = tmp_path / "role-executor.md"
    role_file.write_text("You are an executor.")
    monkeypatch.setattr("plugins.omh.omh_roles._REFERENCES_DIR", tmp_path)

    # Marker present but is_first_turn=False → no role injection
    result = pre_llm_call(is_first_turn=False, user_message="[omh-role:executor] Do it")
    assert result is None


def test_pre_llm_call_no_user_message_no_crash():
    result = pre_llm_call(is_first_turn=True)
    assert result is None


# ---------------------------------------------------------------------------
# pre_tool_call — delegate_task role validation
# ---------------------------------------------------------------------------

def test_pre_tool_call_valid_role_passes(tmp_path, monkeypatch):
    role_file = tmp_path / "role-executor.md"
    role_file.write_text("executor prompt")
    monkeypatch.setattr("plugins.omh.omh_roles._REFERENCES_DIR", tmp_path)

    from plugins.omh.hooks.tool_hooks import pre_tool_call
    # args= is the kwarg Hermes actually delivers (hermes_cli/plugins.py:1816).
    result = pre_tool_call(
        tool_name="delegate_task",
        args={"goal": "[omh-role:executor] Do it"},
    )
    assert result is None


def test_pre_tool_call_unknown_role_warns(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr("plugins.omh.omh_roles._REFERENCES_DIR", tmp_path)

    from plugins.omh.hooks.tool_hooks import pre_tool_call
    with caplog.at_level(logging.WARNING, logger="plugins.omh.hooks.tool_hooks"):
        result = pre_tool_call(
            tool_name="delegate_task",
            args={"goal": "[omh-role:ghost] Do it"},
        )
    # Non-blocking: returns None. The warning is the observable effect.
    assert result is None
    assert any("ghost" in r.message and "unknown role" in r.message for r in caplog.records)


def test_pre_tool_call_real_hermes_kwarg_is_honoured(tmp_path, monkeypatch, caplog):
    """Regression guard: the hook must read `args`, not an invented `tool_input`."""
    monkeypatch.setattr("plugins.omh.omh_roles._REFERENCES_DIR", tmp_path)

    from plugins.omh.hooks.tool_hooks import pre_tool_call
    with caplog.at_level(logging.WARNING, logger="plugins.omh.hooks.tool_hooks"):
        pre_tool_call(tool_name="delegate_task", args={"goal": "[omh-role:typo] x"})
    assert any("unknown role" in r.message for r in caplog.records), (
        "hook ignored the real Hermes `args=` kwarg"
    )


def test_pre_tool_call_batch_tasks_validated(tmp_path, monkeypatch, caplog):
    """Batch delegate_task (tasks=[...]) goals are validated too."""
    monkeypatch.setattr("plugins.omh.omh_roles._REFERENCES_DIR", tmp_path)

    from plugins.omh.hooks.tool_hooks import pre_tool_call
    with caplog.at_level(logging.WARNING, logger="plugins.omh.hooks.tool_hooks"):
        pre_tool_call(
            tool_name="delegate_task",
            args={"tasks": [{"goal": "no marker"}, {"goal": "[omh-role:ghost] x"}]},
        )
    assert any("ghost" in r.message for r in caplog.records)


def test_pre_tool_call_no_marker_passes(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr("plugins.omh.omh_roles._REFERENCES_DIR", tmp_path)

    from plugins.omh.hooks.tool_hooks import pre_tool_call
    with caplog.at_level(logging.WARNING, logger="plugins.omh.hooks.tool_hooks"):
        result = pre_tool_call(
            tool_name="delegate_task",
            args={"goal": "Implement feature X"},
        )
    assert result is None
    assert not caplog.records


def test_pre_tool_call_non_delegate_ignored():
    from plugins.omh.hooks.tool_hooks import pre_tool_call
    result = pre_tool_call(
        tool_name="read_file",
        args={"path": "/foo/bar"},
    )
    assert result is None


def test_pre_tool_call_no_goal_passes():
    from plugins.omh.hooks.tool_hooks import pre_tool_call
    result = pre_tool_call(tool_name="delegate_task", args={})
    assert result is None


# ---------------------------------------------------------------------------
# pre_llm_call — missing is_first_turn kwarg logs debug
# ---------------------------------------------------------------------------

def test_pre_llm_call_missing_is_first_turn_logs_debug(caplog):
    with caplog.at_level(logging.DEBUG, logger="plugins.omh.hooks.llm_hooks"):
        result = pre_llm_call()
    assert result is None
    assert any("is_first_turn" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# pre_llm_call — unknown role on first turn
# ---------------------------------------------------------------------------

def test_pre_llm_call_unknown_role_first_turn(tmp_path, monkeypatch):
    monkeypatch.setattr("plugins.omh.omh_roles._REFERENCES_DIR", tmp_path)
    result = pre_llm_call(is_first_turn=True, user_message="[omh-role:nonexistent-role-xyz] do stuff")
    assert result is not None
    assert "context" in result
    assert "Unknown role" in result["context"]
    assert "nonexistent-role-xyz" in result["context"]


# ---------------------------------------------------------------------------
# pre_llm_call — multiple active modes on subsequent turn
# ---------------------------------------------------------------------------

def test_pre_llm_call_multi_mode_subsequent_turn(monkeypatch):
    monkeypatch.setattr(
        "plugins.omh.hooks.llm_hooks.state_list_active",
        lambda: {
            "modes": [
                {"mode": "ralph", "phase": "execute", "age_seconds": 10},
                {"mode": "ralplan", "phase": "planning", "age_seconds": 5},
            ]
        },
    )
    result = pre_llm_call(is_first_turn=False)
    assert result is not None
    assert "context" in result
    ctx = result["context"]
    assert "ralph" in ctx
    assert "ralplan" in ctx


# ---------------------------------------------------------------------------
# session_hooks — mode in active list but state_read returns exists=False
# ---------------------------------------------------------------------------

def test_session_end_skips_mode_with_no_state_file(monkeypatch):
    monkeypatch.setattr(
        "plugins.omh.hooks.session_hooks.state_list_active",
        lambda: {"modes": [{"mode": "ralph"}]},
    )
    monkeypatch.setattr(
        "plugins.omh.hooks.session_hooks.state_read",
        lambda mode: {"exists": False, "data": {}},
    )
    on_session_end()  # must not raise


# ---------------------------------------------------------------------------
# session_hooks — state exists but active=False
# ---------------------------------------------------------------------------

def test_session_end_skips_inactive_mode(monkeypatch):
    mock_write = MagicMock()
    monkeypatch.setattr(
        "plugins.omh.hooks.session_hooks.state_list_active",
        lambda: {"modes": [{"mode": "ralph"}]},
    )
    monkeypatch.setattr(
        "plugins.omh.hooks.session_hooks.state_read",
        lambda mode, instance_id=None: {"exists": True, "data": {"active": False}},
    )
    monkeypatch.setattr("plugins.omh.hooks.session_hooks.state_write", mock_write)
    on_session_end()
    mock_write.assert_not_called()


# ---------------------------------------------------------------------------
# session_hooks — per-instance modes keep their own file (regression)
# ---------------------------------------------------------------------------

def test_session_end_stamps_per_instance_mode(monkeypatch):
    """Regression: instance_id must be threaded into read AND write.

    state_list_active() reports {"mode", "instance_id"} for per-instance files;
    dropping instance_id wrote the wrong file (and missed the instance's own).
    """
    seen = {}
    mock_write = MagicMock()

    def fake_read(mode, instance_id=None):
        seen["read"] = (mode, instance_id)
        return {"exists": True, "data": {"active": True, "phase": "search"}}

    def fake_write(mode, data, instance_id=None):
        seen["write"] = (mode, instance_id, data.get("_interrupted_at") is not None)

    monkeypatch.setattr(
        "plugins.omh.hooks.session_hooks.state_list_active",
        lambda: {"modes": [{"mode": "deep-research", "instance_id": "topic-a"}]},
    )
    monkeypatch.setattr("plugins.omh.hooks.session_hooks.state_read", fake_read)
    monkeypatch.setattr("plugins.omh.hooks.session_hooks.state_write", fake_write)

    on_session_end()

    assert seen["read"] == ("deep-research", "topic-a")
    assert seen["write"][:2] == ("deep-research", "topic-a")
    assert seen["write"][2] is True


# ---------------------------------------------------------------------------
# session_hooks — state_write raises exception
# ---------------------------------------------------------------------------

def test_session_end_handles_write_exception(monkeypatch, caplog):
    monkeypatch.setattr(
        "plugins.omh.hooks.session_hooks.state_list_active",
        lambda: {"modes": [{"mode": "ralph"}]},
    )
    monkeypatch.setattr(
        "plugins.omh.hooks.session_hooks.state_read",
        lambda mode, instance_id=None: {"exists": True, "data": {"active": True, "phase": "execute"}},
    )
    monkeypatch.setattr(
        "plugins.omh.hooks.session_hooks.state_write",
        MagicMock(side_effect=OSError("disk full")),
    )
    with caplog.at_level(logging.WARNING, logger="plugins.omh.hooks.session_hooks"):
        on_session_end()  # must not raise
    assert any("ralph" in r.message or "disk full" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# tool_hooks — malformed / unexpected args never raise
# ---------------------------------------------------------------------------

def test_pre_tool_call_non_dict_args_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr("plugins.omh.omh_roles._REFERENCES_DIR", tmp_path)
    from plugins.omh.hooks.tool_hooks import pre_tool_call
    assert pre_tool_call(tool_name="delegate_task", args="not a dict") is None
    assert pre_tool_call(tool_name="delegate_task", args=None) is None
    assert pre_tool_call(tool_name="delegate_task") is None


def test_pre_tool_call_malformed_tasks_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr("plugins.omh.omh_roles._REFERENCES_DIR", tmp_path)
    from plugins.omh.hooks.tool_hooks import pre_tool_call
    assert pre_tool_call(tool_name="delegate_task", args={"tasks": "nope"}) is None
    assert pre_tool_call(tool_name="delegate_task", args={"tasks": [None, 5]}) is None
