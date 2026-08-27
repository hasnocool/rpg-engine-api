# Claude / Claude Code Instructions

Before making changes, read and follow:

1. [`PLAN.md`](PLAN.md) — canonical architecture, roadmap, milestone exit criteria, and definition of done.
2. [`AGENTS.md`](AGENTS.md) — repository-wide execution policy and spec-routing rules.
3. Relevant normative specs for the task:
   - [`docs/testing/HUMAN_PLAYTESTING.md`](docs/testing/HUMAN_PLAYTESTING.md)
   - [`docs/testing/SIMULATION_QUALITY_LAB.md`](docs/testing/SIMULATION_QUALITY_LAB.md)
   - [`docs/testing/LOCAL_TEST_AGENT.md`](docs/testing/LOCAL_TEST_AGENT.md)
   - [`docs/ai/SIMPLE_NPC_AI.md`](docs/ai/SIMPLE_NPC_AI.md)
   - [`docs/authoring/CONTENT_AUTHORING.md`](docs/authoring/CONTENT_AUTHORING.md)
   - [`docs/operations/DM_SESSION_OPERATIONS.md`](docs/operations/DM_SESSION_OPERATIONS.md)
   - [`docs/extensions/TRUSTED_EXTENSIONS_AND_MIGRATIONS.md`](docs/extensions/TRUSTED_EXTENSIONS_AND_MIGRATIONS.md)

Do not create a Claude-specific competing roadmap, creator architecture, testing system, test-evidence protocol, NPC AI, plugin boundary, or migration model. `PLAN.md` controls architecture and `AGENTS.md` controls workflow.

Preserve server authority, deterministic command/event/replay semantics, visibility boundaries, non-blocking async behavior, data-only ordinary content packs, explicit trusted extensions, immutable published content versions, branch-based restore semantics, and public-interface playtesting.

For execution claims, follow `LOCAL_TEST_AGENT.md`: local-agent/CI evidence is commit-bound and authoritative for what actually ran. Do not claim `verified locally`, `all tests pass`, integration success, or release readiness without matching evidence for the exact candidate commit. If evidence is unavailable, report `not executed` and identify the required canonical profile.