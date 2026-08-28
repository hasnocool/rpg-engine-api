# RPG Engine API — Complete Architecture and Implementation Plan

## Status

**Project:** `rpg-engine-api`  
**Target runtime:** Python 3.12+  
**Primary API:** FastAPI REST + WebSockets  
**Architecture:** headless, deterministic, event-driven RPG simulation platform  
**Initial compatible rules package:** SRD 5.2.1-based ruleset  
**Canonical planning document:** this file  
**Executable implementation ledger:** [`TODO.md`](TODO.md)  
**Test execution policy:** local test agent only; GitHub Actions are prohibited

The goal is to let any client—Godot, Unity, browser, mobile, TUI, SSH, Discord-style UI, AI narrator, automation service, creator tool, simulation worker, or another game engine—create, author, test, operate, and play a D&D-style RPG by treating this API as the authoritative game simulation.

The engine owns the rules and state. Clients discover capabilities, submit commands, receive events, render projections, and use explicit authoring/operations APIs rather than bypassing the authoritative runtime.

`PLAN.md` defines architecture and roadmap. `TODO.md` translates that roadmap into the ordered, checkable execution queue and cumulative playability gates. When the two disagree, this plan wins and the TODO must be corrected.

---

# 1. Product vision

`rpg-engine-api` should behave more like an **RPG operating system** than a combat microservice.

The authoritative server owns:

- campaign configuration and history;
- ruleset/content versions;
- characters, NPCs, creatures, companions, summons, and other actors;
- character creation and progression;
- classes, subclasses, species, backgrounds, feats, skills, proficiencies, spells, powers, features, and talent trees;
- parties and campaign membership;
- sessions, adventures, scenes, encounters, and world state;
- simulation time and wall-clock decision deadlines;
- turn-based, timed-turn, active-time, real-time-with-pause, real-time, and hybrid combat scheduling;
- actions, reactions, interrupts, movement, cooldowns, resources, rests, and effects;
- spatial authority, perception, hidden information, discovery, lighting, terrain, and world objects;
- inventory, equipment, containers, currency, vendors, trade, rewards, loot, and crafting;
- quests, objectives, dialogue, factions, reputation, relationships, world events, travel, calendars, weather, and NPC schedules;
- deterministic dice/randomness;
- authoritative event history, replay, snapshots, migrations, and save/load;
- multiplayer permissions and actor-control grants;
- player-facing game/combat logs and administrative audit logs;
- thin-client capability discovery;
- replaceable actor controllers, including a deterministic baseline NPC AI and later advanced AI/scripted controller boundaries;
- creator workspaces, content validation/publication, encounter templates, and content versioning;
- lobbies, invitations, ready checks, live DM/session operations, checkpoints/branches, recaps, and journals;
- simulation, content-quality, reachability, balance-evidence, and regression tooling;
- an explicit boundary between data-only content packs and trusted executable rules extensions;
- a canonical local-only test execution contract that produces commit-bound machine-readable evidence for merge and release gates;
- a cumulative executable TODO whose completion path continually produces something a human-facing client can actually play.

Clients should primarily:

1. authenticate;
2. query visible state/projections;
3. discover legal actions and creation choices;
4. submit typed commands;
5. subscribe to live events;
6. render the resulting state;
7. use explicit authoring/session/quality APIs when acting as creators or administrators.

A client must never need to reimplement hidden rules to stay synchronized with the server.

---

# 2. Rules and licensing boundary

The initial compatible rules package should use **System Reference Document 5.2.1** as its redistributable rules/content foundation.

Official references:

- SRD 5.2.1: https://www.dndbeyond.com/srd
- Creator FAQ: https://www.dndbeyond.com/creator-faq
- Basic Rules reference: https://www.dndbeyond.com/sources/dnd/br-2024
- Character creation reference: https://www.dndbeyond.com/sources/dnd/br-2024/creating-a-character
- Playing the Game reference: https://www.dndbeyond.com/sources/dnd/br-2024/playing-the-game
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/

Publicly readable D&D Beyond pages may be used to understand current behavior, but they must not be treated as automatically licensed for redistribution. Only appropriately licensed content belongs in redistributable packs.

The generic engine must not hard-code trademarks, setting-specific lore, or proprietary content.

```text
core engine
    +
rulesets/
    srd_5_2_1/
    custom_fantasy/
    campaign_specific/
```

The SRD-facing package should use current terminology such as `species`. Generic/custom rulesets may expose aliases such as `ancestry` or legacy `race`, without creating separate engine implementations.

Every distributable content record must retain source/license provenance.

---

# 3. Non-negotiable architectural rules

1. **Server authority first.** Clients request actions; the server determines outcomes.
2. **Commands change state; queries read state.** Avoid arbitrary mutable CRUD for gameplay authority.
3. **Events are durable facts.** Authoritative history is append-only.
4. **Time is a domain concept.** Never use `sleep()` to implement simulation progression.
5. **Simulation time and wall-clock deadlines are separate.**
6. **Rules are pluggable.** The core must not become an SRD monolith.
7. **Clients are replaceable.** No rule may require a specific rendering engine.
8. **Determinism is testable.** State transitions must be reproducible.
9. **Version everything affecting replay.** Rules, content, schemas, events, commands, snapshots, projections, campaign settings, controller behavior versions, and trusted extension behavior.
10. **AI is a controller, not an authority.** It submits normal commands; the initial autonomous NPC AI is the deterministic `SimpleNpcController`, not an LLM requirement.
11. **Async paths remain non-blocking.** DB/network I/O uses async-safe operations; heavy CPU work is isolated.
12. **Concurrency is explicit.** Stream versions, idempotency, and deterministic ordering protect multiplayer state.
13. **Licensed-content boundaries remain visible.**
14. **Observability is part of the architecture.** Commands/events are traceable end to end.
15. **No hidden client rules.** The API exposes enough metadata for thin clients.
16. **Visibility is enforced server-side before serialization.** Server-side controllers also receive only actor-permitted/controller-safe information.
17. **Definitions and instances are separate.** Content templates are immutable/versioned; campaign state is mutable/event-driven.
18. **Every core subsystem must define state, commands, events, lifecycle, permissions, replay, failures, migrations, and tests before implementation.**
19. **Every user-visible gameplay capability must be programmatically playable through public client interfaces.** Unit tests alone do not prove a gameplay feature is complete.
20. **The end-to-end playtest client must remain thin.** It may discover legal capabilities from the server, but must not duplicate hidden rules to make tests work.
21. **The baseline NPC AI remains simple, deterministic, replaceable, and non-omniscient.** Advanced utility AI, behavior trees, planners, and LLM/external-model adapters build on the same controller/command boundary rather than replacing it.
22. **Authoring drafts and published content are different lifecycles.** Mutable drafts never become live campaign definitions until validation and explicit publication create immutable versioned artifacts.
23. **Creator tools are not gameplay backdoors.** Creator/DM Studio APIs generate validated definitions or privileged commands; they do not patch authoritative campaign state directly.
24. **Ordinary content packs are data-only.** Arbitrary executable code belongs only in explicitly trusted deployment-installed extensions with narrow capabilities.
25. **Checkpoints preserve history.** The default restore workflow creates a branch from history instead of destructively rewriting the authoritative event stream.
26. **Simulation uses the real runtime.** Balance/content-quality tooling may automate the engine but must not become a simplified second rules/combat implementation.
27. **Content upgrades are explicit.** Active campaigns do not silently receive mechanic-changing pack/extension revisions; upgrades use diff, compatibility, impact, migration dry-run, checkpoint, activation, and replay verification.
28. **Execution claims require local evidence.** A remote agent may design or inspect tests, but claims that suites passed require commit-bound evidence from the designated local test agent.
29. **Verification is revision-specific.** Green evidence for one commit does not automatically verify a later code-changing commit; blocked/skipped required suites are never silently counted as passed.
30. **Implementation follows the executable TODO.** Unless explicitly redirected, agents work the earliest unchecked, unblocked item in the active roadmap phase and update TODO status from objective implementation/evidence only.
31. **Playability is cumulative.** A later milestone must not silently break an earlier P0–P8 playable gate; such a break is a product regression.
32. **GitHub Actions are prohibited.** The repository must not contain or depend on `.github/workflows/*`, GitHub-hosted Actions runners, Actions self-hosted runners, Actions artifacts, or Actions status checks for testing, merge gates, milestone proof, or release proof. Runtime verification is local-only unless the user explicitly reverses this policy.

