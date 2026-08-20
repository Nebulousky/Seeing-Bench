---
name: research
description: Investigate a question and record the findings as a durable note, without changing production behaviour. Use when a decision needs evidence, when evaluating a library, format, licence or external source, or before implementing anything derived from a paper or spec.
---

# Research

Acquire knowledge and evidence, and leave it somewhere it survives the conversation. The
output is a note in `docs/research/`, written to `docs/research/TEMPLATE.md`.

**Do not modify production behaviour.** Research that edits the thing it is studying is no
longer research, and its findings are no longer about the code anyone else has.

## Preconditions

None. Research is usually the prerequisite for another task rather than having its own.

Production code derived from an external source **requires the note to exist first**
(`docs/external-sources.md`), so if this research is feeding an implementation, it is not
optional groundwork — it is the first step of that work.

## Procedure

1. **State the question** in one sentence, and what decision the answer unblocks. A question
   that unblocks nothing does not need researching yet.

2. **Delegate the reading.** Use the `investigator` subagent. It is read-only by toolset, so
   the no-modification boundary is enforced rather than remembered, and it reads in its own
   context so this session pays for the findings rather than the search. Give it the project
   facts it needs — it starts with none.

3. **Separate primary from secondary sources.** Read the specification, the paper, the code.
   A summary of a paper is evidence about the summary. Record which claims you verified
   yourself and which you are relaying.

4. **Record numbers with their method.** A figure without its sample size and how it was
   measured cannot be judged later, only believed or not.

5. **Write the note** to the template, including the sections most often skipped:
   - **Limits of the evidence** — what the sources do *not* establish. This is what stops
     someone later applying a result to a question it never measured.
   - **Negative and null results** — what showed no effect, so it is not retried.
   - **What this changes** — the concrete actions implied, and where each was carried out. A
     note with nothing in this section did not need writing.

6. **Note the date and how fast the subject moves.** Findings about tool behaviour go stale
   in months; findings about a file format may not. Say which this is.

## Escalation

- If the findings imply an architectural change, stop. That is a Plan task, and deciding it
  inside a Research contract skips the discussion it deserves.
- If sources disagree, report the disagreement and what would resolve it. Do not average
  them into a single confident answer — the disagreement is usually the finding.
- If the question cannot be answered from available sources, say so plainly and record what
  was searched. "None found" is a result; a plausible guess presented as a finding is a
  liability that outlives the conversation.
