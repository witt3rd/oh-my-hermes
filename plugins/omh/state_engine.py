"""
OMH State Engine — atomic, versioned state management for .omh/ directory.

All state operations go through this module. Skills call the omh_state tool,
which delegates here. Hooks also use these functions directly.
"""

import json
import os
import time
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = 1


def _state_dir() -> Path:
    """Resolve the .omh/state/ directory relative to cwd."""
    return Path.cwd() / ".omh" / "state"


def _logs_dir() -> Path:
    """Resolve the .omh/logs/ directory relative to cwd."""
    return Path.cwd() / ".omh" / "logs"


def _state_path(mode: str) -> Path:
    """Path to a mode's state file."""
    return _state_dir() / f"{mode}-state.json"


def _meta_envelope(data: dict) -> dict:
    """Wrap data with _meta tracking fields."""
    return {
        **data,
        "_meta": {
            "schema_version": SCHEMA_VERSION,
            "written_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "written_by": "omh-plugin",
        },
    }


def _atomic_write(path: Path, data: dict) -> None:
    """Write JSON atomically: temp file → fsync → rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, indent=2, default=str) + "\n"

    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent), suffix=".tmp", prefix=f".{path.stem}_"
    )
    try:
        os.write(fd, content.encode("utf-8"))
        os.fsync(fd)
        os.close(fd)
        os.rename(tmp_path, str(path))
    except Exception:
        os.close(fd) if not os.get_inheritable(fd) else None
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def state_read(mode: str) -> Dict[str, Any]:
    """Read a mode's state file.

    Returns dict with:
      exists: bool
      data: dict or None
      stale: bool (>2h since last write)
      age_seconds: float or None
    """
    path = _state_path(mode)
    if not path.exists():
        return {"exists": False, "data": None, "stale": False, "age_seconds": None}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return {"exists": True, "data": None, "stale": False,
                "error": f"Failed to read state: {e}"}

    meta = raw.get("_meta", {})
    written_at = meta.get("written_at")
    age = None
    stale = False
    if written_at:
        try:
            import datetime
            wt = datetime.datetime.fromisoformat(written_at.replace("Z", "+00:00"))
            age = (datetime.datetime.now(datetime.timezone.utc) - wt).total_seconds()
            stale = age > 7200  # 2 hours
        except (ValueError, TypeError):
            pass

    return {"exists": True, "data": raw, "stale": stale, "age_seconds": age}


def state_write(mode: str, data: dict) -> Dict[str, Any]:
    """Write a mode's state file atomically with _meta envelope."""
    if not isinstance(data, dict):
        return {"error": "data must be a JSON object"}

    envelope = _meta_envelope(data)
    path = _state_path(mode)
    try:
        _atomic_write(path, envelope)
        return {"success": True, "path": str(path)}
    except Exception as e:
        return {"error": f"Failed to write state: {e}"}


def state_clear(mode: str) -> Dict[str, Any]:
    """Delete a mode's state file."""
    path = _state_path(mode)
    if not path.exists():
        return {"success": True, "existed": False}
    try:
        path.unlink()
        return {"success": True, "existed": True}
    except OSError as e:
        return {"error": f"Failed to delete state: {e}"}


def state_check(mode: str) -> Dict[str, Any]:
    """Quick status check without full data load."""
    path = _state_path(mode)
    if not path.exists():
        return {"exists": False, "active": False, "phase": None}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        meta = raw.get("_meta", {})
        written_at = meta.get("written_at")
        age = None
        stale = False
        if written_at:
            try:
                import datetime
                wt = datetime.datetime.fromisoformat(written_at.replace("Z", "+00:00"))
                age = (datetime.datetime.now(datetime.timezone.utc) - wt).total_seconds()
                stale = age > 7200
            except (ValueError, TypeError):
                pass

        return {
            "exists": True,
            "active": raw.get("active", False),
            "phase": raw.get("phase"),
            "stale": stale,
            "age_seconds": age,
        }
    except (json.JSONDecodeError, OSError):
        return {"exists": True, "active": False, "phase": None, "error": "corrupt"}


def state_list_active() -> Dict[str, Any]:
    """List all active OMH modes."""
    sd = _state_dir()
    if not sd.exists():
        return {"modes": []}

    modes = []
    for f in sd.glob("*-state.json"):
        mode_name = f.stem.replace("-state", "")
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
            if raw.get("active", False):
                modes.append({
                    "mode": mode_name,
                    "phase": raw.get("phase"),
                    "iteration": raw.get("iteration"),
                })
        except (json.JSONDecodeError, OSError):
            continue

    return {"modes": modes}


def cancel_set(mode: str, reason: str = "user request",
               requested_by: str = "user") -> Dict[str, Any]:
    """Set cancel fields in a mode's state file."""
    result = state_read(mode)
    if not result["exists"] or result["data"] is None:
        return {"error": f"No active state for mode '{mode}'"}

    data = result["data"]
    # Remove _meta before merging (will be re-added by state_write)
    data.pop("_meta", None)
    data["cancel_requested"] = True
    data["cancel_reason"] = reason
    data["cancel_requested_by"] = requested_by
    data["cancel_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    return state_write(mode, data)


def cancel_check(mode: str, ttl_seconds: int = 30) -> Dict[str, Any]:
    """Check if a mode has a pending cancel signal within TTL."""
    result = state_read(mode)
    if not result["exists"] or result["data"] is None:
        return {"cancelled": False}

    data = result["data"]
    if not data.get("cancel_requested"):
        return {"cancelled": False}

    cancel_at = data.get("cancel_at")
    if cancel_at:
        try:
            import datetime
            ct = datetime.datetime.fromisoformat(cancel_at.replace("Z", "+00:00"))
            age = (datetime.datetime.now(datetime.timezone.utc) - ct).total_seconds()
            if age > ttl_seconds:
                return {"cancelled": False, "reason": "cancel signal expired",
                        "age_seconds": age}
        except (ValueError, TypeError):
            pass

    return {
        "cancelled": True,
        "reason": data.get("cancel_reason", "unknown"),
        "requested_by": data.get("cancel_requested_by", "unknown"),
    }