---

# 4. Shared domain primitives

## 4.1 Stable identifiers

Every durable entity has an opaque durable ID and a separate stable content key.

```text
EntityIdentity
    id
    key
    display_name_key
```

Examples:

```text
srd_5_2_1:class/fighter
srd_5_2_1:species/human
my_pack:feature/arcane_training
campaign:homebrew/item/moon_key
```

Display names are never authoritative identifiers.

## 4.2 Definition references

```text
DefinitionRef
    pack_id
    pack_version
    key
    content_hash
```

Events that depend on a definition retain enough information to resolve the exact pinned version during replay.

## 4.3 Requirement expressions

All prerequisites use one typed declarative expression model.

```text
RequirementExpr
    operator
    operands
```

Required operators include:

```text
all
any
not
level_at_least
class_level_at_least
ability_at_least
has_feature
has_proficiency
has_item
has_tag
has_condition
resource_at_least
quest_state
faction_reputation_at_least
world_flag
campaign_setting
ruleset_predicate
```

Rulesets may register typed predicates. Content payloads may not contain arbitrary executable server code.

## 4.4 Choice groups

Character creation, progression, content options, and campaign creation use the same choice model.

```text
ChoiceGroup
    id
    min_choices
    max_choices
    options
    prerequisites
    uniqueness_policy
    replacement_policy
```

Selections preserve their source and selected option IDs.

## 4.5 Grants

```text
Grant
    grant_type
    target_ref
    quantity_or_rank
    duration
    stacking_policy
    source_ref
```

Grant types include feature, proficiency, resource, action, movement mode, sense, language, item, spell/power, progression currency, and tags.

## 4.6 Visibility

```text
VisibilityPolicy
    audience
    discovery_requirement
    redact_fields
```

Audiences include public, campaign members, party, controller-only, DM-only, service-only, and custom roles.

Visibility is applied before response/event serialization and before building controller decision views.

## 4.7 Source metadata

```text
SourceMetadata
    source_pack_id
    source_version
    license_id
    attribution_id
    source_reference
    content_hash
```

This supports SRD content, project-original content, licensed third-party packs, and campaign-local homebrew without losing provenance.

---

# 5. Rulesets, content packs, house rules, and campaign content locks

## 5.1 Ruleset manifest

```text
RulesetManifest
    id
    version
    schema_version
    engine_api_range
    license
    attribution
    capabilities
    entry_pack_ids
```

Capabilities may include initiative, timing/economy translations, character creation, leveling/multiclassing, spellcasting, conditions, inventory/encumbrance, spatial rules, rests, crafting, and economy.

## 5.2 Content pack manifest

```text
ContentPackManifest
    id
    version
    schema_version
    namespace
    ruleset_compatibility
    engine_api_range
    dependencies
    optional_dependencies
    conflicts
    load_after
    license
    attribution
    content_hash
```

A pack may contain classes, species, backgrounds, features, progression graphs, actions, spells/powers, items, creatures, conditions, quests, dialogue, recipes, world/location templates, campaign templates, encounter templates, narration templates, NPC personality profiles, and references to versioned NPC behavior profiles.

## 5.3 Dependency and conflict resolution

Activation resolves dependencies, rejects unsupported cycles/incompatible ranges/duplicate keys, applies overrides only when declared, creates a deterministic ordered lock, and validates all references. There is no silent last-write-wins behavior.

## 5.4 Campaign content lock

```text
CampaignContentLock
    ruleset_ref
    pack_refs[]
    house_rule_set_ref
    schema_versions
    combined_hash
```

Replay uses the content lock active at the event sequence being reconstructed. Controller profile and trusted extension versions affecting interpretation are likewise pinned or otherwise recoverable.

## 5.5 Mid-campaign content revisions

```text
ProposeContentRevision
ValidateContentRevision
ActivateContentRevision
RollbackContentRevision
```

Activation either migrates affected state safely or fails with an incompatibility report. Old history remains bound to old definitions.

## 5.6 House rules

House rules are typed data, not arbitrary code patches.

---

# 6. Command/event architecture and determinism

Clients and controllers submit **commands**. The engine emits **events**.

Never allow direct authoritative patches such as changing HP or coordinates from a client, creator UI, simulation harness, or AI-controller payload.

Processing path:

```text
command
    -> authentication/controller authorization
    -> authorization
    -> schema validation
    -> idempotency check
    -> concurrency/version check
    -> timing validation
    -> rules validation
    -> deterministic resolution
    -> domain events
    -> atomic persistence
    -> projections/outbox
    -> WebSocket publication
```

## 6.1 Deterministic randomness

The server controls RNG state. Dice/random results generate events. Same initial state + rules/content versions + RNG seed + command stream must produce the same canonical outcome.

Named RNG streams separate dice, loot, encounters, world/procedural generation, optional controller variation, and playtest/scenario behavior.

## 6.2 Event metadata

Persist event/stream/campaign sequencing, simulation/server time, actor/command/causation/correlation IDs, rules/content lock data, event type/schema version, and payload. Controller decision traces are diagnostic, not authoritative.

## 6.3 Event sourcing and projections

Authoritative events feed rebuildable projections such as campaign state, actors/characters, encounters, inventory, quests, maps, timeline, available actions, visibility-filtered world state, controller-safe views, logs, journals, and recaps.

Snapshots reduce replay cost but never replace authoritative history.

---

# 7. First-class time and scheduler

The engine separates simulation time from wall-clock decision time and supports readiness, deadlines, action duration, cooldowns, delays, interrupts, reactions, periodic effects, world events, NPC schedules, and actor/controller availability.

Timing modes:

```text
turn_based
timed_turn_based
active_time
real_time_with_pause
real_time
hybrid
```

No request handler, controller, playtest, or simulation worker sleeps to represent simulation time. Controller eligibility is event-driven rather than busy-polled.

---

# 8. Universal action transaction model

All gameplay actions use a common definition/lifecycle with costs, prerequisites, targeting, timing, effects, cooldowns, interruptions, deterministic conflict ordering, and available-action discovery.

Clients/controllers consume server-advertised legal actions. They do not independently redefine legality.

---

# 9. Effects, features, resources, abilities, and conditions

Mechanics use reusable typed definitions/effect pipelines rather than one-off imperative handlers where practical. Features, resources, health, abilities/spells/powers, conditions, modifiers, triggers, durations, stacking, and generic resolution contexts/outcomes are versioned and deterministic.

---

# 10. Reactions and interrupts

Reactions are deterministic interrupt windows. Human and NPC controllers may only choose from eligible advertised reaction actions under their timing/visibility policies.

---

# 11. Spatial authority and movement

The server owns movement/position semantics through replaceable spatial adapters:

```text
TheaterOfMindSpace
GraphSpace
SquareGridSpace
HexSpace
Continuous2DSpace
Continuous3DSpace
```

Movement is an action; clients/controllers never patch coordinates. NPC controllers use authoritative movement intents/candidates rather than a second path/range rules engine.

---

# 12. Perception, hidden state, discovery, terrain, and world objects

True world state is separate from actor knowledge. Clients and controllers receive knowledge/visibility projections, never omniscient aggregates. Discovery is event-driven; world objects, containers, terrain, hazards, senses, lighting/visibility and secret checks remain server-authoritative.

---

# 13. Actor model

