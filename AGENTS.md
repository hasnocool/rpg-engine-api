# Agent Instructions — rpg-engine-api

`PLAN.md` is the single authoritative architecture and implementation roadmap for this repository.

These instructions apply to Codex, OpenCode, Claude/Claude Code, Gemini, Pi/Oh My Pi, Prime, GitHub Copilot, and any other coding agent working in this repository. Tool-specific instruction files should defer to this file and `PLAN.md` rather than creating a second roadmap.

## Mandatory startup sequence

Before changing code or documentation:

1. Read `PLAN.md` completely enough to understand the architecture, non-negotiable rules, active milestone, and definition of done.
2. Inspect the current repository state and tests.
3. Identify the **earliest incomplete roadmap milestone** relevant to the requested work unless the user explicitly directs work on a later milestone.
4. Read that milestone's goal, deliverables, exit criteria, and any earlier architectural sections it depends on.
5. State internally which contracts the change touches: domain state, commands, events, projections, persistence, rules/content, timing, visibility, API, or live protocol.
6. Do not invent a competing architecture when `PLAN.md` already defines the boundary.
7. If a genuinely new architectural decision is required, update `PLAN.md` and add an ADR under `docs/decisions/` when the decision is non-trivial or difficult to reverse.

## Current implementation priority

Until v0.1 is complete, work from **`v0.1 — Deterministic Core + Shared Contracts`** in `PLAN.md`.

Recommended implementation sequence:

```text
PR 1  Project scaffold + architecture boundaries
PR 2  Stable IDs + shared domain primitives
PR 3  Commands + events + command receipts + error taxonomy
PR 4  Deterministic RNG streams + dice
PR 5  In-memory event store + replay + canonical state hashing
PR 6  PostgreSQL async event store + migrations + transactional outbox seam
PR 7  Snapshots + projection versions + rebuild seam
PR 8  Command bus + idempotency + optimistic concurrency
PR 9  Ruleset/content manifests + DefinitionRef/content-lock primitives
PR 10 Initial REST command/query contracts
PR 11 Initial WebSocket event/resume protocol seam
PR 12 Reference campaign fixture + deterministic integration/golden tests
```

Do not skip foundational PRs merely because a later gameplay feature is more visible. Later milestones depend on v0.1's stable contracts.

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
Category       Schema ready   Data mapped   Conformance tests
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

## Reference integration campaign

Use a deliberately small reference campaign as the integration fixture instead of relying only on isolated unit examples.

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

Eventually include a few NPCs, quests, one vendor, one crafting recipe, a hidden/discovery case, dialogue, faction state, scheduled world event, normal encounter, and timed encounter. Add pieces only when the corresponding milestone exists.

## Python and async requirements

- Target Python 3.12+.
- Use modern typing throughout.
- Use FastAPI/Pydantic v2 conventions appropriate to current versions.
- Use SQLAlchemy 2.x async APIs and async-capable PostgreSQL drivers.
- Never perform blocking DB/network/file operations directly on the async event loop.
- Never use `time.sleep()` for game progression or inside async request handling.
- Avoid ordinary `threading.Lock` in async request paths; use async-aware synchronization when coordination is necessary.
- Isolate CPU-heavy work such as large replay batches or pathfinding from the event loop through bounded worker execution when needed.
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
```

Domain code should not import FastAPI, SQLAlchemy ORM sessions, WebSocket connections, or other transport/infrastructure concerns.

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
- API contract tests when endpoints appear.

Use ASGI-native async testing for async API paths rather than introducing blocking test clients into async tests.

## Required checks before declaring work complete

1. Re-read the active milestone exit criteria in `PLAN.md`.
2. Run all relevant unit/integration/determinism/replay tests.
3. Verify no blocking operation was introduced into async paths.
4. Verify state changes occur through commands/events rather than direct client mutation.
5. Verify new public schemas are versioned/documented.
6. Verify visibility/security boundaries when new data becomes client-visible.
7. Verify replay/content provenance when rules/content definitions are involved.
8. Update `PLAN.md` only when architecture/roadmap decisions changed or milestone checkboxes are objectively satisfied.
9. Do not claim a milestone or PR slice complete when its exit criteria are not demonstrated.

## Preventing project drift

Do not:

- create a second roadmap that competes with `PLAN.md`;
- implement post-v1.0 distributed/MMO work during an earlier milestone unless explicitly requested;
- hard-code one client, renderer, map type, or combat timing mode into core domain logic;
- make Redis or in-memory state the only authoritative persistence layer;
- put proprietary non-licensed D&D text/content into the repository;
- let AI/LLM output mutate state without typed command/rules validation;
- bypass event history with direct database updates for gameplay changes;
- treat projections or logs as the source of truth;
- introduce client-side hidden rules to make a feature work.

When a request conflicts with a non-negotiable architectural rule in `PLAN.md`, preserve the architectural invariant and implement the requested behavior through the planned extension point instead.