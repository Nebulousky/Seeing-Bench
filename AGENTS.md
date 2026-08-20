# SeeingBench Development Rules

SeeingBench is scientific/computational-imaging software for benchmarking atmospheric lunar
reconstruction algorithms against retained synthetic truth and, later, independent orbital
truth. It is built for algorithm developers who need to know whether a reconstruction
recovered genuine lunar information rather than merely producing a sharper-looking image.
The central constraint is that reconstruction and validation truth remain separate:
ground-truth data may score an algorithm, but must not influence the reconstruction under
test.

This is the canonical rulebook. Tool-specific files (`CLAUDE.md`) point here and never
restate rules. Detail lives in the documents listed under **Where the rules live**.

**Authority.** This file is normative policy; accepted design docs record design decisions;
tests define required behaviour; code is the current implementation. These are different
kinds of authority, not a ranking. If they materially conflict, **stop and surface the
inconsistency**; never silently pick a winner or "fix" one to match another.

## Commands

```bash
ruff check .                              # lint
ruff format --check .                     # formatting
mypy src/seeingbench tests                # types
pytest -q                                 # tests
python .claude/hooks/scaffold_check.py    # scaffolding integrity
python .claude/hooks/licence_check.py     # dependency licences and notices
```

## Definition of done

Work is done when **every command above exits 0**, and:

- tests cover the change; a bug fix has a regression test that failed before the fix
- externally derived work cites its source in the implementation documentation
- documents that are now wrong have been updated

Report the evidence: the command run and what it returned. If you did not run it, say so.

## Boundaries

| | |
|---|---|
| **Always** | run the commands above before claiming done; cite external sources; keep derived products separate from the user's originals |
| **Ask first** | adding a dependency; changing an accepted plan or ADR; changing a public API; writing outside the package; anything irreversible |
| **Never** | modify the user's original files; commit datasets, secrets or machine-local paths; loosen a tolerance to make a test pass; weaken a gate instead of fixing what it caught; copy code from a reference implementation |

**Escalate: stop and report rather than working around:**

- a gate fails **3 times on the same cause**: stop, report the failure output
- policy, docs, tests and code disagree: stop, surface it, never pick a winner
- the task turns out to be a different task type: stop, re-triage
- a fix's root cause is architectural: stop; that is a Plan task, not a Fix

## Task routing

Identify the task type before substantial work. Where a skill exists, invoke it by name.
State the contract up front: type, scope, whether preconditions are met, intended validation.

A task may reveal another type but must not silently expand into it.

| Type | Precondition | Done when | Must not |
|---|---|---|---|
| **Triage** `/triage` | none | Type, prerequisites, risk and workflow identified | Do the work itself |
| **Research** `/research` | none | Note written to `docs/research/` from its template | Modify production behaviour |
| **Plan** `/phase-plan` | Relevant authority read | Accepted plan per `docs/plans/TEMPLATE.md` | Decide flagged-open questions alone |
| **Experiment** `/experiment` | Question and success criteria defined first | Results note recorded; negative results count | Leak into production |
| **Implement** | Accepted plan where required | Code, tests, docs, attribution; gates pass | Broaden scope; invent architecture |
| **Validate** | Metrics chosen for the property tested | Results recorded against stated criteria | Loosen tolerances to pass |
| **Fix** `/bugfix` | Defect reproduced, or documented why impossible | Root cause found; regression test passes | Change code before reproduction |
| **Refactor** | Behaviour covered by tests | Tests pass unchanged; structure improved | Change behaviour; smuggle features |
| **Optimise** `/optimise` | Baseline benchmark; profiled bottleneck | Before/after recorded; equivalence validated | Claim improvement without measurement |
| **Review** | none | Findings reported with locations and severity | Modify the work under review |
| **Converge** `/converge` | none | Conflicts between authorities reported | Resolve a conflict unilaterally |
| **Document** | none | Docs match reality | Duplicate canonical content |
| **Maintain** | Licence check for new dependencies | Gates pass; scoped to housekeeping | Drive-by behaviour changes |

Use the read-only subagents for Research, Review and Triage so the boundary is enforced by
tooling rather than by memory: `investigator` (research) and `reviewer` (review). Neither
can modify the repository.

## Hard rules

1. **Validation independence.** Reconstruction inputs, adapter preparation, and external
   engine invocations must never receive LRO, LOLA, NAC, synthetic latent truth, truth warp
   fields, or metrics-derived data unless the run is explicitly labelled as
   prior-informed. A diff that passes `truth/`, orbital-reference paths, or evaluator
   outputs into reconstruction code violates this rule.

2. **Licensing.** Enforced by `licence_check.py`. Permissive (MIT/BSD/Apache/ISC/PSF) is
   fine; **LGPL only if dynamically linked and user-replaceable**; strong copyleft
   (GPL/AGPL/SSPL) is refused where proprietary distribution must remain possible. Every new
   dependency gets its `THIRD-PARTY-NOTICES.md` entry **in the same change**. Full rules and
   the rules for bundled assets: `docs/external-sources.md`.

3. **Attribution.** Every algorithm or technique taken from an external source cites that
   source where it is implemented. Never imply that an existing published technique
   originated here.

4. **User data is not damaged.** Never modify, overwrite or write into the user's original
   files. Derived products are stored separately. Functions do not mutate their inputs
   unless mutation is the documented, intentional API.

Rules 2-4 protect against failures no benchmark measures. They are kept on judgement, and
the absence of an eval is not evidence against them; see section 6 of
`docs/research/2026-08-19-agent-scaffolding-field-report.md`.

## Git

Trunk-based; `main` always passes the gates. Branch as `type/short-topic` for anything
risky, large or experimental. Linear history: rebase or squash, no merge commits.
Imperative commit subject <=72 characters; the body explains **why**. Full rules:
`docs/development/git.md`.

## Where the rules live

| Document | Owns |
|---|---|
| `docs/architecture.md` | Layering, module map, dependency direction, project-wide conventions |
| `docs/data-handling.md` | Precision, types, conventions, what must never be silently destroyed |
| `docs/configuration.md` | Synthetic config schema, defaults, units, and CLI override behaviour |
| `docs/development/testing.md` | What "validated" means; how the scaffolding itself is evaluated |
| `docs/development/git.md` | Branching, history, commit conventions, versioning |
| `docs/development/agent-context.md` | What agents load and persist; auto memory and promotion |
| `docs/external-sources.md` | The source -> note -> implementation -> validation chain; dependencies |
| `docs/security.md` | Network and user-data posture; instruction files as executable input |
| `docs/roadmap.md` | What is being built, in what order, and each phase's exit criterion |
| `docs/plans/` | How one phase is executed, from `docs/plans/TEMPLATE.md` |
| `docs/decisions/` | Decisions that outlive the phase that made them (ADRs) |
| `docs/research/` | Findings from Research tasks, from `docs/research/TEMPLATE.md` |
| `evals/` | Scenarios that test whether these rules change agent behaviour |

`.claude/rules/*.md` load the relevant subset of these automatically when matching files are
touched. They restate only the lines that must never be missed; the documents above remain
canonical.

When adding a rule, prefer a gate, then a hook, then a path-scoped rule, then prose here.
Durable knowledge belongs in the repository, never only in a conversation.
