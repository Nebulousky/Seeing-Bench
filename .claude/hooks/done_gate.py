"""Claude Code Stop hook: refuse to end a turn on a knowingly broken tree.

The commit gate catches problems at `git commit`. Nothing caught the case where
an agent decides work is finished and simply does not commit — and compliance
with instructions measurably decays through a session, so the later a step sits
in a workflow the less reliably it happens. A Stop hook is enforcement at exactly
that point: it blocks the turn from ending until the check passes.

Cost matters, because Stop fires at the end of every turn including
conversational ones. So:

  - a clean working tree exits immediately, doing no work at all
  - a dirty tree runs only the fast gates (lint, format, scaffolding)
  - mypy and pytest stay at commit time, where their cost is proportionate

Claude Code overrides a Stop hook after 8 consecutive blocks, so this can slow a
determined agent down but cannot deadlock it.

Registered in `.claude/settings.json`. Remove that entry to opt out.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gates as gatelib  # noqa: E402


def tree_is_dirty() -> bool:
    """Whether tracked files have uncommitted changes.

    Untracked files are ignored: scratch files a turn happened to create are not
    a reason to refuse to hand control back to the user.
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            capture_output=True,
            text=True,
            cwd=gatelib.ROOT,
        )
    except OSError:
        return False
    return result.returncode == 0 and bool(result.stdout.strip())


def main() -> int:
    if not tree_is_dirty():
        return 0

    to_run = [g for g in gatelib.SCAFFOLD_GATES if gatelib.is_fast(g)]
    package = gatelib.package_dir()
    if package is not None:
        to_run += [
            g for g in gatelib.resolve(gatelib.PROJECT_GATES, package) if gatelib.is_fast(g)
        ]

    failures = gatelib.failures(to_run)
    if failures:
        print(
            "Not done: the working tree has uncommitted changes and a fast gate "
            "fails (AGENTS.md, Definition of done).\n\n"
            + "\n\n".join(failures)
            + "\n\nFix these, or say explicitly that you are leaving the tree in "
            "this state and why.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
