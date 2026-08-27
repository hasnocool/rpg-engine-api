# RPG Engine API — Architecture and Implementation Plan

## Status

**Project:** `rpg-engine-api`  
**Target runtime:** Python 3.12+  
**Primary API:** FastAPI + REST + WebSockets  
**Architecture:** Headless, deterministic, event-driven RPG simulation engine  
**Primary compatible rules package:** SRD 5.2.1-based ruleset  
**Goal:** Allow any client—Godot, Unity, browser, TUI, SSH, mobile, Discord-style interface, AI narrator, or custom service—to build a D&D-style RPG on top of one authoritative API.

---

## 1. Vision

`rpg-engine-api` should be the authoritative game simulation layer rather than a client-specific combat service.

The API owns:

- campaign state;
- world state;
- game time;
- actors and characters;
- NPCs and creatures;
- encounters;
- initiative and readiness;
- actions and reactions;
- dice and deterministic randomness;
- movement and spatial authority;
- spells, abilities, effects, and conditions;
- inventory and equipment;
- quests and objectives;
- dialogue state;
- factions and reputation;
- character progression;
- event history;
- save/load/replay;
- AI-controlled actor permissions;
- multiplayer authority;
- client capability discovery.

Clients should primarily:

1. query state;
2. query available actions;
3. submit commands;
4. subscribe to events;
5. render the resulting authoritative state.

A client must never need to independently reimplement the core rules in order to remain synchronized with the server.

---

## 2. Rules and licensing boundary

The project should use **System Reference Document 5.2.1** as its reusable compatibility foundation.

Wizards of the Coast publishes SRD 5.2.1 under **Creative Commons Attribution 4.0 International (CC-BY-4.0)** and states that it is intended to provide a foundation for third-party products.

Official references:

- SRD 5.2.1: https://www.dndbeyond.com/srd
- Creator FAQ: https://www.dndbeyond.com/creator-faq
- D&D Beyond Playing the Game reference: https://www.dndbeyond.com/sources/dnd/br-2024/playing-the-game
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/

### Important boundary

The D&D Beyond Basic Rules may be useful as an online reference for understanding current game behavior, but the project must not copy non-SRD D&D Beyond content into the repository merely because it is publicly readable.

Only content clearly covered by an appropriate license should be redistributed with the engine.

### Implementation strategy

Do **not** hard-code the engine around trademarks, setting-specific lore, or proprietary content.

Use a generic core engine with installable rulesets:

```text
rpg-engine-api/
    core engine
        +
    rulesets/
        srd_5_2_1/
        custom_fantasy/
        campaign_specific/
```

The core should know how to evaluate rules, but the SRD-specific mechanics and data should live in a rules package.

---

## 3. Core architectural principle: time is first-class

Traditional round-based combat must be only one scheduling policy.

The engine should understand:

- simulation time;
- wall-clock decision time;
- readiness;
- deadlines;
- action duration;
- cooldowns;
- delays;
- interrupts;
- reaction windows;
- scheduled world events;
- periodic effects;
- actor availability.

It should **not** fundamentally assume that every game uses fixed turns.

This makes it possible for the same rules engine to support:

```text
turn_based

timed_turn_based

active_time

real_time_with_pause

real_time

hybrid
```

---

## 4. Required timing modes

### 4.1 `turn_based`

Traditional initiative-driven combat.

Characteristics:

- participants roll initiative;
- actors take turns in initiative order;
- a round models approximately six seconds of game-world time;
- rules determine movement, actions, bonus actions, reactions, and other resources;
- no real-world deadline is required.

### 4.2 `timed_turn_based`

Traditional initiative plus a configurable real-world action deadline.

Example:

```text
simulation round duration: ~6 game-world seconds
player decision window: 15 wall-clock seconds
timeout policy: forfeit_turn
```

If the player fails to act before the deadline, the engine advances according to the timeout policy.

Required timeout policies:

```text
forfeit_turn
auto_dodge
auto_defend
repeat_previous_action
ai_control
pause_game
dm_decides
```

`forfeit_turn` should be the initial default for the requested timed-combat mode.

### 4.3 `active_time`

Final Fantasy-style active-time combat.

Each actor has a readiness meter or computed `ready_at` timestamp.

Readiness may be influenced by ruleset-defined values such as:

- initiative;
- Dexterity or equivalent attribute;
- conditions;
- effects;
- equipment;
- class features;
- temporary modifiers.

When an actor becomes ready:

```text
ActorReady
    -> ActionWindowOpened
    -> command received OR deadline expires
    -> action resolves OR timeout policy runs
    -> readiness resets/recalculates
```

