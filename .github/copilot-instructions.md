# GitHub Copilot Repository Instructions

Before implementing or suggesting repository changes, use these as the canonical instructions:

1. [`AGENTS.md`](../AGENTS.md) — repository-wide execution policy, current milestone discipline, implementation contracts, testing expectations, controller rules, and anti-drift requirements.
2. [`PLAN.md`](../PLAN.md) — authoritative architecture, roadmap, contracts, milestone exit criteria, and definition of done.
3. [`docs/testing/HUMAN_PLAYTESTING.md`](../docs/testing/HUMAN_PLAYTESTING.md) — normative black-box human-play testing specification.
4. [`docs/ai/SIMPLE_NPC_AI.md`](../docs/ai/SIMPLE_NPC_AI.md) — normative baseline deterministic NPC/creature controller specification.

Do not create a competing roadmap, test architecture, or NPC AI design, and do not bypass the deterministic server-authoritative command/event design.

For asynchronous Python code, keep DB/network/file I/O non-blocking, use async-safe libraries/primitives, and never use blocking sleeps or blocking synchronization in async request/controller paths.

Work from the earliest incomplete relevant milestone unless the user explicitly requests another milestone. Do not mark roadmap work complete unless its tests, public play path, controller behavior where relevant, and exit criteria are demonstrated.

For baseline non-human actors use `SimpleNpcController`: deterministic one-step behavior profiles, actor-visible information only, server-advertised legal actions, stable tie-breaking, safe fallback behavior, and the same normal typed command/rules-validation path as human actors. Do not require an LLM or external model before the advanced-AI milestone.