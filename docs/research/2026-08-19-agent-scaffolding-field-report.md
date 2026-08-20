# Research: how should agent scaffolding be written, and does any of it work?

```yaml
Status: Complete
Date: 2026-08-19
Sources examined: 40
Informs: docs/decisions/0001, docs/decisions/0002, and the rebuild of AGENTS.md
```

## 1. Question

Agent scaffolding — a canonical rules file, task workflows, scoped subagents, a commit
gate — is now a widespread practice. Does the evidence show it improves agent behaviour,
and if so which parts? The answer decides what this template should contain and what form
its rules should take.

## 2. Scope

Investigated: the AGENTS.md convention and its ecosystem equivalents (Cursor, Copilot,
Cline, Gemini CLI), Claude Code's own instruction and enforcement mechanisms, spec-driven
development frameworks, practitioner context-engineering methodologies, agent-config
linting, and the security posture of distributed rules files.

Not investigated: non-Python ecosystems in depth, IDE-integrated assistants without a
repository rules file, and enterprise governance tooling.

Evidence current as of **August 2026**. Several findings concern fast-moving product
behaviour (Claude Code feature set, skill invocation reliability) and should be re-checked
before being relied on again. The four controlled studies are more durable than the
practitioner guidance around them.

## 3. Sources examined

**Primary — controlled studies** (numbers below taken from the papers, not from summaries):

- arXiv 2602.11988, *Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for
  Coding Agents?*, ETH SRI Lab — <https://arxiv.org/abs/2602.11988>
- arXiv 2606.20512, *Probe-and-Refine Tuning of Repository Guidance for Coding Agents* —
  <https://arxiv.org/abs/2606.20512>
- arXiv 2605.10039, *Instruction Adherence in Coding Agent Configuration Files: A Factorial
  Study of Four File-Structure Variables* — <https://arxiv.org/abs/2605.10039>
- Vercel, *AGENTS.md outperforms skills in our agent evals* —
  <https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals>
- Chroma, *Context Rot: How Increasing Input Tokens Impacts LLM Performance* —
  <https://www.trychroma.com/research/context-rot>

**Primary — specifications and vendor documentation:**

- AGENTS.md specification, Linux Foundation Agentic AI Foundation — <https://agents.md/>
- Claude Code: best practices, memory and CLAUDE.md, skill authoring, plugin marketplaces —
  <https://code.claude.com/docs/en/best-practices>, <https://code.claude.com/docs/en/memory>,
  <https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices>
- Anthropic, *Effective context engineering for AI agents* —
  <https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents>
- GitHub Copilot repository custom instructions, including `applyTo` path scoping

**Secondary — practitioner methodology and analysis** (relayed, not independently verified):

- HumanLayer, *Advanced Context Engineering / Frequent Intentional Compaction* —
  <https://github.com/humanlayer/advanced-context-engineering-for-coding-agents>
- GitHub Spec Kit — <https://github.com/github/spec-kit>
- Blake Crosley, *AGENTS.md Patterns: What Actually Changes Agent Behavior* (A/B tested)
- *The AGENTS.md Field Guide, 2026*; awesome-claude-code; Cline Memory Bank
- INNOQ and Marmelab critiques of spec-driven development

**Primary — security:**

- Pillar Security, *Rules File Backdoor* —
  <https://www.pillar.security/blog/new-vulnerability-in-github-copilot-and-cursor>
- MITRE ATLAS AML.CS0041; Cloud Security Alliance, README instruction injection

**Tooling surveyed:** agnix, agents-lint, cclint; pip-license-checker, REUSE, SPDX;
MADR 4.0; Diataxis; uv, Ruff, mypy, pyrefly, ty.

## 4. Findings

### 4.1 The four controlled studies

| Study | Method and sample | Headline result |
|---|---|---|
| arXiv 2602.11988 | AGENTbench: 138 instances across 12 Python repos with developer-written context files, plus SWE-bench Lite (300). Claude Code with Sonnet 4.5, Codex with GPT-5.2 and 5.1-mini, Qwen Code with Qwen3-30b-coder | Context files **cost +20-23%** per task. Developer-written **+4%** success, LLM-generated **-3%**; *neither statistically significant*. Steps rose 2.45-3.92 per instance; reasoning tokens +10-22% for LLM-generated files |
| arXiv 2606.20512 | Guidance tuned by synthetic bug-fix probes vs static guidance vs none | Tuned **33.0%** resolve vs **28.3%** static vs **25.5%** baseline — significant. The gain was **coverage**: correct file located **+14.5pp** more often, while patch quality stayed flat at ~59% |
| arXiv 2605.10039 | Factorial: 1,650 Claude Code sessions, 16,050 function-level observations, 2 TypeScript codebases, 3 frontier models, 5 tasks; mixed-effects with Bayesian analysis | Size, instruction position, file architecture and contradictions in adjacent files: **no detectable effect** after correction. Size and conflict showed strong evidence *for no effect* (Bayes factors 0.05-0.10). Compliance fell **~5.6% odds per generated function** within a session |
| Vercel evals | Next.js 16 API tasks, four configurations | No docs **53%**, skill by default **53%**, skill with explicit instructions **79%**, an 8KB docs index in AGENTS.md **100%**. The skill went **uninvoked in 56%** of runs |

