# GitHub Copilot Repository Instructions

Before implementing or suggesting repository changes, use these as the canonical instructions:

1. [`AGENTS.md`](../AGENTS.md) — repository-wide execution policy, current milestone discipline, implementation contracts, testing gates, and anti-drift rules.
2. [`PLAN.md`](../PLAN.md) — authoritative architecture, roadmap, contracts, milestone exit criteria, and definition of done.
3. [`docs/testing/HUMAN_PLAYTESTING.md`](../docs/testing/HUMAN_PLAYTESTING.md) — normative programmatic human-play specification for black-box end-to-end gameplay testing.

Do not create a competing roadmap or testing framework, and do not bypass the deterministic server-authoritative command/event design.

For asynchronous Python code, keep DB/network/file I/O non-blocking, use async-safe libraries/primitives, and never use blocking sleeps or blocking synchronization in async request paths. Timed gameplay tests must use controllable clocks instead of sleeping through real durations.

Work from the earliest incomplete relevant milestone unless the user explicitly requests another milestone. For every user-visible gameplay change, add or extend a black-box scenario that reaches the feature through public REST/WebSocket interfaces as an authenticated player/DM/spectator persona. Do not duplicate hidden rules in the test client.

Do not mark roadmap work complete unless its unit/integration/replay checks, relevant human-play scenarios, deterministic failure artifacts/seeds, visibility behavior, and milestone exit criteria are demonstrated.