Players, NPCs, monsters, pets, companions, summons, and AI actors share a component-based actor foundation.

Initial controller types:

```text
human
simple_npc
scripted
remote_service
system
```

Later controller types may include utility AI, behavior trees, external agents, and LLM adapters.

```text
ControllerAssignment
    controller_type
    controller_version
    behavior_profile_ref | null
    enabled
    fallback_controller_type | null
```

Definitions/templates remain separate from mutable actor instances.

---

# 14. Character creation

Character creation is a resumable server-authoritative draft/session workflow with ruleset-driven steps, dependency invalidation, ability-generation policies, species/background/classes/subclasses, proficiencies, equipment, feats/features, abilities, identity, higher-level starts, multiclassing, lifecycle, import/export, and validation/finalization.

Derived values are projections rather than independently mutable fields.

---

# 15. Progression and skill/talent trees

A generic versioned progression graph supports conventional class progression and richer custom branching trees with ranks, prerequisites, mutually-exclusive paths, grants, respec policies, hidden nodes, and multiple advancement policies.

---

# 16. Campaign creation and configuration

Campaign creation is a resumable workflow covering ruleset/template, timing, progression/rest, spatial model, world clock, visibility/logging, content packs, player rules, house rules, and baseline controller policies.

Configuration changes are versioned for replay.

---

# 17. Membership, parties, sessions, adventures, scenes, and encounters

Membership/control grants are server-authoritative. Parties, game sessions, optional adventures, scenes, and runtime encounter lifecycles are explicit domain objects. `EncounterTemplate` authoring is defined separately in the creator specification.

When an encounter participant is assigned `simple_npc`, the scheduler/controller service requests a decision when that actor becomes eligible and submits the selected normal command.

---

# 18. Living world, calendar, travel, weather, and environment

The same scheduler drives combat and world time. World/region/location hierarchy, calendars, clock policies, travel, weather/environment, scheduled world events, and NPC schedules share the simulation timeline.

Baseline NPC out-of-combat autonomy is limited to authored/simple states such as idle, follow, hold, move-to-location, and execute-schedule-step until advanced AI.

---

# 19. Exploration, social interaction, dialogue, and narration

Exploration/social intents are typed actions. Dialogue is a state machine whose choices produce typed commands/effects. The baseline NPC controller does not generate natural language.

Authoritative events are facts; player-facing narration is a visibility-filtered projection. The deterministic narration-template renderer is the baseline. Optional later LLM narration may paraphrase visible facts but cannot invent authoritative state.

Detailed authoring/narration contracts: [`docs/authoring/CONTENT_AUTHORING.md`](docs/authoring/CONTENT_AUTHORING.md).

---

# 20. Quests, factions, reputation, and relationships

Quest objective graphs support sequential/parallel/optional/exclusive/hidden/timed/repeatable objectives. Faction/relationship state is event-driven and rules/content-defined. Static/simulation quality analysis should detect unreachable or structurally invalid content when possible.

---

# 21. Inventory, equipment, economy, trade, rewards, and crafting

Items/instances, inventories, currencies/wallets, vendors/trade, rewards/loot, and crafting are server-authoritative. Crafting progresses on simulation time. Content authoring and quality validation cover references/acquisition paths.

---

# 22. Rest, recovery, cooldowns, and regeneration

Rest is a first-class scheduled process; cooldowns/regeneration are timeline transitions with mode-appropriate projections.

---

# 23. AI and Dungeon Master boundaries

Baseline NPC controller: [`docs/ai/SIMPLE_NPC_AI.md`](docs/ai/SIMPLE_NPC_AI.md).

`SimpleNpcController` is deterministic, shallow, visibility-safe, profile-driven, and subordinate to available-action/rules validation. Initial profiles cover aggressive melee, ranged, balanced/defensive, support, passive, and flee.

Advanced AI may later add utility/goals/memory/planners/external/LLM adapters while preserving the same visible-input -> typed-command -> authoritative-events boundary.

DM powers are privileged commands, not arbitrary DB writes. Live DM/session operational workflows are defined in [`docs/operations/DM_SESSION_OPERATIONS.md`](docs/operations/DM_SESSION_OPERATIONS.md).

---

# 24. Logging, history, recaps, and journals

Maintain four separate concepts: authoritative domain event log, player game/combat log projection, administrative audit log, and operational logs.

Session recaps, character journals, quest/discovery journals, campaign chronicles, NPC encounter history, and related views are visibility-filtered deterministic projections over authoritative history. Optional AI summaries may stylistically summarize those facts but are not authoritative.

---

# 25. Replay, snapshots, checkpoints, branches, and schema evolution

The engine supports replay from start/snapshot, historical inspection, projection rebuilds, event upcasters, and versioned schemas.

Named checkpoints are durable references to campaign sequence/time/snapshot information. The default restore workflow creates a campaign branch from a checkpoint/sequence rather than erasing later authoritative history.

Detailed checkpoint/branch/session lifecycle: [`docs/operations/DM_SESSION_OPERATIONS.md`](docs/operations/DM_SESSION_OPERATIONS.md).

---

# 26. REST API contract

Initial public API domains cover rules/content, character/campaign creation, world/scene/party/session/actors/encounters/timeline/actions/commands/events/effects/items/abilities/features/quests/dialogues/factions/vendors/recipes.

Creator/operations additions include authoring workspaces/drafts/validation/releases, encounter templates, lobbies/ready checks/control grants/checkpoints/branches/recaps/journals, content-revision diff/impact/dry-run, and quality/simulation job/report APIs.

State-changing gameplay operations prefer typed commands. Authoring mutable drafts and operational job resources may use conventional resource APIs where they are not authoritative campaign gameplay state.

API errors are typed/versioned; queries carry projection/version metadata; unbounded collections use opaque cursors.

---

# 27. Character, campaign, creator, and operational projections

Core projections include CharacterSheet and CampaignDashboard plus role-aware creator/session views such as:

```text
CreatureEditorView
EncounterEditorView
QuestGraphEditorView
DialogueGraphEditorView
WorldGraphEditorView
CampaignLobby
SessionRecap
CharacterJournal
CampaignChronicle
ContentQualityReport
CompatibilityReport
CampaignContentImpactReport
```

All remain derived/read models unless explicitly defined as mutable authoring/operations state.

---

# 28. WebSocket live protocol

The live protocol provides authenticated subscriptions, ordered delivery, acknowledgement/resume, snapshot+delta resync, bounded backpressure, heartbeats, and server-side visibility filtering.

Lobby/presence notifications can use live channels but ephemeral presence is not authoritative gameplay history unless campaign policy explicitly turns it into events.

---

# 29. Persistence, concurrency, authoring storage, and transaction model

Recommended authoritative persistence stack:

```text
PostgreSQL
SQLAlchemy 2.x async
asyncpg
Alembic
```

Gameplay authority uses event streams/receipts/snapshots/projections/outbox with optimistic concurrency/idempotency.

Mutable authoring drafts may use conventional revisioned persistence; do not event-source every editor keystroke. Published definitions are immutable/versioned.

Simulation jobs/results are operational/isolated data and never mutate live production campaign streams.

Keep database migrations, event upcasters, projection migrations/rebuilds, content migrations, controller/profile migrations, and trusted-extension compatibility/migrations distinct.

---

# 30. Authentication, authorization, security, and abuse controls

Authorization evaluates role plus resource scope. DM is a permission bundle, not a DB bypass. Authoring/publishing, session operations, checkpoints/branches, simulation jobs, content activation, and trusted extension administration use explicit permissions.

Imported content and authored text are untrusted input. Ordinary content packs cannot execute arbitrary code. Secrets/tokens never appear in gameplay events/logs/exports/controller traces/simulation artifacts/test-evidence artifacts.

---

# 31. Assets, localization, accessibility, and units

Asset refs, localized text refs, canonical units/conversion metadata, and accessibility-oriented semantic descriptions remain client-independent. Authoring/published content validates asset/license references.

