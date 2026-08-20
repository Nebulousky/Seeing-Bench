---
name: phase-plan
description: Produce a phase or substantial-feature plan following the project's planning standard. Use when starting a roadmap phase or a large feature, or when asked how a piece of work should be executed before any code is written.
---

# Phase planning

Produces a plan per `docs/plans/TEMPLATE.md`. Plans are execution documents, never decision
authority — decisions that outlive the phase are promoted to a design document or an ADR in
`docs/decisions/`, and the plan links to them.

## Preconditions

- The relevant authority has been read: the roadmap entry, `docs/architecture.md`, the
  design documents and research notes this phase depends on, and any prior plans it builds
  on. Reading these is the work, not a formality — a plan written without them will
  contradict one of them.
- If the phase rests on an external source, its research note exists first
  (`docs/external-sources.md`).

## Procedure

1. **Read the authority first.** Cite what you read in the plan's Existing constraints
   section, concretely rather than as a generic pointer.
2. **List every open decision the phase contains.** Classify each as either decidable from
   existing authority — decide it, record the rationale and the alternatives — or genuinely
   open. For genuinely open decisions, present options with a recommendation and **discuss
   with the user before writing it as decided**. Never invent a foundational contract while
   filling out a template.
3. **Draft the plan** with every template section present, using `N/A` plus a one-line
   justification where a section genuinely does not apply. Pay particular attention to:
   invariants (§3), what is taken from each external source (§5), dispositions for unknowns
   (§6), interfaces and ownership (§7), milestone exit conditions (§9), named real datasets
   (§10), measurable acceptance criteria (§11), and failure and fallback conditions (§12).
4. Set `Status: Draft`. Present the open decisions and the draft for discussion.
5. On agreement, set `Status: Accepted`. Only then may the phase's first feature branch be
   created.

## Escalation

- A decision you cannot resolve from existing authority is not yours to make. Flag it and
  stop; an Accepted plan containing an invented contract is worse than no plan.
- If the phase needs an ADR before it can be planned, say so and stop. That is a task-type
  transition, not a section to fill in.
