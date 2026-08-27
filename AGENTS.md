# Agent Instructions — rpg-engine-api

`PLAN.md` is the single authoritative architecture and implementation roadmap for this repository.

Detailed normative specifications referenced by the plan:

- `docs/testing/HUMAN_PLAYTESTING.md` — public-interface human-play testing.
- `docs/testing/SIMULATION_QUALITY_LAB.md` — simulation, balance evidence, reachability analysis, and Content Testing SDK.
- `docs/ai/SIMPLE_NPC_AI.md` — deterministic baseline NPC controller.
- `docs/authoring/CONTENT_AUTHORING.md` — creator workspaces, validation, publishing, Creator/DM Studio APIs, encounter authoring, NPC personality, and narration templates.
- `docs/operations/DM_SESSION_OPERATIONS.md` — lobbies, invitations, sessions, control handoff, checkpoints/branches, recaps, and journals.
- `docs/extensions/TRUSTED_EXTENSIONS_AND_MIGRATIONS.md` — data-only content boundary, trusted executable extensions, compatibility, dry-run migration, activation, rollback/branching.

These instructions apply to Codex, OpenCode, Claude/Claude Code, Gemini, Pi/Oh My Pi, Prime, GitHub Copilot, and any other coding agent working in this repository. Tool-specific instruction files must defer to these canonical documents rather than creating competing roadmaps or subsystem designs.

## Mandatory startup sequence

Before changing code or documentation:

1. Read `PLAN.md` enough to understand the architecture, non-negotiable rules, active milestone, and definition of done.
2. Inspect the current repository state and tests.
3. Identify the earliest incomplete roadmap milestone relevant to the requested work unless the user explicitly directs otherwise.
4. Read every detailed specification relevant to the changed subsystem:
   - gameplay/public-client behavior -> `HUMAN_PLAYTESTING.md`;
   - NPC/controller behavior -> `SIMPLE_NPC_AI.md`;
   - authored content/creator APIs/encounters/personality/narration -> `CONTENT_AUTHORING.md`;
   - lobby/session/DM/checkpoint/recap/journal -> `DM_SESSION_OPERATIONS.md`;
   - simulation/content testing/reachability/balance evidence -> `SIMULATION_QUALITY_LAB.md`;
   - plugins/extensions/content upgrades/migrations -> `TRUSTED_EXTENSIONS_AND_MIGRATIONS.md`.
5. Identify which contracts the change touches: domain state, definitions, commands, events, projections, timing, persistence, visibility, controllers, authoring, operations, testing, extensions, or migration.
6. Identify how the behavior will be proven: unit/integration tests, public human-play scenario, simulation/reachability check, or migration fixture.
7. Do not invent a competing architecture when a canonical specification already defines the boundary.
8. If a genuinely new non-trivial architectural decision is required, update `PLAN.md` and add an ADR under `docs/decisions/`.

## Current implementation priority

Until v0.1 is complete, work from **v0.1 — Deterministic Core + Shared Contracts**.

Recommended sequence:

```text
PR 1  Project scaffold + architecture boundaries + playtest harness skeleton
PR 2  Stable IDs + shared primitives + ControllerAssignment + definition/extension seams
PR 3  Commands + events + command receipts + errors
PR 4  Deterministic RNG streams + dice + seed-bundle support
PR 5  In-memory event store + replay + canonical state hashing
PR 6  PostgreSQL async event store + migrations + outbox seam
PR 7  Snapshots + projection versions + rebuild seam
PR 8  Command bus + idempotency + optimistic concurrency
PR 9  Ruleset/content manifests + DefinitionRef/content-lock primitives
PR 10 Initial REST/query contracts + black-box async playtest client
PR 11 Initial WebSocket/resume protocol + live playtest client
PR 12 Testing Grounds fixture + v0.1 human-play/determinism integration suite
```

Do not skip foundational work because a later feature is more visible.

## Cross-cutting architecture invariants

### Server authority

- Gameplay state changes through typed commands and authoritative events.
- Clients, AI controllers, creator tools, and test harnesses must not patch authoritative gameplay state directly.
- Projections, logs, AI traces, recaps, and simulation reports are derived/non-authoritative.

### Determinism and replay

- Version every schema/content/controller/extension behavior that can affect replay.
- Use independent deterministic RNG streams; do not let test behavior, NPC decision variation, weather, loot, or unrelated systems perturb combat dice.
- Preserve idempotency and optimistic concurrency.
- Replay must not require re-calling mutable external services.

### Visibility

