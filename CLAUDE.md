@AGENTS.md

`AGENTS.md` (imported above) is the canonical source of development rules for this
repository. Do not duplicate or override those rules here — this file holds only what is
specific to Claude Code.

## Claude Code specifics

- **Auto memory is not the repository.** Notes saved to `~/.claude/projects/<project>/memory/`
  are machine-local and never appear in a diff. They may hold local convenience only;
  anything another contributor, another machine or CI would need gets promoted into the repo.
  Rules and promotion targets: `docs/development/agent-context.md`.
- **Delegate exploration.** Use the `investigator` subagent for research that reads many
  files, so this session pays for the findings rather than the search. It is read-only by
  toolset, which is also how the Research boundary is enforced.
- **Clear between unrelated tasks.** Two corrections on the same point means the context is
  the problem; a fresh session with a better prompt beats a long one carrying failed
  approaches.
- **`/context`** shows what actually loaded. Check that before concluding a rule is being
  ignored — an instruction that never entered the context window was not declined.
- **The Stop hook** (`.claude/hooks/done_gate.py`) blocks a turn from ending when the tree is
  dirty and a fast gate fails. Remove its entry from `.claude/settings.json` to opt out.