---

# 32. Import/export, portable packages, and content authoring

Character/campaign exports retain version/content provenance without auth/control grants. Content pack archives include manifest, definitions, migrations, localization resources, declared assets, and hashes.

Imports always stage/validate before activation.

The authoring lifecycle is:

```text
workspace/draft
    -> layered validation
    -> preview/runtime dry run
    -> playtest/simulation evidence
    -> publish-ready
    -> immutable versioned content-pack release
    -> optional install/activation into campaign lock
```

Detailed authoring contracts: [`docs/authoring/CONTENT_AUTHORING.md`](docs/authoring/CONTENT_AUTHORING.md).

---

# 33. Reliability, backup, restore, and crash recovery

Backups include authoritative DB data, pinned content/extension metadata, required campaign assets, and migration metadata. Automated restore tests verify event/projection integrity.

Restart recovery restores timeline/deadlines/controller eligibility/outbox/projection state without duplicate actions.

Content upgrades create recovery checkpoints/branches as required; restore/migration semantics preserve historical content interpretation.

---

# 34. Observability, simulation, and analytics

Operational metrics cover command/event/projection/scheduler/WebSocket/controller behavior plus authoring validation, simulation throughput, migration failures, and quality-regression signals.

Analytics and simulation consume/drive separate pipelines and are never prerequisites for authoritative command processing.

The Simulation/Quality Lab is defined in [`docs/testing/SIMULATION_QUALITY_LAB.md`](docs/testing/SIMULATION_QUALITY_LAB.md).

---

# 35. Testing strategy

Normative test specifications:

- [`docs/testing/HUMAN_PLAYTESTING.md`](docs/testing/HUMAN_PLAYTESTING.md)
- [`docs/testing/SIMULATION_QUALITY_LAB.md`](docs/testing/SIMULATION_QUALITY_LAB.md)
- [`docs/testing/LOCAL_TEST_AGENT.md`](docs/testing/LOCAL_TEST_AGENT.md)
- [`docs/ai/SIMPLE_NPC_AI.md`](docs/ai/SIMPLE_NPC_AI.md)

Testing includes unit/domain/controller tests, rules conformance, deterministic replay, creation workflows, timing/action matrices, visibility/security, content compatibility, migration fixtures, persistence failures, API/live contracts, property/model-based tests, public-interface human-play scenarios, generated action walkers, simulation batches, static/reachability analysis, and performance benchmarks.

`Testing Grounds` is the canonical continuous end-to-end playtest campaign and grows to cover campaign/lobby/session, character creation, town/social/quests, trade/crafting, travel/discovery, autonomous NPC encounters, rewards/progression, reconnect, checkpoint/branch, session close/recap, and replay.

Execution verification is separate from test design. **Only local-agent evidence** may satisfy execution gates. Evidence must bind the exact commit, canonical local test profile, environment, suite results, and relevant artifacts. Missing, blocked, or stale evidence cannot be represented as a green execution result.

The executable checklist and playability ladder in [`TODO.md`](TODO.md) are part of test planning: each phase identifies the public journey and canonical local profile that prove it.

GitHub Actions and remote CI are not part of the testing architecture. See Section 50.

---

# 36. Initial technical stack

```text
Python 3.12+
FastAPI
Pydantic v2
SQLAlchemy 2.x async
asyncpg
PostgreSQL
Alembic
pytest
pytest-asyncio
Hypothesis
httpx with ASGI transport
WebSockets
```

Baseline NPC AI requires no ML/LLM dependency. Later optional infrastructure may include Redis for ephemeral coordination/cache, OpenTelemetry, Prometheus, structlog, and evidence-driven performance libraries.

---

# 37. Proposed repository structure

```text
rpg-engine-api/
├── src/rpg_engine_api/
│   ├── api/
│   ├── application/
│   ├── domain/
│   ├── controllers/
│   ├── rules/
│   ├── rulesets/
│   ├── authoring/
│   ├── simulation/
│   ├── persistence/
│   └── infrastructure/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── rules/
│   ├── controllers/
│   ├── determinism/
│   ├── replay/
│   ├── visibility/
│   ├── migration/
│   ├── simulation/
│   └── playtest/
├── scripts/
│   └── test
├── artifacts/
│   └── test-evidence/       # generated/usually not committed
├── examples/
├── docs/
│   ├── architecture/
│   ├── api/
│   ├── rules/
│   ├── ai/SIMPLE_NPC_AI.md
│   ├── authoring/CONTENT_AUTHORING.md
│   ├── operations/DM_SESSION_OPERATIONS.md
│   ├── extensions/TRUSTED_EXTENSIONS_AND_MIGRATIONS.md
│   ├── testing/HUMAN_PLAYTESTING.md
│   ├── testing/SIMULATION_QUALITY_LAB.md
│   ├── testing/LOCAL_TEST_AGENT.md
│   └── decisions/
├── migrations/
├── PLAN.md
├── TODO.md
├── AGENTS.md
└── pyproject.toml
```

`.github/` may contain repository configuration such as Copilot instructions, but `.github/workflows/` must remain absent/empty under the local-only execution policy.

`PLAN.md` is the canonical roadmap. Detailed specifications above are normative elaborations of this plan. `TODO.md` is the executable implementation ledger and must remain consistent with both.

---

# 38. Implementation roadmap

## v0.1 — Deterministic Core + Shared Contracts

### Goal

Create the smallest authoritative engine capable of typed commands -> reproducible versioned events, while establishing the seams that later gameplay, authoring, controllers, testing, simulation, extensions, and evidence-driven local execution depend on.

### Deliverables

- Python 3.12+ scaffold and FastAPI factory;
- Pydantic command/event/shared schemas;
- stable IDs/namespaced keys/`DefinitionRef`;
- `RequirementExpr`, `ChoiceGroup`, `Grant`, visibility, source metadata;
- `ControllerAssignment` and controller registry seam;
- definition-schema registry and immutable published-definition identity/version seam;
- trusted-extension/version metadata seam and data-only ordinary content invariant;
- campaign/actor aggregate foundations;
- command bus/envelope/receipts/errors;
- deterministic RNG streams/dice;
- in-memory and PostgreSQL async event stores;
- stream versions/idempotency/upcaster/snapshot/projection/outbox seams;
- canonical state hashing/replay fixtures;
- health/readiness endpoints;
- playtest harness skeleton, seed/transcript/artifact/coverage schemas;
- `TestEvidenceBundle`/suite/environment schemas;
- canonical local test-profile runner/manifest seam with at least `smoke` and `pr` foundations;
- programmatic `scripts/test-all` wrapper for full canonical profile sweeps against local PostgreSQL;
- machine-readable JUnit/evidence artifact output;
- ContentQualityReport/CompatibilityReport schema seams;
- Testing Grounds fixture skeleton;
- black-box minimal command/replay/idempotency/conflict scenarios;
- complete `TODO.md` Phase A through playability gates P0/P1.

### Exit criteria

The minimal public command path is deterministic/replayable; an actor can carry a versioned controller assignment; published definitions and trusted-extension metadata have stable version seams; the playtest/quality artifact foundations exist without later architecture rewrites; a local executor can run the initial canonical profile for an exact commit and the full canonical profile sweep programmatically; and TODO P0/P1 are demonstrated rather than merely coded.

---

## v0.2 — First-Class Time + Universal Actions

Add the full scheduler/timing modes, universal action lifecycle, deadlines/timeouts, controller eligibility hooks, movement/rest/cooldown foundations, exact controllable-clock playtests, disconnect/control-handoff timing seams, and include those suites in the canonical local profiles.

Exit when one representative action works deterministically under every timing mode and controller eligibility/timeout/reconnect paths require no blocking sleeps or polling, with matching **local evidence** for the candidate revision before the milestone execution gate is satisfied and `TODO.md` Phase B complete.

---

