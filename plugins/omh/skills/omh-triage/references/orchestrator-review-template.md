# Orchestrator review template

Used at the Phase-2 → Phase-3 gate. The orchestrator (you) reviews the
distilled output before any closures, recasts, or board updates execute.

This is **your bar applied honestly**. If the run produced more
ceremony than rigor — say so. Don't push verdicts to the user that
you don't believe yourself. (See `omh-ralplan-driver` P25.)

---

```markdown
# Orchestrator review — <YYYY-MM-DD> triage run

## What was run

- Backlog: <N> open issues at start
- Roles: <Maintainer, Skeptic>
- Phases completed: 0 (context), 1 (role passes), 2 (distillation)
- Phase 3 (execution) GATED on this review

## Verdict on the run itself

- **Quality of Maintainer pass:** <strong / mixed / weak — with reasoning>
- **Quality of Skeptic pass:** <strong / mixed / weak — with reasoning>
- **Distillation conflicts:** <N — each enumerable>
- **Confidence in the proposed closures:** <high / mixed / low>

## What I'm proposing to execute

- **Closures:** <list — each with one-line reason>
- **Recasts:** <list — each with body-surgery summary>
- **Refile-smaller:** <list — each with new-form summary>
- **Project board updates:** <list>

## What I'm NOT executing yet

- **Conflicts requiring your decision:** <list — each framed as a
  specific question>
- **Recasts where I'm not confident in the new body:** <list>

## Lessons I'd fold into the skill if you agree

<L1, L2, ... — observations from this run that may want patching
into omh-triage / omh-triage-driver / host PROCESS.md.>

## My honest assessment

<One paragraph: did this run actually need the multi-role consensus
shape, or would a single-perspective walk have produced the same
verdicts? If single-perspective would have worked, name what the
multi-role pass added; if it added nothing, that's a lesson for
the skill (T6 — running too often or under-pressing roles).>

## Approval requested

- [ ] Execute proposed closures
- [ ] Execute proposed recasts
- [ ] Execute proposed refile-smaller
- [ ] Execute proposed board updates
- [ ] Decisions on the N conflicts: <answers>

⚒️ <orchestrator>
- YYYY-MM-DD
```

The honesty discipline is load-bearing: if you find yourself writing
"the loop surfaced some interesting questions" or "the user may want
to weigh in on..." for everything — both are signals that you've
dropped to the loop's altitude. Read `omh-ralplan-driver` P25
for the full treatment.
