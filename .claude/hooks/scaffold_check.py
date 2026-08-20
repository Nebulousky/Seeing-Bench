"""Verify the agent scaffolding itself: references, drift, frontmatter, Unicode.

The scaffolding's failure mode is rot, not breakage. A pointer to a document
somebody deleted, a gate command changed in one file and not the other two, a
skill whose description no longer says when to use it — none of these raise an
error anywhere, and all of them quietly stop the scaffolding working.

Run it directly, or let the pre-commit and Stop hooks run it:

    python .claude/hooks/scaffold_check.py

Exits 0 when clean, 1 when problems are found. Stdlib only, by design: this file
must keep working in a repository that has no dependencies installed yet.
"""

import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gates as gatelib  # noqa: E402

ROOT = gatelib.ROOT

AGENTS_LINE_BUDGET = 150
SKILL_LINE_BUDGET = 500

# Paths that legitimately do not exist in a template that has not been set up.
EXPECTED_ABSENT = {
    "pyproject.toml",
    "CHANGELOG.md",
    "THIRD-PARTY-NOTICES.md",
}

# Characters that carry no visible glyph and can hide instructions in a file a
# reviewer believes they have read. The Rules File Backdoor vector; see
# docs/security.md.
INVISIBLE = (
    {0x00AD, 0x180E, 0x2028, 0x2029, 0xFEFF}
    | set(range(0x200B, 0x2010))  # zero-width and bidi marks
    | set(range(0x202A, 0x202F))  # bidi embedding and override
    | set(range(0x2060, 0x2065))  # word joiner, invisible operators
    | set(range(0x2066, 0x206A))  # bidi isolates
    | set(range(0xE0000, 0xE0080))  # tag characters
)

INSTRUCTION_GLOBS = (
    "AGENTS.md",
    "CLAUDE.md",
    "SETUP.md",
    "README.md",
    ".claude/**/*.md",
    "docs/**/*.md",
    "evals/**/*.md",
    "experiments/**/*.md",
)

# `path/like/this` in backticks, or a markdown link target.
BACKTICK = re.compile(r"`([^`\n]+)`")
LINK = re.compile(r"\]\(([^)\s]+)\)")

# Bare filenames worth verifying: those this template owns at the repository
# root. Anything else without a slash is ambiguous and is left alone.
ROOT_FILES = {
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "SETUP.md",
    "THIRD-PARTY-NOTICES.md",
    "CHANGELOG.md",
    "pyproject.toml",
    ".gitignore",
    ".gitattributes",
}


def sanitise(text: str) -> str:
    """Make a message safe to print on any console.

    Findings quote file content, and the whole point of the Unicode check is that
    the content may contain characters a terminal cannot render — one of which
    would otherwise crash the reporter that found it. Invisible characters are
    shown as their code point so the message stays readable and printable.
    """
    out = []
    for char in text:
        if ord(char) in INVISIBLE or not char.isprintable():
            out.append(f"<U+{ord(char):04X}>")
        else:
            out.append(char)
    return "".join(out)


class Report:
    def __init__(self) -> None:
        self.problems: list[str] = []
        self.notes: list[str] = []

    def problem(self, where: str, message: str) -> None:
        self.problems.append(sanitise(f"{where}: {message}"))

    def note(self, message: str) -> None:
        self.notes.append(sanitise(message))


def instruction_files() -> list[Path]:
    seen: dict[Path, None] = {}
    for pattern in INSTRUCTION_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            if path.is_file():
                seen[path] = None
    return list(seen)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


# --------------------------------------------------------------------------- #
# Check: referenced paths exist
# --------------------------------------------------------------------------- #


def candidate_paths(text: str) -> set[str]:
    """Path-looking tokens from backtick spans and markdown links."""
    found = set()
    for match in list(BACKTICK.finditer(text)) + list(LINK.finditer(text)):
        token = match.group(1).strip().rstrip(".,;:")
        if not token or any(c in token for c in "*<>| ") or "://" in token:
            continue
        if token.startswith(("~", "#", "http", "/", ".venv")):
            continue
        if not token.isascii():
            continue
        found.add(token.rstrip("/"))
    return found


