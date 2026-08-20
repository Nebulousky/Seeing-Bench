"""The quality gates, declared once and shared by every hook that runs them.

`AGENTS.md` lists the same commands for humans and agents to read, and
`.github/workflows/ci.yml` runs them in CI. Those two are text and can drift from
this file, so `scaffold_check.py` compares all three and fails when they disagree.

Gates are split into two tiers because this template ships without a
`pyproject.toml`: a fresh clone has no package to lint or type-check, but its
scaffolding can still be broken. SCAFFOLD_GATES therefore run always, and
PROJECT_GATES activate once a package exists.
"""

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PACKAGE_PLACEHOLDER = "<package>"

# Run in every repository, set up or not.
SCAFFOLD_GATES: list[list[str]] = [
    ["python", ".claude/hooks/scaffold_check.py"],
]

# Run once a pyproject.toml exists and a package directory resolves.
PROJECT_GATES: list[list[str]] = [
    ["ruff", "check", "."],
    ["ruff", "format", "--check", "."],
    ["mypy", "src/seeingbench", "tests"],
    ["pytest", "-q"],
    ["python", ".claude/hooks/licence_check.py"],
]

# Cheap enough to run when a turn ends, not just when a commit is attempted.
# Excludes mypy and pytest, which are too slow to run on every turn.
FAST_GATE_NAMES: frozenset[str] = frozenset({"ruff", "scaffold_check.py"})


def find_tool(name: str) -> str:
    """Prefer the project venv's tools; fall back to PATH."""
    for bindir in ("Scripts", "bin"):
        candidate = ROOT / ".venv" / bindir / name
        for suffix in (".exe", ""):
            path = candidate.with_name(candidate.name + suffix)
            if path.exists():
                return str(path)
    return shutil.which(name) or name


def package_dir() -> str | None:
    """The importable package to type-check, or None if not resolvable.

    Tries the wheel's declared packages first, then the distribution name with
    the usual dash/underscore normalisation, then a src/ layout.
    """
    import tomllib

    pyproject = ROOT / "pyproject.toml"
    if not pyproject.exists():
        return None
    config = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    declared = (
        config.get("tool", {})
        .get("hatch", {})
        .get("build", {})
        .get("targets", {})
        .get("wheel", {})
        .get("packages", [])
    )
    candidates = [*declared]

    name = config.get("project", {}).get("name")
    if name:
        candidates += [name.replace("-", "_"), f"src/{name.replace('-', '_')}"]

    for candidate in candidates:
        if (ROOT / candidate).is_dir():
            return candidate
    return None


def resolve(gates: list[list[str]], package: str | None) -> list[list[str]]:
    """Substitute the package placeholder into the gate commands."""
    return [[package if arg == PACKAGE_PLACEHOLDER and package else arg for arg in gate] for gate in gates]


def is_fast(gate: list[str]) -> bool:
    """Whether this gate is cheap enough for the Stop hook."""
    return any(part.split("/")[-1] in FAST_GATE_NAMES for part in gate)


def run(gate: list[str]) -> str | None:
    """Run one gate; return its output on failure, None on success."""
    try:
        result = subprocess.run(
            [find_tool(gate[0]), *gate[1:]],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
    except OSError as exc:
        # A missing tool is a failed gate, not a reason to let the commit
        # through: an uninstalled linter checks nothing.
        return f"$ {' '.join(gate)}\ncould not run {gate[0]}: {exc}"
    if result.returncode != 0:
        output = (result.stdout + result.stderr).strip()
        return f"$ {' '.join(gate)}\n{output[-3000:]}"
    return None


def failures(gates: list[list[str]]) -> list[str]:
    """Run every gate, returning the output of each that failed."""
    return [output for gate in gates if (output := run(gate)) is not None]
