# Architecture Decision Records

Use this directory for non-trivial architectural decisions that intentionally refine or change the contracts in [`PLAN.md`](../../PLAN.md).

`PLAN.md` remains the canonical roadmap. ADRs explain *why* an important decision was made; they do not replace the plan.

## When an ADR is required

Create an ADR when a decision is expensive to reverse or materially changes one or more of these boundaries:

- aggregate or event-stream ownership;
- persistence/event-store layout;
- deterministic RNG model;
- command/event/query schema strategy;
- scheduler or action semantics;
- rules/content-pack compatibility;
- visibility/security model;
- REST/WebSocket compatibility contracts;
- concurrency/transaction strategy;
- migration/versioning policy;
- core dependency or framework choice.

Routine refactors and implementation details that preserve existing contracts do not need an ADR.

## Naming

Use monotonically numbered files:

```text
0001-short-decision-title.md
0002-next-decision.md
```

## Template

```markdown
# ADR NNNN — Title

## Status

Proposed | Accepted | Superseded | Rejected

## Context

What problem or constraint requires a decision?

## Decision

What are we choosing?

## Consequences

What becomes easier, harder, constrained, or intentionally unsupported?

## Alternatives considered

What serious alternatives were evaluated and why were they not chosen?

## Plan impact

Which sections/milestones in `PLAN.md` need to be updated?
```

When an ADR changes architecture, update `PLAN.md` in the same PR so agents never have to reconstruct the current architecture by reading historical ADRs.