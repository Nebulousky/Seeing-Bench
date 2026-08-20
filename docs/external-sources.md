# Work derived from external sources

This document owns the traceability chain for anything taken from a paper, spec, article or
other implementation. It is the canonical text; the path-scoped loader at
`.claude/rules/external-sources.md` carries only the lines that must never be missed.

The chain is: **source → note (`docs/research/`) → implementation → validation.**

## Rules that do not bend

- **Never copy code from a reference implementation**, regardless of its licence, where the
  obligation or its provenance would be inherited silently. Reimplement from the
  description. Read reference repositories for understanding only.
- **Record the licence of a *description* separately from the licence of its *code*.** A
  permissively licensed paper does not make its accompanying repository permissive, and the
  reverse is equally true.
- **Never imply that an existing published technique originated here.** Every algorithm or
  technique taken from an external source cites that source in its implementation
  documentation.

## Production code

Before externally derived work enters the package, all of the following exist:

1. A research note in `docs/research/`, written first — including the assumptions the
   source depends on, which are usually the part that does not survive contact with real
   data.
2. A citation in the implementation documentation, naming what was taken from where.
3. Validation per `docs/development/testing.md`.

## Prototypes

Prototypes live in `experiments/` and need only a citation and a short results note. The
gates do not block `experiments/`, and production standards do not apply there.

Record **negative results**. An experiment that failed is a completed experiment, and an
unrecorded failure is rediscovered — usually by the same person, about a year later.

## Promotion from experiments/ to production

Promotion is a separate Implement task, never a move commit. It requires:

- tests
- validation against known-correct reference data
- comparison against the existing baseline
- documented limitations
- reasonable performance

**Impressive output is never sufficient.** A result that looks better is not evidence of a
better method; that is what the comparison against baseline is for.

## Dependencies

New dependencies are governed by hard rule 2 in `AGENTS.md` and enforced by
`.claude/hooks/licence_check.py`. In summary: permissive licences are fine, LGPL only if
dynamically linked and user-replaceable, strong copyleft is refused where proprietary
distribution must remain possible, and every dependency needs its `THIRD-PARTY-NOTICES.md`
entry in the same change.

The gate checks the **transitive** set — the declared runtime dependencies and everything
they pull in — because the case that matters most is a permissive package that itself
depends on a copyleft one. Development tooling is excluded by construction: it is not
reachable from `[project].dependencies`. A dependency that is declared but not installed is
reported rather than skipped; a licensing gate that quietly passes what it could not check
is worse than none.

`python .claude/hooks/licence_check.py --sbom` writes a minimal CycloneDX SBOM of that same
set, which is the easiest way to regenerate or audit `THIRD-PARTY-NOTICES.md`.

Two things the gate deliberately does not do. It does not judge whether an LGPL dependency
is *actually* dynamically linked and user-replaceable — that is a human call, so LGPL is
reported as conditional rather than passed or failed. And it does not verify per-file
licence headers; if this project needs that, adopt the REUSE specification and add
`reuse lint` to the gates in `.claude/hooks/gates.py`.

The same test applies to bundled assets. Share-alike and non-commercial material is
development-only and must never enter a distributed build.

Prefer mature, maintained packages. Add dependencies conservatively — but do not
reimplement hard, well-solved low-level functionality just to avoid one.

## Related

- `docs/research/TEMPLATE.md` — the note format
- `THIRD-PARTY-NOTICES.md` — the attribution record
- `.claude/skills/experiment/SKILL.md` — the workflow for `experiments/`