Other actors continue progressing while a player decides unless the encounter policy explicitly pauses readiness.

### 4.4 `real_time_with_pause`

Continuous simulation with optional authoritative pausing.

Useful for:

- party RPGs;
- tactical clients;
- accessibility;
- AI-assisted play;
- single-player games.

### 4.5 `real_time`

World-of-Warcraft-style continuous combat semantics.

Actors may have:

- global cooldowns;
- ability cooldowns;
- attack timers;
- cast times;
- movement states;
- resource regeneration;
- interrupts;
- periodic effects;
- reaction windows.

The server should remain event-driven rather than relying on a mandatory 30/60 Hz game loop.

### 4.6 `hybrid`

The scheduler supports mixed timing policies.

Examples:

```text
players: active_time
boss: real_time
summons: automatic real_time
world: real_time
dialogue: turn_based
```

The scheduler must be able to compose these policies without creating separate combat engines.

---

## 5. Two independent clocks

The engine must distinguish **simulation time** from **wall-clock decision time**.

### Simulation time

Represents time inside the fictional world.

Examples:

- combat rounds;
- spell duration;
- travel time;
- NPC schedules;
- weather events;
- rests;
- condition ticks;
- crafting;
- quest deadlines.

### Wall-clock decision time

Represents how long a connected user has to make a choice.

Examples:

- 15 seconds to choose an action;
- 5 seconds to react;
- 30 seconds to answer dialogue;
- reconnect grace period.

Never use wall-clock passage as the authoritative source for deterministic simulation state.

---

## 6. Event-driven scheduler

The scheduler should be one of the central systems in the engine.

Conceptual event types:

```text
ActorReady
TurnStarted
TurnEnded
ActionWindowOpened
ActionWindowExpired
ActionStarted
ActionCompleted
ActionInterrupted
ReactionWindowOpened
ReactionWindowClosed
MovementStarted
MovementCompleted
SpellCastStarted
SpellCastCompleted
CooldownExpired
ConditionTicked
ConditionExpired
WorldEventTriggered
NpcScheduleTriggered
EncounterStarted
EncounterEnded
```

Internally, scheduled work should be ordered primarily by simulation timestamp and a deterministic tie-break key.

Suggested conceptual structure:

```text
ScheduledEvent
    event_id
    campaign_id
    simulation_time
    priority
    sequence
    actor_id
    event_type
    payload
```

The scheduler must produce deterministic results when given the same initial state, command stream, ruleset version, and RNG seed.

---

## 7. Commands vs. events

Clients submit **commands**.

The engine emits **events**.

### Example commands

```text
Attack
CastSpell
Move
Dash
Dodge
Disengage
Help
Hide
Influence
Ready
Search
Study
UseItem
EquipItem
Interact
Talk
Rest
EndTurn
AcceptQuest
Travel
CreateCharacter
LevelUp
```

### Example events

```text
CommandAccepted
CommandRejected
AttackDeclared
AttackRolled
AttackHit
AttackMissed
DamageRolled
DamageApplied
HealingApplied
ActorMoved
SpellCast
EffectApplied
EffectExpired
ConditionApplied
ConditionRemoved
TurnStarted
TurnTimedOut
RoundStarted
RoundEnded
ActorDowned
ActorDefeated
ItemAcquired
QuestUpdated
LocationDiscovered
```

### Rule

Clients must not directly mutate authoritative state.

Bad:

```http
PATCH /actors/{id}
{
  "hit_points": 9999
}
```

Good:

```http
POST /commands
{
  "type": "cast_spell",
  "actor_id": "actor-123",
  "target_ids": ["monster-17"],
  "spell_id": "spell-example"
}
```

Processing path:

```text
command
    -> authentication
    -> authorization
    -> schema validation
    -> timing validation
    -> rules validation
    -> deterministic resolution
    -> domain events
    -> authoritative state update
    -> persistence commit
    -> event publication
```

---

## 8. Deterministic simulation

Determinism should be implemented from the first milestone.

The server controls randomness.

Each campaign/session receives deterministic RNG state.

Dice should generate auditable events such as:

```json
{
  "type": "DiceRolled",
  "expression": "1d20+5",
  "rolls": [14],
  "modifier": 5,
  "total": 19,
  "purpose": "attack",
  "rng_sequence": 381
}
```

### Benefits

- replay;
- debugging;
- crash recovery;
- desync detection;
- save/load;
- spectator playback;
- deterministic tests;
- campaign branching;
- rewind/debug tooling;
- AI training datasets;
- combat analytics.

---

## 9. Event sourcing and projections

The long-term authoritative model should support append-only domain events.

