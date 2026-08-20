# Evals

Scenarios that test whether the rules, skills and subagents in this repository actually
change agent behaviour.

## Why this directory exists

Guidance written speculatively does not improve agent behaviour; guidance tuned against
observed failures does. The difference measured in the literature is 25.5% versus 33.0%
resolve rate — see `docs/research/2026-08-19-agent-scaffolding-field-report.md`, section 4.1.

The practical consequence: **a rule added because it seemed sensible is not finished work.**
This directory is where it gets finished.

## The method

Full version in `docs/development/testing.md`. In short:

1. Run a representative task **without** the rule or skill. Record the specific failure —
   not "it did badly", but what it did instead.
2. Write the scenario from that failure, using `TEMPLATE.md`.
3. Establish the baseline: measure behaviour without the change.
4. Write the **minimum** rule that addresses the gap.
5. Compare against the baseline. Keep the change only if behaviour actually moved.

Author the instructions in one session and test them in a fresh one. An agent that just
wrote a rule is not a fair test of whether that rule reads clearly to an agent that has not.

## Running

`run.sh` is a starting point, not a finished harness. It runs each scenario's prompt through
`claude -p` in a temporary copy of the repository and saves the transcript for you to read.
Judging is deliberately left to a human: an automated judge is worth building once there are
enough scenarios to make reading them all tedious, and not before.

```bash
./evals/run.sh                     # every scenario
./evals/run.sh bugfix-reproduce    # one
```

## What this does not cover

Adherence is measurable. Whether a rule prevents a rare, unrecoverable error is not — no
eval here will ever exercise the licensing rule or the data-safety rule, because their
whole value is in the failure that does not happen.

The absence of an eval for those rules is not evidence against them. See section 6 of the
research note.
