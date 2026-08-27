# Agent Instructions — rpg-engine-api

`PLAN.md` is the single authoritative architecture and implementation roadmap for this repository.

`docs/testing/HUMAN_PLAYTESTING.md` is the normative testing specification for proving that the systems in `PLAN.md` are actually playable end to end through public interfaces.

These instructions apply to Codex, OpenCode, Claude/Claude Code, Gemini, Pi/Oh My Pi, Prime, GitHub Copilot, and any other coding agent working in this repository. Tool-specific instruction files must defer to this file, `PLAN.md`, and the human-play testing specification rather than creating a second roadmap or testing architecture.

## Mandatory startup sequence

Before changing code or documentation:

1. Read `PLAN.md` completely enough to understand the architecture, non-negotiable rules, active milestone, and definition of done.
2. Read `docs/testing/HUMAN_PLAYTESTING.md` whenever the task changes a user-visible gameplay capability, public API/live protocol, persistence/replay behavior, timing behavior, visibility, or client workflow.
3. Inspect the current repository state and tests.
4. Identify the **earliest incomplete roadmap milestone** relevant to the requested work unless the user explicitly directs work on a later milestone.
5. Read that milestone's goal, deliverables, exit criteria, and any earlier architectural sections it depends on.
6. Identify which contracts the change touches: domain state, commands, events, projections, persistence, rules/content, timing, visibility, API, live protocol, or human-play scenarios.
7. Identify the player/DM/client journey that reaches the changed behavior and the scenario that should prove it programmatically.
8. Do not invent a competing architecture when `PLAN.md` already defines the boundary.
9. If a genuinely new architectural decision is required, update `PLAN.md` and add an ADR under `docs/decisions/` when the decision is non-trivial or difficult to reverse.

## Current implementation priority

Until v0.1 is complete, work from **`v0.1 — Deterministic Core + Shared Contracts`** in `PLAN.md`.

Recommended implementation sequence:

```text
PR 1  Project scaffold + architecture boundaries + playtest harness skeleton
PR 2  Stable IDs + shared domain primitives
PR 3  Commands + events + command receipts + error taxonomy
PR 4  Deterministic RNG streams + dice + seed-bundle support
PR 5  In-memory event store + replay + canonical state hashing
PR 6  PostgreSQL async event store + migrations + transactional outbox seam
PR 7  Snapshots + projection versions + rebuild seam
PR 8  Command bus + idempotency + optimistic concurrency
PR 9  Ruleset/content manifests + DefinitionRef/content-lock primitives
PR 10 Initial REST command/query contracts + black-box async playtest client
PR 11 Initial WebSocket event/resume protocol + live playtest client
PR 12 Testing Grounds fixture + v0.1 human-play/determinism integration suite
```

Do not skip foundational PRs merely because a later gameplay feature is more visible. Later milestones depend on v0.1's stable contracts.

## Human-play testing is part of implementation, not cleanup

Every user-visible gameplay capability must have a programmatic path that behaves like a real human-facing client.

Use both:

```text
white-box tests
    unit/component/domain tests
    may call internal Python interfaces

black-box human-play tests
    use public REST/WebSocket interfaces
    authenticate as player/DM/spectator personas
    never mutate domain/database state as a gameplay shortcut
```

A feature is not end-to-end complete merely because unit tests pass.

For a gameplay feature to count as playable, a programmatic persona must be able to:

1. discover the capability through public interfaces;
2. observe only authorized/visible information;
3. submit the same action/command a real client would submit;
4. receive the authoritative receipt/events/projections;
5. continue from the resulting state;
6. exercise retry/reconnect/timing behavior when relevant;
7. replay the resulting history to the same canonical state.

Do not teach the playtest client hidden rules. If the test client must duplicate server legality formulas to use a feature, improve capability/action discovery instead.

## Required human-play questions for every gameplay change

Before considering a feature complete, answer:

```text
How does a human reach this feature?
How does the public client discover it?
Which role/persona owns the action?
What exact public command/action is submitted?
What should that role see before and after?
What information must remain hidden?
What happens for an invalid choice?
What happens if the user waits too long?
What happens on retry or duplicate delivery?
What happens if the client disconnects/reconnects?
How is the exact session replayed deterministically?
Which playtest scenario proves all relevant behavior?
```