```text
commands
    -> domain events
    -> event store
    -> projections
```

Useful projections include:

- current campaign state;
- actor state;
- encounter state;
- inventory state;
- quest state;
- map occupancy;
- current timeline;
- available actions;
- player-visible state.

Snapshots should periodically compact replay cost without replacing the source event history.

### Required metadata

Every persisted domain event should eventually include:

```text
event_id
campaign_id
stream_id
stream_version
sequence
simulation_time
server_timestamp
actor_id
command_id
causation_id
correlation_id
ruleset_id
ruleset_version
payload_schema_version
payload
```

---

## 10. Rules runtime

The core engine should expose a typed rules-runtime interface rather than embedding SRD behavior throughout domain objects.

Conceptual responsibilities:

```text
RulesRuntime
    validate_command(...)
    resolve_command(...)
    calculate_available_actions(...)
    calculate_targets(...)
    calculate_modifiers(...)
    calculate_movement(...)
    evaluate_trigger(...)
    resolve_reaction(...)
    translate_timing_mode(...)
```

The rules runtime owns mechanics.

The scheduler owns time.

The spatial layer owns geometry/relationships.

The persistence layer owns durable state.

The API layer owns transport.

These boundaries should remain strict.

---

## 11. Ruleset packages

Rulesets should be versioned packages.

Suggested interface:

```text
RulesetManifest
    id
    name
    version
    schema_version
    license
    attribution
    capabilities
    content_version
```

Capabilities may include:

```text
initiative
turn_economy
active_time_translation
real_time_translation
spellcasting
conditions
character_creation
leveling
multiclassing
inventory
encumbrance
spatial_rules
rests
```

The first complete package should be:

```text
rulesets/srd_5_2_1/
```

---

## 12. Effect pipeline

Spells, conditions, abilities, items, environmental effects, buffs, debuffs, and class features should share a generalized effect system.

Conceptual effect definition:

```text
Effect
    source
    targets
    trigger
    requirements
    modifiers
    operations
    duration
    stacking_policy
    expiration
```

### Trigger examples

```text
on_apply
on_remove
on_turn_start
on_turn_end
on_action_declared
on_attack_roll
on_hit
on_miss
on_damage
on_damage_received
on_move
on_enter_area
on_leave_area
on_spell_cast
on_reaction_window
on_time_elapsed
```

### Modifier examples

```text
armor_class
attack_roll
saving_throw
ability_check
movement_speed
damage
healing
resource_cost
cooldown
action_duration
readiness_rate
```

The engine should avoid implementing individual spells as arbitrary Python functions wherever a declarative effect can represent them.

---

## 13. Reactions and interrupts

Reactions should be modeled as interruptible event windows.

```text
triggering event
    -> eligible reactions calculated
    -> ReactionWindowOpened
    -> commands accepted until policy closes window
    -> reaction resolves
    -> triggering resolution continues/cancels/changes
```

Timing policies may map reaction windows differently:

```text
turn_based: rules/DM controlled

timed_turn_based: configurable wall-clock deadline

active_time: short action window

real_time: short interrupt window or automated policy
```

Reaction handling must be deterministic even when multiple eligible actors respond concurrently.

---

## 14. Action economy abstraction

The scheduler must not hard-code an action/bonus-action structure.

Instead, the ruleset exposes action resources and capabilities.

For a traditional turn-based ruleset, an actor may have resources similar to:

```text
movement
action
bonus_action
reaction
free_interaction
```

A real-time translation may express equivalent abilities as:

```text
action duration
global cooldown
ability cooldown
cast duration
movement velocity
resource cost
```

This permits one content model to support multiple scheduling styles.

---

## 15. Spatial authority

The engine must not require one map representation.

Define a `SpatialAdapter` interface with implementations such as:

```text
TheaterOfMindSpace
GraphSpace
SquareGridSpace
HexSpace
Continuous2DSpace
Continuous3DSpace
```

Required operations should eventually include:

```text
distance(a, b)
can_see(a, b)
can_reach(a, b)
path(a, b)
cover(a, b)
occupants(position)
can_occupy(actor, position)
terrain_cost(position)
area_query(shape)
```

This allows:

- text adventures;
- tactical 2D clients;
- Godot 2D;
- Godot 3D;
- Unity;
- browser maps;
- graph-based theater-of-the-mind worlds.

---

## 16. Actor model

Players, NPCs, monsters, pets, companions, summons, and AI actors should share a common actor foundation.

Prefer composition over deep inheritance.

```text
Actor
    Identity
    Controller
    Attributes
    Resources
    Movement
    Perception
    Inventory
    Equipment
    Features
    Spellcasting
    Conditions
    Effects
    Progression
    FactionMembership
    Reputation
    Knowledge
    Location
```

