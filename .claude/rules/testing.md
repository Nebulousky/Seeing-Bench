---
paths:
  - "tests/**"
  - "**/test_*.py"
  - "**/*_test.py"
---

# Testing

Full rules: `docs/development/testing.md`.

The lines that must never be missed:

- **A bug fix gets a regression test that failed before the fix**, and failed for the
  root-cause reason — not merely failed.
- **Tolerances are justified in the test, and never loosened to make a failing test pass.**
  If a tolerance is wrong, change it deliberately and record why.
- A test that would pass if the code did nothing is not a test.
