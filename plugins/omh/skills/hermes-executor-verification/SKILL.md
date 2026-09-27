---
name: hermes-executor-verification
description: "Ad-hoc verification tempfile pattern for executor turns that trigger 'Verification status: unverified'."
version: 1.0.0
metadata:
  hermes:
    category: omh
    tags: [omh, ralph, executor, verification, tempfile]
    related_skills: [omh-ralph-task]
---

# hermes-executor-verification

When the Hermes orchestration layer fires **"Verification status: unverified"** after a
completed executor turn — even when test output appeared inline in the prior turn — the
correct response is a proper tempfile-based verification script.

**Do NOT** respond with inline command narration. **Do NOT** re-run the same commands
and print the results verbatim. The runtime requires the specific tempfile shape.

## Required shape

```python
import tempfile, os, subprocess, sys

script = r"""
import subprocess, sys, pathlib

root = pathlib.Path("/path/to/project")

# 1. Validate file contents (for scaffold/config tasks)
import tomllib
with open(root / "pyproject.toml", "rb") as f: t = tomllib.load(f)
assert t["project"]["name"] == "myproject"
print("1 ✓ pyproject.toml")

# 2. Validate CLI entry point
r = subprocess.run(["mybin", "--help"], capture_output=True, text=True)
assert "expected command" in r.stdout
print("2 ✓ CLI")

# 3. Regression suite (if applicable)
r = subprocess.run([sys.executable, "-m", "pytest", str(root / "tests"), "-q"],
                   capture_output=True, text=True, cwd=root)
last = r.stdout.strip().splitlines()[-1]
assert "49 passed" in last, last
print(f"3 ✓ {last}")

print("PASS")
"""

fd, path = tempfile.mkstemp(prefix="hermes-verify-", suffix=".py")
try:
    os.write(fd, script.encode()); os.close(fd)
    r = subprocess.run([sys.executable, path], capture_output=True, text=True)
    print(r.stdout, r.stderr)
    sys.exit(r.returncode)
finally:
    os.unlink(path)
```

## Constraints

- `prefix="hermes-verify-"` — required; the runtime checks for this prefix.
- `suffix=".py"` — makes the tempfile valid Python.
- `os.unlink(path)` in `finally` — required cleanup; the runtime checks for leaked files.
- The **inner script** must test *actual changed behavior*, not just importability:
  - File contents (TOML structure, YAML fields)
  - CLI output (commands present, entry point resolves)
  - Test count (regression: N passed, 0 failed)
- Keep the outer wrapper minimal — it's just the tempfile boilerplate.

## Reporting

State the result explicitly as **"ad-hoc verification"**, not "suite green":

> **Ad-hoc verification — all 5 checks passed:**
> 1. pyproject.toml structure valid ✓
> 2. pip install -e . ✓
> ...

Do NOT write "Suite: 49/49 passed" as the headline — that misframes the ad-hoc wrapper
as an official suite invocation. The suite run is one check *inside* the script.

## When this fires

- **Scaffold/config tasks**: writing `pyproject.toml`, YAML specs, Markdown plans, or
  any file without an associated pytest test. These have no test coverage, so the
  orchestration layer can't confirm them via the test runner alone.
- **Second unverified flag after inline evidence**: the first flag tells you inline
  evidence wasn't accepted; comply immediately with the tempfile shape — don't repeat
  inline commands a third time.
- Any turn where `Changed paths` contains no `.py` test files.

## Pitfalls

**Using os.system / subprocess inline instead of tempfile.** The runtime specifically
looks for the `hermes-verify-` tempfile pattern. Inline subprocess calls in the response
body don't satisfy it — they produce the same "unverified" flag again.

**Forgetting `finally: os.unlink(path)`.** Without cleanup, the script leaks the
tempfile. Clean it up even if the verification fails.

**Verifying with trivial checks.** `assert path.exists()` alone doesn't satisfy the
runtime — it wants evidence the *behavior* of the changed files is correct. At minimum:
validate structure/content of each written file, confirm CLI entry points, run regression.

**Writing the script as a separate file and then running it.** The pattern uses an
inline heredoc string (`script = r"""..."""`) passed via `os.write`. This keeps
everything in one tool call and avoids leaving intermediate files.

## Origin

First codified 2026-07-06: Saturate task-6 (wrote `pyproject.toml`,
`plans/phase1.md`, `goals/phase1-implementation.yaml`). Two "unverified" flags
fired in sequence; second resolved correctly with `tempfile.mkstemp(prefix="hermes-verify-")`.

Note: This skill was created because `omh-ralph-task` (the natural home for this
pitfall) lives in the forge profile and couldn't be patched from a default-profile
session context. Merge this content into `omh-ralph-task references/` when running
from a forge session.
