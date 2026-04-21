---
name: omh-deep-research
description: >
  Multi-phase web research that decomposes a topic into subtopics, dispatches
  parallel researcher subagents, synthesizes a report, and verifies citations
  before marking it confirmed. State is durable: kill at any phase boundary
  and re-invoke to resume. Sentinel: `.omh/research/{slug}-report.md` with
  frontmatter `status: confirmed`.
version: 1.0.0
tags: [research, web, synthesis, parallel, omh]
category: omh
metadata:
  hermes:
    requires_toolsets: [terminal, omh, web]
---

# OMH Deep Research — Multi-Phase Web Research with Citation Verification

## When to Use

- The user asks for "deep research on", "a research report about",
  "comprehensive research", "investigate X", "what's known about Y"
- omh-deep-interview encounters an unfamiliar domain and needs background
- omh-ralplan needs external context before it can plan responsibly
- The user's question requires synthesizing 3+ web sources into one
  coherent answer, not a single search

## When NOT to Use

- A confirmed report already exists at `.omh/research/{slug}-report.md`
  with `status: confirmed` for this topic — view it instead
- The question is answerable by a single web_search call
- The user wants real-time / current-events data only (this skill
  emphasizes durable synthesis, not freshness)
- No `web` toolset is available in this Hermes install (see Prerequisites)

## Prerequisites

This skill fail-fasts if any of the following are missing:

- **`web` toolset** — provides `web_search` AND `web_extract`. If either
  is unavailable, print:
  ```
  omh-deep-research requires the `web` toolset (web_search + web_extract); aborting.
  ```
  and exit before doing any work.
- **`omh_state` tool** — preferred path. If absent, fall back to manual
  JSON read/write at `.omh/state/research-state.json` (singleton). If
  neither is writable, fail-fast with a clear error.
- **Write access** to `.omh/` for state, plan, findings, report, log.

Hermes discovery: `hermes skills list | grep omh-deep-research` should
return this skill once installed.

### Installation (symlink for Hermes discovery)

```
mkdir -p ~/.hermes/skills/omh && ln -snf <repo>/plugins/omh/skills/omh-deep-research ~/.hermes/skills/omh/omh-deep-research
```

Parent dir creation MUST precede the symlink.

## Architecture

Five invocation phases, exit-safe between any two:

| # | Phase     | Reads                                  | Writes                                                       | Subagents |
|---|-----------|----------------------------------------|--------------------------------------------------------------|-----------|
| 1 | decompose | user query                             | `{slug}-plan.md`, state.phase=search                         | none      |
| 2 | search    | plan, state, findings/                 | new findings file(s), state.completed_subtopics, phase       | 1-3 `[omh-role:researcher]` parallel |
| 3 | gap_check | all findings                           | optional `_followup.md` OR direct phase flip                 | 0 or 1 `[omh-role:researcher]` |
| 4 | synthesize| all findings (parent inlines)          | `{slug}-report.md` `status: draft`, phase=verify             | 1 `[omh-role:research-synthesist]` |
| 5 | verify    | report + findings (parent inlines)     | confirmed frontmatter / state mutate / blocked               | 1 `[omh-role:research-verifier]` |

**Singleton state.** State lives in `.omh/state/research-state.json`
(singleton; one active research session per project — matches
omh-deep-interview line 233). Per-session artifacts are slug-keyed under
`.omh/research/`. The earlier `research-{id}.json` wording from the
spec is superseded.

**Parent owns the filesystem.** All web tool use happens inside delegated
subagents. The parent reads findings files and inlines their contents
into synthesist's and verifier's `context` field. Subagents return
text only.

**Roles are referenced, never inlined.** Use `[omh-role:NAME]` markers.
The full role bodies live in `plugins/omh/references/role-*.md`.

## Procedure

### Phase 0: Check for Existing State and Sentinel

Before starting any new research session:

1. **Cancel check first** — `omh_state(action="cancel_check", mode="research")`.
   If cancelled, log `CANCELLED` and exit cleanly with no further work.
