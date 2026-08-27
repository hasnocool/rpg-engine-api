# Gemini Agent Instructions

Before making changes, read and follow in this order:

1. [`PLAN.md`](PLAN.md) — canonical architecture, invariants, roadmap and definition of done.
2. [`AGENTS.md`](AGENTS.md) — repository-wide execution/governance policy.
3. [`TODO.md`](TODO.md) — ordered executable work queue, playability ladder and local evidence gates.
4. Relevant normative specs, especially [`docs/testing/LOCAL_TEST_AGENT.md`](docs/testing/LOCAL_TEST_AGENT.md).

`PLAN.md` controls architecture. `TODO.md` controls day-to-day implementation order and must be corrected if it conflicts with the plan.

Unless the user explicitly directs later work, implement the earliest unchecked, unblocked TODO in the active milestone. Do not create a Gemini-specific roadmap, parallel TODO, test system, AI architecture, creator architecture or migration model.

Keep cumulative playability gates P0–P8 and the continuous Testing Grounds journey working as the project grows. A milestone is not complete while its required playable gate is broken.

Preserve server authority, deterministic command/event/replay behavior, visibility boundaries, non-blocking async behavior, `SimpleNpcController` as baseline autonomous NPC controller, immutable published content versions, branch-based restore semantics, data-only ordinary content packs, explicitly trusted executable extensions and public-interface human-play testing.

## Local-only test execution

This repository **must never use GitHub Actions** unless the user explicitly reverses the repository policy.

- Do not create or restore `.github/workflows/*`.
- Do not suggest GitHub Actions as the test runner.
- Do not use Actions status checks/artifacts as verification evidence.
- Do not substitute remote CI for the designated local test agent.
- GitHub is for source control/review; execution verification is local.

For execution claims, follow `LOCAL_TEST_AGENT.md`: **local-agent evidence only** is commit-bound and authoritative for what actually ran. Do not claim `verified locally`, `all tests pass`, integration success, a TODO execution gate, or release readiness without matching local evidence for the exact candidate commit. If evidence is unavailable, leave verification TODOs unchecked or `[AWAITING EVIDENCE]` and identify the canonical local profile that must run.

Update `TODO.md` only from objective repository state and local evidence; implementation state and execution verification are distinct.