## v0.3 — SRD Combat Runtime + Encounter Authoring + Simple NPC Combat AI

Add SRD combat foundations, encounter runtime lifecycle, `EncounterTemplate` authoring schema, participant groups/waves/objectives/rewards/scaling foundation, `SimpleNpcController` combat MVP, behavior profiles/reactions/fallbacks, encounter smoke simulation, human-vs-NPC playtest, and deterministic AI-vs-AI simulation.

Exit when a creator can define/validate a basic encounter template and a human-facing test client can instantiate/play it against autonomous enemies through public interfaces with deterministic replay, proven by the required local profile/evidence bundle for the exact revision and `TODO.md` P2 playable-combat gate.

---

## v0.4 — Effects/Resources/Abilities + Progression + Authoring/Extension Primitives

Add data-driven effects/features/resources/abilities/conditions/progression, authoring schemas for those definitions, safe declarative DSL expansion, trusted extension points for predicates/effect operations if required, simulation metrics for abilities/resources/effects, and generated-action exploration.

Exit when representative mechanics can be authored/validated/published, exercised by humans/NPCs, and inspected through simulation without custom hidden handlers, with local execution evidence for relevant integration/playtest/simulation suites and the P2 slice still working.

---

## v0.5 — Spatial Authority + Perception + Exploration + World Authoring

Add spatial adapters, path/LOS/cover/terrain/objects/containers/hazards/scenes/discovery, controller-safe perception/movement, world/location/scene/object authoring schemas, optional trusted spatial adapter provider seam, and spatial/perception simulation invariants.

Exit when one exploration/encounter fixture works across multiple spatial adapters and clients/controllers receive only permitted knowledge, verified by the canonical local profile and visibility/playtest evidence, and `TODO.md` P3 is complete.

---

## v0.6 — Complete Character Runtime + Character/Progression Authoring

Add full ruleset-driven character creator/runtime, higher-level/multiclass/advancement/import-export, authoring schemas for classes/species/backgrounds/templates/progression, systematic creator/playtest matrices, and progression reachability analysis.

Exit when generic clients and creator tools can discover, author, validate, create, and advance representative characters without local hidden rules, with local evidence for creation/playtest/reachability paths, and `TODO.md` P4 is complete.

---

## v0.7 — Campaign Creator + Living World + Creator Studio Foundations + Session Operations + Quality Lab

This is the major composition milestone.

Add:

- campaign creation/templates/content locks/house rules;
- parties/world/calendar/travel/weather/NPC schedules;
- quests/dialogue/factions/relationships/economy/vendors/loot/crafting;
- simple NPC schedule-step integration and `NpcPersonalityProfile`;
- authoring workspaces/drafts, layered validation, publish-ready/published release workflow;
- quest/dialogue/world/vendor/recipe/campaign authoring schemas;
- baseline deterministic narration templates;
- Creator/DM Studio API foundations and schema discovery;
- lobbies, invitations, memberships, ready checks, sessions, control grants/handoff;
- named checkpoints and branch-from-checkpoint/sequence workflow;
- deterministic session recaps/journals/chronicles;
- semantic content diff/impact report foundations;
- typed content migration descriptors and automatic pre-upgrade checkpoint;
- initial Content Testing SDK;
- quest/dialogue/world/content reachability analysis;
- creator-facing ContentQualityReport;
- local-agent `playtest`, `simulation`, `migration`, `replay`, `full`, and long-form Testing Grounds profile integration;
- Testing Grounds long-form town -> social -> quest -> trade -> travel -> autonomous encounter -> reward -> progression -> checkpoint/session-close journey;
- `TODO.md` P5 and P6 playable campaign/creator gates.

Exit when a creator can author/publish a small campaign content set, a DM can host/operate a complete session, and the quality lab can validate/reachability-test/simulate the reference content without bypassing the real runtime, with reproducible local evidence for the composed workflow and P5/P6 complete.

---

## v0.8 — Advanced Intelligent and External Controllers

Build richer utility/goals/memory/schedules/external/LLM controllers on the proven baseline. Add controller comparisons in the simulation lab, explicit external-controller circuit breakers/fallbacks, AI DM command surfaces, trusted controller-provider extension seams, and local executor evidence for external-controller/fallback scenarios.

`SimpleNpcController` remains the deterministic baseline/reference/fallback and all earlier playable gates remain regression requirements.

---

## v0.9 — Stable Universal Client + Creator + Operations + Extension APIs

Stabilize `/api/v1`, OpenAPI/error/version/deprecation contracts, auth, discovery, projections, action targeting, history cursors, WebSocket resume/backpressure/snapshot+delta, localization/assets/import-export, Python SDK, terminal/WebSocket clients, plus:

- stable Creator/DM Studio authoring/schema-discovery APIs;
- stable lobby/session/control/checkpoint/branch/recap/journal APIs;
- stable Simulation/Content Testing SDK and CLI contracts;
- local/containerized test deployment support;
- stable trusted extension API/capability contracts;
- content semantic diff/compatibility/impact/migration-preview APIs;
- controller assignment/status surfaces without leaking hidden AI state;
- stable local test CLI/profile manifests and `TestEvidenceBundle` schema;
- execution targets for in-process, local-server, and containerized local test deployments;
- `TODO.md` P7 content-evolution flow.

Exit when the same executable scenarios can validate public game clients, creator workflows, session operations, simulation tooling, content-upgrade preview, and canonical local test profiles through stable contracts, with P7 complete.

---

## v1.0 — Production-Ready SRD 5.2.1 RPG Engine Platform

Deliver stable core/game/client/controller schemas, SRD-compatible rules package, deterministic `SimpleNpcController`, complete authoring/validation/publish workflow, reference Creator APIs/examples, complete session/lobby/checkpoint/recap workflow, Content Testing SDK and simulation-lab reference workflows, trusted extension boundary documentation, content upgrade dry-run/activation/rollback-or-branch workflow, migration/replay fixtures, sample campaign/content, observability/security/backup/recovery/performance tooling, reference clients, executable release acceptance scenarios, and a strict **local `release` evidence bundle** for the exact release candidate commit.

### v1.0 success statement

A third-party developer can build a supported client; a creator can author/validate/publish content; a DM can host and recover sessions; non-human actors can play autonomously; content can be simulated and quality-checked; campaigns can safely evolve content versions; and release claims are backed by reproducible **local execution evidence**—all without modifying the authoritative core, duplicating hidden rules, or destroying historical replayability. `TODO.md` P8 is the executable release-quality gate.

---

# 39. v1.0 end-to-end acceptance matrix

The existing gameplay acceptance matrix remains mandatory and executable. It must cover rules/content setup, campaign/lobby/session creation, character creation, exploration/world interaction, social/quest systems, encounter/timing/controllers, progression, logs/history/replay, live sync, and content/controller evolution/recovery.

In addition, v1.0 release scenarios must demonstrate the creator/operations/quality/extension acceptance set in Section 47, the cumulative P0–P8 playability requirements in `TODO.md`, and be included in the exact release candidate's local `release` `TestEvidenceBundle`.

---

# 40. Definition of a planning-complete subsystem

A subsystem is not considered planned merely because a noun/interface exists. Before implementation define:

- authoritative state or explicit non-authoritative/mutable-draft status;
- content/definition schema;
- commands/events where authoritative;
- queries/projections;
- lifecycle/state machine;
- permissions and visibility;
- concurrency/idempotency;
- persistence/replay implications;
- migration/version behavior;
- failure/error behavior;
- live/API behavior where relevant;
- import/export behavior where relevant;
- controller/AI boundary where relevant;
- authoring/validation/publish workflow where relevant;
- simulation/reachability/quality evidence where relevant;
- trusted extension implications where relevant;
- automated tests/milestone exit criteria;
- canonical local test profile(s) and required evidence artifacts;
- its ordered `TODO.md` implementation items and playability impact;
- source/license provenance for distributable content;
- public human/client journey for user-visible behavior;
- coverage-manifest entries for positive/negative/visibility/timing/reconnect/controller/replay cases.

