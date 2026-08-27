# Programmatic Human Playtesting Specification

## Status

**Project:** `rpg-engine-api`  
**Role:** Normative testing specification implementing the testing, determinism, client, and v1.0 acceptance requirements in `PLAN.md`.  
**Primary goal:** Every gameplay capability must be testable programmatically through the same public interfaces a real player, Dungeon Master, spectator, or client application would use.

`PLAN.md` remains the single product/architecture roadmap. This document defines how the plan's gameplay systems are systematically proven end to end.

---

# 1. Core principle: test like a human client

The project must have two complementary classes of tests:

```text
white-box tests
    domain/unit/component tests
    may call internal Python interfaces
    prove local invariants cheaply

black-box human-play tests
    use public REST + WebSocket contracts
    act through authenticated player/DM/spectator clients
    prove the product is actually playable end to end
```

A feature is **not considered fully playable** merely because its unit tests pass.

For a gameplay feature to count as end-to-end complete, a programmatic client must be able to:

1. discover the capability through the public API;
2. observe only the information its role/actor should see;
3. submit the same command/action a human-facing client would submit;
4. receive the resulting command receipt/events/projections;
5. continue the game from the resulting state;
6. reconnect/resynchronize when applicable;
7. replay the authoritative history to the same canonical state;
8. produce a reproducible transcript/artifact if the scenario fails.

Human-play tests must not patch database rows, mutate aggregates directly, call hidden rules helpers as a shortcut, or inject outcomes that a production client could not request.

---

# 2. The playtest harness is a first-class product component

Create a reusable test harness under a structure similar to:

```text
tests/
├── playtest/
│   ├── harness/
│   │   ├── client.py
│   │   ├── websocket.py
│   │   ├── persona.py
│   │   ├── clock.py
│   │   ├── scenario.py
│   │   ├── runner.py
│   │   ├── assertions.py
│   │   ├── coverage.py
│   │   ├── artifacts.py
│   │   └── chaos.py
│   ├── scenarios/
│   │   ├── campaign_creation/
│   │   ├── character_creation/
│   │   ├── exploration/
│   │   ├── dialogue_quests/
│   │   ├── inventory_economy/
│   │   ├── combat/
│   │   ├── timing_modes/
│   │   ├── progression/
│   │   ├── persistence_replay/
│   │   ├── visibility_security/
│   │   ├── reconnect_resync/
│   │   └── content_evolution/
│   ├── fixtures/
│   └── manifests/
└── ...
```

The harness should be usable against:

```text
in_process_asgi
local_server
containerized_server
remote_test_deployment
```

The exact transport may vary, but the gameplay path must remain the public API/live protocol.

---

# 3. Scenario model

Every human-play scenario should have a typed, versioned definition.

Conceptual model:

```text
PlaytestScenario
    id
    schema_version
    title
    description
    milestone
    feature_tags[]
    ruleset_ref
    content_lock_ref
    seed_bundle
    server_mode
    personas[]
    setup
    steps[]
    checkpoints[]
    expected_terminal_state
    cleanup
    artifact_policy
```

A scenario should be expressible in Python through typed builders. A declarative YAML/JSON representation may also be supported later, but it must validate into the same typed model rather than becoming a second execution system.

Scenarios must be deterministic by default. Any intentional nondeterminism must be explicitly declared and bounded by invariant assertions.

---

# 4. Personas: simulate real roles, not generic API calls

The harness must model different human/client roles.

```text
PlaytestPersona
    id
    principal_role
    controlled_actor_ids
    behavior_profile
    think_time_profile
    connection_profile
    visibility_expectations
```

Required persona categories as the engine grows:

```text
campaign_owner
dungeon_master
player
spectator
service_client
slow_player
reconnecting_player
invalid_action_player
multi_device_player
```

Later fuzz/model-based tests may add generated personas.

A persona can only use commands and information that its authenticated principal is allowed to access.

---

# 5. Human behavior simulation

Programmatic play must cover realistic player behavior, not only perfect instantaneous commands.

