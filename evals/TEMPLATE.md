# Eval: <what behaviour this tests>

```yaml
Targets: <the rule, skill or subagent under test>
Created: <YYYY-MM-DD>
Baseline measured: <yes/no, date>
```

> **How to use this template.** One file per scenario, three scenarios per skill. Write the
> scenario **from an observed failure**, not from an imagined one — a scenario invented
> alongside the rule it tests will pass for the wrong reason. Delete these instructions when
> filling it in.

## The observed failure

What the agent actually did without this rule or skill, on a real task. Quote the behaviour.
If this section says "it might not follow the rule", the scenario is not grounded in
anything and should not be written yet.

## Prompt

The exact prompt given to the agent. Self-contained: it must not depend on conversation
history.

```text
<prompt>
```

## Fixtures

Files the scenario needs, and their starting state. Keep them small — a fixture nobody can
read in a minute is a fixture nobody will debug.

## Expected behaviour

What a correct run does, as observable actions rather than internal reasoning:

- [ ] <ran the reproduction before editing any file>
- [ ] <wrote the failing test first>
- [ ] <reported the command output as evidence>

## Counter-behaviour

What a *wrong* run does. Stating this separately matters: a scenario that only lists good
behaviour is passed by an agent that does everything, including things it should not.

- [ ] <did not edit files outside the stated scope>
- [ ] <did not loosen a tolerance>

## Baseline

Behaviour **without** the rule or skill loaded, and the date measured. Without this the
scenario cannot show that the rule did anything.

## Result

| Date | Configuration | Outcome | Notes |
|---|---|---|---|
| | baseline | | |
| | with rule | | |

## Verdict

Did the rule change behaviour? If not, the honest action is to delete the rule rather than
keep it and hope. A rule that does not change behaviour is costing context for nothing.
