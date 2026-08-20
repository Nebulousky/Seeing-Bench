---
name: converge
description: Check that policy, design docs, ADRs, plans, tests and code still agree, and report the conflicts. Use when authorities may have drifted apart, before accepting a plan, after a large merge, or when something read in one document contradicts another.
---

# Converge

`AGENTS.md` says that when policy, design docs, tests and code materially conflict, stop
and surface the inconsistency rather than silently picking a winner. That rule is useless
without a way to go looking. This is that way.

**Report conflicts. Do not resolve them.** Resolving a conflict between two authorities is a
decision, and decisions that outlive the phase belong in an ADR agreed with the user — not
in a drive-by edit made by whichever agent noticed first.

## Preconditions

None. This is safe to run at any time and is cheapest run often.

## Procedure

1. **Establish what claims to be true.** Read, in this order: `AGENTS.md`, the documents in
   its pointer table, accepted ADRs in `docs/decisions/`, plans in `docs/plans/` with status
   Accepted or In progress, and `docs/roadmap.md`.

2. **Check each pair that can disagree.** Not every combination — these are the ones that
   drift in practice:

   | Pair | What to look for |
   |---|---|
   | Policy vs docs | A rule in `AGENTS.md` that its owning document contradicts or no longer mentions |
   | Docs vs code | A stated convention, layering rule or invariant the code does not follow |
   | Docs vs tests | A documented invariant with no test, or a test asserting the opposite |
   | ADR vs code | An accepted decision the implementation has quietly moved away from |
   | Plan vs reality | A plan marked In progress whose milestones are already done or abandoned |
   | Roadmap vs plans | A phase with no Accepted plan whose code has started |
   | Docs vs docs | Two documents owning the same subject — the ownership rule broken |

3. **Verify before reporting.** Read the actual code or test, not just the document. A
   document being terse is not a conflict. State what you checked and what you found sound,
   not only what is wrong.

4. **Classify each finding:**

   - **Conflict** — two authorities assert incompatible things. Needs a decision.
   - **Drift** — one authority is simply out of date. Needs an update, not a decision.
   - **Gap** — something asserted nowhere that should be. Needs an owner.

5. **Report** with file and line for both sides of each finding, the classification, and
   what kind of work would resolve it — an ADR, a doc update, a code change, a test. Include
   a recommendation; do not act on it.

If nothing conflicts, say so plainly. A convergence check that always finds something is a
convergence check nobody will run twice.

## Escalation

- More than a handful of conflicts usually means an authority was changed without its
  dependants — report the pattern, not just the instances.
- A conflict where both sides look deliberate is the important case. Do not guess which was
  intended; that is precisely the decision to hand back.
