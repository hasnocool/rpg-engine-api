# Gemini Agent Instructions

Before making changes, read and follow:

1. [`AGENTS.md`](AGENTS.md) — repository-wide agent execution policy, current implementation contract, testing gates, and anti-drift rules.
2. [`PLAN.md`](PLAN.md) — the single authoritative architecture, roadmap, milestone exit criteria, and definition of done.
3. [`docs/testing/HUMAN_PLAYTESTING.md`](docs/testing/HUMAN_PLAYTESTING.md) — normative black-box human-play testing specification for proving gameplay through public REST/WebSocket interfaces.

Do not create a separate Gemini-specific architecture, roadmap, or testing framework. If these documents appear to conflict, `PLAN.md` controls product architecture, `AGENTS.md` controls agent workflow, and the human-play specification controls how player-visible behavior is proven end to end.

Work from the earliest incomplete relevant milestone unless the user explicitly directs otherwise. Preserve deterministic command/event architecture, server authority, replay/versioning, licensing boundaries, non-blocking async behavior, and role-aware visibility.

For any user-visible gameplay change, add or extend a programmatic human-play scenario. The playtest persona must use the public API/live protocol rather than calling domain internals or duplicating hidden rules. Test timing with controllable clocks instead of real sleeps, capture deterministic seeds/failure artifacts, and add player-visible bug regressions to the human-play suite.