def checkable(token: str) -> bool:
    """Whether a token is a repo-relative path we can meaningfully verify.

    Requires the first segment to be a real directory, which excludes prose that
    happens to contain a slash (`type/short-topic`, `ui/application`) and slash
    commands (`/bugfix`). A bare filename is only checked when it is one this
    template is expected to own at the root, so that a reference to
    `settings.json` is not mistaken for a claim that it sits in the root.
    """
    if "/" not in token:
        return token in ROOT_FILES
    first = token.split("/", 1)[0]
    return bool(first) and (ROOT / first).is_dir()


def check_references(report: Report) -> None:
    for path in instruction_files():
        text = path.read_text(encoding="utf-8")
        for token in sorted(candidate_paths(text)):
            if not checkable(token) or token in EXPECTED_ABSENT:
                continue
            if not (ROOT / token).exists():
                line = next(
                    (i for i, ln in enumerate(text.splitlines(), 1) if token in ln), 0
                )
                report.problem(f"{rel(path)}:{line}", f"referenced path does not exist: {token}")


# --------------------------------------------------------------------------- #
# Check: gate commands agree across AGENTS.md, gates.py and ci.yml
# --------------------------------------------------------------------------- #


def declared_gates() -> list[str]:
    everything = gatelib.SCAFFOLD_GATES + gatelib.PROJECT_GATES
    return [" ".join(gate) for gate in everything]


def agents_md_gates() -> list[str]:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    block = re.search(r"## Commands\s*\n+```bash\n(.*?)```", text, re.S)
    if not block:
        return []
    commands = []
    for raw in block.group(1).splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            commands.append(" ".join(line.split()))
    return commands


def check_gate_drift(report: Report) -> None:
    # Compared exactly, including flags. AGENTS.md documents the command that
    # actually runs, so an added flag is drift like any other change: a reader
    # who copies the documented command must get the behaviour the gate has.
    declared = set(declared_gates())
    documented = agents_md_gates()
    if not documented:
        report.problem("AGENTS.md", "no '## Commands' bash block found; gate drift cannot be checked")
        return

    for command in documented:
        if command not in declared:
            report.problem("AGENTS.md", f"gate documented but not declared in gates.py: {command}")
    for command in sorted(declared - set(documented)):
        report.problem("gates.py", f"gate declared but not documented in AGENTS.md: {command}")

    # CI runs the gates through run_gates.py rather than listing them, so the
    # list has one definition and CI cannot drift. Check only that it still does.
    ci_path = ROOT / ".github" / "workflows" / "ci.yml"
    if ci_path.exists():
        ci = ci_path.read_text(encoding="utf-8")
        if "run_gates.py" not in ci:
            report.problem(
                "ci.yml",
                "does not invoke .claude/hooks/run_gates.py; CI would no longer run the "
                "declared gates",
            )


# --------------------------------------------------------------------------- #
# Check: invisible and bidirectional Unicode
# --------------------------------------------------------------------------- #


def check_unicode(report: Report) -> None:
    for path in instruction_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for column, char in enumerate(line, 1):
                if ord(char) in INVISIBLE:
                    name = unicodedata.name(char, "unnamed")
                    report.problem(
                        f"{rel(path)}:{lineno}:{column}",
                        f"invisible or bidirectional character U+{ord(char):04X} ({name}) "
                        f"- see docs/security.md",
                    )


# --------------------------------------------------------------------------- #
# Check: frontmatter on skills, agents and rules
# --------------------------------------------------------------------------- #


def frontmatter(path: Path) -> dict[str, str] | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    fields: dict[str, str] = {}
    current: str | None = None
    for line in text[3:end].splitlines():
        if not line.strip():
            continue
        if line.lstrip().startswith("- ") and current:
            fields[current] = (fields.get(current, "") + " " + line.strip()[2:]).strip()
        elif ":" in line and not line.startswith((" ", "\t")):
            key, _, value = line.partition(":")
            current = key.strip()
            fields[current] = value.strip()
    return fields