---

# 41. Definition of done for every milestone

A milestone is not complete until applicable code is typed/non-blocking; required unit/integration/determinism/replay/visibility/controller tests exist; public schemas are documented/versioned; migrations/upcasters are included; licensing/provenance is correct; command/event/controller/content compatibility is preserved; concurrency/idempotency is tested; user-visible features have black-box play scenarios; timing uses controllable clocks; failures are reproducible; coverage manifests are current; creator-facing schemas validate/publish correctly; simulation/reachability checks exist where the feature is content-driven; extension/content migrations are dry-run/replay-tested where interpretation changes; the corresponding TODO phase is objectively complete; and its cumulative playability gate still passes.

For the **execution gate**, the required **local-agent `TestEvidenceBundle`** must match the candidate commit and canonical local profile. If evidence is unavailable, blocked, stale, or missing required suites, the work may be described as implemented but not execution-verified and must not be represented as locally passing. The matching TODO verification checkbox stays unchecked or `[AWAITING EVIDENCE]`.

---

# 42. First implementation slice

The first slice remains intentionally small and maps directly to `TODO.md` Phase A:

```text
app/config
shared IDs/definitions/requirements/choices/visibility
controller assignment/interface seam
commands/events/dice/campaign/actor
command bus
event store/outbox
health/command API
playtest harness skeleton
TestEvidenceBundle + test profile runner skeleton
quality/compatibility artifact schemas
```

Prove CreateCampaign/CreateActor, controller assignment, deterministic dice, replay hash, idempotent retry, stale stream conflict, and one public playtest command/replay path. The local executor should be able to run the initial `smoke`/`pr` profile and emit commit-bound machine-readable evidence. Do not import large content catalogs, implement advanced AI, or build the full Creator Studio yet.

The first development objective is not “finish all infrastructure”; it is to reach P0/P1 quickly while keeping the architecture correct, then build toward P2—the first game-like human-vs-autonomous-NPC combat slice.

---

# 43. Deliberately post-v1.0 work

Explicit future scope includes distributed zones/shards, large-world cross-process interest/migration, massive presence, sophisticated behavior-tree/GOAP/planner systems beyond the initial advanced-controller boundary, rich procedural-world tooling, polished full visual map/creator editors, third-party extension/content marketplaces, hosted billing/entitlements, advanced collaborative authoring, polished alternate-timeline UX, and engine-specific rendering integrations beyond reference client/SDK contracts.

---

# 44. Long-term product goal

The engine should support multiple timing modes and replaceable controllers without replacing the game-state model, rules runtime, action system, scheduler, persistence, client API, authoring formats, replay model, evidence contract, or playable-product execution path.

> **The engine understands time, events, actions, resources, effects, space, knowledge, rules, content, sessions, and replaceable controllers—not one hard-coded turn system, client, authoring UI, or AI implementation.**

> **If a human can do it in a supported client, a deterministic programmatic persona must be able to do it through the same public interfaces; if content can be authored, it must be validateable/testable/versionable; if a campaign evolves, old history must remain interpretable; if a change is claimed to pass locally, that claim must be backed by revision-matched machine-produced local evidence; and the implementation sequence must continuously converge on and preserve a playable game.**

---

# 45. Programmatic human-play testing architecture

[`docs/testing/HUMAN_PLAYTESTING.md`](docs/testing/HUMAN_PLAYTESTING.md) is normative. Public-interface-only playtests model player/DM/spectator personas, timing/reconnect behavior, independent seeds, scenario DSL/transcripts, visibility/invariant assertions, failure replay bundles, generated available-action walkers, chaos/recovery, **local execution modes**, coverage manifests, and the continuous Testing Grounds campaign journey.

The v1.0 gameplay acceptance matrix must be executable, not prose-only.

---

# 46. Baseline deterministic NPC AI architecture

[`docs/ai/SIMPLE_NPC_AI.md`](docs/ai/SIMPLE_NPC_AI.md) is normative.

Baseline AI is a deterministic one-decision-at-a-time `SimpleNpcController` using visibility-filtered state and server-advertised legal actions. Versioned behavior profiles cover aggressive melee, ranged, balanced/defensive, support, passive, and flee. It submits normal commands, has safe deterministic fallback, and does not generate natural language or perform long-term planning.

Roadmap placement:

```text
v0.1 controller assignment/interface seam
v0.2 eligibility hooks
v0.3 combat MVP
v0.5 perception/spatial movement integration
v0.7 authored schedule integration
v0.8 advanced utility/external/LLM controllers
```

---

# 47. Creator, DM operations, simulation quality, extensions, and content evolution

This section incorporates all twelve additional planning areas into the canonical roadmap. Detailed schemas/workflows are normative in:

- [`docs/authoring/CONTENT_AUTHORING.md`](docs/authoring/CONTENT_AUTHORING.md)
- [`docs/operations/DM_SESSION_OPERATIONS.md`](docs/operations/DM_SESSION_OPERATIONS.md)
- [`docs/testing/SIMULATION_QUALITY_LAB.md`](docs/testing/SIMULATION_QUALITY_LAB.md)
- [`docs/extensions/TRUSTED_EXTENSIONS_AND_MIGRATIONS.md`](docs/extensions/TRUSTED_EXTENSIONS_AND_MIGRATIONS.md)

## 47.1 Content authoring system

Use a mutable `AuthoringWorkspace`/`DraftDefinition` lifecycle followed by layered validation, runtime preview/playtest, publish-ready state, and immutable versioned `PublishedContentPack` releases. Finalized campaigns never reference mutable drafts.

Validation covers schemas, namespaces, references, ruleset compatibility, provenance/licenses, graph reachability, semantic/runtime instantiation, and required play/simulation evidence.

## 47.2 Creator / DM Studio API

Provide schema-discoverable authoring APIs for creatures/NPCs, items, abilities, progression trees, quests, dialogue, encounters, world/scene/location content, vendors, recipes, AI profiles, campaign templates, and narration templates.

Specialized editor projections are convenience views; canonical published definitions remain runtime schemas. Creator APIs cannot bypass campaign command/event authority.

## 47.3 Encounter authoring

`EncounterTemplate` is versioned content distinct from runtime `Encounter` instances. Templates define participant groups/controller assignments, spawns/positions, waves/triggers, objectives, environmental effects, reinforcements, escape/completion/failure policies, rewards, scaling, and narration refs.

Creators can preview resolved participants/actions/map validity and run simulation/playtest evidence before publication.

## 47.4 Automated balance / simulation lab

Use the real engine runtime/rules/controllers to run reproducible encounter/situation batches under deterministic seeds and configuration matrices. Capture outcome/duration/action/resource/controller/objective metrics and retain outlier seeds.

Support matched-seed comparisons across encounter/content/controller/timing revisions. Do not reduce this to one opaque universal “balance score.”

## 47.5 Narration / presentation layer

Authoritative events are facts. Narration is a visibility-filtered projection using deterministic localized templates as baseline. `GameMessage` links back to source event IDs/sequence ranges. Optional later LLM narration may paraphrase visible facts but cannot create authoritative consequences or hidden facts.

## 47.6 Game/lobby lifecycle

Explicitly support invitations/membership, lobby open/join/leave, actor selection/control grants, ready checks, session open/pause/resume/close, multi-device conflict handling, spectator presence, disconnect grace, AFK policies, and explicit temporary controller handoff/restoration.

Lobby/presence metadata is not automatically authoritative gameplay history.

## 47.7 Named saves/checkpoints/branches

`CampaignCheckpoint` records a named historical sequence/time/content lock and optional snapshot ref. Checkpoint deletion removes only the reference.

Default restore creates `CampaignBranch` from a checkpoint/sequence, preserving parent/fork metadata and old history. Pre-migration/session-boundary automatic checkpoints are supported.

