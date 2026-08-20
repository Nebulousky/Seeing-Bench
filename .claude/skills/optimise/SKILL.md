---
name: optimise
description: Improve performance while preserving validated behaviour, with before and after measurements. Use when work concerns speed, memory or throughput, or when something is reported as too slow.
---

# Optimise

**No improvement claim without before and after measurements.** Rewriting something in a
faster language because that language is faster is not evidence.

## Preconditions

Verify these; do not assume them. Stop and surface if any is unmet:

- the behaviour being optimised is validated — tests and validation exist, so there is
  something to preserve;
- a baseline benchmark exists, or is created first;
- the bottleneck is identified by profiling or measurement, not intuition.

Correct, then validated, then profiled, then optimised — in that order.

## Procedure

1. **Baseline** — benchmark the current implementation, recording the environment: hardware,
   versions, input sizes, configuration. Use warm-up runs so the number measures the code
   rather than the first-call costs around it.
2. **Profile** — find where the time or memory actually goes. The answer is regularly not
   where it was assumed to be, which is the entire reason for this step.
3. **Change** — one optimisation at a time, targeting the measured bottleneck.
4. **Benchmark after** — same data, same configuration, same stopping criteria. A faster run
   to a worse answer is not a speedup.
5. **Validate equivalence** — outputs match the validated behaviour within justified
   tolerances, and the relevant test suite passes.
6. **Record** the before and after numbers where the next person will find them.
7. **If the win is not measurable, revert.** Keep the simpler code.

## Escalation

- If the bottleneck is architectural, stop. Restructuring is a Plan task, and doing it under
  an Optimise contract skips the decision that restructuring deserves.
- If preserving behaviour would require loosening a tolerance, stop. That is on the never
  list.