Behavior profiles should support:

```text
immediate_action
fixed_think_time
seeded_random_think_time
delayed_but_valid_action
timeout_no_action
invalid_then_correct_action
open_menu_then_act
cancel_then_reselect
reaction_accept
reaction_decline
disconnect_then_resume
multiple_tabs_or_devices
```

Important timing scenarios include:

- acting immediately;
- acting just before a decision deadline;
- acting exactly at the deadline boundary according to the documented policy;
- acting after expiration and receiving the proper rejection;
- taking no action and exercising `forfeit_turn` or another timeout policy;
- disconnecting during a decision window;
- reconnecting before/after grace expiration;
- receiving a reaction opportunity while another action is pending;
- pausing/resuming real-time-with-pause sessions;
- competing simultaneous commands from multiple actors.

---

# 6. Clock control: never make the suite wait in real time

Human-play tests must not rely on long `sleep()` calls to test a 15-second turn, multi-hour rest, travel, crafting, cooldown, or scheduled world event.

The engine already separates simulation time from wall-clock decision time. The test architecture must preserve that separation.

Use injectable clock interfaces:

```text
SimulationClock
WallClock
```

Production uses real monotonic/wall-clock implementations where required.

Tests use deterministic controllable implementations:

```text
ControllableSimulationClock
ControllableWallClock
```

The test harness may advance the injected clock through fixture control, but the player persona must still interact only through public gameplay APIs.

Clock advancement is a **test environment control**, not a gameplay command and not a hidden way to mutate game outcomes.

Boundary semantics must be tested at exact timestamps, not approximated by sleeps.

---

# 7. Deterministic seed bundles

Every scenario records all authoritative random seeds/stream identities required to replay it.

```text
SeedBundle
    campaign_seed
    dice_seed
    loot_seed
    encounter_seed
    world_seed
    procedural_seed
    scenario_behavior_seed
```

The human-behavior RNG must be independent from game RNG.

A random player delay or generated test action must never perturb authoritative dice/loot/world results.

Failures must print/store the complete seed bundle.

---

# 8. Scenario step DSL

Scenario steps should map closely to what a human client does.

Example conceptual operations:

```text
authenticate
begin_campaign_creation
choose_campaign_option
finalize_campaign
invite_member
begin_character_creation
choose_character_option
finalize_character
join_party
open_session
query_projection
query_available_actions
submit_action
wait_for_event
advance_test_clock
move
interact
choose_dialogue
accept_quest
trade
craft
start_encounter
choose_target
react
end_turn
disconnect
reconnect
resume_subscription
assert_visible
assert_hidden
assert_event
assert_projection
assert_log
assert_state_hash
restart_server
rebuild_projection
replay_campaign
```

The DSL should prefer semantic operations built on public API calls over raw HTTP request duplication in every test.

It must still expose a low-level escape hatch for contract tests that need to send malformed or version-incompatible requests.

---

# 9. Assertions and oracles

Human-play assertions should be layered.

## 9.1 Transport assertions

Verify:

```text
HTTP status
command receipt status
error code
schema version
correlation/request IDs
cursor behavior
WebSocket ordering
ack/resume behavior
```

## 9.2 Player-visible assertions

Verify what the persona actually sees:

```text
available actions
character sheet
world/scene projection
inventory
quest journal
dialogue choices
combat log
decision deadline
visible enemies/objects
hidden information absence
```

## 9.3 Event assertions

Verify authoritative event type/order/payload shape without coupling tests to irrelevant implementation details.

## 9.4 Domain invariant assertions

Examples:

```text
resources never spend twice
inventory quantities conserve across transfers
stream versions increase monotonically
a timed-out actor cannot later apply the expired action
an unauthorized persona never receives DM-only fields
reconnect does not duplicate authoritative actions
projection sequence never exceeds authoritative committed sequence
replay yields the same canonical hash
```

## 9.5 Golden assertions

Use curated golden transcripts/snapshots only for stable, meaningful contracts. Avoid giant brittle snapshots of incidental formatting.