Controller types may include:

```text
human
ai
scripted
remote_service
system
```

The actor model should not create separate incompatible state machines for player characters versus NPCs.

---

## 17. Character creation and progression

The engine should eventually provide a complete character-creation API.

Capabilities:

- choose ruleset;
- choose species/ancestry equivalent from licensed content;
- choose class;
- choose background;
- ability-score generation;
- skill choices;
- languages;
- equipment selection;
- spells;
- features;
- appearance/description metadata;
- custom biography;
- validation;
- advancement;
- leveling;
- feature choices;
- multiclassing when supported by ruleset.

Character creation should use the same command/event architecture as gameplay so every change is auditable and recoverable.

---

## 18. Living-world simulation

The same scheduler should drive non-combat time.

Examples:

```text
08:00 shop opens
09:15 party departs
10:00 weather front arrives
12:30 effect expires
14:00 NPC reaches destination
18:00 shop closes
23:00 guard shift changes
02:00 encounter opportunity occurs
```

World systems should include:

- calendar;
- weather;
- travel;
- NPC schedules;
- location state;
- settlements;
- factions;
- reputation;
- quests;
- environmental effects;
- rest and recovery;
- scheduled encounters;
- persistent world events.

Combat should ultimately be one high-intensity state of the same world rather than an unrelated simulation engine.

---

## 19. Quest engine

Quests should be state machines driven by domain events rather than client-managed checklists.

Example objective predicates:

```text
visit_location
acquire_item
defeat_actor
defeat_actor_type
talk_to_actor
protect_actor
survive_until
learn_fact
reach_reputation
trigger_world_event
custom_rule_predicate
```

Quest events:

```text
QuestOffered
QuestAccepted
ObjectiveProgressed
ObjectiveCompleted
QuestCompleted
QuestFailed
QuestExpired
```

---

## 20. Dialogue and social interaction

Dialogue state should be server-authoritative.

The system should support:

- dialogue nodes;
- conditional choices;
- ability checks;
- reputation requirements;
- faction requirements;
- inventory requirements;
- quest state;
- discovered knowledge;
- AI-generated dialogue proposals;
- deterministic consequences.

AI may generate dialogue text or suggest intent, but rule consequences must still pass through server commands.

---

## 21. AI integration boundary

LLMs and agent systems must not directly mutate state.

Preferred flow:

```text
game state
    -> AI context
    -> AI proposes intent
    -> intent translator
    -> typed command
    -> rules validation
    -> deterministic resolution
    -> events
```

Example AI intent:

```text
"Move behind the wagon, hide, and attack the mage."
```

Translated commands might become:

```text
Move
Hide
Attack
```

The engine determines what is legal and what succeeds.

This permits AI-controlled NPCs and AI Dungeon Masters without making the LLM authoritative.

---

## 22. Dungeon Master authority

DM capabilities should also be explicit commands rather than arbitrary database mutation.

Potential privileged commands:

```text
CreateEncounter
SpawnActor
DespawnActor
RevealLocation
RevealKnowledge
SetWeather
ScheduleWorldEvent
StartDialogue
AdvanceQuest
GrantItem
ApplyEffect
PauseTimeline
ResumeTimeline
OverrideRuleResolution
```

DM overrides should produce auditable events.

---

## 23. API domains

Initial API organization should converge toward:

```text
/api/v1/campaigns
/api/v1/worlds
/api/v1/regions
/api/v1/locations
/api/v1/maps
/api/v1/actors
/api/v1/characters
/api/v1/encounters
/api/v1/timelines
/api/v1/actions
/api/v1/commands
/api/v1/events
/api/v1/effects
/api/v1/conditions
/api/v1/items
/api/v1/inventories
/api/v1/spells
/api/v1/features
/api/v1/quests
/api/v1/dialogues
/api/v1/factions
/api/v1/rulesets
/api/v1/sessions
```

Avoid creating CRUD endpoints for authoritative mutable state when the operation should instead be a command.

---

## 24. Capability discovery

A major design goal is making thin generic clients possible.

Clients should be able to request current available actions:

```http
GET /api/v1/actors/{actor_id}/available-actions
```

Conceptual response:

```json
{
  "actor_id": "fighter-1",
  "simulation_time": 128.4,
  "decision_deadline": "...",
  "actions": [
    {
      "type": "attack",
      "targets": ["goblin-1", "goblin-2"]
    },
    {
      "type": "move",
      "max_distance": 30
    },
    {
      "type": "dodge"
    }
  ]
}
```

The server should also expose ruleset metadata so a client can generate interfaces dynamically.