2. **Singleton check** — `omh_state(action="check", mode="research")`. If
   `omh_state` is unavailable, read `.omh/state/research-state.json`
   manually.
3. **Sentinel self-heal (recovery from crash between confirm and
   clear).** If active state exists AND its slug's
   `.omh/research/{slug}-report.md` has frontmatter `status: confirmed`,
   the previous run crashed after writing the sentinel but before
   clearing state. Treat as completed: log
   `REPORT_CONFIRMED_RECOVERED slug={slug}`, clear state via
   `omh_state(action="clear", mode="research")`, exit.
4. **Active mismatched session** — if active state exists with a
   different slug than the new request, prompt user:
   resume the existing one / abandon and start fresh / cancel.
5. **Already-confirmed for this topic** — if the user re-invokes for a
   topic whose `{slug}-report.md` exists with `status: confirmed`,
   prompt: refresh (mint a new slug and re-run) / view existing report /
   cancel.
6. **Resume mid-flight** — if active state exists for the same topic,
   read `state.phase` and jump directly to that phase.
7. **No active state** — proceed to Phase 1.

### Phase 1: Decompose

1. Cancel check: `omh_state(action="cancel_check", mode="research")`.
2. **Mint a slug** — concrete rule:
   `slug = kebab(topic)[:40] + '-' + YYYYMMDD + '-' + random4`
   where `random4` is 4 lowercase-hex chars.
   `kebab()` = lowercase, replace runs of non-alphanumeric with `-`,
   strip leading/trailing `-`, truncate to 40 chars.
3. Decompose the user's topic into 3-5 subtopics. For each subtopic,
   draft 2-3 candidate search queries.
4. **Write the plan** atomically (tmp → fsync → rename) to
   `.omh/research/{slug}-plan.md` with frontmatter:
   ```
   ---
   status: planning
   topic: {original user topic}
   slug: {slug}
   subtopics:
     - name: {subtopic 1 name}
       queries: [{q1}, {q2}, {q3}]
     - ...
   ---
   ```
5. **Initialize state** via `omh_state(action="write", mode="research", data={...})`:
   ```
   {
     "phase": "search",
     "slug": "{slug}",
     "topic": "{topic}",
     "subtopic_count": N,
     "completed_subtopics": [],
     "started_at": "{ISO-8601}",
     "session_id": "{uuid4}",
     "synthesis_attempts": 0
   }
   ```
6. Log `STARTED slug={slug}` and `PLAN_WRITTEN slug={slug} subtopics=N`.
7. Exit. Re-invocation will pick up at Phase 2 via the Phase 0 resume path.

### Phase 2-5

Implemented in subsequent tasks (T5-T9). Phase boundaries are
exit-safe; resumption is by re-invoking the skill — Phase 0 routes to
the correct phase via `state.phase`.

## Sentinel

Downstream skills (omh-deep-interview, omh-ralplan, omh-autopilot) detect
a completed research session by:

```
.omh/research/{slug}-report.md  with frontmatter `status: confirmed`
```

This file is the durable contract. State is ephemeral; the sentinel is
the source of truth.

## Pitfalls

- **Never call `web_search` or `web_extract` from the parent.** All web
  tool use happens inside delegated `[omh-role:researcher]` subagents.
- **Never inline role text.** Use `[omh-role:NAME]` markers; bodies live
  in `plugins/omh/references/role-*.md`.
- **Phase boundaries are commit points.** Each phase MUST exit cleanly
  after writing its outputs and updating state. Long-running phases
  that span multiple delegations are not exit-safe.
- **One active research session per project.** Phase 0 enforces this.
  Don't create parallel research states.
- **Slug collisions are user-visible.** The `random4` suffix keeps
  same-topic same-day re-runs from clobbering each other.

## Known Gaps

- **Persistence to wiki / fact_store / memory** is not yet integrated.
  The sentinel report is the only durable interface in v1. (Q2)
- **Per-call subagent tool scoping for `[omh-role:research-verifier]`**
  may be unavailable depending on Hermes install; READ-ONLY contract is
  enforced by prose in `role-research-verifier.md` in that case. (A5)
