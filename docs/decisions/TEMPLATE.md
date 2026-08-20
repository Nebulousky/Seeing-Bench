# <NNNN>. <short title of the decision>

```yaml
Status: Proposed | Accepted | Rejected | Deprecated | Superseded by <NNNN>
Date: <YYYY-MM-DD>
```

> **How to use this template.** Adapted from MADR 4.0 (minimal). An ADR records a decision
> that outlives the phase that made it. Plans are execution documents and are not decision
> authority (`AGENTS.md`, Planning) — when a plan makes a decision that stays true after
> the phase ends, it is promoted here and the plan links to it.
>
> Number files sequentially and never renumber. An ADR is immutable once Accepted: to
> change a decision, write a new ADR that supersedes it and update this one's status.
> Delete these instructions when filling the template in.

## Context and problem statement

What forced a decision. Two or three sentences, written so a reader who was not present
understands the pressure that made this worth deciding rather than leaving open.

## Considered options

- <option 1>
- <option 2>
- <option 3>

## Decision

We chose **<option>**.

<Why. The deciding reason, not a summary of every advantage — what made the other options
unacceptable.>

## Consequences

**Good:** <what improves.>

**Bad:** <what we now have to live with. An ADR with no cost recorded is usually one where
the cost was not examined.>

## Alternatives, and why not

| Option | Rejected because |
|---|---|
| <option> | <reason> |