---

## 25. WebSocket event stream

REST handles commands and queries.

WebSockets handle live game updates.

Suggested connection:

```text
/api/v1/ws/campaigns/{campaign_id}
```

Potential subscription channels:

```text
campaign.*
world.*
encounter.*
actor.*
timeline.*
quest.*
dialogue.*
system.*
```

Example events:

```text
ActorMoved
ActorReady
TurnStarted
ActionWindowOpened
ActionWindowExpiring
TurnTimedOut
AttackResolved
SpellCast
EffectApplied
CreatureDefeated
QuestUpdated
WorldTimeAdvanced
```

Clients should receive monotonic event sequence numbers so they can detect missed data and resynchronize.

---

## 26. Concurrency model

The API must be safe under concurrent multiplayer command submission.

Requirements:

- asynchronous HTTP/WebSocket paths;
- no blocking DB/network work on the event loop;
- optimistic concurrency or stream-version checks;
- command idempotency;
- deterministic conflict handling;
- per-stream or per-campaign serialization where required;
- no ordinary `threading.Lock` inside async request code;
- use async-aware coordination primitives;
- isolate CPU-heavy simulation work when necessary;
- transactional event append + projection updates where feasible.

A command should include an idempotency identifier so retries do not duplicate actions.

---

## 27. Persistence

Recommended initial stack:

```text
PostgreSQL
SQLAlchemy 2.x async
asyncpg
Alembic
```

Potential tables:

```text
campaigns
ruleset_installations
event_streams
domain_events
snapshots
actors
encounters
timelines
sessions
projection_versions
command_receipts
```

Normalized gameplay projections may be added as required for fast querying, but the event history should remain capable of reconstructing authoritative state.

Redis may later be used for ephemeral coordination/pub-sub/cache workloads, but it should not become the sole authoritative game-state store.

---

## 28. Authentication and authorization

Plan for:

```text
User
CampaignMembership
Role
ActorControlGrant
Session
```

Roles may include:

```text
owner
dungeon_master
player
spectator
service
```

Authorization must verify which actors and privileged commands a session may control.

---

## 29. Observability

Instrument the engine from early milestones.

Metrics should eventually include:

```text
commands/sec
command latency
command rejection rate
events/sec
scheduled events processed/sec
scheduler lag
projection lag
websocket connections
websocket event lag
DB transaction latency
snapshot duration
replay throughput
active campaigns
active encounters
```

Use structured logs with:

```text
campaign_id
actor_id
command_id
event_id
correlation_id
stream_version
simulation_time
```

---

## 30. Testing strategy

### Unit tests

Test deterministic domain behavior without HTTP or database dependencies.

### Rules conformance tests

For each implemented SRD mechanic:

```text
Given
When
Then
```

Use table-driven test cases.

### Determinism tests

Run identical command streams twice and assert identical event/state hashes.

### Replay tests

Build state normally, rebuild from events, and compare canonical hashes.

### Timing-mode tests

Every major combat scenario should eventually run through:

```text
turn_based
timed_turn_based
active_time
real_time_with_pause
real_time
```

where the ruleset supports the mode.

### Property-based tests

Use generated scenarios for:

- dice bounds;
- resource accounting;
- stream versions;
- scheduler ordering;
- effect expiration;
- invariant checking.

### Multiplayer race tests

Simulate concurrent commands against the same encounter and assert exactly one deterministic resolution when commands conflict.

### API integration tests

Use ASGI-native asynchronous testing rather than blocking test clients inside async tests.

---

## 31. Proposed repository structure

```text
rpg-engine-api/
├── src/
│   └── rpg_engine_api/
│       ├── api/
│       │   ├── rest/
│       │   └── websocket/
│       ├── application/
│       │   ├── commands/
│       │   ├── queries/
│       │   └── services/
│       ├── domain/
│       │   ├── actors/
│       │   ├── combat/
│       │   ├── timeline/
│       │   ├── effects/
│       │   ├── spatial/
│       │   ├── inventory/
│       │   ├── progression/
│       │   ├── quests/
│       │   ├── dialogue/
│       │   ├── world/
│       │   └── events/
│       ├── rules/
│       │   ├── runtime/
│       │   ├── interfaces/
│       │   └── registry/
│       ├── rulesets/
│       │   └── srd_5_2_1/
│       ├── persistence/
│       │   ├── event_store/
│       │   ├── repositories/
│       │   └── projections/
│       └── infrastructure/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── rules/
│   ├── determinism/
│   ├── replay/
│   └── simulation/
├── examples/
│   ├── terminal_client/
│   ├── websocket_client/
│   └── sample_campaign/
├── docs/
│   ├── architecture/
│   ├── api/
│   ├── rules/
│   └── decisions/
├── migrations/
├── PLAN.md
├── README.md
└── pyproject.toml
```

