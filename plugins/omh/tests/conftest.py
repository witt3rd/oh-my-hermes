"""Shared test isolation for the OMH plugin suite.

Loading the plugin runs ``register()`` -> ``_install_skills()``, which copies the
bundled skills into the Hermes home. Without redirection a plain test run writes
into the developer's real ``~/.hermes/skills/omh/`` — a live-environment side
effect no unit test should have. Pointing ``HERMES_HOME`` at a temp dir is the
isolation mechanism Hermes itself uses (see the host repo's tests/conftest.py).

Must stay in this directory: pytest applies a conftest before collecting the
tests beside it, so the redirection is in place before any plugin import.
"""

import pytest


@pytest.fixture(autouse=True)
def isolate_hermes_home(tmp_path, monkeypatch):
    """Redirect HERMES_HOME so plugin installs land in a temp dir, not ~/.hermes."""
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    return hermes_home