If these questions cannot be answered, the feature is not ready to be represented as complete roadmap work.

## v0.1 playtest harness contract

Build the reusable harness under a structure similar to:

```text
tests/playtest/
├── harness/
│   ├── client.py
│   ├── websocket.py
│   ├── persona.py
│   ├── clock.py
│   ├── scenario.py
│   ├── runner.py
│   ├── assertions.py
│   ├── coverage.py
│   └── artifacts.py
├── scenarios/
├── fixtures/
└── manifests/
```

The harness must support deterministic typed scenarios, personas, seed bundles, transcript/failure artifacts, feature tags, and eventually controllable test clocks.

The public gameplay path must be usable against in-process ASGI first and remain portable to a real local/containerized server later.

### Test clocks

Never use long real sleeps to test gameplay time.

Preserve the engine's separation of simulation time and wall-clock decision time using injectable clock abstractions. Tests may control injected clocks at the environment/fixture level while player personas still interact only through public gameplay interfaces.

Use exact boundary-time assertions for deadlines.

### Seed separation

Authoritative game RNG and scenario/human-behavior RNG must be independent.

Named game streams should remain conceptually separate, for example:

```text
dice
loot
encounters
world
procedural_generation
```

The playtest harness may have its own `scenario_behavior_seed`. A generated think-time delay must never perturb the next authoritative combat die result.

### Failure artifacts

A failed human-play scenario should capture enough information to reproduce it exactly:

```text
scenario_id
scenario schema version
git/engine revision
ruleset/content lock
seed bundle
persona definitions
executed steps
relevant REST receipts
relevant WebSocket events
projection snapshots
authoritative sequence range
canonical state hashes
failed assertion
```

Never store secrets/auth tokens in artifacts.

## v0.1 implementation contracts

### Stable identifiers

Use opaque durable IDs for runtime entities and namespaced stable keys for content definitions. Display names are never identifiers.

Required early concepts include:

```text
CampaignId
ActorId
CharacterId
CommandId
EventId
StreamId
DefinitionRef
ContentRef
```

Persist exact definition/content version references when replay correctness depends on them.

### Command envelope

Every state-changing request flows through a typed command envelope. At minimum preserve the semantics planned in `PLAN.md`:

```text
CommandEnvelope
    command_id
    command_type
    schema_version
    campaign_id
    actor_id | null
    expected_stream_version | null
    idempotency_key
    client_sequence | null
    payload
```

Authenticated principal/role data comes from server authentication context, never trusted command payload fields.

### Command receipt

Every command returns a stable receipt containing status, resulting event IDs/range when accepted, and a structured rejection when rejected/conflicted/already processed.

Retries with the same idempotency key must not duplicate authoritative events.

### Events

Domain events are append-only authoritative facts. Every event schema is versioned from its first implementation.

Plan for metadata including:

```text
event_id
campaign_id
stream_id
stream_version
global/campaign sequence
simulation_time
server_timestamp
actor_id
command_id
causation_id
correlation_id
content_lock_hash
event_type
schema_version
payload
```

Do not use operational logs as authoritative state.

### Aggregate and stream boundaries

Prefer explicit, narrow ownership rather than one mutable global object.

Initial stream candidates:

```text
campaign:{campaign_id}
actor:{actor_id}
character:{character_id}
encounter:{encounter_id}
timeline:{timeline_id}
inventory:{inventory_id}
quest:{quest_id}
```

Before introducing a new stream, define:

- what state it owns;
- which commands may mutate it;
- which events it emits;
- its concurrency boundary;
- snapshot/replay behavior;
- whether a transaction must atomically affect another stream.

Avoid cross-stream writes unless the application service explicitly coordinates them transactionally.

### Event store

The PostgreSQL design should support at minimum:

```text
event_streams
domain_events
command_receipts
snapshots
projection_versions
transactional_outbox
```

`domain_events` should support efficient lookup by stream/version, campaign sequence, event ID, command ID, event type, and campaign/time ranges as needed by planned queries.

