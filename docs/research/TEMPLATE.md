# Research: <question>

```yaml
Status: In progress | Complete | Superseded
Date: <YYYY-MM-DD>
Sources examined: <n>
Informs: <plan, ADR, or task this was done for>
```

> **How to use this template.** A research note is the durable output of a Research task
> (`AGENTS.md`, Task types). It exists because findings that live only in a conversation
> are lost, and because production code derived from an external source requires the note
> to exist *first* (`docs/external-sources.md`).
>
> Research notes are cheap to write and expensive to skip. A bad line of research leads to
> far more wasted work than a bad line of code, because everything downstream is built on
> it. Every section below must be present; use `N/A — <reason>` rather than deleting one.

## 1. Question

One sentence: what were we trying to learn, and what decision does the answer unblock?

## 2. Scope

What was and was not investigated, and the date the evidence was current. Findings about
fast-moving tools go stale; a reader a year from now needs to know what "current" meant.

## 3. Sources examined

Files with line references, URLs, papers, specs. Separate **primary** sources (the spec,
the paper, the code) from **secondary** ones (blog posts, summaries). State which claims
you verified yourself and which you are relaying.

## 4. Findings

Facts found, separated from inference. Where a finding is quantitative, record the number,
the sample it came from, and the method — enough that a later reader can judge whether it
still applies rather than taking the headline on trust.

## 5. Conclusions and confidence

What follows from the findings, each with a confidence level and the evidence it rests on.
Mark disagreement between sources explicitly rather than averaging it away.

## 6. Limits of the evidence

What the sources do **not** establish. This section is the one most often skipped and most
often needed: it is what stops a later reader over-applying a result to a question it never
measured.

## 7. Negative and null results

What was tried and did not work, and what showed *no* effect. Recorded so it is not
rediscovered. A null result is a finding.

## 8. Open questions

What remains undetermined, and what would resolve each.

## 9. What this changes

The concrete actions the findings imply, and where each was carried out — a plan, an ADR,
a code change, or a decision not to act. A research note with no line in this section did
not need to be written.
