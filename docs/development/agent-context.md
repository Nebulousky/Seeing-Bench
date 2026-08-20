# Agent context: what loads, what persists, what gets promoted

This document owns the mechanics of how project knowledge reaches an agent, what an agent is
allowed to persist outside the repository, and when something it learned has to be promoted
into version control.

It exists because `AGENTS.md` states that durable knowledge belongs in the repository and
never only in a conversation — and an agent that writes notes to a machine-local memory
directory is doing exactly the thing that rule forbids, without ever disobeying it.

## What loads, and when

| Mechanism | Loads | Cost |
|---|---|---|
| `AGENTS.md` via `CLAUDE.md` | Every session, in full | Paid on every task |
| `.claude/rules/*.md` with `paths:` | When a matching file is touched | Paid only when relevant |
| `.claude/skills/*/SKILL.md` | When invoked, or when the model judges it relevant | Paid on use |
| `docs/**` | Only when read | Free until needed |

Rules for placing something new are in
`docs/decisions/0002-enforcement-over-instruction.md`: prefer a gate, then a hook, then a
path-scoped rule, then prose.

Use `/context` to see what actually loaded. If a rule is being ignored, check that it loaded
at all before rewriting it — an instruction that never entered the context window is not an
instruction the model declined to follow.

## Auto memory

Claude Code keeps a per-repository memory directory outside the repository, at
`~/.claude/projects/<project>/memory/`, and writes notes to it as it works. It is:

- **machine-local** — not shared with anyone, not present in a fresh clone, not on CI
- **not version-controlled** — it never appears in a diff and no one reviews it
- **shared across worktrees** of the same repository, but not across machines
- **partially loaded** — only the first 200 lines or 25KB of its `MEMORY.md` index

### Rules

- **Auto memory may hold convenience only.** Local build quirks, paths, tool invocations,
  preferences discovered while working. Things whose loss costs a few minutes.
- **Nothing may live only in auto memory** that another contributor, another machine, or CI
  would need. If losing it would cost more than rediscovering it, it belongs in the
  repository.
- **Never let a secret, credential, token or customer datum reach it.** It sits outside the
  repository, so `.gitignore` does not protect it and no secret scanner looks at it.
- **Subagent memory is separate.** A subagent does not inherit the main conversation's auto
  memory. Do not use it as a handoff channel; pass what a subagent needs in its prompt.

### Promotion

When a note in auto memory turns out to be a project fact rather than a local convenience,
move it to where it can be reviewed:

| What it turned out to be | Where it belongs |
|---|---|
| A rule everyone must follow | `AGENTS.md`, or a path-scoped rule |
| Knowledge about the domain or the design | The owning document in `docs/` |
| A claim about behaviour | A test |
| A decision with consequences | An ADR in `docs/decisions/` |
| A finding from investigation | A note in `docs/research/` |

Audit what has accumulated with `/memory`. Doing this occasionally is the cheapest way to
find rules that were never written down — an entry that keeps being re-learned is a rule
missing from the repository.

## Working within the context budget

Model performance degrades as context fills, and instruction compliance decays measurably
through a session — roughly 5.6% lower odds per generated function
(`docs/research/2026-08-19-agent-scaffolding-field-report.md`, section 4.1). Practical
consequences for work in this repository:

- **Delegate exploration.** Use the `investigator` subagent for research that reads many
  files. It reads in its own context and returns findings, so the main session pays for the
  answer rather than the search.
- **Clear between unrelated tasks** rather than accumulating an irrelevant history.
- **Prefer a fresh session with a better prompt** to a long session carrying failed
  approaches. Two corrections on the same point means the context is the problem.
- **The late steps of a workflow are the ones that get skipped.** That is why the gates exist
  and why `done_gate.py` runs at the end of a turn — not as a substitute for reading the
  workflow, but because compliance is weakest exactly where a workflow's verification sits.

Aim to keep utilisation moderate rather than maximal; roughly half the window is a
reasonable working target for complex work, leaving room for the complications that appear
later in a task.

## Giving agents knowledge of an API surface

Once this project has a public API that agents must use correctly, the highest-leverage
option is a **compressed index in the always-on file** rather than a skill they must decide
to invoke. In the strongest published measurement of this, an 8KB delimited index of a
framework's API — compressed from 40KB of prose, and holding references to files rather than
their content — took task pass rate from 53% to 100%, while the equivalent knowledge offered
as a retrievable skill reached 79% and went uninvoked in 56% of runs.

The general rule: **knowledge needed on most tasks belongs in the always-on file; knowledge
needed on a specific, explicitly-triggered workflow belongs in a skill.**

This is a technique for later, not now — the template has no API surface. It is recorded
here so the option is known when there is one, and so nobody rediscovers it by writing a
skill first.

## If this becomes a monorepo

The mechanisms above are single-package by default. For several packages in one repository:

- Nested `AGENTS.md` files scope rules to a subtree; the **nearest file to the edited file
  wins**, and every major agent tool implements that same precedence rule.
- Path-scoped rules in `.claude/rules/` already handle per-package scoping without nesting,
  and are preferable while one root `AGENTS.md` is still accurate.
- `scaffold_check.py` resolves referenced paths from the repository root. Nested files with
  package-relative references will need it taught about that.

Prefer path scoping until a subtree genuinely needs rules that contradict the root — at which
point nesting is the honest expression of it.

## Related

- `AGENTS.md` — the always-on rules and the pointer table
- `docs/decisions/0001-canonical-rules-in-docs-with-path-scoped-loaders.md` — why rules are arranged this way
- `docs/security.md` — instruction files as executable input