Enforce uniqueness for event IDs, command idempotency, and stream versions at the database level where possible.

### Deterministic RNG

Do not use an uncontrolled process-global RNG for authoritative game results.

Use deterministic named streams so unrelated random operations do not perturb each other. Initial conceptual streams:

```text
dice
loot
encounters
world
procedural_generation
```

Each authoritative random result must be reproducible from pinned state/seed/stream position and should emit or be represented by an auditable domain event.

Weather generation, for example, must not silently change the next combat die result merely because it consumed randomness from one shared generator.

### Projections

Treat projections as rebuildable derived views, not authorities.

Early projection seams should anticipate:

```text
CampaignProjection
ActorProjection
CharacterSheetProjection
EncounterProjection
TimelineProjection
AvailableActionsProjection
GameLogProjection
```

Every projection needs a schema/build version and last processed authoritative sequence.

### REST envelope

Keep success/error/query responses consistent from the beginning. Responses should carry relevant request/correlation IDs and projection/version metadata rather than forcing clients to infer freshness.

Use opaque cursor pagination for unbounded collections.

### WebSocket protocol seam

Initial live-protocol design should support these semantic messages even if v0.1 only implements a subset:

```text
client.hello
client.subscribe
client.unsubscribe
client.ack
client.ping

server.ready
server.event
server.resync_required
server.error
server.pong
```

Plan for monotonic ordering, acknowledgement/resume, snapshot+delta synchronization, bounded backpressure, and server-side visibility filtering. Never silently drop authoritative events to a slow client.

### Rules/action expression boundary

Content definitions may use typed declarative structures such as `RequirementExpr`, `ChoiceGroup`, `Grant`, modifiers, effects, and action definitions.

Never execute arbitrary Python/code embedded in third-party content packs.

The long-term action/effect DSL must remain versioned, typed, validated, deterministic, and safe to inspect/replay.

## Reference SRD mapping discipline

Do not bulk-import SRD content before the engine schemas can represent and test it.

Track categories conceptually as:

```text
Category       Schema ready   Data mapped   Conformance tests   Human-play scenarios
Abilities
Skills
Species
Backgrounds
Classes
Subclasses
Feats
Actions
Conditions
Equipment
Spells/Abilities
Creatures
```

Only redistribute content covered by an appropriate license and preserve required attribution/source metadata.

When a content category becomes playable, add at least one representative human-play scenario before expanding the catalog broadly.

## Reference integration campaign

Use the deliberately small **Testing Grounds** campaign as the canonical human-play/integration fixture instead of relying only on isolated unit examples.

Target shape:

```text
Testing Grounds
├── Town
│   ├── Tavern
│   ├── Merchant
│   ├── Blacksmith
│   └── Gate
└── Forest
    ├── Road
    ├── Hidden Path
    ├── Goblin Camp
    └── Ruins
```

Eventually include a few NPCs, quests, one vendor, one crafting recipe, a hidden/discovery case, dialogue, faction state, scheduled world event, normal encounter, timed encounter, and later ATB/real-time cases. Add pieces only when the corresponding milestone exists.

Maintain one long-form campaign journey that grows with the engine so a test persona can actually create a character, enter the world, explore, interact, fight, progress, reconnect, and replay the campaign instead of only running disconnected subsystem demos.

## Coverage manifest

Maintain a machine-readable mapping from planned/implemented features to tests.

For each gameplay feature, track as applicable:

```text
feature_id
milestone
implementation_status
unit tests
integration tests
human-play scenario IDs
timing modes
roles/personas
spatial adapters
ruleset/content refs
negative cases
replay cases
```

A milestone cannot be declared complete while an implemented user-visible feature lacks a public human-play scenario unless the feature is explicitly internal-only.

## Python and async requirements

- Target Python 3.12+.
- Use modern typing throughout.
- Use FastAPI/Pydantic v2 conventions appropriate to current versions.
- Use SQLAlchemy 2.x async APIs and async-capable PostgreSQL drivers.
- Never perform blocking DB/network/file operations directly on the async event loop.
- Never use `time.sleep()` for game progression, decision-window testing, or inside async request handling.
- Avoid ordinary `threading.Lock` in async request paths; use async-aware synchronization when coordination is necessary.
- Isolate CPU-heavy work such as large replay batches or pathfinding from the event loop through bounded worker execution when needed.
- Use async-safe multi-client playtest clients and structured concurrency.
- Prefer explicit transactions and deterministic conflict handling.

