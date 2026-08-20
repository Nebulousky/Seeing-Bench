"""Run every applicable quality gate. The entry point CI uses.

CI calls this rather than listing the gates itself, so the gate list has exactly
one definition (`gates.py`) and CI cannot drift from the pre-commit hook. The
tradeoff is that CI shows one step instead of one per gate; the output below
names which gate failed, which recovers most of that.

    python .claude/hooks/run_gates.py

Exits 0 when every gate passes, 1 otherwise.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gates as gatelib  # noqa: E402


def main() -> int:
    to_run = list(gatelib.SCAFFOLD_GATES)

    package = gatelib.package_dir()
    if package is not None:
        to_run += gatelib.resolve(gatelib.PROJECT_GATES, package)
        print(f"gates: scaffolding + project (package: {package})")
    elif (gatelib.ROOT / "pyproject.toml").exists():
        print(
            "No package directory could be resolved from pyproject.toml. Set "
            "[project].name to match the package directory, or edit package_dir() "
            "in .claude/hooks/gates.py.",
            file=sys.stderr,
        )
        return 1
    else:
        # A template that has not been set up yet still has scaffolding worth
        # checking. Matches pre_commit_gate.py.
        print("gates: scaffolding only (no pyproject.toml yet)")

    failures = gatelib.failures(to_run)
    for failure in failures:
        print(f"\n{failure}", file=sys.stderr)

    if failures:
        count = len(failures)
        print(f"\n{count} gate{'s' if count != 1 else ''} failed.", file=sys.stderr)
        return 1

    print(f"all {len(to_run)} gates passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
