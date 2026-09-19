# Honest Gaps

OMH v1.0 replicates the core execution pipeline (~85%) but not the full OMC
feature surface (~60% overall). This document tracks what's missing.

For gaps that require Hermes-level changes (LSP, stop prevention, HUD), see
[`hermes-constraints.md`](hermes-constraints.md).

## Could Be Skills (Not Yet Built)

| Gap | What OMC Has | Priority | Effort |
|-----|-------------|----------|--------|
| **More agent roles** | designer, qa-tester, scientist, git-master, tracer, vision, product-manager, ux-researcher, etc. | Medium | Low per role — add as needed |
| **Deslop pass** | `ai-slop-cleaner` as mandatory post-process in ralph | Medium | New skill |
| **Model tier routing** | Auto-routes Haiku/Sonnet/Opus by task complexity. We use one model for all. | Low-Medium | **Native via `delegation.model` / `delegation.provider` config** — see [`research/hermes-multiagent.md`](research/hermes-multiagent.md) §5. OMH should ship recommended config presets (cheap-tier for verifier/deslop leaves) rather than build its own router. Per-task routing within a single batch is not yet supported by the public schema. |
| **Ontology extraction** | Tracks entities across interview rounds with stability ratios | Medium-High | Deep-interview v1.1 |
| **Brownfield explore-first** | Scans codebase before asking the user | Medium | Deep-interview v1.1 |
| **Team mode** | Native agent teams with direct inter-agent messaging | Low | Fundamental architecture difference — Hermes subagents are isolated |
| **Multi-model orchestration** | Claude + Codex + Gemini workers via tmux | Medium | **Natively supported via per-task `acp_command` in `delegate_task`** — see [`research/hermes-multiagent.md`](research/hermes-multiagent.md) §6. A ralplan variant where Planner=Claude Code, Architect=Codex, Critic=Hermes-native is a few-line change. Candidate skill: `omh-cross-model-debate`. **Validation spike required first** — ACP-as-worker behavior under the `omh_delegate` contract-injection wrapper is unverified (2026-04-22). |
