#!/usr/bin/env bash
# Run eval scenarios against a throwaway copy of the repository.
#
# A starting point, not a finished harness. It executes each scenario's prompt in
# an isolated copy so a run cannot touch your working tree, and saves the
# transcript for you to read against the scenario's expected behaviour.
#
# Judging is deliberately manual. An automated judge is worth building once there
# are enough scenarios that reading them all is tedious, and not before — a judge
# written first tends to encode the behaviour you assumed rather than the
# behaviour you observed.
#
#   ./evals/run.sh                    # every scenario
#   ./evals/run.sh bugfix-reproduce   # one scenario
#
# Requires the `claude` CLI on PATH.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCENARIOS="$ROOT/evals/scenarios"
RESULTS="$ROOT/evals/results"

if ! command -v claude >/dev/null 2>&1; then
  echo "claude CLI not found on PATH." >&2
  exit 1
fi

if [ ! -d "$SCENARIOS" ]; then
  echo "No scenarios yet. Copy evals/TEMPLATE.md into evals/scenarios/<name>.md" >&2
  echo "and write it from an observed failure — see evals/README.md." >&2
  exit 1
fi

mkdir -p "$RESULTS"
stamp="$(date +%Y%m%d-%H%M%S)"

run_one() {
  local scenario="$1"
  local name
  name="$(basename "$scenario" .md)"
  echo "=== $name ==="

  # Extract the first fenced block after the '## Prompt' heading.
  local prompt
  prompt="$(awk '/^## Prompt/{f=1;next} f&&/^```/{c++;next} f&&c==1{print} c==2{exit}' "$scenario")"
  if [ -z "$prompt" ]; then
    echo "  no prompt block found; skipping" >&2
    return
  fi

  # Isolated copy: an eval must not be able to modify the repository it tests.
  local workdir
  workdir="$(mktemp -d)"
  trap 'rm -rf "$workdir"' RETURN
  git -C "$ROOT" archive HEAD | tar -x -C "$workdir"

  local out="$RESULTS/$stamp-$name.txt"
  (cd "$workdir" && claude -p "$prompt" --output-format text) >"$out" 2>&1 || true
  echo "  transcript: ${out#"$ROOT"/}"
  echo "  now read it against the expected behaviour in ${scenario#"$ROOT"/}"
}

if [ $# -gt 0 ]; then
  run_one "$SCENARIOS/$1.md"
else
  shopt -s nullglob
  for scenario in "$SCENARIOS"/*.md; do
    run_one "$scenario"
  done
fi
