# Testing and Validation Strategy

This document owns what "validated" means here. The path-scoped loader at
`.claude/rules/testing.md` carries only the lines that must never be missed and points here
for the rest.

## Rules That Do Not Bend

- **A bug fix gets a regression test that failed before the fix**, and failed for the
  root-cause reason, not merely failed.
- **Tolerances are justified in the test, and never loosened to make a failing test pass.**
  If a tolerance is wrong, change it deliberately and record why.
- **Code without tests is not done.** Neither is code without attribution or validation.

## Levels

1. Unit correctness: every public metric, IO conversion, config validation rule, and
   simulation invariant gets tests.
2. Validation against known truth: synthetic cases must compare generated outputs against
   retained latent truth and exact warp truth.
3. Independent comparison: N/A for the initial offline implementation; required before
   claiming physical atmosphere or orbital-rendering accuracy.
4. Real-data validation: N/A until LRO/LOLA/SPICE integration begins; datasets and metrics
   must be named before that implementation starts.

## Tolerances

Exact invariants use exact assertions. TIFF round trips allow half a 16-bit least
significant bit because export quantizes `[0, 1]` floats to unsigned 16-bit samples.
Floating-point algorithm tests use `numpy.testing` defaults unless a test states a physical
or quantization reason for a wider tolerance.

## What Must Have a Test

Every bug fix, documented data-shape convention, explicit numeric conversion, metric edge
case, and benchmark filesystem contract change must have a test. Any implementation derived
from a paper or external specification must have validation tests tied to its research note.

## Evaluating the Agent Scaffolding Itself

The rules, skills and subagent definitions in this repository are also subject to
validation. The method remains the same as the original scaffold: record an observed failure
in `evals/`, write the scenario first, establish the baseline, then keep only rules that
change behaviour.

## Related

- `evals/`: the scenarios and the runner
- `docs/data-handling.md`: the invariants most worth asserting
- `docs/external-sources.md`: what validation an externally derived algorithm requires