---

# Implementation Roadmap

## v0.1 — Deterministic Core

### Goal

Create the smallest authoritative engine capable of accepting typed commands and producing reproducible events.

### Deliverables

- [ ] Python 3.12+ project scaffold.
- [ ] FastAPI application factory.
- [ ] Pydantic v2 command/event schemas.
- [ ] domain identifier types.
- [ ] campaign aggregate.
- [ ] actor aggregate foundation.
- [ ] command bus.
- [ ] event dispatcher.
- [ ] deterministic RNG service.
- [ ] dice-expression abstraction.
- [ ] append-only in-memory event store for tests.
- [ ] PostgreSQL event-store implementation.
- [ ] stream versioning.
- [ ] command idempotency.
- [ ] snapshots interface.
- [ ] canonical state hashing.
- [ ] deterministic replay tests.
- [ ] health/readiness endpoints.

### Exit criteria

The same initial state + RNG seed + command stream produces byte-equivalent canonical event/state results.

---

## v0.2 — First-Class Time

### Goal

Make one scheduler authoritative for combat and world events.

### Deliverables

- [ ] `SimulationClock`.
- [ ] timeline aggregate.
- [ ] scheduled-event priority queue abstraction.
- [ ] deterministic tie-breaking.
- [ ] pause/resume.
- [ ] game-time advancement.
- [ ] delayed events.
- [ ] periodic events.
- [ ] cancellation/rescheduling.
- [ ] actor readiness state.
- [ ] turn/round policy interface.
- [ ] scheduled world events.
- [ ] clock replay tests.

### Exit criteria

A campaign can deterministically advance through scheduled actor, combat, condition, and world events without using wall-clock sleeps.

---

## v0.2.1 — Multi-Mode Timing

### Goal

Implement all requested combat timing modes over the same scheduler.

### Deliverables

- [ ] `turn_based`.
- [ ] `timed_turn_based`.
- [ ] `active_time`.
- [ ] `real_time_with_pause`.
- [ ] `real_time`.
- [ ] `hybrid` policy composition.
- [ ] wall-clock action deadlines.
- [ ] `ActionWindowOpened`.
- [ ] `ActionWindowExpired`.
- [ ] timeout policies.
- [ ] `forfeit_turn` policy.
- [ ] readiness-rate calculations.
- [ ] cooldown scheduling.
- [ ] cast-time scheduling.
- [ ] reconnect/grace policy interfaces.
- [ ] timing-mode simulation tests.

### Exit criteria

One sample encounter can be executed under every supported timing mode without replacing the underlying combat/rules engine.

---

## v0.3 — SRD Combat Runtime

### Goal

Implement the licensed combat foundation through a dedicated SRD 5.2.1 rules package.

### Deliverables

- [ ] ruleset manifest and registry.
- [ ] SRD attribution/licensing documentation.
- [ ] ability/check primitives.
- [ ] initiative.
- [ ] movement resources.
- [ ] action resources.
- [ ] attack resolution.
- [ ] damage.
- [ ] healing.
- [ ] saving throws.
- [ ] advantage/disadvantage framework.
- [ ] critical-result framework where licensed rules require it.
- [ ] conditions foundation.
- [ ] reactions.
- [ ] ready/triggered actions.
- [ ] encounter start/end.
- [ ] available-action discovery.
- [ ] conformance test suite.

### Exit criteria

A complete basic encounter can be run through the API without a client implementing combat rules.

---

## v0.4 — Rules Runtime + Effect Pipeline

### Goal

Move reusable mechanics into a generalized typed resolution/effect system.

### Deliverables

- [ ] resolution contexts.
- [ ] typed outcomes.
- [ ] modifier pipeline.
- [ ] effect definitions.
- [ ] trigger hooks.
- [ ] durations.
- [ ] stacking policies.
- [ ] periodic effects.
- [ ] area effects.
- [ ] resource-cost effects.
- [ ] concentration-style capability hooks.
- [ ] reactions integrated with effect triggers.
- [ ] action-economy capability definitions.
- [ ] ruleset capability negotiation.

### Exit criteria

Representative abilities, conditions, and spells can be expressed primarily through reusable effect primitives rather than custom imperative handlers.

---

## v0.5 — Spatial Authority

### Goal

Make the server authoritative for positioning without coupling it to one client representation.

### Deliverables

