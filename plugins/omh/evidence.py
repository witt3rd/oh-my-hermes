"""
OMH Evidence Gathering — run build/test/lint commands safely and capture output.

Uses shlex.split + shell=False for security. Commands must match a configurable
allowlist of prefixes.
"""

import json
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


# Default allowlist (overridden by config.yaml)
DEFAULT_ALLOWLIST = [
    "npm ", "npx ", "yarn ", "pnpm ",
    "cargo ", "make", "cmake ",
    "go ", "python ", "python3 ", "pytest",
    "pip ", "uv ", "ruff ", "mypy ", "tsc", "eslint", "prettier",
    "rustfmt", "clippy", "gradle", "mvn ", "dotnet ", "mix ", "bundle ", "rake ",
]


def _load_config() -> dict:
    """Load plugin config.yaml if present."""
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(config_path.read_text()) or {}
    except Exception:
        return {}


def _get_allowlist() -> List[str]:
    config = _load_config()
    return config.get("evidence_allowlist", DEFAULT_ALLOWLIST)


def _get_max_commands() -> int:
    config = _load_config()
    return config.get("evidence_max_commands", 10)


def _get_truncate() -> int:
    config = _load_config()
    return config.get("evidence_truncate", 2000)


def _check_allowlist(cmd: str, allowlist: List[str]) -> Optional[str]:
    """Check if a command matches the allowlist. Returns error message or None."""
    stripped = cmd.strip()
    for prefix in allowlist:
        if stripped.startswith(prefix):
            return None
    return (
        f"Command '{stripped[:50]}...' does not match the evidence allowlist. "
        f"Allowed prefixes: {', '.join(allowlist[:10])}... "
        f"Configure in ~/.hermes/plugins/omh/config.yaml"
    )


def _truncate_output(text: str, max_chars: int) -> tuple:
    """Truncate output keeping the tail (most errors are at the end).
    Returns (truncated_text, was_truncated)."""
    if len(text) <= max_chars:
        return text, False
    return "...[truncated]...\n" + text[-max_chars:], True


def gather_evidence(
    commands: List[str],
    workdir: Optional[str] = None,
    truncate: Optional[int] = None,
) -> Dict[str, Any]:
    """Run commands and capture output.

    Uses shlex.split + shell=False for security.
    Commands must match the configured allowlist.
    """
    allowlist = _get_allowlist()
    max_commands = _get_max_commands()
    max_chars = truncate or _get_truncate()

    if len(commands) > max_commands:
        return {"error": f"Too many commands ({len(commands)}). Max: {max_commands}"}

    cwd = workdir or str(Path.cwd())
    results = []
    all_pass = True

    for cmd in commands:
        # Check allowlist
        error = _check_allowlist(cmd, allowlist)
        if error:
            results.append({
                "command": cmd,
                "output": "",
                "exit_code": -1,
                "error": error,
                "truncated": False,
            })
            all_pass = False
            continue

        # Run with shlex.split + shell=False
        try:
            args = shlex.split(cmd)
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout per command
                cwd=cwd,
            )
            combined = proc.stdout + proc.stderr
            output, was_truncated = _truncate_output(combined, max_chars)

            results.append({
                "command": cmd,
                "output": output,
                "exit_code": proc.returncode,
                "truncated": was_truncated,
            })
            if proc.returncode != 0:
                all_pass = False

        except subprocess.TimeoutExpired:
            results.append({
                "command": cmd,
                "output": "Command timed out after 300 seconds",
                "exit_code": -1,
                "error": "timeout",
                "truncated": False,
            })
            all_pass = False
        except FileNotFoundError:
            results.append({
                "command": cmd,
                "output": f"Command not found: {shlex.split(cmd)[0]}",
                "exit_code": -1,
                "error": "not_found",
                "truncated": False,
            })
            all_pass = False
        except Exception as e:
            results.append({
                "command": cmd,
                "output": str(e),
                "exit_code": -1,
                "error": str(type(e).__name__),
                "truncated": False,
            })
            all_pass = False

    return {"results": results, "all_pass": all_pass}
