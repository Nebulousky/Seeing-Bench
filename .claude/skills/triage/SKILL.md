---
name: triage
description: Determine what work a request actually requires and route it to the correct task type, without doing the work. Use when a request is vague, when a bug report or idea arrives, or when it is unclear which workflow a roadmap item needs.
---

# Triage

Your job is to determine what work is required — **not to do it**.

## Preconditions

None. Triage is the workflow with no entry cost, which is why it comes first when the type
is unclear.

## Procedure

1. Restate the request in one sentence; note what information is missing.
2. Classify the **primary task type** (`AGENTS.md`, Task routing) and any prerequisite tasks
   — Research before Fix, Plan before Implement.
3. Check which authority applies: does this touch an accepted design doc, plan, ADR or
   contract? Would it require changing one? Changing an authority is itself a task type.
4. Assess risk — could this affect correctness, data integrity or provenance?

   SeeingBench risk axes: validation independence, data/provenance preservation, numeric
   correctness, coordinate/warp convention correctness, and whether a metric could reward
   impossible or unsupported detail.

5. Output the task contract:

```text
Primary type:         <type>
Prerequisite tasks:   <types or none>
Plan required:        <yes/no, per AGENTS.md preconditions>
Likely files/modules: <paths>
Risk:                 <low/medium/high + why>
Missing information:  <questions for the user, if any>
Recommended workflow: <skill or plain task>
```

Stop there. Starting the recommended work is a separate, authorised step.

## Escalation

- If the request contains two task types, say so and recommend the order. Do not merge them.
- If the risk is high and the missing information is material, recommend Research first
  rather than guessing well enough to proceed.
