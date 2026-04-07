# omha-deep-interview — Consensus Plan

## Consensus Status
- **Round 1**: Planner drafted, Architect APPROVED with 5 concerns, Critic REQUEST_CHANGES (3 critical, 5 warnings)
- **Round 2**: Planner revised addressing all feedback, Architect APPROVE, Critic APPROVE
- **Consensus**: REACHED at Round 2 — all three perspectives approve

## Revision Summary
Key changes from v1 → v2 based on multi-agent review:
- Scoring is advisory heuristic only (coarse bins), NEVER auto-terminates (Critic C1)
- Spec schema defined consumer-first from ralplan/autopilot needs (Critic C2)
- State stores round summaries not transcripts, lossy resumability acknowledged (Critic C3)
- Coarse bins (HIGH/MEDIUM/LOW/CLEAR) replace float scores (Architect A1)
- State schema designed before loop implementation (Architect A3)
- Single adaptive instruction replaces three challenge modes (Critic W1)
- Default 5 rounds, extensible to 10 (Critic W2)
- Brownfield explicitly asked, not auto-detected (Critic W3)
- 1-2 follow-ups per round (Critic W5)
- Spec confirmation step added
- Integration test with ralplan added
- Logging added

---

## Summary

Build a Socratic interview skill that elicits project requirements through structured conversation. The skill asks questions across four dimensions (Goal, Constraints, Success Criteria, Existing Context), tracks coverage using coarse bins (HIGH/MEDIUM/LOW/CLEAR) as internal heuristics only, and adapts its questioning approach when stuck. Default 5 rounds with user-extensible option. Exit is ALWAYS user-confirmed — scoring never auto-terminates. The spec output format is defined consumer-first: what ralplan's Planner subagent and autopilot's skip-detection need dictates the schema. State stores round summaries (not full transcripts) for resumability. Brownfield detection is user-prompted, not auto-detected.

---

## Tasks

### T1: Define Spec Schema (Consumer-First)
**Description**: Examine what ralplan and autopilot actually consume. Ralplan's Planner subagent receives the spec as context text. Autopilot checks .omha/specs/ for existence and reads the file. Define the spec schema BACKWARDS from these consumers. Must include YAML frontmatter with version, status, created timestamp, and interview-id.

**Dependencies**: None
**Complexity**: Medium
**Acceptance Criteria**:
- Spec schema documented with every field justified by a consumer need
- YAML frontmatter includes: version, status (draft|confirmed), created, interview_id, project_name
- Body sections: Goal, Constraints, Success Criteria, Existing Context, Open Questions, Assumptions
- Ralplan's Planner role prompt can parse it without modification
- A sample spec file exists as a template in the skill's templates/ dir
- Schema includes a "confirmation" field (user must confirm before final)

### T2: Define State Schema
**Description**: Design the interview state file stored at .omha/state/interview-{id}.json. Stores round summaries (not full transcripts) to keep state compact and resumable. Include dimension coverage bins, round count, and user decisions.

**Dependencies**: T1 (state must reference spec schema fields)
**Complexity**: Small
**Acceptance Criteria**:
- State schema documented with all fields
- Each round stored as: {round_number, dimension_focus, summary (max 200 words), coverage_update}
- Coverage tracked as {goal: HIGH|MEDIUM|LOW|CLEAR, constraints: ..., success: ..., context: ...}
- Includes: interview_id, project_name, current_round, max_rounds, status (active|paused|confirmed|abandoned)
- Single-interview constraint: if active interview exists, skill resumes it (no parallel interviews)
- Schema stored in skill's references/ dir

### T3: Implement Opening Phase
**Description**: The first interaction. Ask the user to describe their project in 2-3 sentences. Then ask: "Is this a greenfield project or are you working within an existing codebase/system?" Initialize state file. Check for existing active interview and offer to resume or abandon it.

**Dependencies**: T2
**Complexity**: Small
**Acceptance Criteria**:
- Prompts user for project description
- Explicitly asks greenfield vs brownfield (no auto-detection)
- Creates state file with initial coverage: all dimensions HIGH
- If existing active interview found, offers resume/abandon choice
- Logs opening to state as round 0 summary

### T4: Implement Interview Loop (Core)
**Description**: The main question loop. Each round:
1. Assess which dimension has highest ambiguity (coarse bin comparison)
2. Ask 1 primary question targeting that dimension
3. Allow 1-2 brief follow-ups if the answer is unclear or partial
4. Update dimension coverage bin based on user response
5. Present coverage summary to user: "Here's where we stand: Goal [MEDIUM], Constraints [HIGH], ..."
6. Ask user: "Continue, or is this enough?" — user controls exit

Default 5 rounds. If user wants to continue past 5, allow up to 10. Scoring bins are internal heuristics only — NEVER auto-terminate.

For brownfield projects, use dimension weights 35/25/25/15 for Goal/Constraints/Success/Context to prioritize existing context.

**Dependencies**: T2, T3
**Complexity**: Large
**Acceptance Criteria**:
- Loop runs up to 5 rounds by default
- User can extend to 10 if they choose "continue" at round 5
- User can exit at ANY round by saying "enough", "done", "that's it", etc.
- Each round targets the highest-ambiguity dimension
- 1-2 follow-ups allowed per round (not strictly one question)
- Coverage bins displayed to user each round
- Brownfield weighting applied when user indicated brownfield in T3