---

# 10. Human-play transcript

Every scenario should be able to emit a chronological transcript that a developer can read like a game session.

Conceptual example:

```text
[00] DM creates campaign `testing-grounds`
[01] Player A begins character creation
[02] Player A chooses Fighter
[03] Player A chooses Human
[04] Character finalizes successfully
[05] Session opens
[06] Player A enters Town Gate
[07] Player A sees Guard, Gate, Road
[08] Player A chooses Move -> Road
[09] Encounter starts
[10] Player A becomes ready; deadline +15s
[11] Player A waits 16s
[12] TurnTimedOut / forfeit_turn
[13] Goblin acts
...
```

On failure, include the last successful step and all relevant IDs/sequences.

---

# 11. Failure replay bundle

Any failed human-play scenario should be reproducible from a compact artifact bundle.

```text
PlaytestFailureBundle
    scenario_id
    scenario_schema_version
    git_revision
    engine_version
    ruleset/content_lock
    seed_bundle
    configuration
    persona definitions
    executed_steps
    REST request/receipt summary
    WebSocket frame/event summary
    relevant projection snapshots
    authoritative event sequence range
    canonical state hashes
    failure assertion
```

The goal is:

```text
one failure -> one command to replay locally
```

No production secrets or auth tokens may be written to artifacts.

---

# 12. Coverage manifest

Create a machine-readable coverage manifest that maps planned capabilities to playtest scenarios.

Conceptual shape:

```text
FeatureCoverageEntry
    feature_id
    milestone
    implementation_status
    unit_test_refs[]
    integration_test_refs[]
    playtest_scenario_refs[]
    timing_modes[]
    roles[]
    spatial_adapters[]
    ruleset_content_refs[]
    negative_case_refs[]
    replay_case_refs[]
```

Coverage categories should eventually include every major subsystem in `PLAN.md`:

```text
campaign_creation
character_creation
classes
species
backgrounds
skills
progression
movement
perception
exploration
dialogue
quests
inventory
equipment
economy
trade
crafting
combat
actions
reactions
conditions
effects
spells_or_powers
rests
travel
world_events
factions
logging
permissions
visibility
replay
content_revisions
WebSocket_resume
backup_restore
```

No milestone may be declared complete while required implemented features have no programmatic human-play path unless the feature is explicitly internal-only.

---

# 13. Reference playable world: Testing Grounds

The existing `Testing Grounds` integration fixture becomes the canonical human-play world and grows with milestones.

Target structure:

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

It should eventually contain enough controlled content to exercise:

- campaign creation;
- player/DM membership;
- at least two playable character builds;
- species/background/class choices;
- visible and hidden world objects;
- movement and perception;
- one social NPC and branching dialogue;
- one quest with parallel/conditional objectives;
- one vendor and currency transaction;
- one inventory/container workflow;
- one crafting recipe;
- one faction/reputation change;
- one scheduled world event;
- one standard turn-based encounter;
- one timed-turn encounter;
- one active-time encounter;
- one real-time/real-time-with-pause scenario when implemented;
- effects/conditions/reactions;
- progression/level-up;
- save/replay/reconnect scenarios.

Only add fixture content when the corresponding milestone exists. Keep the world small enough that failures remain understandable.

---

# 14. Scenario suites

## 14.1 Campaign creation suite

Test:

- valid default campaign;
- every timing mode once available;
- invalid/incompatible ruleset/content choices;
- house-rule validation;
- draft resume/cancel/expire;
- role/member configuration;
- content lock determinism.

## 14.2 Character creation suite

Test:

- all supported creation steps;
- at least one legal path per class/species/background once mapped;
- invalid prerequisite choices;
- changing upstream choices and downstream revalidation;
- ability-score policies;
- higher-level creation;
- multiclass paths when supported;
- save/resume/cancel/expire;
- final sheet projection;
- import/export validation.

## 14.3 Exploration and movement suite

Test:

- legal movement;
- blocked movement;
- path/cost calculations;
- multiple spatial adapters;
- entering/exiting scenes;
- hidden objects;
- discovery;
- visibility/lighting/perception boundaries;
- travel and marching order.

## 14.4 Social/dialogue/quest suite

Test:

- start/end dialogue;
- conditional choices;
- hidden choices;
- social checks where applicable;
- quest offer/accept/progress/fail/complete;
- parallel/conditional/timed objectives;
- reputation/faction consequences.

## 14.5 Inventory/economy/crafting suite

Test:

- acquire/drop/transfer;
- containers and permissions;
- equip/unequip/use/consume;
- stack split/merge;
- insufficient currency;
- successful/failed trade;
- vendor schedules/pricing hooks;
- crafting start/progress/interruption/completion;
- conservation of items/currency.

## 14.6 Combat suite

Test:

- encounter start/positioning;
- initiative/readiness;
- available actions;
- legal/illegal targets;
- movement during encounter;
- attacks/checks/saves;
- damage/healing;
- resource spend/recovery;
- conditions/effects;
- reactions/interrupts;
- defeat/end/cleanup/rewards;
- combat log.

## 14.7 Timing-mode matrix

Every representative combat/action scenario should be mapped across supported modes:

```text
turn_based
timed_turn_based
active_time
real_time_with_pause
real_time
hybrid
```

Not every rule must exist in every mode, but each supported translation must have human-play coverage.

## 14.8 Progression suite

Test:

- XP/milestone/progression grants;
- level-up session;
- prerequisite validation;
- mutually exclusive nodes;
- ranked nodes;
- feature/resource changes;
- respec when enabled;
- resulting character sheet/actions.

## 14.9 Persistence/replay suite

Test:

- stop/start server;
- restore active campaign;
- replay from start;
- replay from snapshot;
- projection rebuild;
- older event schema upcast fixtures;
- canonical hash equality;
- no duplicate action after restart/retry.

## 14.10 Visibility/security suite

Test each scenario from multiple roles and assert hidden fields/events are absent before serialization.

Test unauthorized actor control, DM-only audit/log access, invalid tokens/roles, and stale grants.

## 14.11 Reconnect/resynchronization suite

Test:

- disconnect before event;
- disconnect during action window;
- miss several events;
- resume from acknowledged sequence;
- snapshot+delta resync;
- backpressure disconnect;
- no silent authoritative-event loss;
- no duplicate commands after retry.

## 14.12 Content evolution suite

Test install, dependency conflict, activation, migration, pinned replay, upgrade, rollback, and failed revision behavior through the public admin/DM interfaces intended for those operations.

---

# 15. Model-based and generated playtesting

Handwritten scenarios prove known workflows. The project should also grow model-based/generated tests that explore combinations humans may reach unexpectedly.

## 15.1 Available-action walker

A generated player may:

1. query its current visible projection;
2. query available actions;
3. choose one action using a deterministic scenario RNG;
4. generate a valid target/input from the advertised schema;
5. submit it;
6. verify invariants;
7. repeat for N steps.

Crucially, the walker should not reimplement hidden game rules. It uses the same server-advertised capabilities a generic client would use.

## 15.2 Negative-action generator

Generate near-valid invalid requests:

```text
wrong target
out-of-range target
stale stream version
expired action window
insufficient resource
unauthorized actor
invalid choice count
wrong schema version
```

Assert stable rejection codes and no unintended events/state changes.

## 15.3 State-machine testing

Use Hypothesis stateful testing where appropriate for bounded subsystems such as:

- inventory transfers;
- progression choices;
- character draft choices;
- command idempotency;
- event-stream versioning;
- WebSocket acknowledgement/resume;
- action reservation/refund states.

---

# 16. Chaos playtesting

End-to-end tests should deliberately inject recoverable failures around normal player behavior.

Test controls may simulate:

```text
WebSocket disconnect
HTTP retry
duplicate command delivery
out-of-order client responses
slow consumer/backpressure
server restart
DB reconnect
outbox delay
projection lag
expired auth/session
```

