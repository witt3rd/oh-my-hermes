"""Tests for plugins/omh/__init__.py — _install_skills behavior."""

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from plugins.omh import _install_skills


@pytest.fixture()
def skill_src(tmp_path):
    """Create a minimal fake skills source directory."""
    src = tmp_path / "skills_src"
    src.mkdir()
    skill = src / "omh-test-skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("# Test skill\n")
    return src


def test_install_skills_copies_when_missing(tmp_path, skill_src):
    dest_root = tmp_path / "skills_dest"
    dest_root.mkdir()

    _install_skills(skill_src, dest_root)

    assert (dest_root / "omh-test-skill" / "SKILL.md").exists()
    assert (dest_root / "omh-test-skill" / "SKILL.md").read_text() == "# Test skill\n"


def test_install_skills_skips_existing(tmp_path, skill_src):
    dest_root = tmp_path / "skills_dest"
    dest_root.mkdir()

    # Pre-create destination with different content
    existing = dest_root / "omh-test-skill"
    existing.mkdir()
    (existing / "ORIGINAL.md").write_text("original\n")

    _install_skills(skill_src, dest_root)

    # Original file must still be there; SKILL.md must NOT have been installed
    assert (existing / "ORIGINAL.md").exists()
    assert not (existing / "SKILL.md").exists()


def test_install_skills_cleans_up_tmp_on_error(tmp_path, skill_src):
    dest_root = tmp_path / "skills_dest"
    dest_root.mkdir()

    # Make copytree fail by making the tmp_dest unwritable after creation
    original_copytree = shutil.copytree

    def fail_copytree(src, dst, **kwargs):
        original_copytree(src, dst, **kwargs)
        raise OSError("simulated failure before rename")

    with patch("plugins.omh.shutil.copytree", side_effect=fail_copytree):
        _install_skills(skill_src, dest_root)

    # tmp dir must be cleaned up; dest must not have been created
    assert not (dest_root / "omh-test-skill._installing").exists()
    assert not (dest_root / "omh-test-skill").exists()


def test_install_skills_creates_dest_root(tmp_path, skill_src):
    dest_root = tmp_path / "nested" / "skills_dest"
    # dest_root does not exist yet

    _install_skills(skill_src, dest_root)

    assert (dest_root / "omh-test-skill" / "SKILL.md").exists()


def test_register_tools():
    ctx = MagicMock()
    with patch("plugins.omh._install_skills"):
        from plugins.omh import register
        register(ctx)
    names = {c.args[0] for c in ctx.register_tool.call_args_list}
    assert names == {"omh_state", "omh_gather_evidence"}