- [ ] `SpatialAdapter` contract.
- [ ] theater-of-mind adapter.
- [ ] graph adapter.
- [ ] square-grid adapter.
- [ ] continuous 2D adapter.
- [ ] occupancy.
- [ ] distance.
- [ ] pathfinding hooks.
- [ ] terrain costs.
- [ ] line of sight.
- [ ] cover.
- [ ] movement validation.
- [ ] area/shape queries.
- [ ] spatial events.

### Exit criteria

The same encounter can be represented by at least two different spatial adapters while preserving rules authority.

---

## v0.6 — Character Runtime

### Goal

Support complete API-driven character creation and advancement.

### Deliverables

- [ ] character-creation session.
- [ ] attribute selection/generation.
- [ ] class selection.
- [ ] licensed species/ancestry data.
- [ ] background selection.
- [ ] skills.
- [ ] equipment.
- [ ] inventory.
- [ ] features.
- [ ] spellcasting.
- [ ] rests.
- [ ] progression.
- [ ] levels.
- [ ] feature-choice validation.
- [ ] character export/import schema.

### Exit criteria

A client can create, validate, save, load, and advance a playable character entirely through the API.

---

## v0.7 — Living World

### Goal

Extend the scheduler from encounters into persistent campaign simulation.

### Deliverables

- [ ] campaign calendar.
- [ ] world time.
- [ ] regions.
- [ ] locations.
- [ ] travel.
- [ ] NPC schedules.
- [ ] factions.
- [ ] reputation.
- [ ] weather/events interface.
- [ ] quest runtime.
- [ ] objective predicates.
- [ ] dialogue runtime.
- [ ] knowledge/discovery state.
- [ ] persistent location state.
- [ ] environmental effects.

### Exit criteria

A campaign continues to evolve through scheduled world events even when no combat encounter is active.

---

## v0.8 — Intelligent Actors

### Goal

Allow AI/scripted actors to use exactly the same legal command surface as humans.

### Deliverables

- [ ] controller interface.
- [ ] scripted controller.
- [ ] utility-AI controller.
- [ ] perception model.
- [ ] goals.
- [ ] tactical scoring.
- [ ] schedules.
- [ ] persistent memories/knowledge.
- [ ] intent-to-command boundary.
- [ ] optional external LLM controller adapter.
- [ ] AI Dungeon Master command surface.
- [ ] simulation safeguards and authorization.

### Exit criteria

An encounter and a basic world loop can run with no human-controlled NPCs while every AI action remains rules-validated and replayable.

---

## v0.9 — Universal Client API

### Goal

Make the API complete enough that clients become presentation layers.

### Deliverables

- [ ] stable `/api/v1` REST surface.
- [ ] WebSocket protocol.
- [ ] subscriptions.
- [ ] sequence-based resync.
- [ ] OpenAPI contract.
- [ ] authentication.
- [ ] campaign membership.
- [ ] actor-control grants.
- [ ] DM/player/spectator roles.
- [ ] capability discovery.
- [ ] available-action discovery.
- [ ] schema versioning.
- [ ] API compatibility policy.
- [ ] Python SDK.
- [ ] reference terminal client.
- [ ] reference WebSocket client.

### Exit criteria

A thin client can discover capabilities, create/load a campaign, create a character, join an encounter, play it, receive live events, and inspect world/quest state without embedding SRD logic.

---

## v1.0 — SRD 5.2.1 RPG Engine API

### Goal

Deliver a stable, reusable, documented API-first RPG simulation engine.

### Deliverables

- [ ] stable core domain interfaces.
- [ ] stable event schemas.
- [ ] stable command schemas.
- [ ] SRD 5.2.1 compatible rules package.
- [ ] required CC attribution.
- [ ] deterministic replay suite.
- [ ] sample campaign.
- [ ] sample encounters.
- [ ] sample characters.
- [ ] terminal reference client.
- [ ] API reference.
- [ ] architecture documentation.
- [ ] ruleset-authoring documentation.
- [ ] client-authoring documentation.
- [ ] deployment documentation.
- [ ] PostgreSQL migrations.
- [ ] observability baseline.
- [ ] security review.
- [ ] load tests.
- [ ] release/versioning policy.

### v1.0 success statement

A third-party developer should be able to build a turn-based, timed-turn, ATB-style, real-time-with-pause, or real-time fantasy RPG client using the same engine API and licensed rules package without modifying the authoritative server core.

---

# Post-v1.0 Roadmap

## v1.1 — Multiplayer hardening

- distributed sessions;
- reconnect recovery;
- presence;
- spectator support;
- latency compensation policies;
- command deduplication across gateways;
- stronger authorization/auditing.

## v1.2 — Advanced rules runtime

