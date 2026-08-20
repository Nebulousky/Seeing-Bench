---
paths:
  - "**/*.py"
---

# Architecture

Full rules: `docs/architecture.md`. Read it before adding a module, adding an import across
package boundaries, or introducing state.

The lines that must never be missed:

- **No silent fallbacks.** If a failure would change the algorithm, quality or behaviour of
  the result, raise or warn explicitly. Never substitute a different method silently.
- **Dependency direction is one-way.** Domain modules never depend on UI or application
  state. No circular imports.
- **Pass RNG generators explicitly.** Never seed or read global RNG state in library code.
- **Derived products record their provenance:** inputs, algorithm and version, parameters,
  seed, software version, and the model or agent identity where one was involved.