Chroma's context-rot work supplies the mechanism behind session-length effects: all 18
models tested degrade as input grows, with 30+ point drops when the relevant content sits
in the middle of a long context.

### 4.2 What the content of a context file should be

2602.11988 found codebase overviews and directory enumerations gave **no measurable
benefit** for locating relevant files, while **specific tooling instructions** (use `uv`,
use `pytest`) did help. Its recommendation is that human-written context files describe only
minimal requirements, because unnecessary requirements make tasks harder. Notably, agents
**did** follow the instructions — adherence was not the failure, usefulness was.

### 4.3 What writing style changes behaviour

Blake Crosley's A/B runs (identical tasks, 10+ repetitions with and without each pattern)
found **no measurable change** from: prose without commands, ambiguous directives such as
"be careful" or "where appropriate", contradictory priorities without explicit ordering, and
style guides carrying no enforcement command.

Measurable change came from: command-first instructions, closure defined as specific exit
codes, sections organised by workflow phase rather than by topic, and escalation rules with
a hard "never" list and an explicit attempt count.

The same source cites ICLR 2026 *Ambig-SWE*: models "almost never interact" when
requirements conflict, and prompting them to interact improved performance **up to 74%**.

### 4.4 Conditional loading is the industry-wide convergence

Every major ecosystem provides a way to load rules only when they are relevant: Claude
Code's `.claude/rules/*.md` with `paths:` frontmatter, Cursor's `.mdc` `globs` and
`alwaysApply`, Copilot's `.github/instructions/*.instructions.md` with `applyTo`, and
AGENTS.md directory nesting where the nearest file wins (the OpenAI repository reportedly
carries 88 of them).

### 4.5 Enforcement is categorically different from instruction

Anthropic's documentation states the distinction directly: settings and hooks are "enforced
by the client regardless of what Claude decides to do", while CLAUDE.md content "shapes
Claude's behavior but is not a hard enforcement layer" — it is delivered as a user message,
with no guarantee of compliance. A Stop hook can block a turn from ending until a check
passes, overridden after 8 consecutive blocks; `/goal` is a session-scoped prompt-based Stop
hook, separating the agent that works from the agent that decides it is done.

### 4.6 Distributed rules files are an attack surface

The Rules File Backdoor (Pillar Security; MITRE ATLAS AML.CS0041) embeds instructions in
rules files using hidden Unicode. It survives forking and propagates to everyone who clones
the repository. The Cloud Security Alliance published parallel findings on README
instruction injection. This applies directly to any repository whose purpose is to be
cloned — which is exactly what this one is.

### 4.7 Process frameworks

Spec-driven frameworks (Spec Kit, BMAD-METHOD, Kiro, OpenSpec) share a constitution, spec,
plan, tasks, implement chain. Spec Kit additionally provides cross-artefact consistency
checking (`/analyze`) and a code-versus-spec gap report (`/converge`).

Recurring criticism: specs diverge from code as projects grow, document overhead can exceed
the cost of building the feature, and agents treat specs as suggestions — one critique puts
adherence near 70%. HumanLayer's methodology puts human review on the research and plan
artefacts rather than on the diff, reasoning that "a bad line of a plan could lead to
hundreds of bad lines of code; a bad line of research could land you with thousands", and
targets 40-60% context utilisation with failure ranked incorrect > incomplete > noisy.

### 4.8 Evaluation-driven authoring

Anthropic's skill-authoring guidance is explicit that evaluations come *before*
documentation: run the task without the skill, document the failures, build three scenarios
testing those gaps, then write the minimum that passes. The refinement loop uses one model
instance to author instructions and a fresh instance to use them, with observed failures
driving revision. This is 2606.20512's probe-and-refine result expressed as a workflow.

## 5. Conclusions and confidence

1. **Speculative rules files do not pay for themselves.** *High confidence* — 2602.11988 is
   the largest and most direct test, across three agents and four models.
2. **Guidance tuned against observed failures does pay.** *High confidence* — 2606.20512,
   statistically significant and mechanistically explained (coverage, not patch quality).
