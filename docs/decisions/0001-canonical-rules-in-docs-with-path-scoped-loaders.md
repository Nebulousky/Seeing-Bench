# 0001. Canonical rules live in docs/, with path-scoped loaders in .claude/rules/

```yaml
Status: Accepted
Date: 2026-08-19
```

## Context and problem statement

`AGENTS.md` held every rule in the project, loaded in full at the start of every session.
Two pressures made that untenable. First, the evidence: repository context files cost
20-23% more per task for no significant gain in success, and the benefit that does exist
comes from specific, relevant instructions rather than from bulk (`docs/research/2026-08-19-agent-scaffolding-field-report.md`,
sections 4.1-4.2). Second, `AGENTS.md` was holding content its own sources-of-truth table
assigns elsewhere — data handling, architecture layering and testing rules all belong to
documents in `docs/`.

Every major agent ecosystem now offers conditional loading — Claude Code's `paths:`
frontmatter, Cursor's `globs`, Copilot's `applyTo`, AGENTS.md directory nesting. Adopting
it is clearly right. The question was *where the canonical text lives*, because
`.claude/rules/` is Claude-specific and this template's stated premise is that
tool-specific files are pointers and never state rules themselves.

## Considered options

- Canonical rule text in `docs/`, with thin path-scoped loaders in `.claude/rules/`
- Canonical rule text inside `.claude/rules/` with `paths:` frontmatter, `docs/` linking to it
- No split: keep one tool-agnostic `AGENTS.md` and simply trim it

## Decision

We chose **canonical rule text in `docs/`, with thin path-scoped loaders in
`.claude/rules/`**.

Each loader carries `paths:` frontmatter, states inline the two or three rules that must
never be missed, and points at the owning document for the rest. The rules remain
tool-agnostic and readable by any agent through the `AGENTS.md` pointer table; Claude
additionally gets them loaded at the moment they become relevant.

The deciding reason is that conditional loading is worth having but not worth making the
rulebook Claude-only. A project using Codex or Cursor must still be able to find every rule
this template sets, and a rule that exists only in `.claude/` would be invisible to them.

Inlining the non-negotiable line in the loader rather than deferring everything is
deliberate: Anthropic's authoring guidance warns that nested references are often only
partially read, so the loader must carry the part that cannot be missed even if the linked
document is never opened.

## Consequences

**Good:** the always-on budget carries only what applies to every task. Domain rules arrive
when their files are touched. The sources-of-truth table is now true rather than aspirational
— each subject really is owned by one document. Rules stay portable across agents.

**Bad:** a rule now lives in two places in a weak sense — the loader restates its most
critical line, and the document holds the full text. That is a real duplication risk, and it
is why `scaffold_check.py` verifies every loader resolves to an existing document. Claude
also pays one extra file read when it needs the full rule. And the evidence for the benefit
is indirect: 2605.10039 found file size had *no* measurable effect on adherence, so this
buys cost and relevance, not compliance. We should not expect agents to follow the rules
better because of it.

## Alternatives, and why not

| Option | Rejected because |
|---|---|
| Canonical text inside `.claude/rules/` | Best loading behaviour, but makes the rulebook Claude-only and inverts the template's stated premise that tool-specific files never state rules |
| No split, trim `AGENTS.md` only | Simplest and fully portable, but forfeits conditional loading entirely and leaves `AGENTS.md` owning content the sources-of-truth table assigns to `docs/` |
