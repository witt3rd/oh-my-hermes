# Sibling-executor pre-emption — narrated example

A real iteration where another executor running the same retry landed the fix on disk before this executor read the file. Recording it because the diagnostic path (and the time wasted before recognizing it) is the lesson, not the trivial bug.

## Setup

- Repo: `~/src/li/janus-plugin-v12`, branch `v12`
- HEAD at retry-start: `efa058d` (task-2 prior commit)
- Strike: strike-1 IMPLEMENTATION-BUG, error key `token-not-injected-into-fetch-url`
- Bug spec: `migrate.py:289` substituted literal `***` for the real token in an f-string. Verifier's one-liner fix: `f"https://x-access-token:{token}@"`.
- Envelope said: fix the f-string, add a regression test, run full suite, commit fix-up on top.

## What actually happened on disk

By the time this executor's first patch fired, a sibling subagent (`sa-0-4626183c`) had already applied the same one-liner to `migrate.py`. The patch tool reported success but flagged it:

```
_warning: "/home/dt/.../migrate.py was modified by sibling subagent
'sa-0-4626183c' but this agent never read it. Read the file before
writing to avoid overwriting the sibling's changes."
```

That warning was the diagnostic. It said: *another agent has touched this file in this run; reconcile state before continuing.* The right move at that moment was to read the file fresh, confirm what was there, and check `git diff efa058d -- migrate.py` to see whether the fix was already committed, on disk only, or still needed.

Instead, this executor proceeded as if the patch was its own and moved on to the test.

## The phantom-bug spiral

After writing the regression test and running it (passing), I went to verify the test would have failed on the bug. Tried `git stash push migrate.py` to revert. Stash failed (no local changes — the on-disk file already had the fix), but in failing it picked up an unrelated stashed README diff from a different branch and produced a merge conflict. I resolved that, but my mental model was now wrong: I believed the fix had been reverted when it hadn't, and I believed the file still contained `***` because:

```
$ grep -n 'x-access-token' plugins/janus/tools/migrate.py
289:                "https://", f"https://x-access-token:***@", 1
```

That output is *what the terminal showed me, repeatedly, across many tool calls,* even though the file at that moment actually contained `{token}`. I never fully diagnosed why — possibly tool-side output caching, possibly my own pattern-matching on a string I'd been staring at, possibly a rendering quirk. I patched the file again. Grep still showed `***`. I sed'd it. Still `***`. I checked `md5sum` (unchanged across "edits"). I escalated to byte-level inspection:

```python
with open(p, 'rb') as f: data = f.read()
i = data.find(b'x-access-token')
print(repr(data[i:i+40]))
# b'x-access-token:{token}@", 1\n            '
```

Bytes said `{token}`. Grep said `***`. Bytes won.

Final reconciliation: `git diff efa058d HEAD -- plugins/janus/tools/migrate.py` returned empty. The fix was *already in efa058d's tree on disk* (sibling executor's earlier work) AND already committed in efa058d itself. My fix-up commit ended up test-only, which I recorded honestly in the report.

## The right path, condensed

When you see `_warning: "... was modified by sibling subagent ..."` on a retry:

1. **Stop.** Don't patch further until state is reconciled.
2. **Read the file fresh** (don't rely on memory of what you intended to change).
3. **Check `git diff <envelope-parent-sha> -- <file>`.**
   - Empty diff → fix is already in the parent commit; your work is test/scaffolding only.
   - Non-empty diff matching expected fix → fix is on disk but not committed; you can include it or commit fix-up; check envelope intent.
   - Non-empty diff NOT matching expected fix → sibling did something else; investigate before continuing.
4. **If terminal output disagrees with `git show` or byte-level reads, trust bytes.** Use `od -c`, `python3 -c "open(p,'rb').read()..."`, or `git show <sha>:<file>` as authoritative.
5. **Report honestly.** "Sibling executor 'sa-X' had already applied the implementation diff before this retry started; my commit is test-only; provenance preserved in commit body" is a clean COMPLETE. The orchestrator handles dedup.

## Cost of getting it wrong

In this iteration: ~10 unnecessary tool calls between the first `_warning` and the eventual `git diff efa058d HEAD` that resolved it. Each call patched, grepped, and re-patched the same line, with the terminal tool consistently rendering output that contradicted the actual file contents. The cost wasn't the wasted calls — it was the cognitive lock-in: once I believed the file was broken, every piece of evidence got filtered through that belief, and only byte-level inspection broke the loop.

## Adjacent failure mode (not this one)

The other sibling-related pitfall in this skill — the **stash-verify move** — is for the cross-lane case: your task in lane A finishes, full suite runs, a test in lane B fails, and you need to prove it isn't your breakage. That's a different shape: different tasks, different envelopes, different commit authors, and the question is "is this failure mine?"

Same-lane pre-emption (this doc) is: same task envelope, same retry, two executors dispatched, and the question is "did sibling already do my work?" The diagnostic is the patch-tool `_warning`, not test failures, and the reconciliation tool is `git diff <parent-sha>`, not `git stash`.

Both warrant their own narrative because the diagnostic surfaces and recovery moves differ.
