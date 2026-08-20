---
name: experiment
description: Test an uncertain hypothesis in experiments/ with criteria fixed in advance and results recorded. Use when the question is whether an approach would work, when prototyping, or before committing to a technique not yet validated here.
---

# Experiment

**A negative result is a valid completed experiment.** The failure mode to avoid is an
experiment quietly becoming production code.

## Preconditions

- The question and its success and failure criteria are defined **before anything runs**.
  Criteria chosen after seeing results are not criteria.
- The work lives in `experiments/`, never in the production package.

## Procedure

1. **Question** — one sentence: what are we trying to learn?
2. **Hypothesis and criteria** — define success and failure criteria and the metrics that
   decide them, before running anything. Prefer data with known correct answers; name the
   real datasets used.
3. **Design** — the smallest experiment that answers the question. Code lives in
   `experiments/<name>/`, cites its sources, and may be rough. Production standards do not
   apply and the gates do not block it. The licensing rules in `docs/external-sources.md`
   still do: no copied reference code, even here.
4. **Run and analyse** against the pre-stated criteria. Resist moving the goalposts. If the
   criteria were wrong, say so explicitly and re-state them rather than quietly
   reinterpreting the result.
5. **Record** — a results note beside the code: question, setup, data, metrics, outcome,
   limitations, and the decision it informs. Negative results are recorded in the same
   detail as positive ones; an unrecorded failure gets rediscovered.
6. **Never import experiment code into the production package.** Promotion is a separate
   Implement task with its own preconditions: tests, validation against known-correct
   reference data, comparison against the existing baseline, documented limitations, and
   reasonable performance.

## Escalation

- If production code starts depending on an experiment, stop. That is promotion happening
  by accident, and it needs the Implement preconditions above.
- If the criteria cannot be stated before running, the task is Research, not Experiment.
