"""Claude Code PreToolUse hook: run the quality gates before any git commit.

Reads the tool call from stdin (JSON). If the Bash command is a git commit, runs
the gates declared in `gates.py` and blocks the commit (exit 2) on any failure,
feeding the failure output back to the agent. Any other command passes through
untouched (exit 0).

The gate list lives in `gates.py` so this file, `done_gate.py` and CI cannot
disagree about what the gates are. The type-check target is resolved from
`pyproject.toml`, so nothing here needs editing per project.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gates as gatelib  # noqa: E402

COMMIT = re.compile(r"\bgit\b[^|;&]*\bcommit\b")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0
    command = payload.get("tool_input", {}).get("command", "")
    if not COMMIT.search(command):
        return 0

    # The scaffolding can be broken in a repository that has no package yet, so
    # these run regardless of whether the project has been set up.
    to_run = list(gatelib.SCAFFOLD_GATES)

    package = gatelib.package_dir()
    if package is not None:
        to_run += gatelib.resolve(gatelib.PROJECT_GATES, package)
    elif (gatelib.ROOT / "pyproject.toml").exists():
        print(
            "Commit blocked: the quality gates cannot run because no package "
            "directory could be resolved from pyproject.toml. Set [project].name "
            "to match the package directory, or edit package_dir() in "
            ".claude/hooks/gates.py.",
            file=sys.stderr,
        )
        return 2
    # No pyproject at all: the project is not set up yet and there is nothing to
    # gate beyond the scaffolding. Deliberately permissive so the first commits
    # of a new repo are possible.

    failures = gatelib.failures(to_run)
    if failures:
        print(
            "Commit blocked: quality gates failed (AGENTS.md, Definition of done).\n\n"
            + "\n\n".join(failures),
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
