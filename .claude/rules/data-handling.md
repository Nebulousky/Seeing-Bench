---
paths:
  - "**/*.py"
---

# Data handling

Full rules: `docs/data-handling.md`. Read it before changing anything that converts,
normalises, casts, or discards values.

The line that must never be missed:

**Never silently destroy information.** No silent clipping, no silent NaN or null
substitution, no destructive normalisation, no unnecessary quantisation. Where corrupted
output would otherwise result, fail loudly.

Any transformation that changes scale, range, units or interpretation is explicit and
documented at the API that performs it.