### T5: Implement Adaptive Questioning
**Description**: Single adaptive instruction: "If a dimension has been targeted for 2+ consecutive rounds without moving from its current bin, change your approach — try asking from a different angle, propose a concrete example and ask if it's wrong, or ask what's blocking clarity."

This is a prompt instruction, not a code branch. It goes into the interview loop's system prompt.

**Dependencies**: T4
**Complexity**: Small
**Acceptance Criteria**:
- Adaptive instruction included in loop system prompt
- When a dimension is stuck (same bin for 2+ rounds), the next question uses a noticeably different approach
- No hardcoded round thresholds for mode switching
- No separate "challenge mode" concept

### T6: Implement Spec Generation
**Description**: When user confirms exit, generate the spec from accumulated round summaries. Spec follows the schema from T1. Write to .omha/specs/{project-name}-spec.md. Status is "draft".

**Dependencies**: T1, T4
**Complexity**: Medium
**Acceptance Criteria**:
- Spec generated from state round summaries
- Follows T1 schema exactly
- YAML frontmatter populated correctly
- Written to .omha/specs/
- Open Questions section populated with any dimension still at HIGH or MEDIUM

### T7: Implement Spec Confirmation Step
**Description**: After generating draft spec, display it to the user and ask for confirmation. User can: confirm (status → confirmed), request edits (re-enter a mini-round targeting specific sections), or abandon.

**Dependencies**: T6
**Complexity**: Medium
**Acceptance Criteria**:
- Draft spec displayed to user in full
- User prompted: "Confirm this spec, request changes, or abandon?"
- On confirm: status updated to "confirmed" in both spec and state
- On edit request: targeted follow-up questions, then regenerate spec
- On abandon: state marked abandoned, spec file deleted
- Only "confirmed" specs are considered valid by downstream consumers

### T8: Implement Logging
**Description**: Add structured logging to .omha/logs/interview-{id}.log. Log: round transitions, dimension coverage changes, user decisions (continue/exit/confirm/abandon), errors. NOT full transcripts — just events and decisions.

**Dependencies**: T4
**Complexity**: Small
**Acceptance Criteria**:
- Log file created per interview
- Events logged with timestamps
- Coverage transitions logged (e.g., "goal: HIGH → MEDIUM at round 3")
- User decisions logged
- No full conversation text in logs (privacy + size)

### T9: Write SKILL.md
**Description**: Compose the full skill file. Includes: trigger conditions, the complete procedure, pitfalls, and linked file references (templates/spec-template.md, references/state-schema.md).

**Dependencies**: T1-T8 (all implementation tasks)
**Complexity**: Medium
**Acceptance Criteria**:
- Valid skill YAML frontmatter
- Clear trigger conditions ("deep interview", "requirements", "what should we build")
- Step-by-step procedure covering opening, loop, spec gen, confirmation
- Pitfalls section covering: don't auto-terminate, don't store transcripts, ask about brownfield, single-interview constraint
- References to state schema, spec template, and sample spec

### T10: Integration Test with Ralplan
**Description**: End-to-end test: run a mock interview, generate a spec, then feed it to ralplan and verify the Planner subagent can parse and use it. Verify autopilot would detect the spec in .omha/specs/ and skip its requirements phase.

**Dependencies**: T9
**Complexity**: Medium
**Acceptance Criteria**:
- A sample confirmed spec exists in .omha/specs/
- Ralplan's Planner subagent receives the spec and produces a valid plan (doesn't ask for clarification that the spec already answers)
- Autopilot detection logic confirmed (spec exists → skip requirements)
- Any schema mismatches between spec output and consumer expectations documented and fixed

---

## Execution Order

```
T1 (spec schema) → T2 (state schema) → T3 (opening) → T4 (loop) → T5 (adaptive) → T6 (spec gen) → T7 (confirmation) → T8 (logging) → T9 (SKILL.md) → T10 (integration test)
```

T8 can start after T4 (parallel with T5-T7).

---

## Risks

R1. **LLM scoring unreliable** — Coarse bins mitigate but heuristic can still be wrong. Mitigation: bins are advisory only, user always controls exit.

R2. **State resumability is inherently lossy** — Summaries lose nuance. Mitigation: acknowledged limitation, documented in pitfalls.

R3. **Spec schema drift** — If ralplan/autopilot change, spec becomes stale. Mitigation: version field in frontmatter allows compatibility checks.

R4. **User fatigue** — Even 5 rounds may be too many for simple projects. Mitigation: user can exit any round.

R5. **Brownfield complexity** — Hard to capture in interview. Mitigation: dedicated Context dimension with higher weight.

---

## Open Questions

Q1. Should the spec include a "confidence" indicator per section to help ralplan's Planner know where to probe further?

Q2. Should there be a "quick mode" that skips the interview entirely for users who know exactly what they want?

Q3. What happens when a user wants to update a confirmed spec later? New interview or edit-in-place? (Suggest: new interview pre-populated from old spec.)

Q4. Should the spec reference specific files/paths discovered during brownfield questioning?
