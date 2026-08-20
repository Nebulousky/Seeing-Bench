"""Enforce the licensing hard rule as an exit code rather than a paragraph.

`AGENTS.md` hard rule 2 governs which dependency licences are acceptable and
requires a `THIRD-PARTY-NOTICES.md` entry in the same change. Both are checkable,
so both are checked here rather than left to recall.

    python .claude/hooks/licence_check.py

Inert until a `pyproject.toml` exists. Configure in that file:

    [tool.licence-check]
    allowed  = ["MIT", "BSD", "Apache", "ISC", "PSF", "MPL"]
    denied   = ["GPL", "AGPL", "SSPL"]
    ignore   = ["ruff", "mypy", "pytest"]      # never distributed
    overrides = { somepkg = "MIT" }            # metadata is wrong or missing

Checks the **transitive** runtime set - the declared dependencies and everything
they pull in - because the case that matters most is a permissive package that
depends on a copyleft one. Development tooling is excluded by construction: it is
not reachable from [project].dependencies.

`--sbom` writes a minimal CycloneDX SBOM of that set to stdout instead of
checking it.

Stdlib only: a licensing gate that needs a dependency installed to tell you about
your dependencies is a gate that fails open on a fresh checkout.
"""

import json
import sys
import tomllib
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NOTICES = ROOT / "THIRD-PARTY-NOTICES.md"

DEFAULT_ALLOWED = ["MIT", "BSD", "Apache", "ISC", "PSF", "MPL", "Unlicense", "Zlib"]
DEFAULT_DENIED = ["AGPL", "SSPL", "GPL"]


def config() -> dict | None:
    pyproject = ROOT / "pyproject.toml"
    if not pyproject.exists():
        return None
    return tomllib.loads(pyproject.read_text(encoding="utf-8"))


def licence_text(dist: metadata.Distribution) -> str:
    """Everything the distribution says about its licence, as one string."""
    meta = dist.metadata
    parts = [
        meta.get("License-Expression", ""),
        meta.get("License", ""),
        *[c for c in meta.get_all("Classifier", []) or [] if "License" in c],
    ]
    return " ".join(p for p in parts if p and p != "UNKNOWN")


def classify(text: str, allowed: list[str], denied: list[str]) -> tuple[str, str]:
    """Return (verdict, reason). Verdict is ok, denied, conditional or unknown."""
    upper = text.upper()
    if not upper.strip():
        return "unknown", "no licence metadata"

    # LGPL must be tested before GPL: it is permitted under a condition this
    # script cannot verify, whereas GPL and AGPL are not permitted at all.
    if "LGPL" in upper and "AGPL" not in upper:
        return "conditional", "LGPL: permitted only if dynamically linked and user-replaceable"
    for token in denied:
        if token.upper() in upper:
            return "denied", f"{token} found in: {text.strip()[:80]}"
    for token in allowed:
        if token.upper() in upper:
            return "ok", token
    return "unknown", f"unrecognised licence: {text.strip()[:80]}"