3. **A speculative rules file cannot be fixed by trimming or reordering it.** *High
   confidence*, and the most counter-intuitive result: 2605.10039 found strong evidence for
   *no effect* of size and conflict. The widespread advice to "keep it under 200 lines" does
   not replicate as an adherence lever, though it remains valid as a cost lever.
4. **Rules that cannot be checked by a command do not change behaviour.** *Medium-high
   confidence* — the A/B methodology is sound but single-author and smaller in scale.
5. **Anything needed on every task belongs in the always-on file, not a retrievable skill.**
   *Medium-high confidence* — Vercel's 56% non-invocation is a large effect, but measured on
   one framework and one task family.
6. **Enforcement outperforms instruction wherever a rule can be mechanised.** *High
   confidence* — this is vendor-documented behaviour, not an empirical estimate.
7. **Compliance decays through a session.** *Medium confidence* — replicated across
   conditions within one study; implies late-workflow steps are the ones that get skipped.

### Disagreement between sources

2602.11988 and 2606.20512 appear to conflict: one finds context files do not help, the other
finds guidance improves resolve rate by 7.5 points. They reconcile on *how the guidance was
produced* — written a priori versus tuned from probes. This is the single most important
reading in this note, and the reason conclusion 2 does not simply cancel conclusion 1.

## 6. Limits of the evidence

**All four studies measure task resolution on bug-fix-shaped work.** None measures what this
template mostly exists to protect: licensing hygiene, attribution, provenance,
reproducibility, or not damaging a user's original data. A rule that prevents one
catastrophic commit a year is invisible to every benchmark cited here.

The evidence is therefore decisive about **token-expensive advice** and silent about **hard
constraints**. A future reader must not use "context files do not improve success rates" to
justify deleting a rule that exists to prevent an unrecoverable error, because no study here
measured that class of rule at all.

Further limits: 2602.11988 is Python-only and measures resolution rather than code quality,
security or efficiency. Vercel's result covers one framework and one task family.
2605.10039 is TypeScript-only. None of the studies evaluated multi-session or long-horizon
work, which is where a project rulebook is meant to earn its keep.

## 7. Negative and null results

- **File size, instruction position, file architecture and contradictions in adjacent files
  had no detectable effect on adherence** (2605.10039), with strong Bayesian evidence for no
  effect on size and conflict. Do not re-attempt "fix adherence by restructuring the file".
- **LLM-generated context files trended negative** (-3%) and were highly redundant with
  existing documentation. Auto-generating a rules file is not a shortcut; treat `/init`
  output as a skeleton to cut down, never as a result.
- **Codebase overviews and directory enumerations produced no measurable benefit** for file
  discovery. This is among the most commonly written sections of an AGENTS.md and it does
  nothing.
- **Model-invoked skills frequently do not fire** (56%), and making invocation explicit
  raised it only to 79% while making results prompt-sensitive.

## 8. Open questions

- Does the probe-and-refine result hold for rules that encode *policy* rather than
  navigational knowledge? Nothing measured this, and it is the gap that matters most here.
- Does path-scoped conditional loading recover the cost overhead 2602.11988 measured, or
  merely move it? Untested; worth measuring once this template is used on a real project.
- Does an always-on routing table meaningfully raise skill invocation above the 56%
  baseline? This template now depends on it, so it should be evaluated — see `evals/`.

## 9. What this changes

| Finding | Action | Where |
|---|---|---|
| 4.3, 5.4 — unenforceable prose changes nothing | Rulebook rewritten command-first, closure as exit codes, three-tier boundaries plus attempt budget | `AGENTS.md` |
| 4.4, 5.5 — conditional loading, always-on for universals | Domain rules moved to their owning documents with path-scoped loaders | `docs/`, `.claude/rules/`, ADR 0001 |
| 4.5, 5.6 — enforcement beats instruction | Licence gate, scaffold checker and Stop hook added | `.claude/hooks/`, ADR 0002 |
| 4.6 — rules files are an attack surface | Invisible-Unicode scan; instruction-file trust posture documented | `.claude/hooks/scaffold_check.py`, `docs/security.md` |
| 4.7 — cross-artefact consistency is checkable | Convergence check makes the authority-conflict rule executable | `.claude/skills/converge/` |
| 4.8, 5.2 — tuned guidance is the only kind that works | Eval scaffold and refinement method recorded | `evals/`, `docs/development/testing.md` |
| 5.7 — compliance decays through a session | Late-workflow steps moved behind gates rather than left to instruction | `.claude/hooks/done_gate.py` |
| 6 — evidence is silent on hard constraints | Recorded explicitly, so the hard rules are not trimmed on the strength of studies that never measured them | this note, section 6 |