- Apply visibility before serialization and before building NPC/controller decision views.
- Server-side AI is not omniscient merely because it executes on the server.
- Creator/admin diagnostics may be privileged but must not leak into player projections.

### Async/non-blocking

- Target Python 3.12+ with modern typing.
- Use async-safe FastAPI/SQLAlchemy/PostgreSQL patterns.
- Never use blocking network/DB/file work or `time.sleep()` on async request/controller/timing paths.
- Keep controller decisions bounded/event-driven; no busy polling.
- Isolate CPU-heavy replay, pathfinding, simulations, validation batches, and imports/exports through bounded worker execution when necessary.

## Baseline NPC AI

Until v0.8 advanced-controller work, use `SimpleNpcController` from `docs/ai/SIMPLE_NPC_AI.md`.

Required invariants:

- no LLM/external service is required for baseline NPC gameplay;
- only actor-permitted visible state is available;
- rank only server-advertised legal actions/targets;
- submit normal typed commands through the ordinary validation/event path;
- behavior profiles are versioned data, not creature-specific hidden Python;
- initial profiles remain simple: aggressive melee, ranged, balanced/defensive, support, passive, flee;
- deterministic stable tie-breaking for MVP;
- safe fallback on controller failure;
- human-vs-NPC and AI-vs-AI deterministic tests are required when the combat MVP exists.

Milestone placement:

```text
v0.1 controller assignment/interface seam
v0.2 controller eligibility hooks
v0.3 SimpleNpcController combat MVP
v0.5 perception/spatial integration
v0.7 authored schedule-step integration
v0.8 richer utility/external/LLM controllers
```

## Human-play testing

Every user-visible gameplay capability must be programmatically exercisable through the same public REST/WebSocket contracts a real client uses.

The playtest harness must not become a second rules engine. It can discover legal capabilities from the server, submit commands, observe receipts/events/projections, reconnect, and replay.

For every gameplay feature, ask:

```text
How does a human reach it?
How does the client discover it?
Which role/actor controls it?
Which public command/action performs it?
What should be visible before/after?
What invalid path must be rejected?
What happens on timeout/retry/reconnect?
How is replay verified?
If NPCs participate, which controller/profile drives them?
```

Use controllable clocks instead of long sleeps. Failures should capture deterministic scenario/version/seed/content/controller metadata.

## Creator/content authoring

Follow `docs/authoring/CONTENT_AUTHORING.md`.

Required boundaries:

- drafts are mutable authoring state; published definitions are immutable/versioned;
- finalized campaigns reference published content, never mutable drafts;
- validate schema, namespace, references, ruleset compatibility, provenance/license, graph reachability, and runtime semantics before publish;
- Creator/DM Studio APIs produce the same canonical definition schemas the runtime consumes;
- `EncounterTemplate` is authored content while `Encounter` is a runtime instance;
- authored `NpcBehaviorProfile` and `NpcPersonalityProfile` are separate concerns;
- narration is a projection from visible authoritative facts; optional AI narration cannot invent state;
- do not event-source every editor keystroke.

When adding a new authorable definition type, define its authoring schema, validation, preview/test path, publication/version behavior, and source metadata.

## DM/session operations

Follow `docs/operations/DM_SESSION_OPERATIONS.md`.

Required boundaries:

- lobby/presence coordination is distinct from authoritative gameplay state;
- invitations, roles, actor-control grants, session open/pause/close, and DM overrides use explicit permissions/commands;
- disconnect/AFK policies may delegate to `SimpleNpcController` but must record/restore control explicitly;
- named checkpoints are references to history, not destructive save overwrites;
- default “restore” semantics create a branch from a checkpoint/sequence rather than deleting history;
- recaps/journals/chronicles are visibility-filtered projections;
- session close must handle open encounters/action windows through explicit policy.

## Simulation and Content Testing SDK

Follow `docs/testing/SIMULATION_QUALITY_LAB.md`.

The Simulation/Quality Lab must reuse the real runtime/rules/controllers, never a simplified second combat engine.

Use it to support:

```text
encounter simulation batches
controller/profile comparisons
content-version comparisons
quest/dialogue/progression reachability
unobtainable item checks
unusable ability checks
generated available-action exploration
performance/correctness experiments
creator-facing ContentQualityReport
```

Simulation produces evidence, not an opaque universal “balance score.” Every run must be reproducible from engine revision, content lock, controller versions, configuration, and seed bundle. Promote important outliers into permanent regression fixtures.

## Trusted extensions and migrations

