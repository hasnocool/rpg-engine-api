# Claude / Claude Code Instructions

Before making changes, read and follow:

1. [`AGENTS.md`](AGENTS.md) — repository-wide agent execution policy and current implementation contract.
2. [`PLAN.md`](PLAN.md) — the single authoritative architecture, roadmap, milestone exit criteria, and definition of done.
3. [`docs/testing/HUMAN_PLAYTESTING.md`](docs/testing/HUMAN_PLAYTESTING.md) — required public-interface human-play testing architecture.
4. [`docs/ai/SIMPLE_NPC_AI.md`](docs/ai/SIMPLE_NPC_AI.md) — required baseline deterministic NPC/creature controller design.

Do not create a separate Claude-specific architecture, roadmap, testing system, or NPC AI design. If these files appear to conflict, `PLAN.md` controls architecture and milestone scope, while `AGENTS.md` controls repository-wide agent workflow.

Work from the earliest incomplete relevant milestone unless the user explicitly directs otherwise. Preserve deterministic command/event architecture, server authority, replay/versioning, licensing boundaries, non-blocking async behavior, public-interface playtesting, and controller visibility boundaries.

For ordinary non-human actors before advanced AI work, use the planned `SimpleNpcController`: no LLM requirement, no omniscient state, no direct mutations, deterministic one-step behavior profiles, and all selected actions through the same normal typed command/rules path as human actors.