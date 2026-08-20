# Third-party notices

Every runtime dependency gets an entry here, added **in the same change** that adds the
dependency (`AGENTS.md`, hard rule 2). `.claude/hooks/licence_check.py` parses the `##`
headings in this file and fails the gate on a dependency that has none.

Bundled assets — fonts, icons, data files, reference material — are listed here too, under
the same rules. Share-alike and non-commercial material is development-only and must never
enter a distributed build.

Development-only tooling that is never distributed does not need an entry. List those names
under `[tool.licence-check].ignore` in `pyproject.toml` so the gate agrees with you.

## Format

Copy this shape. The first word of the heading must be the distribution name exactly as it
appears on PyPI, because that is what the gate matches on.

```markdown
## example-package 1.2.3
SPDX: MIT
Source: https://github.com/example/example-package
Used for: what this project actually uses it for.
Notes: anything a redistributor needs to know — attribution requirements, bundled
       sub-components with different licences, patent grants.
```

Record the licence of a *description* (paper, spec, article) separately from the licence of
its *code*; see `docs/external-sources.md`.

## Dependencies

## numpy 2.x
SPDX: BSD-3-Clause
Source: https://github.com/numpy/numpy
Used for: array storage, synthetic image generation, dense displacement fields, FFT metrics,
       and numerical tests.
Notes: runtime dependency.