## 47.8 Session recaps and journals

Deterministic role-aware projections include `SessionRecap`, `CharacterJournal`, `QuestJournal`, `DiscoveryJournal`, `CampaignChronicle`, `NpcEncounterHistory`, and faction/location histories.

Optional AI summarization operates on visibility-filtered structured recap facts and never replaces authoritative history.

## 47.9 NPC social personality

`NpcPersonalityProfile` is separate from combat/action `NpcBehaviorProfile`. Personality carries disposition, goals, loyalties, fears, interests, topic/style tags, relationship/aggression/assistance thresholds, and trade preferences. Social/dialogue rules use visible/known relationship/faction/quest context plus legal social actions.

## 47.10 Content Testing SDK

Expose programmatic creator/local-test functionality for pack validation, creature/encounter instantiation, playtest execution, encounter simulation, batch comparison, quest/dialogue/progression reachability, unobtainable-item/unusable-ability detection, and machine-readable quality reports.

Provide a scriptable CLI/API by v0.9. Important outlier/failure runs can be promoted into permanent regression fixtures.

## 47.11 Trusted extension/plugin boundary

Ordinary `ContentPack`s are data-only and may use only typed declarative engine DSLs. Executable customization uses explicitly deployment-installed `RulesExtension`s with versioned manifests, narrow capabilities/interfaces, explicit permissions, failure isolation, and deterministic/replay compatibility for authoritative effects.

Never auto-load executable code from user-uploaded content archives.

## 47.12 Compatibility and content migration UX

Before live content changes, support candidate lock resolution, semantic revision diff, `CompatibilityReport`, `CampaignContentImpactReport`, typed `ContentMigrationPlan`, isolated dry run/branch, required validation/playtests, automatic checkpoint, atomic activation, and post-activation replay/projection verification.

Rollback occurs only when a valid reverse path exists; otherwise branch from the pre-upgrade checkpoint. Active campaign mechanics default to manual upgrade policy rather than silent automatic changes.

## 47.13 Creator/session/quality acceptance requirements

In addition to Section 39 gameplay acceptance, v1.0 must programmatically prove:

1. Create an authoring workspace and draft definitions.
2. Produce and resolve validation errors for bad references/graphs/provenance.
3. Author and preview a creature/NPC with behavior and personality profiles.
4. Author an `EncounterTemplate` with participants, objectives, reward, and controller assignments.
5. Run encounter smoke simulation using the real runtime.
6. Run a deterministic simulation batch and reproduce a selected outlier seed.
7. Run quest/dialogue/progression reachability analysis on reference content.
8. Publish an immutable versioned content pack only after required gates pass.
9. Open a campaign lobby, invite/join a player, assign actor control, and complete a ready check.
10. Open a game session and play through the reference content.
11. Disconnect a player, apply configured temporary control handoff, reconnect, and explicitly restore control.
12. Create a named checkpoint.
13. Create a branch from that checkpoint and verify identical state at the fork sequence.
14. Close the session and produce visibility-correct recap/journal/chronicle projections.
15. Render deterministic narration messages linked to source events.
16. Demonstrate ordinary content packs cannot execute arbitrary code.
17. Install/enable a trusted test extension only through authorized administration and declared capabilities.
18. Propose a content revision and generate semantic diff/compatibility/campaign-impact reports.
19. Dry-run its migration on an isolated copy/branch and run required play/simulation checks.
20. Activate the content revision with an automatic checkpoint and verify old/new history across the lock boundary.
21. Demonstrate safe rollback or required branch-from-checkpoint behavior when direct rollback is unsafe.
22. Use the Content Testing SDK/CLI to reproduce validation, reachability, simulation, and regression workflows without direct DB mutation.

## 47.14 Unified creator-to-play-to-evolution journey

The long-form reference workflow should eventually prove:

```text
creator drafts content
    -> validates/reachability-checks
    -> authors encounter/NPC personality/controller profiles
    -> simulates/playtests
    -> publishes pack
    -> DM creates campaign
    -> opens lobby/invites players
    -> ready check/session open
    -> players create/join with characters
    -> town/social/quest/trade/craft/explore
    -> autonomous encounter
    -> reward/progression
    -> checkpoint
    -> disconnect/handoff/reconnect
    -> session close/recap/journals
    -> propose content update
    -> semantic diff/impact/dry-run
    -> checkpoint + activate migration
    -> replay old/new history
    -> branch/rollback if required
```

This workflow is the architectural proof that authoring, gameplay, operations, quality tooling, and content evolution are one coherent platform rather than disconnected subsystems.

---

# 48. Local test agent execution and evidence architecture

[`docs/testing/LOCAL_TEST_AGENT.md`](docs/testing/LOCAL_TEST_AGENT.md) is normative for executing repository tests in a real local/deployment-like environment and for communicating results back to remote development/review agents.

## 48.1 Responsibility split

```text
remote development/review agent
    architecture + implementation
    test/scenario design
    static review
    evidence interpretation
    fix preparation

local test agent
    checkout exact candidate revision
    provision required local services
    execute canonical local test profile
    capture machine-readable evidence
    preserve reproducible failure artifacts
```

The designated local executor is the sole authority for claims about what actually ran and passed in that environment. Remote agents remain responsible for requiring the right tests and must not fabricate execution status when they cannot run them.

## 48.2 Commit-bound evidence

Every execution produces a versioned `TestEvidenceBundle` bound to an exact `commit_sha`.

Conceptual top-level fields:

```text
schema_version
evidence_id
repository
commit_sha
branch
dirty_worktree
test_profile
executor_kind = local_agent
executor_version
environment
started_at/finished_at
overall_status
suites[]
artifacts[]
summary
```

Environment metadata records safe reproducibility information such as OS/architecture, Python/dependency fingerprint, PostgreSQL/service versions, engine-config fingerprint, locale/timezone, and relevant feature flags. Secrets are never collected.

## 48.3 Canonical local profiles

The repository converges on one scriptable local test entry point supporting:

```text
smoke
pr
unit
integration
playtest
simulation
migration
replay
performance
full
nightly
release
```

The profile definition—not an agent's ad-hoc substitute—determines which suites are required for a claimed canonical run.

`nightly` is a local profile name; it does not imply a GitHub Actions schedule.

`blocked` or unexpectedly skipped required suites do not count as passed.

## 48.4 Merge gate

Distinguish:

```text
implementation_ready
    code/tests/docs/migrations are prepared

execution_verified
    exact-commit local evidence exists
    required local profile ran
    mandatory suites passed
    disallowed skips/blocks are absent

mergeable
    implementation_ready
    + execution_verified
    + review/policy requirements
```

Default expectations:

- behavior-changing PR -> local `pr` evidence;
- persistence/content interpretation changes -> local `pr` plus relevant `migration`/`replay` evidence;
- performance claims -> targeted local `performance` evidence;
- release candidate -> strict local `release` evidence.

Documentation-only exceptions may be defined by merge policy where runtime execution cannot be affected.

## 48.5 Failure workflow

Failures must be useful to a remote agent without requiring local-machine access.

Preserve, as applicable:

```text
exact failing command/suite
exit code and counts
scenario/simulation ID
seed bundle
rules/content/controller/extension versions
REST/WebSocket transcript
projection/event sequence information
canonical hashes
migration/replay fixture
logs without secrets
```

Classify failures as product, test/fixture, environment, flaky/nondeterministic, or performance regression rather than retrying invisibly until green.

## 48.6 Evidence storage

Generated evidence should use a predictable local tree such as:

```text
artifacts/test-evidence/<evidence_id>/
    evidence.json
    junit/
    coverage/
    playtest/
    replay/
    simulation/
    migration/
    performance/
    logs/
```

Large ephemeral artifacts need not be committed. Durable golden fixtures/regressions are intentionally promoted into the repository when they become part of the test contract.

## 48.7 No fabricated verification

No agent may invent commands, counts, logs, screenshots, green suite status, or local behavior it did not observe.