def normalise(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def requirement_name(spec: str) -> str:
    """The distribution name from a requirement specifier."""
    name = spec.split(";")[0]
    for separator in ("[", "=", ">", "<", "!", "~", "(", " "):
        name = name.split(separator)[0]
    return normalise(name)


def declared_dependencies(cfg: dict) -> set[str]:
    """Names declared in [project].dependencies, normalised."""
    declared = cfg.get("project", {}).get("dependencies", []) or []
    return {n for spec in declared if (n := requirement_name(spec))}


def is_conditional(spec: str) -> bool:
    """Whether a requirement only applies under an extra or environment marker.

    Optional requirements are not necessarily shipped, so pulling their whole
    subtree into the distributed set would flag dependencies nobody installs.
    """
    marker = spec.split(";", 1)[1] if ";" in spec else ""
    return "extra ==" in marker


def distributed_closure(cfg: dict) -> tuple[set[str], set[str]]:
    """The transitive runtime dependency set, and the names that could not be resolved.

    A licensing gate that checks only direct dependencies misses the case that
    matters most: a permissive package that pulls in a copyleft one. This walks
    Requires-Dist from the declared runtime dependencies outward.

    Unresolved names are reported rather than skipped. A dependency that is
    declared but not installed cannot be cleared, and silently passing it would
    make the gate fail open exactly when the environment is incomplete.
    """
    installed = {normalise(d.metadata.get("Name") or ""): d for d in metadata.distributions()}
    closure: set[str] = set()
    unresolved: set[str] = set()
    queue = list(declared_dependencies(cfg))

    while queue:
        name = queue.pop()
        if name in closure or name in unresolved:
            continue
        dist = installed.get(name)
        if dist is None:
            unresolved.add(name)
            continue
        closure.add(name)
        for spec in dist.requires or []:
            if not is_conditional(spec):
                queue.append(requirement_name(spec))

    return closure, unresolved


def notices_entries() -> set[str]:
    if not NOTICES.exists():
        return set()
    entries = set()
    for line in NOTICES.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            name = line[3:].strip().split()[0] if line[3:].strip() else ""
            if name:
                entries.add(name.lower().replace("_", "-"))
    return entries


def emit_sbom(
    cfg: dict,
    closure: set[str],
    installed: dict[str, metadata.Distribution],
    overrides: dict[str, str],
) -> None:
    """Write a minimal CycloneDX SBOM of the distributed set to stdout.

    Deliberately minimal: enough to feed a compliance process or regenerate
    THIRD-PARTY-NOTICES.md, without pulling in a dependency to describe this
    project's dependencies. Redirect it where you need it:

        python .claude/hooks/licence_check.py --sbom > sbom.json
    """
    project = cfg.get("project", {})
    components = []
    for name in sorted(closure):
        dist = installed.get(name)
        licence = overrides.get(name) or (licence_text(dist) if dist else "")
        components.append(
            {
                "type": "library",
                "name": name,
                "version": (dist.metadata.get("Version") if dist else None) or "unknown",
                "purl": f"pkg:pypi/{name}@{(dist.metadata.get('Version') if dist else 'unknown')}",
                "licenses": [{"license": {"name": licence.strip() or "unknown"}}],
            }
        )

    print(
        json.dumps(
            {
                "bomFormat": "CycloneDX",
                "specVersion": "1.5",
                "version": 1,
                "metadata": {
                    "component": {
                        "type": "application",
                        "name": project.get("name", "unknown"),
                        "version": project.get("version", "unknown"),
                    }
                },
                "components": components,
            },
            indent=2,
        )
    )


def main() -> int:
    cfg = config()
    if cfg is None:
        # No project yet; nothing to license-check. Deliberately permissive so a
        # fresh clone can commit, matching pre_commit_gate.py.
        return 0

    section = cfg.get("tool", {}).get("licence-check", {})
    allowed = section.get("allowed", DEFAULT_ALLOWED)
    denied = section.get("denied", DEFAULT_DENIED)
    ignore = {n.lower().replace("_", "-") for n in section.get("ignore", [])}
    overrides = {k.lower().replace("_", "-"): v for k, v in section.get("overrides", {}).items()}

    own = normalise(cfg.get("project", {}).get("name") or "")
    problems: list[str] = []
    warnings: list[str] = []

    # What actually ships: the declared runtime dependencies and everything they
    # pull in. Development tooling is excluded by construction rather than by
    # remembering to ignore-list it.
    closure, unresolved = distributed_closure(cfg)
    closure -= {own} | ignore

    for name in sorted(unresolved - ignore - {own}):
        problems.append(
            f"{name}: declared as a dependency but not installed, so its licence "
            f"cannot be checked. Install it, or ignore-list it if it is not distributed."
        )

    installed = {normalise(d.metadata.get("Name") or ""): d for d in metadata.distributions()}
    for name in sorted(closure):
        dist = installed.get(name)
        text = overrides.get(name) or (licence_text(dist) if dist else "")
        verdict, reason = classify(text, allowed, denied)
        if verdict == "denied":
            problems.append(f"{name}: refused licence - {reason}")
        elif verdict == "unknown":
            problems.append(
                f"{name}: {reason}. Add it to [tool.licence-check].overrides "
                f"once you have checked the licence by hand."
            )
        elif verdict == "conditional":
            warnings.append(f"{name}: {reason}")

    for name in sorted(closure - notices_entries()):
        problems.append(f"{name}: distributed dependency with no THIRD-PARTY-NOTICES.md entry")

    if "--sbom" in sys.argv:
        emit_sbom(cfg, closure, installed, overrides)
        return 0

    for warning in warnings:
        print(f"warning: {warning}")

    if problems:
        print("\nLicensing gate failed (AGENTS.md, hard rule 2):\n", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(
            "\nSee docs/external-sources.md. Do not weaken this gate to get past it.",
            file=sys.stderr,
        )
        return 1

    print("licences OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
