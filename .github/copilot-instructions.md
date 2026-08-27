# GitHub Copilot Repository Instructions

Use these repository instructions before implementing or suggesting changes:

1. [`PLAN.md`](../PLAN.md) — authoritative architecture, invariants and roadmap.
2. [`AGENTS.md`](../AGENTS.md) — repository-wide workflow/governance rules.
3. [`TODO.md`](../TODO.md) — ordered executable work queue, playability ladder P0–P8 and local evidence gates.
4. Relevant detailed specifications, especially [`docs/testing/LOCAL_TEST_AGENT.md`](../docs/testing/LOCAL_TEST_AGENT.md).

`PLAN.md` controls architecture; `TODO.md` controls execution order. If they conflict, preserve the plan and correct the TODO.

Unless the user explicitly directs later work, take the earliest unchecked, unblocked TODO in the active milestone. Do not create a competing roadmap, TODO, testing harness, evidence protocol, NPC AI, creator architecture, plugin boundary or migration design.

Keep the cumulative playability gates and continuous Testing Grounds story working. User-visible work should extend public-interface human play rather than only adding isolated endpoint tests. From P2 onward, canonical encounters should exercise autonomous `SimpleNpcController` opponents.

Keep async request/controller paths non-blocking. Preserve deterministic server-authoritative command/event/replay behavior, visibility filtering, immutable published content versions, branch-based checkpoint restores, data-only ordinary content packs and explicitly trusted executable extensions.

## No GitHub Actions

Despite this file living under `.github/`, this repository **must never use GitHub Actions** unless the user explicitly reverses that policy.

- Do not create `.github/workflows/*`.
- Do not recommend or restore GitHub Actions workflows.
- Do not use GitHub-hosted or Actions self-hosted runners.
- Do not use Actions status checks or artifacts as test evidence.
- Do not substitute remote CI for the designated local test agent.

GitHub is used for repository hosting, PRs and review only. Runtime verification is local.

Local-agent evidence is the sole authority for execution claims. Do not state that tests passed locally, integrations work, a TODO execution gate is complete, or a release is verified unless `LOCAL_TEST_AGENT.md` evidence matches the exact candidate commit and canonical local profile. If no evidence is available, mark/report the relevant TODO as `[AWAITING EVIDENCE]` or not executed and specify the local profile to run.

Update `TODO.md` from objective implementation/local-evidence only. Do not check off a playability or execution gate because code merely appears correct.