## Architecture boundaries

Keep these responsibilities distinct:

```text
api/             transport/auth/schema adaptation
application/     command/query orchestration and transaction boundaries
domain/          deterministic business/game state and invariants
rules/           typed rules evaluation interfaces/runtime
rulesets/        versioned licensed/custom content and mechanics
persistence/     event store, snapshots, projections, outbox
infrastructure/  concrete external integrations and process concerns
tests/playtest/  black-box personas/scenarios using public interfaces
```

Domain code should not import FastAPI, SQLAlchemy ORM sessions, WebSocket connections, or other transport/infrastructure concerns.

The playtest harness must not become a second rules engine.

## Test requirements

Every completed change should add the narrowest meaningful tests and preserve the milestone's broader invariants.

For v0.1, prioritize:

- typed domain unit tests;
- deterministic RNG tests;
- identical-command-stream replay tests;
- canonical state hash tests;
- idempotent retry tests;
- stale stream-version conflict tests;
- event schema/version tests;
- async persistence integration tests when PostgreSQL is introduced;
- projection rebuild tests when projections appear;
- API contract tests when endpoints appear;
- black-box public API playtest smoke scenarios as soon as the public command path exists;
- WebSocket subscribe/resume scenarios as soon as the live protocol exists;
- failure transcript/seed capture for human-play tests.

Use ASGI-native async testing for async API paths rather than introducing blocking test clients into async tests.

Whenever timing is involved, use controllable clocks rather than sleeping through real decision/game durations.

## Bug regression rule

Every player-visible bug fix should add the narrowest durable regression test.

If a human could observe the bug through normal gameplay, add or extend a human-play scenario unless an existing scenario already proves the corrected behavior.

A bug fix is incomplete when the same player-visible failure can silently return without a regression signal.

## Required checks before declaring work complete

1. Re-read the active milestone exit criteria in `PLAN.md`.
2. Re-read the relevant human-play requirements in `docs/testing/HUMAN_PLAYTESTING.md`.
3. Run all relevant unit/integration/determinism/replay tests.
4. Run or add the relevant black-box human-play scenarios for user-visible behavior.
5. Verify no blocking operation or real-time sleep was introduced into async/timing tests.
6. Verify state changes occur through commands/events rather than direct client mutation.
7. Verify the playtest client did not duplicate hidden server rules.
8. Verify new public schemas are versioned/documented.
9. Verify visibility/security boundaries when new data becomes client-visible.
10. Verify retry, timeout, and reconnect behavior where relevant.
11. Verify replay/content provenance when rules/content definitions are involved.
12. Update the coverage manifest for changed gameplay features.
13. Update `PLAN.md` only when architecture/roadmap decisions changed or milestone checkboxes are objectively satisfied.
14. Do not claim a milestone or PR slice complete when its public play path and exit criteria are not demonstrated.

## Preventing project drift

Do not:

- create a second roadmap that competes with `PLAN.md`;
- create a second testing architecture that competes with `docs/testing/HUMAN_PLAYTESTING.md`;
- implement post-v1.0 distributed/MMO work during an earlier milestone unless explicitly requested;
- hard-code one client, renderer, map type, or combat timing mode into core domain logic;
- make Redis or in-memory state the only authoritative persistence layer;
- put proprietary non-licensed D&D text/content into the repository;
- let AI/LLM output mutate state without typed command/rules validation;
- bypass event history with direct database updates for gameplay changes;
- treat projections or logs as the source of truth;
- introduce client-side hidden rules to make a feature or test work;
- mark a gameplay feature complete without a programmatic public-interface play path;
- use sleeps to make timed-turn tests pass;
- hide flaky scenarios instead of preserving their seed/artifact and fixing the cause.

When a request conflicts with a non-negotiable architectural rule in `PLAN.md`, preserve the architectural invariant and implement the requested behavior through the planned extension point.