def check_frontmatter(report: Report) -> None:
    for path in sorted(ROOT.glob(".claude/skills/*/SKILL.md")):
        fields = frontmatter(path)
        if fields is None:
            report.problem(rel(path), "missing YAML frontmatter")
            continue
        for key in ("name", "description"):
            if not fields.get(key):
                report.problem(rel(path), f"frontmatter missing '{key}'")
        description = fields.get("description", "")
        if description.startswith(("I ", "You ", "I'", "You'")):
            report.problem(rel(path), "description must be third person, not first or second")
        if description and "when" not in description.lower():
            report.problem(rel(path), "description does not say when to use the skill")
        name = fields.get("name", "")
        if name and name != path.parent.name:
            report.problem(rel(path), f"frontmatter name '{name}' does not match directory '{path.parent.name}'")

    for path in sorted(ROOT.glob(".claude/agents/*.md")):
        fields = frontmatter(path)
        if fields is None:
            report.problem(rel(path), "missing YAML frontmatter")
            continue
        for key in ("name", "description", "tools"):
            if not fields.get(key):
                report.problem(rel(path), f"frontmatter missing '{key}'")

    for path in sorted(ROOT.glob(".claude/rules/*.md")):
        fields = frontmatter(path)
        if fields is None or not fields.get("paths"):
            report.problem(rel(path), "path-scoped rule missing 'paths' frontmatter")


# --------------------------------------------------------------------------- #
# Check: size budgets
# --------------------------------------------------------------------------- #


def check_budgets(report: Report) -> None:
    agents = ROOT / "AGENTS.md"
    if agents.exists():
        lines = len(agents.read_text(encoding="utf-8").splitlines())
        if lines > AGENTS_LINE_BUDGET:
            report.problem(
                "AGENTS.md",
                f"{lines} lines exceeds the {AGENTS_LINE_BUDGET}-line budget; "
                f"move detail into a document under docs/",
            )
    for path in sorted(ROOT.glob(".claude/skills/*/SKILL.md")):
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > SKILL_LINE_BUDGET:
            report.problem(rel(path), f"{lines} lines exceeds the {SKILL_LINE_BUDGET}-line budget")


# --------------------------------------------------------------------------- #
# Check: setup completeness (informational until the project is real)
# --------------------------------------------------------------------------- #


def check_setup(report: Report) -> None:
    # SETUP.md and README.md describe the convention rather than carrying
    # placeholders, so a marker in them is documentation, not unfinished work.
    documents_the_convention = {"SETUP.md", "README.md"}

    markers = []
    for path in instruction_files():
        if path.name in documents_the_convention:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            # The package placeholder is only a problem where it would break a
            # gate; elsewhere it is a reasonable stand-in in prose.
            breaks_a_gate = path.name == "AGENTS.md" and gatelib.PACKAGE_PLACEHOLDER in line
            if "TODO(setup)" in line or breaks_a_gate:
                markers.append(f"{rel(path)}:{lineno}")

    if not markers:
        return
    if (ROOT / "pyproject.toml").exists():
        for marker in markers:
            report.problem(marker, "unresolved setup placeholder in a configured project")
    else:
        report.note(
            f"{len(markers)} setup placeholder(s) remain - see SETUP.md. "
            f"Not a failure until pyproject.toml exists."
        )


# --------------------------------------------------------------------------- #


def main() -> int:
    # Windows consoles default to a codepage that cannot encode the dashes and
    # arrows used throughout these documents. Degrade rather than crash.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    report = Report()
    check_references(report)
    check_gate_drift(report)
    check_unicode(report)
    check_frontmatter(report)
    check_budgets(report)
    check_setup(report)

    for note in report.notes:
        print(f"note: {note}")

    if report.problems:
        print()
        for problem in report.problems:
            print(problem)
        count = len(report.problems)
        print(f"\n{count} problem{'s' if count != 1 else ''} found in the scaffolding.")
        return 1

    print("scaffolding OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
