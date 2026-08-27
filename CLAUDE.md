# Claude / Claude Code Instructions

Before making changes, read and follow in this order:

1. [`PLAN.md`](PLAN.md) — canonical architecture, invariants, roadmap and definition of done.
2. [`AGENTS.md`](AGENTS.md) — repository-wide execution/governance policy.
3. [`TODO.md`](TODO.md) — ordered executable work queue, playability ladder and local evidence gates.
4. Relevant normative specs:
   - [`docs/testing/HUMAN_PLAYTESTING.md`](docs/testing/HUMAN_PLAYTESTING.md)
   - [`docs/testing/SIMULATION_QUALITY_LAB.md`](docs/testing/SIMULATION_QUALITY_LAB.md)
   - [`docs/testing/LOCAL_TEST_AGENT.md`](docs/testing/LOCAL_TEST_AGENT.md)
   - [`docs/ai/SIMPLE_NPC_AI.md`](docs/ai/SIMPLE_NPC_AI.md)
   - [`docs/authoring/CONTENT_AUTHORING.md`](docs/authoring/CONTENT_AUTHORING.md)
   - [`docs/operations/DM_SESSION_OPERATIONS.md`](docs/operations/DM_SESSION_OPERATIONS.md)
   - [`docs/extensions/TRUSTED_EXTENSIONS_AND_MIGRATIONS.md`](docs/extensions/TRUSTED_EXTENSIONS_AND_MIGRATIONS.md)

`PLAN.md` controls architecture. `TODO.md` controls the day-to-day implementation order and must be corrected if it ever conflicts with the plan.

Unless the user explicitly directs later work, implement the earliest unchecked, unblocked TODO in the active milestone. Do not create a Claude-specific roadmap or parallel TODO.

Keep the cumulative playability gates P0–P8 and the continuous Testing Grounds journey working as the project grows. A milestone is not complete while its required playable gate is broken.

Preserve server authority, deterministic command/event/replay behavior, visibility boundaries, non-blocking async behavior, SimpleNpcController as the baseline autonomous NPC controller, immutable published content versions, branch-based restore semantics, data-only ordinary content packs, explicitly trusted executable extensions and public-interface playtesting.

For execution claims, follow `LOCAL_TEST_AGENT.md`: local-agent/CI evidence is commit-bound and authoritative for what actually ran. Do not claim `verified locally`, `all tests pass`, integration success, a TODO execution gate, or release readiness without matching evidence for the exact candidate commit. If evidence is unavailable, leave the verification TODO unchecked or `[AWAITING EVIDENCE]` and identify the canonical profile that must run.

When completing work, update `TODO.md` objectively: implementation may be marked in progress/awaiting evidence before the local executor verifies it; only evidence-backed execution gates become complete.