# Experiments

Prototypes and "would this work?" investigations. One directory per experiment,
`experiments/<name>/`, each containing its code and a results note.

The full rules are in `docs/external-sources.md`; the workflow is `/experiment`. In short:

- **Criteria before results.** Success and failure criteria are fixed before anything runs.
- **Production standards do not apply here.** The quality gates do not block this directory.
  The licensing rules still do — no copied reference code, even in a prototype.
- **The production package never imports from here.** Promotion is a separate Implement task
  with its own preconditions: tests, validation against known-correct reference data,
  comparison against the baseline, documented limitations, reasonable performance.
- **Record negative results** in the same detail as positive ones. An experiment that failed
  is a completed experiment; an unrecorded failure is one somebody repeats.

If this project will never have experiments, delete this directory, its rules loader
`.claude/rules/external-sources.md`, and the Experiment row in the `AGENTS.md` task table.
`scaffold_check.py` will tell you if you miss a reference.
