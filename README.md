# Oh My Hermes (OMH)

Multi-agent orchestration skills for [Hermes Agent](https://github.com/NousResearch/hermes-agent),
inspired by [oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode)
and rebuilt natively for Hermes primitives.

OMH provides composable skills for consensus planning, requirements
interviewing, and verified execution — plus an optional plugin that adds
hook-based role injection, atomic state management, and evidence gathering.
Skills work standalone with zero dependencies.

| Skill | What It Does |
|-------|--------------|
| **omh-deep-research** | Multi-phase web research: decompose → parallel search → synthesize → verify citations |
| **omh-ralplan** | Consensus planning: Planner → Architect → Critic debate until agreement |
| **omh-ralplan-driver** | Dispatcher's playbook for driving an `omh-ralplan` run — context-package authoring (where quality is born), round dispatch, distillation, final review |
| **omh-deep-interview** | Socratic requirements interview with coverage tracking |
| **omh-ralph** | Verified execution: implement → verify → iterate until done |
| **omh-ralph-driver** | Dispatcher's playbook for driving an `omh-ralph` run — plan-shape, parallel batching, evidence gathering, verifier discipline, strike categorization, Step-7 final architect review, commit hygiene |
| **omh-ralph-task** | Executor's discipline for a single `omh-ralph` task — task-envelope contract, file-scope rigidity, stash-verify-against-HEAD for sibling-task isolation, commit-author override, structured report-back shape |
| **omh-triage** *(v0.1)* | Multi-role consensus triage of an issue backlog — Maintainer (code-anchored) + Skeptic (pruning); more roles coming after lived rounds. See [witt3rd/oh-my-hermes#9](https://github.com/witt3rd/oh-my-hermes/issues/9) |
| **omh-triage-driver** *(v0.1)* | Dispatcher's playbook for driving an `omh-triage` run — pre-flight backlog audit, role-pass dispatch, distillation, user sign-off gate |
| **omh-autopilot** | Full pipeline composing all three skills end-to-end |

Composition (recommended pipeline for unfamiliar domains):

```
omh-deep-research → omh-deep-interview → omh-ralplan → omh-ralph
```

(Or fold `omh-deep-research` in as Phase -1 of `omh-autopilot` when the
domain is unfamiliar; otherwise start at the interview.)

## Install

```bash
hermes skills tap add witt3rd/oh-my-hermes
hermes skills install omh-deep-research omh-ralplan omh-ralplan-driver omh-deep-interview omh-ralph omh-ralph-driver omh-ralph-task omh-autopilot
```

Or copy `skills/<name>/` to `~/.hermes/skills/omh/` manually.

For the optional plugin: install `plugins/omh/` to `~/.hermes/plugins/omh/`
(requires Python 3.10+ and `pyyaml`).

For local development (live edits via symlinks), see [CONTRIBUTING.md](CONTRIBUTING.md).

## Getting Started

- **Need background on an unfamiliar domain?** → `omh-deep-research`
- **Just need a plan?** → `omh-ralplan`
- **Driving a ralplan run yourself?** → `omh-ralplan-driver` (load alongside `omh-ralplan`)
- **Vague idea?** → `omh-deep-interview` then `omh-ralplan`
- **Have a plan, need execution?** → `omh-ralph`
- **Driving a ralph run yourself?** → `omh-ralph-driver` (load alongside `omh-ralph`)
- **Grooming an issue backlog?** → `omh-triage` (load alongside `omh-triage-driver` if you're driving)
- **End-to-end?** → `omh-autopilot`

OMH self-seeds a `.omh/` directory in the project on first use (with the
plugin installed) — including a README explaining the convention and a
`.gitignore` pre-configured for selective sharing. To scaffold up-front
without running a workflow, call `omh_state(action="init")`.

## Known Gaps

- **wiki/fact_store/memory persistence** is not yet integrated for
  research artifacts produced by `omh-deep-research`. The confirmed
  report sentinel (`.omh/research/{slug}-report.md` with `status:
  confirmed`) is the durable interface in v1; downstream skills consume
  it directly. Persisting findings into `fact_store` or wiki is a
  deferred Q2 item.
- **Per-call subagent tool scoping** for the `omh-deep-research`
  verifier may be unavailable depending on Hermes install; the
  READ-ONLY contract is enforced by prose in `role-research-verifier.md`
  in that case (A5).

## Cost Envelope (omh-deep-research)

A typical happy-path session is roughly **5-8 `delegate_task` calls**
(3-5 researchers + 0-1 followup + 1 synthesist + 1 verifier). With one
synthesis retry, expect **up to ~10-12 calls**. The 3-strike retry cap
bounds worst-case at ~14-16 calls before BLOCKED is surfaced.

## Requirements

Hermes Agent v0.7.0+. The plugin additionally requires Python 3.10+ and
`pyyaml`.

## Documentation

- [`docs/concepts.md`](docs/concepts.md) — How the four skills work
- [`docs/plugin.md`](docs/plugin.md) — The v2 plugin (roles, hooks, tools)
- [`docs/omh-delegate.md`](docs/omh-delegate.md) — Hardened delegation wrapper
- [`docs/omc-comparison.md`](docs/omc-comparison.md) — Origins and design choices vs OMC
- [`docs/hermes-constraints.md`](docs/hermes-constraints.md) — How OMH works around Hermes limits
- [`docs/gaps.md`](docs/gaps.md) — What's not built yet
- [`ROADMAP.md`](ROADMAP.md) — Versions and direction

## License

MIT
