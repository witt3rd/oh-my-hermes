# Contributing to Oh My Hermes

## Local Development Setup

For active development, symlink the repo into `~/.hermes/` so edits go live
immediately without copy/sync drift:

```bash
mkdir -p ~/.hermes/plugins
ln -s "$PWD/plugins/omh" ~/.hermes/plugins/omh
ln -s "$PWD/plugins/omh/skills" ~/.hermes/skills/omh
```

Verify:

```bash
ls -la ~/.hermes/plugins/omh ~/.hermes/skills/omh
```

Then restart Hermes to load the plugin's tools and hooks. Skills are
discovered each session — no restart needed for skill-only edits.

### Requirements

- Hermes Agent v0.7.0+
- Python 3.10+ with `pyyaml` available in the Hermes venv
  (verify: `cd ~/.hermes/hermes-agent && uv run python -c "import yaml"`)

### Uninstall

```bash
rm ~/.hermes/plugins/omh ~/.hermes/skills/omh
```

(Symlinks only — your repo is untouched.)

### Testing pre-merge changes against a worktree (proxy pattern)

When you're working on a multi-commit OMH change in a `git worktree` and want
to **battle-test it from a live Hermes session before merging to `master`**,
don't repoint your profile symlinks at the worktree directly. Once-per-flip
edits across multiple profiles are error-prone and easy to leave in a broken
state if you forget which profile is pointing where.

Instead, add **one level of indirection**: a per-machine proxy directory
that profiles always point at, and which you flip in one place to choose
between `master` and any worktree.

**One-time setup (per machine):**

```bash
# Stable per-machine proxy location
mkdir -p ~/.local/share/omh-dev

# Initial target: live master checkout
ln -sfn /path/to/oh-my-hermes/plugins/omh         ~/.local/share/omh-dev/plugin
ln -sfn /path/to/oh-my-hermes/plugins/omh/skills  ~/.local/share/omh-dev/skills

# Profile symlinks now point at the proxy, not the repo
ln -sfn ~/.local/share/omh-dev/plugin  ~/.hermes/plugins/omh
ln -sfn ~/.local/share/omh-dev/skills  ~/.hermes/skills/omh
```

**To work against a worktree:**

```bash
ln -sfn /path/to/oh-my-hermes-<arc>/plugins/omh         ~/.local/share/omh-dev/plugin
ln -sfn /path/to/oh-my-hermes-<arc>/plugins/omh/skills  ~/.local/share/omh-dev/skills
```

**To flip back to master:**

```bash
ln -sfn /path/to/oh-my-hermes/plugins/omh         ~/.local/share/omh-dev/plugin
ln -sfn /path/to/oh-my-hermes/plugins/omh/skills  ~/.local/share/omh-dev/skills
```

Why two proxy entries (`plugin/` + `skills/`) instead of one? Because
profiles symlink them independently — `plugins/omh/` (Python tool/hook code)
and `skills/omh/` (SKILL.md files) live at sibling paths in the profile.
Flipping both together keeps them coherent across master/worktree boundaries.

**Why this matters:** OMH ships to real users. Treating `master` as a place
to "experiment" or "try this and see if it works" risks breaking installs in
the wild. The proxy pattern lets you battle-test arbitrary worktrees from a
live session without ever touching `master`'s tip until the work is baked.

> **Cross-machine portability note.** If your profile symlinks live in a git
> repo that gets exported to other machines (e.g. a forge profile), use
> *relative* paths from the profile to the proxy:
> `ln -sfn ../../../../.local/share/omh-dev/plugin <profile>/plugins/omh`.
> Per-machine proxy contents differ; relative profile→proxy paths stay
> portable. The proxy itself uses absolute paths since it's never exported.

## Testing

Plugin tests live in `plugins/omh/tests/`. Run from the repo root:

```bash
cd plugins/omh && python -m pytest tests/
```

## Style

- Skills follow Hermes SKILL.md format (YAML frontmatter + markdown body)
- Plugin code targets Python 3.10+
- Keep skills standalone-capable; plugin features should enhance, not gate
