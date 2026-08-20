# 0002. Where a rule can be a command, it becomes a command

```yaml
Status: Accepted
Date: 2026-08-19
```

## Context and problem statement

This template's rules were written as prose: comments should explain why, tolerances must be
justified, optimisation follows correctness. None of it could be checked, and the evidence
says that form of instruction does not change behaviour — prose without commands, ambiguous
directives and style guides with no enforcement command all produced no measurable effect in
A/B testing (`docs/research/2026-08-19-agent-scaffolding-field-report.md`, section 4.3).

Meanwhile the mechanism that *does* work was already in the repository and barely used.
Anthropic documents the distinction plainly: hooks and settings are enforced by the client
regardless of what the model decides, whereas instruction files shape behaviour with no
guarantee of compliance. Compliance also decays through a session, roughly 5.6% lower odds
per generated function, so the rules most likely to be dropped are the ones that apply late
in a workflow — exactly where a gate is cheap and a reminder is not.

A contributor adding a rule needs to know which form is expected before they start writing,
or the rulebook drifts back toward prose one well-intentioned paragraph at a time.

## Considered options

- Keep rules as prose and rely on the model following them
- Mechanise every rule, refusing to state any rule that cannot be checked
- Mechanise where possible; state the rest as prose, deliberately and knowing its weight

## Decision

We chose **mechanise where possible; state the rest as prose, deliberately**.

The order of preference when adding a rule:

1. **A gate** — a command in the Definition of Done that exits non-zero when the rule is
   broken. Preferred whenever the violation is detectable from the repository.
2. **A hook** — a `PreToolUse` or `Stop` hook, when the rule must hold at a specific moment
   rather than at commit time.
3. **A path-scoped rule** — when it applies only to certain files (see ADR 0001).
4. **Prose in `AGENTS.md`** — the last resort, reserved for judgement that genuinely cannot
   be mechanised, written command-first and concretely enough to be checkable by a reviewer.

Prose is not banned, because the evidence has a hole in it: every study measured task
resolution on bug-fix work, and none measured licensing hygiene, attribution, provenance or
data safety. A rule preventing one unrecoverable error a year is invisible to those
benchmarks. Refusing to state such a rule because it cannot be mechanised would be reading
the evidence past what it supports.

## Consequences

**Good:** rules that matter are enforced rather than hoped for. Closure is an exit code, so
"done" stops being a judgement call. New rules arrive in a known form. The hard rules with
real teeth — licensing, scaffold integrity — now fail loudly instead of silently.

**Bad:** gates cost time on every commit, and a badly written gate is worse than no gate
because it trains people to bypass it. Mechanising a rule also fixes its interpretation
early, which is wrong for rules still finding their shape. And there is a standing
temptation to weaken a gate rather than fix the thing it caught — which is itself now on the
"never" list in `AGENTS.md`.

## Alternatives, and why not

| Option | Rejected because |
|---|---|
| Keep rules as prose | The form measured to change nothing, and it leaves the repository's most consequential rules depending entirely on recall |
| Mechanise everything, state nothing else | Would delete rules protecting against exactly the failures no benchmark measures; over-reads what the evidence supports |