Chaos injection may affect infrastructure but must never bypass authoritative domain rules.

Each chaos scenario must verify the player can either continue safely or receives a deterministic recoverable error/resync path.

---

# 17. Multi-client playtesting

The harness must support multiple concurrent personas against the same campaign.

Required concurrency scenarios eventually include:

- two players acting in one encounter;
- player and DM issuing concurrent commands;
- simultaneous reaction windows;
- two devices retrying the same command/idempotency key;
- one spectator receiving filtered events;
- one slow client while others continue;
- actor-control handoff;
- join/leave during session/encounter where permitted.

Use async-safe clients and structured concurrency. Do not introduce blocking client operations into async playtests.

---

# 18. Playtest modes

Provide explicit runner modes.

```text
smoke
pr
full
nightly
release
fuzz
chaos
```

Suggested intent:

### `smoke`

Very small deterministic critical path: boot, create minimal campaign/actor, submit command, receive event, replay.

### `pr`

All scenarios affected by changed feature tags plus mandatory core regressions.

### `full`

All deterministic human-play scenarios across currently supported features.

### `nightly`

Full suite plus broader timing/spatial/persona matrices and generated walkers.

### `release`

Full deterministic matrix, migration/replay, restart/recovery, visibility/security, and selected performance/chaos gates.

### `fuzz`

Seeded generated action/state-machine exploration with failure seed capture.

### `chaos`

Infrastructure failure/reconnect/backpressure scenarios.

Exact runtime budgets should be measured and documented rather than guessed in advance.

---

# 19. CI selection and feature tagging

Tests should carry stable feature tags matching the coverage manifest.

Examples:

```text
feature:character_creation
feature:movement
feature:timed_turn
feature:inventory
feature:websocket_resume
milestone:v0.2
ruleset:srd_5_2_1
mode:turn_based
mode:active_time
role:player
role:dm
```

Changed code should map to affected feature tags so PR CI can select relevant scenarios while preserving a mandatory core smoke/regression set.

Do not rely exclusively on selective testing; scheduled full runs remain required.

---

# 20. Playtest artifacts and reports

A run should be able to produce:

```text
summary.json
coverage.json
junit.xml
scenario transcripts
failure replay bundles
selected REST request/receipt logs
selected WebSocket event logs
projection snapshots
canonical state hashes
timing metrics
```

Reports should answer:

- What features were exercised?
- What personas/timing modes/spatial adapters were covered?
- What scenario failed?
- At which public interaction step?
- What authoritative sequence was last known good?
- Can it be replayed exactly?

Artifacts must redact secrets and private credentials.

---

# 21. Bug regression rule

Every gameplay bug fixed after discovery should add the narrowest durable regression at the appropriate layer.

If the bug was observable during human play, add or extend a human-play scenario unless doing so is impossible or redundant with an existing scenario that now catches it.

A bug fix is incomplete when its original player-visible failure can silently return without a regression signal.

---

# 22. Milestone integration requirements

Human-play testing grows with the roadmap.

## v0.1

Build the harness foundation:

- [ ] public async API client;
- [ ] basic WebSocket client seam;
- [ ] typed scenario/step model;
- [ ] deterministic seed bundle;
- [ ] controllable test clocks interface;
- [ ] transcript/artifact capture;
- [ ] minimal player/DM personas;
- [ ] `Testing Grounds` fixture skeleton;
- [ ] smoke scenario: create campaign/actor -> command -> event -> replay/hash;
- [ ] idempotency/conflict public-interface scenarios;
- [ ] coverage manifest format.

### v0.1 human-play exit criterion

A black-box test client can create the minimal supported game state, perform a legal state-changing action through the public API, observe the authoritative result, reconnect/requery as supported, and verify deterministic replay without calling domain internals.

## v0.2

Add:

- [ ] controllable deadline tests;
- [ ] turn-based/timed-turn/ATB/real-time-mode harness hooks as modes become available;
- [ ] human think-time profiles;
- [ ] timeout/forfeit scenario;
- [ ] action reservation/refund scenario;
- [ ] simultaneous-action scenario;
- [ ] reconnect during decision window.