If execution evidence is unavailable, the correct status is:

```text
implemented / not executed
```

or:

```text
execution evidence unavailable
required next local profile: <profile>
```

not a guessed pass result.

## 48.8 Roadmap placement

```text
v0.1
    TestEvidenceBundle schema
    canonical local profile runner/manifest seam
    smoke + pr foundations
    machine-readable suite evidence

v0.2-v0.6
    timing/controller/combat/spatial/character suites enter canonical local profiles

v0.7
    authoring/session/simulation/migration/replay/full profiles
    long-form Testing Grounds local execution

v0.8
    advanced/external controller evidence

v0.9
    stable local test CLI/profile/evidence schemas
    in-process/local-server/containerized local targets

v1.0
    local release TestEvidenceBundle is a required release artifact
```

## 48.9 Release proof

The v1.0 release candidate is not execution-verified until the exact candidate commit has a successful **local** `release` evidence bundle covering the required gameplay acceptance matrix, creator/session/quality acceptance set, migration/replay compatibility, visibility/security, recovery/backup where implemented, simulation/content-quality gates, and the defined performance profile.

A later code change invalidates that release evidence until the required local profile is rerun for the new candidate.

---

# 49. Executable TODO and cumulative playability architecture

[`TODO.md`](TODO.md) is the canonical **execution ledger** for this plan. It expands roadmap milestones into checkable implementation tasks, local test profiles, and cumulative playable-product gates.

## 49.1 Authority and update rules

```text
PLAN.md
    defines architecture and roadmap
        ↓
normative docs/
    define subsystem contracts
        ↓
TODO.md
    defines ordered implementation/checklist work
        ↓
local TestEvidenceBundle
    proves what actually executed
```

Agents must not create a second competing TODO. When new implementation detail is discovered, update `TODO.md`. When architecture changes, update this plan first and then reconcile the TODO.

Unless the user explicitly requests later work, agents select the earliest unchecked, unblocked TODO item in the active milestone.

Implementation and execution verification are separate states. An item may be implemented but remain `[AWAITING EVIDENCE]`; an execution checkbox is not complete until the exact candidate commit has the required **local-agent evidence**.

## 49.2 Playability ladder

The TODO defines cumulative gates:

```text
P0  bootable engine + deterministic public command/replay loop
P1  minimal interactive available-action loop
P2  complete human-vs-SimpleNpcController combat slice
P3  exploration/perception/discovery flowing into encounter
P4  character creation + gameplay + progression
P5  complete DM/player campaign session
P6  creator -> validate/simulate/publish -> playable content
P7  content revision/migration -> continued play/replay
P8  release-quality end-to-end platform
```

A later gate includes the earlier gates unless explicitly superseded. Breaking an earlier gate is a regression, not acceptable milestone progress.

P2 is the first unmistakably game-like vertical slice and must arrive by v0.3. It requires a human-facing client to discover and submit legal actions while `SimpleNpcController` independently drives the opposing non-human actor through the same authoritative command/rules path.

## 49.3 Continuous Testing Grounds journey

Testing Grounds is one cumulative playable story rather than disconnected test fixtures. It grows toward:

```text
create/install content
    -> create campaign
    -> invite/join/ready/session
    -> create/select hero
    -> town dialogue/quest/trade
    -> travel/explore/discover/interact
    -> autonomous NPC encounter
    -> reward/progression
    -> checkpoint
    -> disconnect / optional AI handoff / reconnect
    -> session close + recap/journal
    -> replay identical state
    -> content revision/diff/dry-run/activate
    -> continue play across content-lock boundary
```

Every user-visible subsystem should extend or strengthen this journey when it naturally belongs to it.

## 49.4 Milestone-to-TODO mapping

```text
v0.1 -> TODO Phase A -> P0/P1
v0.2 -> TODO Phase B -> timing/action stability
v0.3 -> TODO Phase C -> P2
v0.4 -> TODO Phase D -> richer data-driven P2
v0.5 -> TODO Phase E -> P3
v0.6 -> TODO Phase F -> P4
v0.7 -> TODO Phase G -> P5/P6
v0.8 -> TODO Phase H -> advanced controller variants without losing baseline gates
v0.9 -> TODO Phases I/J -> stable APIs + P7
v1.0 -> TODO Phase K + P8 release acceptance
```

A roadmap milestone cannot be represented as complete while its corresponding TODO phase or required playable gate is incomplete.

## 49.5 Local evidence integration

Each playable gate defines the canonical local profile(s) required to prove it. Only the designated local test agent executes those profiles for verification; remote agents design/implement the tests and interpret returned evidence.

Typical progression:

```text
P0/P1 -> smoke + pr
P2    -> playtest + replay + simulation
P3/P4 -> playtest + replay (+ targeted migration as needed)
P5/P6 -> full + simulation + replay
P7    -> migration + replay + full
P8    -> release
```

These names describe canonical **local** profiles; profile manifests decide the exact suites. Required blocked or unexpectedly skipped tests do not count as passes.

## 49.6 Playable-product definition of done

The project is not successful merely because endpoints exist. By the mature gates a real/reference client must be able to:

1. start/connect to the service;
2. create or load a campaign;
3. join a session and control a character;
4. discover visible state/legal actions from the server;
5. explore/interact/socialize/trade/craft as supported;
6. play complete encounters against autonomous NPCs;
7. receive rewards and progress a character/quest/world state;
8. survive timeout/disconnect/reconnect flows;
9. checkpoint and continue without destructive history edits;
10. inspect logs/recaps/journals;
11. replay to the same canonical state;
12. eventually author/publish and safely evolve content through the same platform.

The executable TODO exists to make that outcome difficult to lose sight of during implementation.

---

# 50. Local-only execution policy — no GitHub Actions

This section is authoritative and overrides any older generic use of the terms `CI`, `CI evidence`, or `local-agent/CI` elsewhere in repository history or documentation.

## 50.1 Sole execution authority

The designated **local test agent** is the only executor whose machine-produced results may satisfy repository execution gates.

Remote development/review agents may implement tests, inspect code, choose required local profiles, and interpret evidence, but they do not establish execution success unless they are operating as the designated local test agent in the actual local environment.

## 50.2 GitHub Actions prohibition

The repository must not:

- create or retain `.github/workflows/*.yml` or `.github/workflows/*.yaml`;
- use GitHub-hosted Actions runners;
- use self-hosted runners through GitHub Actions;
- depend on Actions checks for PR mergeability;
- publish or consume Actions artifacts as test evidence;
- schedule `nightly`, `full`, `release`, simulation, migration, replay, performance, or other suites through GitHub Actions;
- recommend GitHub Actions as a fallback when local execution is unavailable.

`.github/` may still contain non-Actions configuration such as Copilot repository instructions.

If a workflow file appears in a contribution, agents should remove it as part of repository policy enforcement unless the user explicitly reverses this decision.

## 50.3 Local execution model

Canonical profiles remain:

```text
smoke
pr
unit
integration
playtest
simulation
migration
replay
performance
full
nightly
release
```

All are commands/profiles for the local test runner. Their names do not imply remote CI scheduling.

The local agent may run them manually, through a user-controlled local scheduler, or through user-controlled local orchestration. The result is still local execution and must emit the same exact-commit `TestEvidenceBundle`.

## 50.4 GitHub role

GitHub remains useful for:

```text
source control
branches
pull requests
code review
issues
release metadata
```

It is not the project's test execution platform.

## 50.5 Merge and release proof

A PR or release may be implementation-ready on GitHub while still awaiting local evidence.

```text
implementation_ready
    repository changes prepared

execution_verified
    exact candidate revision tested by local agent
    required local profile passed
    evidence bundle reviewed

mergeable/releasable
    implementation_ready
    + execution_verified
    + normal review/policy requirements
```

The absence of GitHub Actions checks is intentional and must never be interpreted as missing project infrastructure.
