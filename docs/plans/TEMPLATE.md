# Plan: <phase/feature name>

```yaml
Status: Draft | Accepted | In progress | Completed | Superseded
Roadmap phase: <n>
Created: <date>
Last updated: <date>
```

> **How to use this template.** Every section must be present. A section that
> genuinely doesn't apply gets `N/A — <one line of justification>`, never
> silent deletion. Plans contain as much detail as necessary to make
> implementation unambiguous, but no detail whose proper home is a design
> document or API documentation — link there instead.
> Lifecycle: Draft → Accepted (open decisions resolved by discussion) →
> In progress → Completed (retrospective appended) → occasionally
> Superseded. Plans describe *how we currently intend to get somewhere*;
> decisions that remain true after the phase ends are **promoted** to the
> appropriate design doc or an ADR (`docs/decisions/`), with the plan
> linking to them.

## 1. Purpose

The problem, not the implementation. Why this phase exists, and what later
phases depend on it — written so an agent with no conversational context
understands why it is doing the work.

## 2. Scope and non-goals

**In scope:** …

**Not in scope:** … (mandatory — the defence against feature creep)

## 3. Inputs, outputs and invariants

**Inputs:** what this phase consumes.

**Outputs:** what it produces (including provenance/diagnostics).

**Invariants:** properties that must hold throughout — e.g. *inputs are
never mutated; metadata is preserved; no information is discarded without
an explicit, documented step*. Invariants are testable; they feed §10
directly.

## 4. Existing constraints

What this plan must not accidentally contradict: the specific decisions in
`AGENTS.md`, `docs/architecture.md`, prior plans and ADRs that bear on this
work — listed concretely, not as a generic pointer.

## 5. External basis

Which external sources (papers, specs, prior art, upstream APIs) apply, and
**what we are actually taking from each** — not a bibliography. Include
obligations to *future* phases (e.g. "X is not implemented here, but
outputs must retain the metadata X will require").

## 6. Assumptions, unknowns and risks

**Assumptions** (believed true; validated cheaply where possible):

**Unknowns** (genuinely undetermined) — each with a required disposition:
> Unknown: … Resolution: e.g. prototype three approaches on dataset X
> before implementing.

**Risks** (what goes wrong if an assumption fails): …

## 7. Design

Enough detail that another competent developer could implement it: data
flow, algorithms, formulation, module ownership, public interfaces, state
ownership, error behaviour, memory strategy, metadata/provenance handling.

## 8. Alternatives considered

| Decision | Chosen | Alternatives | Reason |
|---|---|---|---|
| … | … | … | … |

Decisions with open status are resolved by discussion before the affected
code is written. **Promotion rule:** any decision that remains
architecturally important after the phase ends moves to the appropriate
design doc or a new ADR; the table then links to it.

## 9. Work breakdown

4–10 milestones, each branch/session-sized, ordered, with dependencies.
Every milestone names a tangible deliverable and an exit condition — never
"work on X". This is a guide, not a ticket backlog.

## 10. Validation strategy

Levels (mark N/A per level with justification):

1. **Unit correctness** — components do what they claim (incl. invariant
   tests from §3).
2. **Validation against known truth** — known input → expected output,
   compared quantitatively rather than by inspection.
3. **Independent comparison** — against established software or libraries,
   to catch gross discrepancies, not to blindly match.
4. **Real-data validation** — name the actual datasets and per-dataset
   purpose and metrics *before* implementation starts.

## 11. Acceptance criteria

Measurable wherever possible, refining the roadmap's exit criterion.
Exploratory thresholds are allowed, but gate on the experiment:
> Threshold: to be established by prototype experiment P1. Production
> implementation does not begin until P1 establishes a justified value.

## 12. Failure modes and fallback

For uncertain work: the failure condition stated up front (what result
means the approach didn't work) and the fallback that ships instead —
preventing sunk-cost behaviour. A documented negative result closes a
milestone as legitimately as success.

## 13. Performance constraints

Constraints, not premature optimisation: target scale, memory envelopes,
streaming obligations. Optimisation itself waits for correctness and
profiling.

## 14. Deliverables

What exists when this plan is finished: code, tests, docs, notes,
benchmarks, **and updates to design documents** — listed explicitly so
completion is objective.

## 15. Definition of Done

The standard phase DoD (extend per phase, never shrink):

- agreed scope implemented; acceptance criteria pass
- validation complete; tests pass
- benchmarks required by the plan recorded
- attribution complete; provenance behaviour implemented
- relevant design docs/ADRs updated to reflect reality
- known limitations documented
- no unresolved blocking decisions remain

## 16. Change log

Significant mid-phase plan changes, dated, with reasons — so the record
isn't Git-history archaeology:

> 2026-…: changed X to Y after validation exposed Z.

## 17. Retrospective *(appended at completion)*

- What changed from the plan:
- Unexpected findings:
- Negative results:
- Technical debt created:
- Decisions promoted to design docs/ADRs:
- Items carried into later phases:
