---
paths:
  - "experiments/**"
  - "docs/research/**"
---

# Work derived from external sources

Full rules: `docs/external-sources.md`.

The lines that must never be missed:

- **Never copy code from a reference implementation**, regardless of licence. Reimplement
  from the description; read reference repositories for understanding only.
- The licence of a **description** (paper, spec, article) is recorded separately from the
  licence of its **code**.
- Prototypes stay in `experiments/` and are never imported by the production package.
  Promotion is a separate Implement task with its own preconditions.
- **Record negative results.** An experiment that failed is a completed experiment.
