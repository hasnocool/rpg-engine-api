# GitHub Copilot Repository Instructions

Use these as the canonical repository instructions before implementing or suggesting changes:

1. [`PLAN.md`](../PLAN.md) — authoritative architecture and roadmap.
2. [`AGENTS.md`](../AGENTS.md) — repository-wide execution policy and spec-routing rules.
3. Relevant detailed specifications:
   - [`docs/testing/HUMAN_PLAYTESTING.md`](../docs/testing/HUMAN_PLAYTESTING.md)
   - [`docs/testing/SIMULATION_QUALITY_LAB.md`](../docs/testing/SIMULATION_QUALITY_LAB.md)
   - [`docs/testing/LOCAL_TEST_AGENT.md`](../docs/testing/LOCAL_TEST_AGENT.md)
   - [`docs/ai/SIMPLE_NPC_AI.md`](../docs/ai/SIMPLE_NPC_AI.md)
   - [`docs/authoring/CONTENT_AUTHORING.md`](../docs/authoring/CONTENT_AUTHORING.md)
   - [`docs/operations/DM_SESSION_OPERATIONS.md`](../docs/operations/DM_SESSION_OPERATIONS.md)
   - [`docs/extensions/TRUSTED_EXTENSIONS_AND_MIGRATIONS.md`](../docs/extensions/TRUSTED_EXTENSIONS_AND_MIGRATIONS.md)

Do not create a competing roadmap, creator architecture, testing harness, test-evidence protocol, NPC AI, plugin boundary, or migration design.

Keep async request/controller paths non-blocking. Preserve deterministic server-authoritative command/event/replay behavior, visibility filtering, immutable published content versions, branch-based checkpoint restores, data-only ordinary content packs, explicitly trusted executable extensions, and public-interface human-play testing.

Local-agent/CI evidence is the authority for execution claims. Do not state that tests passed locally, integrations work, or a release is verified unless `LOCAL_TEST_AGENT.md` evidence matches the exact candidate commit and required canonical profile. If no evidence is available, describe the work as not executed and specify which profile should run.

Do not mark roadmap work execution-complete unless its required tests, play scenarios, authoring validation, simulation/reachability checks, migration evidence, and commit-bound local/CI execution evidence are demonstrated where applicable.