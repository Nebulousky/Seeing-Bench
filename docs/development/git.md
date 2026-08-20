# Git workflow and versioning

This document owns branching, history, commit conventions and versioning. `AGENTS.md`
carries only the lines needed on every task and points here for the rest.

## Trunk-based

`main` must always pass the quality gates. Direct commits to `main` are fine for docs,
config and small self-contained changes; anything risky, large or experimental gets a
short-lived branch, merged when green and deleted after.

Mandatory pull requests begin when there is a second contributor or CI enforcing them.

**Branch naming:** `type/short-topic` — `feat/…`, `fix/…`, `docs/…`, `exp/…` for
`experiments/` work.

## Linear history

Rebase or fast-forward; squash a messy branch. No merge commits from long-lived divergence —
`git bisect` must stay usable, and it is only useful if history is a line.

## Commit messages

Imperative subject, 72 characters or fewer. The body explains **why** and any behavioural
consequences. Small coherent commits, plain language, no marketing tone.

Not Conventional Commits — no type prefixes required.

Commit messages are where the reasoning for a change belongs. Comments in code explain
constraints the code cannot show; they do not explain why a change is correct.

## Never commit

Datasets, model checkpoints, build artifacts, secrets, machine-local paths, commented-out
dead code.

Line endings are normalised to LF in the repository via `.gitattributes`.

## Versioning

**SemVer with 0.x semantics** — breaking changes are allowed in minor bumps before 1.0,
matching the rule that correctness beats compatibility pre-release.

The version lives in `pyproject.toml` and `seeingbench.__version__`, and nowhere else.
Releases get annotated tags (`v0.1.0`). `CHANGELOG.md` follows Keep a Changelog format and
starts at the first tagged release, not before — a changelog with no releases in it is a
file people learn to ignore.

## Related

- `AGENTS.md` — the boundaries and the never list
- `docs/security.md` — why instruction-file diffs get code-level review