- deeper effect composition;
- richer reactions;
- transformation/replacement effects;
- nested resolution;
- rules-debug traces;
- ruleset hot-loading boundaries.

## v1.3 — Advanced deterministic event sourcing

- branching campaigns;
- rewind tooling;
- alternate-timeline simulation;
- state verification endpoints;
- fast replay infrastructure;
- snapshot compaction policies.

## v1.4 — Advanced spatial simulation

- continuous 3D adapter;
- collision hooks;
- navigation meshes;
- zones/portals;
- advanced LOS;
- elevation;
- dynamic terrain;
- client interpolation metadata.

## v1.5 — Intelligent living actors

- behavior trees;
- goal planning;
- utility AI;
- tactical planning;
- social memory;
- schedules;
- persistent relationships;
- faction-level planning.

## v2.0 — Large-world / MMO runtime

- zone servers;
- interest management;
- actor migration between zones;
- authoritative continuous movement;
- high-frequency combat events;
- distributed event transport;
- horizontal scaling;
- persistent shards/worlds;
- instance servers;
- large-scale observability;
- load shedding;
- backpressure;
- operational tooling.

---

# API design rules

1. **Server authority first.** Clients request actions; the server determines outcomes.
2. **Commands change state; queries read state.** Avoid arbitrary mutable CRUD.
3. **Events are durable facts.** Never silently rewrite history.
4. **Time is a domain concept.** Never use `sleep()` to implement game progression.
5. **Wall-clock deadlines are not simulation time.** Keep them separate.
6. **Rules are pluggable.** The core engine must not become an SRD monolith.
7. **Clients are replaceable.** No rule may require a particular rendering engine.
8. **Determinism is testable.** Every state transition must be reproducible.
9. **Version everything that affects replay.** Rules, schemas, commands, events, snapshots.
10. **AI is a controller, not an authority.** AI submits commands through normal validation.
11. **Async paths remain non-blocking.** Database/network operations use async-safe implementations.
12. **Concurrency is explicit.** Stream versions and idempotency protect multiplayer state.
13. **Licensed-content boundaries remain visible.** Keep SRD-derived data clearly attributable and separable.
14. **Observability is part of architecture.** Commands and events must be traceable.
15. **No client-side hidden rules.** The server exposes enough capability information for thin clients.

---

# Initial technical stack

Recommended starting point:

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
httpx / ASGI transport for API tests
WebSockets
```

Potential later additions:

```text
Redis          ephemeral coordination/pub-sub/cache only
OpenTelemetry  traces/metrics
Prometheus     metrics
structlog      structured logging
orjson         serialization where beneficial
```

Dependency additions should remain evidence-driven rather than becoming architectural requirements prematurely.

---

# First implementation slice

The first implementation PR after this plan should remain intentionally small.

Suggested scope:

```text
src/rpg_engine_api/
    app.py
    config.py
    domain/
        ids.py
        commands.py
        events.py
        dice.py
        campaign.py
    application/
        command_bus.py
    persistence/
        event_store.py
    api/
        health.py

tests/
    unit/
    determinism/
```

Implement only enough to prove:

```text
CreateCampaign command
    -> CampaignCreated event

CreateActor command
    -> ActorCreated event

RollDice command/internal operation
    -> DiceRolled event

replay(events)
    -> identical state hash
```

Do not begin by importing hundreds of spells, monsters, classes, or content records. Prove the runtime architecture first.

---

# Definition of done for every milestone

A milestone is not complete until:

- [ ] code is typed;
- [ ] async paths avoid blocking operations;
- [ ] unit tests pass;
- [ ] integration tests pass where applicable;
- [ ] deterministic/replay invariants pass where applicable;
- [ ] public schemas are documented;
- [ ] migrations are included for persistence changes;
- [ ] architecture changes are documented;
- [ ] licensed-content attribution remains correct;
- [ ] no client-specific assumptions have leaked into the core;
- [ ] commands/events are version-compatible or migration is documented;
- [ ] observable failures produce actionable logs.

---

# Long-term product goal

The finished project should behave less like a traditional game server and more like an **RPG simulation platform**.

A developer should be able to choose:

```text
ruleset = srd_5_2_1
combat_mode = turn_based
```

or:

```text
ruleset = srd_5_2_1
combat_mode = timed_turn_based
turn_deadline = 15s
timeout_policy = forfeit_turn
```

or:

```text
ruleset = srd_5_2_1
combat_mode = active_time
```

or:

```text
ruleset = srd_5_2_1
combat_mode = real_time
```

without replacing the game-state model, combat resolution system, rules engine, persistence model, or client API.

That is the central architectural constraint for the project.
