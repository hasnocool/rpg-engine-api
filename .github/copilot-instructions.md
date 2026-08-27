# GitHub Copilot Repository Instructions

Before implementing or suggesting repository changes, use these as the canonical instructions:

1. [`AGENTS.md`](../AGENTS.md) — repository-wide execution policy, current milestone discipline, v0.1 implementation contract, testing expectations, and anti-drift rules.
2. [`PLAN.md`](../PLAN.md) — authoritative architecture, roadmap, contracts, milestone exit criteria, and definition of done.

Do not create a competing roadmap or bypass the deterministic server-authoritative command/event design.

For asynchronous Python code, keep DB/network/file I/O non-blocking, use async-safe libraries/primitives, and never use blocking sleeps or blocking synchronization in async request paths.

Work from the earliest incomplete relevant milestone unless the user explicitly requests another milestone. Do not mark roadmap work complete unless its tests and exit criteria are demonstrated.