## v0.3

Add complete human-play combat loops, reactions, conditions, movement, targeting, encounter cleanup, and combat-log assertions.

## v0.4

Add effect/resource/spell-or-power/progression primitive scenarios and generated action-state coverage.

## v0.5

Add exploration, perception, hidden information, world objects, multiple spatial adapters, and role/visibility assertions.

## v0.6

Add full character-creation matrix, upstream-choice revalidation, higher-level creation, progression, import/export, and resulting playable-character scenarios.

## v0.7

Add campaign creation, party/session, world travel, dialogue, quests, factions, economy, vendor, crafting, scheduled events, and complete `Testing Grounds` adventure flow.

## v0.8

Run the same scenarios with scripted/AI-controlled actors where applicable and verify they receive only player-visible capabilities/knowledge.

## v0.9

Promote the harness to strict public-contract testing across REST/WebSocket, generated clients/SDKs, reconnect/resync, pagination, localization/units metadata, and compatibility/deprecation behavior.

## v1.0

The full 76-step acceptance flow in `PLAN.md` must exist as executable scenario(s), not just prose. Release gating must prove it programmatically through public interfaces.

---

# 23. Complete campaign journey scenario

Maintain at least one long-form scenario that feels like a human actually playing rather than isolated API tests.

Target journey:

```text
install/discover ruleset
    -> create campaign
    -> configure timed combat
    -> invite player
    -> create character
    -> inspect character sheet
    -> join party/session
    -> enter town
    -> talk to NPC
    -> accept quest
    -> buy/sell or acquire item
    -> leave town
    -> travel/explore
    -> discover hidden path/object
    -> enter encounter
    -> move/attack/use ability
    -> exercise reaction
    -> intentionally miss one timed turn
    -> finish encounter
    -> loot/reward
    -> update quest
    -> return/interact
    -> gain progression
    -> level/unlock feature
    -> save/reconnect
    -> inspect logs/history
    -> replay campaign
    -> verify canonical state
```

As features land, this journey should grow instead of creating a separate disconnected demo for every subsystem.

---

# 24. Test client must remain thin

The playtest client is also a reference for real client authors.

It may know how to:

- authenticate;
- render/parse schemas;
- query actions;
- choose from advertised options;
- send commands;
- consume events;
- maintain local projection cursors;
- reconnect/resync.

It must **not** know hidden combat formulas, eligibility rules, secret world state, authoritative dice outcomes, or rules needed to decide legality.

If a playtest requires duplicating hidden server rules merely to function, treat that as an API/capability-discovery design failure and fix the API rather than teaching the test client secret rules.

---

# 25. Definition of human-play-testable

A gameplay subsystem is programmatically human-play-testable when:

- [ ] setup can be created through supported public/admin interfaces or deterministic fixtures explicitly allowed by the test environment;
- [ ] a player/DM persona can discover the relevant capability;
- [ ] legal actions can be performed through public interfaces;
- [ ] illegal actions produce stable public errors without corrupting state;
- [ ] resulting visible projections/events/logs can be asserted;
- [ ] hidden state remains hidden from unauthorized personas;
- [ ] timing behavior can be tested without real sleeps;
- [ ] disconnect/retry behavior is defined where relevant;
- [ ] authoritative events can replay to the same state;
- [ ] the scenario has stable feature/milestone tags;
- [ ] failures produce a replayable artifact with seeds and sequence IDs.

---

# 26. Agent/testing rule

Whenever an agent implements or changes a user-visible gameplay capability, it must ask:

```text
How would a human reach this feature?
How would the public client discover it?
What exact command/action would the human submit?
What should each role see before and after?
What happens if they wait, retry, disconnect, or submit an invalid choice?
How is the scenario deterministically replayed?
Which playtest scenario proves it?
```

If those questions cannot be answered, the feature is not complete enough to merge as a finished gameplay capability.
