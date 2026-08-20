---
name: bugfix
description: Fix a defect with a reproduction, an identified root cause, and a regression test that failed beforehand. Use when a bug is reported, when behaviour is wrong or unintended, or when a test fails for a reason nobody has explained yet.
---

# Bugfix

**Do not change code until the defect is reproduced**, or there is a documented reason
reproduction is impossible.

## Preconditions

- A reproduction exists, or the reason one cannot exist is written down.
- The behaviour is genuinely unintended. If it is intended and merely undesirable, this is a
  Plan or Implement task.

## Procedure

1. **Reproduce** — the smallest input or command that shows the defect. Record it.
2. **Characterise** — expected versus actual; since when (use `git log`); scope, meaning one
   module or systemic. Ask explicitly whether it affects outputs already produced and
   stored, because that decides whether a fix is sufficient or a correction is also needed.
3. **Root cause** — explain *why* it happens, not just where. If the root cause is
   architectural, meaning an accepted contract is wrong, stop: that is a task-type
   transition and must be surfaced, not absorbed.
4. **Write the failing regression test** — it must fail **for the root-cause reason** before
   the fix, not merely fail. Justify any tolerance; never pick one that happens to pass.
5. **Fix** — the minimal change that addresses the root cause. Not the symptom, and not a
   general improvement noticed on the way.
6. **Verify** — the regression test passes, the full suite passes, and adjacent code is
   checked for the same pattern. The same bug in a sister module is the same bug.
7. The commit message explains the root cause and why the fix is correct.

## Escalation

- A gate that fails 3 times on the same cause: stop and report the output rather than trying
  a fourth approach.
- If reproduction fails after a genuine attempt, stop and report what was tried. A fix for a
  defect nobody has reproduced is a guess with a test attached.