Follow `docs/extensions/TRUSTED_EXTENSIONS_AND_MIGRATIONS.md`.

Non-negotiable distinction:

```text
ContentPack    data-only declarative content; no arbitrary executable code
RulesExtension trusted deployment-installed executable code with explicit capabilities
```

Do not allow uploaded content packs to execute Python/shell/dynamic imports.

Trusted extensions receive narrow typed interfaces, must preserve replay/determinism for authoritative effects, must be explicitly installed/administered, and may not receive unrestricted infrastructure internals by default.

Content upgrades must support:

```text
candidate lock resolution
semantic diff
compatibility report
campaign impact report
migration plan
dry run on isolated copy/branch
required validation/playtests
automatic checkpoint
atomic activation
post-activation replay verification
rollback when safe or branch when not
```

Never silently auto-upgrade active campaign mechanics.

## Architecture boundaries

Keep responsibilities distinct:

```text
api/             transport/auth/schema adaptation
application/     orchestration/transactions
 domain/          deterministic game state/invariants
rules/           rules evaluation/runtime
rulesets/        licensed/custom mechanics/content integration
controllers/     replaceable actor decisions; no rules authority
authoring/       mutable drafts/validation/publishing workflows
persistence/     events/snapshots/projections/outbox
infrastructure/  external/process concerns
simulation/      isolated quality/simulation workers using real runtime
tests/playtest/  black-box public-interface personas/scenarios
```

Published content and trusted extension packages may live under other concrete directories, but the conceptual boundaries above must remain.

## Reference content discipline

Do not bulk-import content before schemas, validators, and representative playtests can support it.

Track categories such as abilities, skills, species, backgrounds, classes, feats, actions, conditions, equipment, creatures, quests, dialogue, encounters, and world content by:

```text
schema ready
data mapped
validation ready
conformance tests
human-play scenarios
simulation/static-analysis checks where relevant
```

Only redistribute appropriately licensed material and preserve attribution/source metadata.

## Testing Grounds

`Testing Grounds` is the canonical growing integration campaign.

It should eventually prove one continuous journey through:

```text
content install -> campaign/lobby/session -> character creation -> town/social/quest
-> trade/crafting -> travel/discovery -> autonomous NPC encounter -> rewards/progression
-> disconnect/reconnect -> checkpoint/branch -> session close/recap -> replay
```

Authored encounters should use real `EncounterTemplate`s. From v0.3 onward, canonical enemies normally use `SimpleNpcController`.

## Required completion checks

Before declaring work complete:

1. Re-read the active milestone and relevant normative specs.
2. Run relevant unit/integration/determinism/replay tests.
3. Add/run black-box human-play scenarios for user-visible gameplay.
4. Add/run controller tests when NPC autonomy is involved.
5. Add/run authoring validation/publish tests for new content schemas.
6. Add/run simulation/reachability/content-quality checks when the feature affects authored graphs/encounters/content usability.
7. Verify no blocking operations, polling loops, or real sleeps were introduced into async/timing paths.
8. Verify state changes still pass through proper commands/events.
9. Verify visibility boundaries for clients/controllers/recaps.
10. Verify public/content/controller/extension schemas are versioned.
11. Verify source/license provenance for distributable content.
12. Verify retry/timeout/reconnect/controller fallback behavior where relevant.
13. Verify migration/upcast/content-lock/extension compatibility when persistent interpretation changes.
14. Update test/feature coverage manifests.
15. Update `PLAN.md` only when architecture/roadmap decisions changed or milestone checkboxes are objectively satisfied.
16. Do not claim completion when the relevant public play path, authoring path, or migration/test evidence is missing.

## Preventing project drift

Do not:

- create competing roadmaps or replacement subsystem architectures;
- require an LLM for baseline NPC play;
- give AI omniscient state;
- implement hidden client/controller rules;
- let ordinary content packs execute arbitrary code;
- let creator tools bypass published-definition validation/versioning;
- make checkpoints destructive history rewrites;
- make recaps/journals authoritative state;
- build a second simplified simulator instead of reusing the real runtime;
- publish structurally invalid content because a UI happens to accept it;
- silently auto-upgrade campaign mechanics;
- bypass event history with direct gameplay DB updates;
- use Redis/in-memory state as the only authority;
- hide flaky tests instead of preserving their reproducible artifact;
- implement post-v1.0 distributed/MMO/marketplace scope during earlier milestones unless explicitly requested.

When a request conflicts with a non-negotiable architecture rule, preserve the invariant and implement the desired behavior through the planned extension point.