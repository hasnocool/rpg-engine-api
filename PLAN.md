# RPG Engine API — Complete Architecture and Implementation Plan

## Status

**Project:** `rpg-engine-api`  
**Target runtime:** Python 3.12+  
**Primary API:** FastAPI REST + WebSockets  
**Architecture:** headless, deterministic, event-driven RPG simulation platform  
**Initial compatible rules package:** SRD 5.2.1-based ruleset  
**Canonical planning document:** this file

The goal is to let any client—Godot, Unity, browser, mobile, TUI, SSH, Discord-style UI, AI narrator, automation service, or another game engine—create and play a D&D-style RPG by treating this API as the authoritative game simulation.

The engine owns the rules and state. Clients discover capabilities, submit commands, receive events, and render projections.

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
- AI/scripted controller boundaries.

Clients should primarily:

1. authenticate;
2. query visible state/projections;
3. discover legal actions and creation choices;
4. submit typed commands;
5. subscribe to live events;
6. render the resulting state.

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
9. **Version everything affecting replay.** Rules, content, schemas, events, commands, snapshots, projections, and campaign settings.
10. **AI is a controller, not an authority.** It submits normal commands.
11. **Async paths remain non-blocking.** DB/network I/O uses async-safe operations; heavy CPU work is isolated.
12. **Concurrency is explicit.** Stream versions, idempotency, and deterministic ordering protect multiplayer state.
13. **Licensed-content boundaries remain visible.**
14. **Observability is part of the architecture.** Commands/events are traceable end to end.
15. **No hidden client rules.** The API exposes enough metadata for thin clients.
16. **Visibility is enforced server-side before serialization.**
17. **Definitions and instances are separate.** Content templates are immutable/versioned; campaign state is mutable/event-driven.
18. **Every core subsystem must define state, commands, events, lifecycle, permissions, replay, failures, migrations, and tests before implementation.**

---

# 4. Shared domain primitives

## 4.1 Stable identifiers

Every durable entity has an opaque durable ID and a separate stable content key.

```text
EntityIdentity
    id                 # opaque UUID/ULID-like identity
    key                # namespaced stable key
    display_name_key   # localization key
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

Grant types include:

```text
feature
proficiency
resource
action
movement_mode
sense
language
item
spell_or_power
progression_currency
tag
```

## 4.6 Visibility

```text
VisibilityPolicy
    audience
    discovery_requirement
    redact_fields
```

Audiences include:

```text
public
campaign_members
party
controller_only
dm_only
service_only
custom_role
```

Visibility is applied before response/event serialization.

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

Capabilities may include:

```text
initiative
turn_economy
active_time_translation
real_time_translation
character_creation
leveling
multiclassing
spellcasting
conditions
inventory
encumbrance
spatial_rules
rests
crafting
economy
```

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

A pack may contain classes, species, backgrounds, features, progression graphs, actions, spells/powers, items, creatures, conditions, quests, dialogue, recipes, world/location templates, and campaign templates.

## 5.3 Dependency and conflict resolution

Activation must:

1. resolve dependency versions;
2. reject unsupported cycles;
3. reject incompatible engine/ruleset ranges;
4. reject duplicate un-namespaced keys;
5. apply overrides only when explicitly declared;
6. create a deterministic ordered content lock;
7. validate references before activation.

There is no silent last-write-wins behavior.

## 5.4 Campaign content lock

Every finalized campaign configuration revision pins content.

```text
CampaignContentLock
    ruleset_ref
    pack_refs[]
    house_rule_set_ref
    schema_versions
    combined_hash
```

Replay uses the content lock active at the event sequence being reconstructed.

## 5.5 Mid-campaign content revisions

```text
ProposeContentRevision
ValidateContentRevision
ActivateContentRevision
RollbackContentRevision
```

Activation either migrates affected state safely or fails with an incompatibility report. Old history remains bound to old definitions.

## 5.6 House rules

House rules are typed data, not code patches.

```text
HouseRuleDefinition
    id
    target_rule_key
    operation
    parameters
    prerequisites
    compatibility
```

Supported operations may replace a policy, adjust numeric parameters, enable/disable a capability, or select a ruleset-defined variant.

---

# 6. Command/event architecture and determinism

Clients submit **commands**. The engine emits **events**.

Example commands:

```text
CreateCampaign
CreateActor
Attack
CastAbility
MoveActor
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
BeginCharacterCreation
FinalizeCharacter
BeginLevelUp
```

Example events:

```text
CommandAccepted
CommandRejected
CampaignCreated
ActorCreated
AttackDeclared
AttackRolled
AttackHit
AttackMissed
DamageApplied
HealingApplied
ActorMoved
AbilityActivated
EffectApplied
ConditionApplied
TurnStarted
TurnTimedOut
ActorDefeated
ItemAcquired
QuestUpdated
WorldTimeAdvanced
```

Never allow direct authoritative patches such as changing HP or coordinates from a client payload.

Processing path:

```text
command
    -> authentication
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

The server controls RNG state. Dice/random results generate events.

```text
DiceRolled
    expression
    rolls
    modifier
    total
    purpose
    rng_sequence
```

Same initial state + rules/content versions + RNG seed + command stream must produce the same canonical outcome.

## 6.2 Event metadata

Each persisted event eventually carries:

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
content_lock_hash
event_type
schema_version
payload
```

## 6.3 Event sourcing and projections

```text
commands
    -> domain events
    -> event store
    -> projections
```

Useful projections include:

- campaign state;
- actor/character sheet;
- encounter state;
- inventory;
- quests;
- map occupancy;
- timeline;
- available actions;
- role-filtered world state;
- game/combat logs.

Snapshots reduce replay cost but never replace authoritative history.

---

# 7. First-class time and scheduler

Traditional rounds are one scheduling policy, not the engine itself.

The engine understands:

- simulation time;
- wall-clock decision time;
- readiness;
- deadlines;
- action duration;
- cooldowns;
- delays;
- interrupts;
- reaction windows;
- periodic effects;
- world events;
- NPC schedules;
- actor availability.

## 7.1 Two clocks

**Simulation time** drives the fictional world: rounds, effects, travel, weather, crafting, quests, rests, and schedules.

**Wall-clock decision time** limits how long a connected user may make a choice.

Never use wall-clock passage as the authoritative simulation clock.

## 7.2 Timing modes

### `turn_based`

Traditional initiative-driven rounds and turns.

### `timed_turn_based`

Traditional initiative plus a configurable real-world deadline.

```text
player decision window = 15 seconds
timeout policy = forfeit_turn
```

Required timeout-policy hooks:

```text
forfeit_turn
auto_dodge
auto_defend
repeat_previous_action
ai_control
pause_game
dm_decides
```

### `active_time`

Final-Fantasy-style readiness. Actors become ready according to a ruleset-defined readiness calculation. Other actors may continue accumulating readiness while a player decides.

### `real_time_with_pause`

Continuous simulation with authoritative pausing.

### `real_time`

Continuous MMO/action-RPG semantics with cooldowns, cast/windup time, movement, resource regeneration, interrupts, periodic effects, and reaction windows.

### `hybrid`

Different actor/system policies may coexist.

```text
players = active_time
boss = real_time
summons = automatic_real_time
world = real_time
dialogue = turn_based
```

## 7.3 Scheduled events

Conceptual types:

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
AbilityCastStarted
AbilityCastCompleted
CooldownExpired
ConditionTicked
ConditionExpired
WorldEventTriggered
NpcScheduleTriggered
EncounterStarted
EncounterEnded
```

Ordering uses simulation timestamp plus deterministic priority/tie-break fields.

No request handler sleeps to wait for simulation time.

---

# 8. Universal action transaction model

Combat, movement, social, inventory, exploration, rest, and custom actions use a common definition.

```text
ActionDefinition
    id
    ruleset_id
    name
    category
    timing
    costs
    prerequisites
    targeting
    range
    movement_requirements
    resolution
    effects
    cooldown
    interruptibility
    tags
```

Categories include:

```text
attack
movement
magic
interaction
exploration
social
inventory
rest
reaction
special
custom
```

## 8.1 Action instance lifecycle

```text
ActionInstance
    id
    definition_ref
    actor_id
    targets
    status
    declared_sequence
    scheduled_start
    scheduled_completion
    reserved_costs
    context
```

Statuses:

```text
proposed
declared
queued
executing
waiting_for_reaction
interrupted
cancelled
resolved
completed
failed
```

Lifecycle:

```text
ActionProposed
    -> validation
    -> ActionDeclared
    -> reserve/pay costs
    -> optional windup/cast
    -> optional reaction windows
    -> resolution
    -> effects/events
    -> cooldown/recovery
    -> ActionCompleted
```

## 8.2 Cost semantics

Every cost declares one of:

```text
pay_on_declare
reserve_on_declare_pay_on_execute
pay_on_success
pay_on_completion
```

Refund behavior is explicit for validation failure, cancellation, interruption, timeout, and server conflict.

Interruption is not generic rollback: already-emitted effects remain unless the rules specifically reverse them.

## 8.3 Simultaneous/conflicting commands

Authoritative ordering:

```text
simulation_time
scheduler_priority
stream_sequence_or_tie_breaker
```

Wall-clock arrival time alone does not decide simultaneous game outcomes.

Stale commands are safely revalidated or rejected with `state_conflict`; they never overwrite newer state.

## 8.4 Available-action discovery

```http
GET /api/v1/actors/{actor_id}/available-actions
```

A response exposes legal action schemas, costs, target constraints, movement allowance, timing state, and decision deadline without requiring client-side rules logic.

---

# 9. Effects, features, resources, abilities, and conditions

## 9.1 Effect pipeline

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

Triggers include apply/remove, turn start/end, action declaration, attacks, damage, movement, entering/leaving areas, ability activation, reactions, and elapsed time.

Modifiers may affect armor/defense, checks, attacks, saves, movement, damage, healing, resource cost, cooldown, action duration, or readiness rate.

Prefer declarative reusable effects over arbitrary one-off imperative handlers.

## 9.2 Feature definitions

```text
FeatureDefinition
    id
    key
    category
    prerequisites
    choice_groups
    grants
    modifiers
    triggered_effects
    actions
    resources
    source_metadata
```

Features may come from class, subclass, species, background, feat, item, condition, quest reward, campaign grant, or custom progression.

## 9.3 Resource definitions

```text
ResourceDefinition
    id
    key
    value_type
    minimum
    maximum_formula
    recovery_rules
    spend_rules
    visibility
```

```text
ResourceState
    definition_ref
    current
    maximum
    reserved
    last_changed_sequence
```

Resources cover health, class resources, spell slots, stamina-like systems, charges, readiness, and cooldown tokens.

## 9.4 Health projection

Health is rules-driven resource state, with a convenience projection:

```text
HealthProjection
    current
    maximum
    temporary
    status
    recovery_options
```

Rules determine consequences at zero and recovery behavior.

## 9.5 Spells/powers/techniques

```text
AbilityDefinition
    id
    key
    ability_type
    level_or_rank
    school_or_category
    activation_timing
    action_cost
    cast_or_windup_duration
    range
    target_schema
    area_schema
    components_or_requirements
    resource_costs
    duration
    concentration_or_maintenance_policy
    effects
    scaling
    interruption_policy
    tags
    source_metadata
```

Character state separates known abilities, prepared/active loadouts, resources, and cooldown state.

## 9.6 Conditions

```text
ConditionDefinition
    id
    key
    prerequisites
    modifiers
    grants
    restrictions
    triggered_effects
    stacking_policy
    duration_policy
    removal_rules
    visibility
```

Condition instances retain source, start sequence/time, stacks, duration, and scheduled expiration.

## 9.7 Generic rule-resolution primitive

```text
ResolutionContext
    actor
    action
    targets
    environment
    active_effects
    timing
    ruleset_revision
```

```text
ResolutionOutcome
    status
    rolls
    modifiers_applied
    resource_changes
    effects
    emitted_events
    rule_trace_id
```

Rule traces are DM/developer-visible unless campaign policy exposes them.

---

# 10. Reactions and interrupts

Reactions are interrupt windows, not a special side-channel.

```text
triggering event
    -> eligible reactions calculated
    -> ReactionWindowOpened
    -> commands accepted under policy
    -> reaction resolves
    -> original resolution continues/cancels/changes
```

Timing policies map the reaction window differently for turn-based, timed-turn, active-time, and real-time modes.

Multiple reactions are deterministically ordered.

---

# 11. Spatial authority and movement

The server owns position/movement semantics but does not require one representation.

```text
SpatialAdapter
```

Implementations:

```text
TheaterOfMindSpace
GraphSpace
SquareGridSpace
HexSpace
Continuous2DSpace
Continuous3DSpace
```

Required operations include:

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

## 11.1 Movement is an action

Clients never patch coordinates directly.

```text
MoveActor
    actor_id
    destination | path | direction
    movement_mode
    client_command_id
```

Movement modes:

```text
walk
run
crawl
climb
swim
fly
jump
teleport
forced
vehicle
custom
```

Turn/grid movement validates path, reactions, cost, and final state.

Real-time movement produces an authoritative trajectory/path plus meaningful events; clients interpolate presentation locally. The domain does not emit one event per rendered frame.

---

# 12. Perception, hidden state, discovery, terrain, and world objects

A server-authoritative RPG must distinguish true world state from what an actor knows.

## 12.1 Senses

```text
SenseDefinition
    sense_type
    range
    precision
    requirements
    blockers
```

The spatial/perception layer answers:

```text
can_perceive(observer, subject)
perception_quality(observer, subject)
known_position(observer, subject)
visible_fields(observer, entity)
```

## 12.2 Hidden information

Clients receive knowledge/visibility projections, never omniscient aggregates.

Secret checks may be resolved server-side with visibility metadata hiding both existence and result where policy permits.

## 12.3 Discovery

```text
EntityDetected
EntityIdentified
LocationDiscovered
FactLearned
MapKnowledgeUpdated
```

Discovery may be actor-, party-, or campaign-scoped.

## 12.4 World objects

```text
WorldObject
    id
    definition_ref
    scene_or_location_id
    spatial_state
    object_state
    interaction_actions
    visibility
```

Objects cover doors, switches, furniture, signs, containers, quest objects, resource nodes, environmental features, and other interactables.

## 12.5 Containers

```text
ContainerState
    inventory_id
    access_policy
    open_state
    lock_state
    capacity
```

## 12.6 Terrain and hazards

```text
TerrainDefinition
    movement_costs
    movement_mode_rules
    visibility_modifiers
    environmental_effects
    tags
```

```text
HazardDefinition
    trigger
    detection_rules
    avoidance_rules
    effects
    reset_policy
    visibility
```

---

# 13. Actor model

Players, NPCs, monsters, pets, companions, summons, and AI actors share a component-based actor foundation.

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

Controller types:

```text
human
ai
scripted
remote_service
system
```

Definitions/templates are separate from instances.

```text
ActorTemplateDefinition
    id
    key
    actor_kind
    base_attributes
    proficiencies
    features
    actions
    resources
    movement
    senses
    equipment
    controller_defaults
    source_metadata
```

```text
ActorInstance
    id
    template_ref | null
    campaign_id
    current_components
    controller
    location
    visibility
```

---

# 14. Character creation

Character creation is a resumable server-authoritative workflow, not one giant mutable character payload.

```text
CharacterCreationSession
    id
    owner_user_id
    campaign_id | null
    ruleset_id
    ruleset_version
    content_lock_hash
    target_starting_level
    status
    current_step
    completed_steps
    available_steps
    selections
    validation_errors
    warnings
    created_at
    updated_at
```

Statuses:

```text
draft
valid
finalized
cancelled
expired
```

## 14.1 Ruleset-driven step graph

A ruleset exposes the creation dependency graph rather than forcing one UI page order.

Example:

```text
ChooseClass
    -> DetermineOrigin
       -> ChooseBackground
       -> ChooseSpecies
       -> ChooseLanguages
    -> DetermineAbilityScores
    -> ChooseClassOptions
    -> ChooseProficiencies
    -> ChooseEquipment
    -> ChooseSpellsOrPowers
    -> ChooseAlignment
    -> CharacterDetails
    -> Validate
    -> Finalize
```

## 14.2 Commands

```text
BeginCharacterCreation
ChooseClass
ChooseSubclass
ChooseSpecies
ChooseBackground
ChooseLanguage
AssignAbilityScores
ChooseSkillProficiency
ChooseToolProficiency
ChooseStartingEquipment
ChooseFeat
ChooseFeatureOption
ChooseSpell
SetAlignment
SetCharacterIdentity
SetCharacterAppearance
SetCharacterBiography
ValidateCharacterDraft
FinalizeCharacter
CancelCharacterCreation
```

Every choice emits auditable events.

## 14.3 Draft dependency invalidation

Changing an upstream choice revalidates downstream choices.

```text
DraftRevalidationResult
    retained_choices
    invalidated_choices
    new_required_choices
    warnings
```

Valid unrelated selections are retained; invalid selections are marked unresolved rather than silently discarded.

## 14.4 Identity/presentation metadata

```text
CharacterIdentity
    name
    pronouns | null
    alignment | null
    age | null
    size
    appearance
    biography
    personality_notes
    ideals
    bonds
    flaws
    portrait_asset_id | null
    tags
```

Rulesets decide which fields have mechanical meaning.

## 14.5 Species

```text
SpeciesDefinition
    id
    ruleset_id
    name
    size_options
    base_speed
    traits
    feature_grants
    choice_groups
    prerequisites
    tags
    source_metadata
```

Species grants feed normal feature/effect/movement/sense systems.

## 14.6 Background/origin

```text
BackgroundDefinition
    id
    name
    ability_score_options
    feat_grants
    skill_proficiencies
    tool_proficiencies
    equipment_options
    feature_grants
    tags
    source_metadata
```

## 14.7 Ability scores and derived values

```text
AbilityState
    base_score
    permanent_adjustments
    temporary_modifiers
    effective_score
    modifier
```

Derived values—proficiency, saves, skills, defense, initiative, speed, HP/resource maxima, and spellcasting values—are calculated projections, not independently mutable fields.

Ability generation policies may include:

```text
fixed_array
point_allocation
deterministic_random_roll
manual_dm_authorized
imported
custom
```

Random generation is server-side and auditable.

## 14.8 Skills and proficiencies

D&D-style skills are separate from videogame-style talent trees.

```text
SkillDefinition
    id
    name
    governing_ability
    ruleset_id
    tags
```

```text
ProficiencyState
    proficiency_id
    proficiency_type
    rank
    source_ids
```

Ranks may include none, half, proficient, expert, or custom.

Knowledge is separately represented through facts, lore entries, discovered locations, identified creatures/items, and known languages.

## 14.9 Classes/subclasses

```text
ClassDefinition
    id
    name
    hit_point_progression
    primary_abilities
    saving_throw_proficiencies
    proficiency_choices
    starting_equipment_choices
    progression_graph_id
    spellcasting_model | null
    resource_definitions
    tags
```

```text
SubclassDefinition
    id
    parent_class_id
    name
    prerequisites
    progression_nodes
    tags
```

## 14.10 Higher-level and multiclass creation

Higher-level creation resolves choices in valid sequential advancement order. Multiclass characters use total level plus per-class levels.

```text
CharacterProgressionState
    total_level
    class_levels[]
    progression_graph_states[]
    pending_advancement_session_id | null
```

The result must be equivalent to legal sequential advancement under the pinned ruleset.

## 14.11 Character lifecycle

```text
draft
active
inactive
retired
unavailable
archived
```

Commands include activate, deactivate, retire, archive, restore, and ownership transfer. Defeat/revival-like gameplay states use rules/conditions rather than deleting history.

## 14.12 Import/export/templates

Templates are definitions. Imported characters enter a validation session and cannot inject server IDs, permissions, or event history. Exports contain snapshot, portable definition references, source provenance, and schema version.

---

# 15. Progression and skill/talent trees

The engine uses a generic directed progression graph rather than hard-coded `if level == ...` logic.

```text
ProgressionGraph
    id
    ruleset_id
    name
    node_ids
    edge_ids
    respec_policy
```

```text
ProgressionNode
    id
    graph_id
    node_type
    name
    rank_count
    cost
    prerequisites
    exclusive_group | null
    grants
    effects
    tags
    ui_metadata
```

```text
ProgressionEdge
    from_node_id
    to_node_id
    requirement
```

Node types may include class/subclass features, feats, ability improvements, skill upgrades, spell unlocks, powers, passives, actions, reactions, resource upgrades, movement upgrades, and custom nodes.

The graph supports:

- linear class progression;
- branching trees;
- mutually exclusive paths;
- ranked nodes;
- level/ability/proficiency/node prerequisites;
- quest/achievement prerequisites for custom rulesets;
- progression currency;
- respec policies;
- temporary/campaign-granted nodes;
- hidden nodes revealed by discovery.

The SRD package maps conventional class progression conservatively onto this model; custom rulesets may expose WoW/Final-Fantasy-style trees.

## 15.1 Advancement policies

```text
experience_points
milestone
session_based
quest_based
skill_use
custom
```

```text
AdvancementState
    character_level
    experience
    advancement_points
    pending_level_ups
    progression_currency
```

A level-up is a transactional resumable advancement session until all choices validate.

---

# 16. Campaign creation and configuration

Campaign creation is also a resumable workflow.

```text
CampaignCreationSession
    id
    owner_user_id
    ruleset_id
    ruleset_version
    status
    selected_template
    options
    validation_errors
```

Suggested flow:

```text
ChooseRuleset
    -> ChooseCampaignTemplate
    -> ConfigureGameModes
    -> ConfigureTime
    -> ConfigureProgression
    -> ConfigureWorld
    -> ConfigureSpatialModel
    -> ConfigureContentPacks
    -> ConfigurePlayerRules
    -> ConfigureLogging
    -> Validate
    -> FinalizeCampaign
```

## 16.1 Campaign configuration

```text
CampaignConfig
    ruleset_id
    ruleset_version
    combat_timing_mode
    turn_deadline
    reaction_deadline
    timeout_policy
    progression_policy
    resting_policy
    spatial_policy
    world_clock_policy
    difficulty_policy
    death_policy
    visibility_policy
    dice_visibility
    logging_policy
    content_pack_ids
    house_rule_ids
```

Campaign configuration changes are versioned for replay.

## 16.2 Campaign templates

Examples:

```text
classic_turn_based
fast_timed_turns
active_time_party_rpg
real_time_action_rpg
real_time_with_pause
sandbox_world
```

Templates provide defaults but do not bypass normal validation.

---

# 17. Membership, parties, sessions, adventures, scenes, and encounters

## 17.1 Campaign membership/control

```text
CampaignMembership
    campaign_id
    user_id
    role
    controlled_actor_ids
    permissions
```

Roles:

```text
owner
dungeon_master
player
spectator
service
```

Actor control is server-authoritative.

## 17.2 Party/group

```text
Party
    id
    campaign_id
    name
    member_actor_ids
    formation
    marching_order
    shared_resource_refs
    leader_actor_id | null
```

NPC companions may belong to parties. Party membership is independent from user membership.

## 17.3 Game session

```text
GameSession
    id
    campaign_id
    status
    opened_at
    closed_at
    world_time_at_open
    participating_members
    active_party_ids
    notes
```

Statuses:

```text
scheduled
open
paused
closed
abandoned
```

Session boundaries support recap/analytics but do not necessarily pause world simulation.

## 17.4 Adventure/episode

Optional organizational grouping for quests, locations, and scenes; it is not a new rules authority.

## 17.5 Scene

```text
Scene
    id
    location_id
    scene_type
    participant_actor_ids
    object_ids
    spatial_instance_id
    visibility_state
    status
```

Scene types include exploration, social, encounter, travel, downtime, and custom.

## 17.6 Encounter

```text
Encounter
    id
    scene_id
    encounter_type
    timing_policy
    status
    participant_ids
    side_or_faction_assignments
    timeline_id
    start_sequence
    end_sequence | null
```

Statuses:

```text
pending
positioning
active
paused
resolving
completed
cancelled
```

Encounter lifecycle defines joins/leaves, positions, start, pause/resume, victory/end conditions, rewards, cleanup, reaction-window closure, movement reconciliation, and release of reserved actions/resources.

---

# 18. Living world, calendar, travel, weather, and environment

The same scheduler drives combat and non-combat world time.

```text
World
    id
    campaign_id
    name
    calendar_id
    current_time
    regions
    world_state
    global_variables
```

Hierarchy:

```text
World
    Region
        Location
            Area / Scene / Map
                SpatialAdapter state
```

World creation may be authored, imported, procedural, AI-assisted through typed commands, or incrementally assembled.

## 18.1 Calendar

```text
CalendarDefinition
    units
    eras
    formatting
```

World time uses a canonical simulation timestamp plus calendar projection.

## 18.2 World clock policies

```text
explicit_only
while_session_open
always_simulated
scaled_real_time
custom
```

## 18.3 Travel

Travel is an action/process:

```text
origin
destination
route
party
pace
estimated_simulation_duration
encounter_event_hooks
resource_effects
```

It can resolve as a summary or finer segments by campaign policy.

Marching order/formation can determine encounter-start positions.

## 18.4 Weather/environment

Weather/environment state is versioned and scheduled. Rules/content decide whether it has mechanical effects.

## 18.5 NPC schedules

NPC activities, shop hours, travel, faction actions, and other world processes use scheduled events on the same simulation timeline.

Combat should ultimately be one high-intensity state of the same living world rather than an unrelated engine.

---

# 19. Exploration, social interaction, and dialogue

Generic exploration intents may include:

```text
Move
Travel
Search
Study
Scout
Interact
Open
Close
Use
Climb
Jump
Swim
Rest
Camp
Forage
Track
Investigate
Listen
Observe
```

Possible exploration events:

```text
LocationEntered
LocationExited
LocationDiscovered
PathDiscovered
FactLearned
ObjectDiscovered
TrapDetected
ResourceFound
EncounterTriggered
WorldEventObserved
```

Social commands may include Talk, Influence, Trade, OfferItem, RequestItem, AskQuestion, Intimidate, Persuade, Deceive, Perform, and UseObject.

Text does not directly mutate game state; consequences flow through typed rules/effects.

## 19.1 Dialogue state machine

```text
DialogueDefinition
    nodes
    transitions
    entry_conditions
```

```text
DialogueNode
    speaker
    text_key_or_content_ref
    choices
    actions
    requirements
    visibility
```

AI may propose dialogue text/intents, but consequences still resolve through normal commands.

---

# 20. Quests, factions, reputation, and relationships

## 20.1 Quest objective graph

```text
QuestDefinition
    id
    name
    prerequisites
    objective_graph
    rewards
    failure_conditions
    visibility
```

```text
QuestObjectiveNode
    id
    predicate
    prerequisites
    completion_mode
    failure_predicate
    visibility
```

Support sequential, parallel, optional, mutually exclusive, hidden, timed, and repeatable objectives.

Predicates may include visiting a location, acquiring an item, defeating/interacting with an actor, surviving until a time, discovering facts, reaching reputation, dialogue branches, and custom typed predicates.

Quest state is projected from authoritative events.

## 20.2 Factions and relationships

```text
Faction
    id
    relationships_to_factions
    tags
```

```text
RelationshipState
    subject_ref
    object_ref
    metrics
    discovered_traits
    history_summary
```

Campaigns may use numeric or tiered relationship/reputation models.

---

# 21. Inventory, equipment, economy, trade, rewards, and crafting

## 21.1 Items

```text
ItemDefinition
    id
    name
    item_type
    weight
    value
    stack_policy
    equip_slots
    requirements
    grants
    actions
    effects
    tags
```

```text
ItemInstance
    id
    definition_id
    owner_or_container
    quantity
    durability | null
    charges | null
    custom_state
```

Commands include acquire, drop, transfer, equip, unequip, use, consume, split/merge stack, store, and retrieve.

## 21.2 Inventories

Inventories may belong to actors, parties, containers, vendors, vehicles, locations, or campaign services.

```text
Inventory
    id
    owner_ref
    slots_or_capacity_policy
    item_instances
    currency_wallet_id | null
```

## 21.3 Currency

```text
CurrencyDefinition
    id
    key
    precision
    exchange_group | null
```

```text
Wallet
    balances
```

Currency changes are commands/events.

## 21.4 Vendors/trade

```text
VendorState
    inventory_id
    pricing_policy
    availability_schedule
    relationship_modifiers
```

Trade validates and reserves both sides, then commits atomically.

## 21.5 Rewards/loot

```text
RewardDefinition
    currency
    item_grants
    progression_grants
    reputation_changes
    feature_grants
    custom_effects
```

Random loot uses deterministic RNG and records resolved definition references.

## 21.6 Crafting

```text
RecipeDefinition
    inputs
    tools_or_capabilities
    prerequisites
    duration
    checks
    outputs
    failure_policy
```

Crafting progresses on simulation time; requests never block for game-time duration.

---

# 22. Rest, recovery, cooldowns, and regeneration

Rest is a first-class scheduled process.

```text
RestInstance
    id
    participants
    rest_type
    start_time
    scheduled_end_time
    interruption_policy
    status
```

Rules determine recovery at start, during, or completion.

Cooldowns and regeneration are scheduled state transitions. Real-time clients may see `ready_at`; turn-based clients may see remaining rounds/turns, both derived from the same scheduler.

---

# 23. AI and Dungeon Master boundaries

## 23.1 AI controllers

```text
game state projection
    -> AI context
    -> intent
    -> intent translator
    -> typed command
    -> normal validation
    -> deterministic resolution
    -> events
```

AI controllers only receive visibility-filtered knowledge and cannot bypass action discovery/permissions.

Controller handoff, timeouts, external-service circuit breakers, and fallback behavior must be explicit.

## 23.2 Dungeon Master authority

DM powers are privileged commands, not arbitrary DB writes.

Examples:

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

Overrides generate auditable events with principal/reason metadata.

---

# 24. Logging and history

There are four separate logging concepts.

## 24.1 Domain event log — authoritative

Append-only source for replay, state reconstruction, branching, save/load, verification, and gameplay history.

## 24.2 Player-facing game/combat log

A projection of domain events for readable history, narration, accessibility, spectators, and combat-log UI.

Verbosity levels may include:

```text
minimal
normal
detailed
debug_rules
```

## 24.3 Administrative audit log

Records DM overrides, permissions, content changes, campaign configuration, moderation/admin operations, and actor-control changes.

Entries include principal, correlation/request IDs, reason, timestamp, and related events.

## 24.4 Operational logs

Structured infrastructure/application diagnostics. They are not game state and are not needed for replay.

Common fields:

```text
request_id
correlation_id
campaign_id
actor_id
command_id
event_id
stream_id
stream_version
simulation_time
```

## 24.5 Log/history query endpoints

```text
GET /api/v1/campaigns/{campaign_id}/events
GET /api/v1/campaigns/{campaign_id}/game-log
GET /api/v1/encounters/{encounter_id}/combat-log
GET /api/v1/characters/{character_id}/history
GET /api/v1/campaigns/{campaign_id}/audit-log
```

Filters include sequence/time ranges, type, actor, encounter, correlation ID, visibility, limit, and cursor.

---

# 25. Replay, snapshots, branching, and schema evolution

A campaign supports:

```text
ReplayFromStart
ReplayFromSnapshot
InspectStateAtSequence
InspectStateAtSimulationTime
CreateBranchFromSequence
CompareBranches
```

Branching UX can remain post-v1.0, but deterministic replay primitives must exist.

## 25.1 Event schema versioning

Each event has `event_type` and `schema_version`.

Old events are read through deterministic upcasters:

```text
stored_v1 -> upcast_v2 -> upcast_v3 -> current_reader
```

Historical payloads are not silently rewritten simply because application code changed.

## 25.2 Projection versioning

```text
projection_type
schema_version
last_event_sequence
build_version
```

All projections have deterministic rebuild paths.

## 25.3 Retention

Retention policies are separate for authoritative events, audit logs, operational logs, WebSocket buffers, and analytics.

Authoritative history required to restore an active campaign cannot be expired unless an archival/compaction format preserves replay semantics.

---

# 26. REST API contract

Initial API domains converge toward:

```text
/api/v1/rulesets
/api/v1/content-packs
/api/v1/character-creation-sessions
/api/v1/characters
/api/v1/campaign-creation-sessions
/api/v1/campaigns
/api/v1/worlds
/api/v1/regions
/api/v1/locations
/api/v1/scenes
/api/v1/parties
/api/v1/sessions
/api/v1/actors
/api/v1/encounters
/api/v1/timelines
/api/v1/actions
/api/v1/commands
/api/v1/events
/api/v1/effects
/api/v1/conditions
/api/v1/items
/api/v1/inventories
/api/v1/abilities
/api/v1/features
/api/v1/quests
/api/v1/dialogues
/api/v1/factions
/api/v1/vendors
/api/v1/recipes
```

Prefer one typed command gateway to dozens of state-mutating endpoints.

## 26.1 Command envelope

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

Principal identity/roles are derived by the server, never trusted from payload fields.

## 26.2 Command receipt

```text
CommandReceipt
    command_id
    status
    accepted_at
    resulting_event_ids
    resulting_sequence_range | null
    rejection | null
```

Statuses:

```text
accepted
rejected
already_processed
conflict
pending_external_resolution
```

Ordinary game commands should resolve synchronously to authoritative acceptance/rejection. Pending external resolution is reserved for explicitly external integrations.

## 26.3 Error taxonomy

Required machine-readable codes:

```text
invalid_schema
unauthenticated
forbidden
not_found
state_conflict
idempotency_conflict
invalid_choice
prerequisite_failed
resource_insufficient
target_invalid
out_of_range
not_actor_ready
deadline_expired
action_not_available
ruleset_incompatible
content_dependency_error
campaign_locked
rate_limited
internal_error
service_unavailable
```

Errors include stable code, human-readable message, correlation ID, and structured details; ordinary clients never receive stack traces.

## 26.4 Query/version contract

Historical-capable queries accept `as_of_sequence` and responses carry:

```text
campaign_id
projection_sequence
projection_schema_version
content_lock_hash
payload
```

Unbounded collections use opaque cursor pagination.

`/api/v1` versions the transport contract; payload schemas are independently versioned. Prefer additive changes; breaking changes require explicit version/deprecation handling.

---

# 27. Character and campaign projections

## 27.1 Character sheet

```text
CharacterSheet
    identity
    species
    background
    classes
    level
    abilities
    saves
    skills
    proficiency_bonus
    defenses
    hit_points
    resources
    speeds
    senses
    languages
    features
    feats
    progression
    attacks
    actions
    reactions
    inventory
    equipment
    spellcasting
    conditions
    effects
```

This is a read projection, never a mutable aggregate payload.

## 27.2 Campaign dashboard

```text
CampaignDashboard
    campaign_summary
    world_time
    active_session
    party
    active_encounters
    current_location
    quests
    recent_game_log
    visible_scheduled_world_events
    connected_members
```

Role/visibility policy controls fields.

## 27.3 Dynamic UI metadata

Definitions may include non-authoritative presentation hints:

```text
label
description
icon_key
category
sort_order
ui_group
recommended_control
```

Generic clients can use these to build character creators, progression trees, action bars, inventories, quest journals, and campaign setup interfaces.

---

# 28. WebSocket live protocol

Suggested connection:

```text
/api/v1/ws/campaigns/{campaign_id}
```

Subscription channels may include:

```text
campaign.*
world.*
scene.*
encounter.*
actor.*
timeline.*
quest.*
dialogue.*
system.*
```

## 28.1 Handshake

Client authenticates and supplies interests plus last acknowledged sequence.

```text
ConnectionReady
    connection_id
    campaign_sequence
    heartbeat_interval
    resync_required
```

## 28.2 Ordered delivery/resume

Visible events carry monotonic ordering. If missed events remain buffered, replay from the last acknowledged sequence. Otherwise return `resync_required`.

## 28.3 Snapshot + delta

Reconnect flow:

1. fetch current projection snapshot;
2. record snapshot sequence;
3. subscribe from `snapshot_sequence + 1`;
4. apply deltas in order.

## 28.4 Backpressure

Outbound buffers are bounded.

- coalesce replaceable projection notifications;
- never silently drop authoritative events;
- disconnect slow clients with a resumable reason if needed;
- reconnect/resync must be deterministic.

Heartbeats/presence are ephemeral unless a campaign rule explicitly makes connectivity part of gameplay.

Events are filtered/redacted before enqueueing.

---

# 29. Persistence, concurrency, and transaction model

Recommended initial persistence stack:

```text
PostgreSQL
SQLAlchemy 2.x async
asyncpg
Alembic
```

Potential tables/projections:

```text
campaigns
campaign_config_revisions
campaign_content_locks
ruleset_installations
content_pack_installations
event_streams
domain_events
snapshots
projection_versions
command_receipts
transactional_outbox
actors
encounters
timelines
sessions
```

## 29.1 Atomic command commit

Where feasible, one transaction commits:

```text
command receipt
new domain events
stream version update
transactional outbox
critical read-your-writes projections
```

WebSocket publication happens after durable commit via outbox/event publishing.

## 29.2 Async/non-blocking requirements

All request-path DB/network I/O is async-safe. Never use ordinary blocking locks or blocking clients on the event loop.

CPU-heavy pathfinding, imports/exports, large replays, and simulation batches run through bounded worker execution or job infrastructure rather than blocking async request handling.

## 29.3 Concurrency

Use optimistic stream versions and/or campaign-level serialization where rules require it. Commands carry idempotency keys so retries cannot duplicate actions.

## 29.4 Migration domains

Keep separate:

- database schema migrations;
- event upcasters;
- projection migrations/rebuilds;
- content-pack/campaign state migrations.

## 29.5 Integrity

Enforce event sequence uniqueness and optional chained/hash checkpoints. Canonical state hashes support verification/testing.

Redis may later support ephemeral coordination/pub-sub/cache but should not be the sole authoritative state store.

---

# 30. Authentication, authorization, security, and abuse controls

```text
Principal
    user | service
    authenticated_identity
    campaign_memberships
    actor_control_grants
```

Permission examples:

```text
campaign.read
campaign.configure
campaign.admin
actor.read
actor.control
scene.admin
content.install
audit.read
spectate
```

DM is a permission bundle, not a magic database bypass.

Apply configurable rate limits to authentication, command submission, expensive queries, exports, and subscriptions while preserving idempotent retry behavior.

Imported content, biographies, dialogue, asset metadata, and third-party pack text are untrusted input. Validate schemas, sizes, references, and markup. Never execute pack text as server code.

Secrets/API keys/tokens must never appear in campaign events, game logs, exports, or client-visible error details.

---

# 31. Assets, localization, accessibility, and units

## 31.1 Asset references

```text
AssetRef
    id
    media_type
    uri_or_storage_key
    content_hash
    license_metadata
    variants
```

Assets may represent portraits, map backgrounds, icons, audio references, handouts, and scene art. Rules should not depend on a client-engine-specific object.

## 31.2 Localization

```text
LocalizedTextRef
    key
    fallback
```

Rules identifiers remain locale-independent.

## 31.3 Units

Store canonical internal units per ruleset/spatial adapter and expose conversion/display metadata. Do not mix display units with authoritative state.

## 31.4 Accessibility metadata

Definitions may carry semantic descriptions/non-visual labels so keyboard, screen-reader, terminal, and text clients can present the same rules correctly.

---

# 32. Import/export and portable packages

## 32.1 Character export

Contains:

```text
format_version
character_snapshot
content_refs
source_metadata
required_pack_refs
optional_presentation_metadata
```

No auth/session/control-grant data.

## 32.2 Campaign export

Modes:

```text
snapshot_export
full_replay_export
```

Full replay includes event streams, snapshots/checkpoints, pinned content locks, configuration revisions, and locally owned content definitions where licensing permits.

## 32.3 Content-pack archive

Includes manifest, definitions, migrations, localization resources, and declared assets. Installation validates hashes, schemas, licensing metadata, dependencies, and namespaces.

## 32.4 Import staging

Imports always enter staging/validation before explicit activation. They never mutate a live campaign on upload alone.

---

# 33. Reliability, backup, restore, and crash recovery

Back up at minimum:

- PostgreSQL authoritative data;
- content-pack storage;
- campaign-local assets needed for restoration;
- migration metadata;
- deployment encryption/key references where appropriate.

A backup is only considered valid after an automated restore can reconstruct campaigns and verify event/projection integrity.

Deployments document their own RPO/RTO targets.

On restart:

1. load durable scheduler/timeline state;
2. rebuild/verify pending scheduled events;
3. restore or expire decision windows using reconnect policy;
4. resume transactional outbox publication;
5. verify projection lag;
6. pass readiness checks before accepting traffic.

Wall-clock deadlines store enough durable data for restart recovery.

---

# 34. Observability and analytics

Metrics should include:

```text
commands_per_second
command_acceptance_latency
command_rejection_by_code
event_append_latency
events_per_second
projection_lag
scheduler_lag
ready_actor_count
action_window_expirations
websocket_connections
websocket_delivery_lag
websocket_resync_count
outbox_backlog
db_pool_saturation
replay_events_per_second
content_validation_failures
snapshot_duration
```

Tracing propagates request/correlation/command IDs through rules resolution, persistence, outbox publication, and WebSocket delivery.

Analytics consume a separate event pipeline and are never required for authoritative command processing.

---

# 35. Testing strategy

## 35.1 Unit tests

Pure deterministic domain behavior without HTTP/DB dependencies.

## 35.2 Rules conformance

Maintain a feature matrix mapping every implemented SRD rules/content category to tests and source provenance.

## 35.3 Determinism/replay

Run identical command streams twice and compare canonical events/state hashes. Rebuild state from events and compare against live projections.

## 35.4 Creation workflows

Test valid/invalid character and campaign paths, upstream-choice invalidation, higher-level starts, multiclass prerequisites, draft resume/expiry, and campaign restrictions.

## 35.5 Timing/action matrix

Representative actions run under every supported mode:

```text
turn_based
timed_turn_based
active_time
real_time_with_pause
real_time
hybrid
```

Test interruption, timeout, reconnect, simultaneity, stale commands, and idempotent retries.

## 35.6 Visibility tests

Golden tests ensure player, party, spectator, DM, and service projections never leak unauthorized fields.

## 35.7 Content compatibility

Test install, dependencies, conflicts, upgrade, rollback, migration, and content-lock replay.

## 35.8 Replay/migration fixtures

Retain historical golden event streams from older schema versions and prove current code can upcast/replay them.

## 35.9 Persistence failure tests

Inject transaction failure, outbox delay, duplicate delivery, projection rebuild, process restart during decision windows, and DB reconnect scenarios.

## 35.10 API/live contract tests

Validate OpenAPI schemas, examples, error codes, auth, pagination, idempotency, WebSocket resume, snapshot+delta, and backpressure behavior.

## 35.11 Property-based testing

Use Hypothesis for dice bounds, resource accounting, stream versions, scheduler ordering, effect expiration, progression prerequisites, and invariant checking.

## 35.12 Performance

Before v1.0 establish measurable p50/p95/p99 command latency, append throughput, replay throughput, WebSocket fanout, active-campaign capacity, and projection-lag profiles. The benchmark harness is mandatory even if deployment targets differ.

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

Potential later additions:

```text
Redis          ephemeral coordination/pub-sub/cache only
OpenTelemetry  traces/metrics
Prometheus     metrics
structlog      structured logging
orjson         serialization where evidence supports it
```

Dependency additions should be evidence-driven.

---

# 37. Proposed repository structure

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
│       │   ├── characters/
│       │   ├── campaigns/
│       │   ├── parties/
│       │   ├── sessions/
│       │   ├── scenes/
│       │   ├── encounters/
│       │   ├── timeline/
│       │   ├── actions/
│       │   ├── effects/
│       │   ├── spatial/
│       │   ├── perception/
│       │   ├── inventory/
│       │   ├── progression/
│       │   ├── quests/
│       │   ├── dialogue/
│       │   ├── economy/
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
│       │   ├── projections/
│       │   └── outbox/
│       └── infrastructure/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── rules/
│   ├── determinism/
│   ├── replay/
│   ├── visibility/
│   ├── migration/
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

`PLAN.md` is the single authoritative roadmap. Future architectural changes should update this file and, when the decision is non-trivial or irreversible, add an ADR under `docs/decisions/`.

---

# 38. Implementation roadmap

## v0.1 — Deterministic Core + Shared Contracts

### Goal

Create the smallest authoritative engine capable of accepting typed commands and producing reproducible versioned events.

### Deliverables

- [ ] Python 3.12+ project scaffold.
- [ ] FastAPI application factory.
- [ ] Pydantic v2 command/event schemas.
- [ ] stable IDs, namespaced keys, `DefinitionRef`.
- [ ] common `RequirementExpr`, `ChoiceGroup`, `Grant`, visibility, and source metadata.
- [ ] campaign aggregate.
- [ ] actor aggregate foundation.
- [ ] command bus.
- [ ] command envelope/receipt and error taxonomy.
- [ ] deterministic RNG/dice service.
- [ ] append-only in-memory event store for tests.
- [ ] PostgreSQL async event store.
- [ ] stream versioning.
- [ ] command idempotency.
- [ ] event schema versions/upcaster interface.
- [ ] snapshots interface.
- [ ] projection version model.
- [ ] transactional outbox interface.
- [ ] canonical state hashing.
- [ ] deterministic replay/golden fixtures.
- [ ] health/readiness endpoints.

### Exit criteria

Same initial state + content lock + RNG seed + command stream produces byte-equivalent canonical results, and older fixture events can enter the current reader through version seams.

---

## v0.2 — First-Class Time + Universal Actions

### Goal

Make one scheduler authoritative for combat/world events and one action transaction model usable by every timing mode.

### Deliverables

- [ ] `SimulationClock` and timeline aggregate.
- [ ] scheduled-event priority queue abstraction.
- [ ] deterministic tie-breaking.
- [ ] pause/resume and game-time advancement.
- [ ] delayed/periodic/cancelled/rescheduled events.
- [ ] actor readiness state.
- [ ] turn/round policy interface.
- [ ] `turn_based`.
- [ ] `timed_turn_based`.
- [ ] `active_time`.
- [ ] `real_time_with_pause`.
- [ ] `real_time`.
- [ ] `hybrid` policy composition.
- [ ] durable wall-clock action/reaction deadlines.
- [ ] timeout policies including `forfeit_turn`.
- [ ] readiness/cooldown/cast-time scheduling.
- [ ] generic `ActionDefinition` and `ActionInstance`.
- [ ] cost reservation/payment/refund semantics.
- [ ] interruption semantics.
- [ ] available-action discovery foundation.
- [ ] movement action foundation.
- [ ] deterministic simultaneous-command ordering.
- [ ] rest/cooldown/regeneration process foundation.

### Exit criteria

One sample action/encounter runs under every supported timing mode without replacing the underlying runtime, with deterministic timeout/reconnect behavior.

---

## v0.3 — SRD Combat Runtime + Encounter Lifecycle

### Goal

Implement licensed combat foundations through the SRD 5.2.1 rules package.

### Deliverables

- [ ] ruleset manifest/registry and SRD attribution.
- [ ] generic resolution context/outcome primitive.
- [ ] abilities/checks/saves.
- [ ] initiative.
- [ ] turn/action resources.
- [ ] attacks, damage, healing.
- [ ] advantage/disadvantage-style modifier framework where licensed.
- [ ] critical-result framework where licensed.
- [ ] health/recovery projection.
- [ ] conditions.
- [ ] reactions/interrupts.
- [ ] Ready-style triggered actions where licensed.
- [ ] encounter state machine and participant join/leave.
- [ ] encounter cleanup/reward hook.
- [ ] server-authoritative combat movement.
- [ ] legal target discovery.
- [ ] combat-log projection.
- [ ] encounter history queries.
- [ ] rule-trace debugging.
- [ ] conformance tests.

### Exit criteria

A thin client can run a complete basic encounter without embedding combat rules.

---

## v0.4 — Effect/Resource/Ability Runtime + Progression Primitives

### Goal

Make mechanics data-driven and provide the primitives needed for classes, spells, powers, talent trees, and advanced conditions.

### Deliverables

- [ ] modifier/effect pipeline.
- [ ] `FeatureDefinition`.
- [ ] `ResourceDefinition`/state and recovery policies.
- [ ] `AbilityDefinition` for spells/powers/techniques.
- [ ] conditions integrated with effects.
- [ ] triggers, durations, stacking, periodic/area effects.
- [ ] maintenance/concentration-style hooks.
- [ ] temporary grants and expiration.
- [ ] `ProgressionGraph`, nodes, edges.
- [ ] prerequisite evaluator.
- [ ] ranked/mutually-exclusive choices.
- [ ] grant/revoke semantics.
- [ ] progression respec policy.
- [ ] progression graph version/migration seam.

### Exit criteria

Representative abilities, conditions, class features, and progression choices can be expressed primarily through reusable definitions/effects instead of custom handlers.

---

## v0.5 — Spatial Authority + Perception + Exploration

### Goal

Make the server authoritative for space and knowledge without coupling to one client representation.

### Deliverables

- [ ] spatial adapter contract.
- [ ] theater-of-mind, graph, square-grid, and continuous-2D adapters.
- [ ] occupancy, distance, pathfinding hooks, terrain cost, LOS, cover, area queries.
- [ ] movement path validation.
- [ ] real-time trajectory contract.
- [ ] senses/perception API.
- [ ] hidden-state/knowledge projection.
- [ ] actor/party/campaign discovery scopes.
- [ ] terrain definitions.
- [ ] world objects/interactables.
- [ ] containers.
- [ ] hazard/environment hooks.
- [ ] scene lifecycle.
- [ ] exploration/travel commands.
- [ ] location/fact discovery.
- [ ] party marching-order/formation foundation.

### Exit criteria

The same encounter/exploration scene works through at least two spatial adapters, while unauthorized clients receive only visibility-filtered knowledge.

---

## v0.6 — Complete Character Runtime

### Goal

Support complete API-driven character creation, character sheets, advancement, and optional skill/talent trees.

### Deliverables

- [ ] character-creation sessions/drafts.
- [ ] ruleset-driven step graph.
- [ ] draft dependency invalidation/revalidation.
- [ ] class/subclass selection.
- [ ] species/background/languages.
- [ ] ability-score generation/assignment policies.
- [ ] skills/tool proficiencies.
- [ ] equipment/items.
- [ ] feats/features.
- [ ] spells/powers/loadouts.
- [ ] identity/appearance/biography.
- [ ] validation/finalization.
- [ ] higher-level creation.
- [ ] multiclass creation/advancement.
- [ ] character lifecycle states.
- [ ] character template/import/export validation.
- [ ] character sheet/skills/features/inventory/spellcasting/resource/action projections.
- [ ] character history.
- [ ] advancement sessions.
- [ ] XP/milestone/progression-point policies.
- [ ] SRD class progression mapped to progression graphs.
- [ ] custom branching talent trees/respec hooks.
- [ ] content-lock compatibility tests.

### Exit criteria

A generic client can discover creation choices, create/validate/save/load a complete character, render its sheet and legal actions, and advance it without local rules logic.

---

## v0.7 — Campaign Creator + Living World + Economy

### Goal

Create complete persistent campaigns beyond combat.

### Deliverables

- [ ] campaign-creation sessions/drafts/templates.
- [ ] timing/progression/rest/spatial/world-clock/visibility/logging configuration.
- [ ] content-pack dependency resolver.
- [ ] campaign content locks/revisions.
- [ ] house-rule sets.
- [ ] campaign memberships/control grants.
- [ ] party model and marching order.
- [ ] game-session model.
- [ ] optional adventure grouping.
- [ ] world/region/location hierarchy.
- [ ] calendar/clock policies.
- [ ] travel process.
- [ ] NPC schedules.
- [ ] weather/environment.
- [ ] factions/reputation/relationships.
- [ ] quest objective graphs.
- [ ] dialogue state machine.
- [ ] inventory ownership model.
- [ ] currency/wallets.
- [ ] vendors/trade.
- [ ] loot/rewards.
- [ ] crafting/recipes.
- [ ] game-log and audit-log projections.
- [ ] role-aware historical queries.

### Exit criteria

A client can create a campaign from nothing, attach characters, explore/travel/interact/trade/craft, run social/quest/world systems, enter combat, and inspect history entirely through the API.

---

## v0.8 — Intelligent and Scripted Actors

### Goal

Allow AI/scripted controllers to use the same legal command surface as humans.

### Deliverables

- [ ] controller interface.
- [ ] scripted controller.
- [ ] utility-AI controller.
- [ ] perception/knowledge input only through filtered projections.
- [ ] goals/tactical scoring/schedules/memory hooks.
- [ ] intent-to-command boundary.
- [ ] optional external LLM adapter.
- [ ] AI Dungeon Master command surface.
- [ ] controller handoff/reconnect semantics.
- [ ] external-controller timeout/circuit-breaker policies.
- [ ] deterministic scripted-controller fixtures.

### Exit criteria

An encounter and basic living-world loop can operate with AI/scripted NPCs while all actions remain rules-validated, authorized, and replayable.

---

## v0.9 — Universal Client API

### Goal

Stabilize contracts so clients become presentation layers.

### Deliverables

- [ ] stable `/api/v1` REST surface.
- [ ] complete error/version/deprecation contract.
- [ ] OpenAPI contract/examples.
- [ ] authentication/authorization.
- [ ] character/campaign creator schema discovery.
- [ ] progression tree rendering metadata.
- [ ] character/campaign projections.
- [ ] available-action/target discovery.
- [ ] event/history cursor contracts.
- [ ] WebSocket handshake/subscriptions/resume/backpressure.
- [ ] snapshot + delta synchronization.
- [ ] movement trajectory events.
- [ ] role-aware visibility.
- [ ] localization/units/accessibility metadata.
- [ ] asset-reference APIs.
- [ ] import/export APIs.
- [ ] rate-limit semantics.
- [ ] Python SDK.
- [ ] generated/open SDK contract tests.
- [ ] reference terminal and WebSocket clients.

### Exit criteria

A thin client can discover capabilities, create/load a campaign and character, join a session, explore, interact, play encounters, receive live events, reconnect safely, and inspect world/quest/history without embedding SRD logic.

---

## v1.0 — Production-Ready SRD 5.2.1 RPG Engine API

### Goal

Deliver a stable, reusable, documented API-first RPG simulation platform.

### Deliverables

- [ ] stable core domain interfaces.
- [ ] stable command/event/query schemas.
- [ ] SRD 5.2.1-compatible rules package and CC attribution.
- [ ] deterministic replay suite.
- [ ] event upcast fixtures across released schemas.
- [ ] projection rebuild tooling.
- [ ] content-pack upgrade/rollback tests.
- [ ] sample campaign, characters, encounters, quests, and world content.
- [ ] API/ruleset/client-authoring documentation.
- [ ] deployment/migration/backup documentation.
- [ ] PostgreSQL migrations.
- [ ] observability baseline.
- [ ] security/authorization audit.
- [ ] visibility-leak tests.
- [ ] load/latency benchmark harness and documented target profile.
- [ ] automated backup/restore verification.
- [ ] crash recovery of timelines/decision windows.
- [ ] terminal reference client.
- [ ] release/versioning policy.
- [ ] complete acceptance matrix below.

### v1.0 success statement

A third-party developer can build a turn-based, timed-turn, ATB-style, real-time-with-pause, or real-time fantasy RPG client using the same server, without modifying the authoritative core or duplicating hidden rules.

---

# 39. v1.0 end-to-end acceptance matrix

A v1.0 release is not complete until automated reference scenarios prove the following through public interfaces.

## Rules/content setup

1. Discover engine/API versions.
2. Discover installed rulesets.
3. Validate/install compatible content packs.
4. Resolve dependencies into a deterministic campaign content lock.
5. Configure a typed house-rule set.

## Campaign creation

6. Begin/resume a campaign draft.
7. Choose ruleset/template.
8. Configure combat timing and timeout behavior.
9. Configure world clock, rest, progression, visibility, logging, spatial, and content policies.
10. Create world/region/location/scene data.
11. Finalize the campaign.
12. Add members and roles.
13. Create a party and marching order.
14. Open a game session.

## Character creation

15. Begin/resume a character draft.
16. Choose class/origin/species/background/languages as supported.
17. Assign abilities/proficiencies/equipment/features/spells-or-powers.
18. Change an upstream selection and prove downstream revalidation works.
19. Create a higher-level character through sequentially valid choices.
20. Validate/finalize the character.
21. Add the character to the party.
22. Query the complete visibility-filtered character sheet.

## Exploration/world interaction

23. Enter a scene/location.
24. Query perceived entities rather than omniscient state.
25. Move using authoritative movement.
26. Discover hidden/unknown information through rules-driven play.
27. Interact with a world object/container.
28. Transfer/store/retrieve inventory items.
29. Complete a trade transaction.
30. Start and complete crafting using simulation time.
31. Travel with marching order and world-time advancement.
32. Observe a scheduled world/environment event.

## Social/quest systems

33. Start a dialogue state machine.
34. Resolve a conditional dialogue choice.
35. Change faction/reputation/relationship state through events.
36. Accept a quest.
37. Advance parallel/conditional objectives.
38. Complete/fail a time-sensitive objective deterministically.

## Encounter/action/timing systems

39. Create/start an encounter from scene state.
40. Establish participants/positions.
41. Query available actions and valid target schemas.
42. Execute movement and a rules action.
43. Spend/reserve/recover resources.
44. Apply/remove a condition/effect.
45. Open and resolve an interrupt/reaction window.
46. Interrupt/cancel an action and verify refund policy.
47. Exercise a timed decision window that expires deterministically.
48. Reconnect/recover during an active decision window.
49. Exercise simultaneous/conflicting commands and deterministic ordering.
50. Complete encounter cleanup and rewards.

## Progression

51. Grant XP/milestone/progression currency according to campaign policy.
52. Begin an advancement session.
53. Unlock/choose progression nodes.
54. Validate mutually exclusive/prerequisite choices.
55. Complete advancement and update derived projections.

## Logs/history/replay

56. Query player game log.
57. Query combat log.
58. Query character history.
59. Query DM/admin audit log with proper authorization.
60. Inspect state at an earlier sequence.
61. Rebuild projections from events.
62. Replay from snapshot and from start to the same canonical state.
63. Replay an older-schema golden event stream through upcasters.

## Live client sync

64. Connect WebSocket and subscribe.
65. Receive ordered visibility-filtered events.
66. Disconnect, miss events, reconnect, and resume.
67. Force buffer exhaustion and verify resumable resync instead of silent loss.
68. Fetch snapshot + delta without a race gap.

## Content evolution/recovery

69. Propose a content-pack revision.
70. Validate dependency/migration compatibility.
71. Activate a new campaign content revision.
72. Replay old history with old pinned definitions and new history with the new revision.
73. Roll back a failed content revision when allowed.
74. Back up the deployment.
75. Restore into a clean environment and verify campaign/event/projection hashes.
76. Restart during scheduled/decision state and recover without duplicate actions.

If all 76 scenarios pass while a thin client never embeds hidden game rules or mutates authoritative state, v1.0 meets the architecture goal.

---

# 40. Definition of a planning-complete subsystem

No future subsystem is considered planned merely because its interface or noun appears in this document.

Before implementation, each core subsystem must define:

- authoritative state;
- content/definition schema;
- commands;
- events;
- queries/projections;
- lifecycle/state machine;
- permissions;
- visibility rules;
- concurrency/idempotency behavior;
- persistence/replay behavior;
- migration/version behavior;
- error/failure behavior;
- WebSocket/live behavior where relevant;
- import/export behavior where relevant;
- automated tests and milestone exit criteria;
- source/license provenance for distributable content.

This checklist applies to every new roadmap item.

---

# 41. Definition of done for every milestone

A milestone is not complete until:

- [ ] code is typed;
- [ ] async paths avoid blocking operations;
- [ ] unit tests pass;
- [ ] integration tests pass where applicable;
- [ ] deterministic/replay invariants pass where applicable;
- [ ] visibility tests pass where applicable;
- [ ] public schemas are documented;
- [ ] migrations/upcasters are included for persistence/schema changes;
- [ ] architecture changes are documented;
- [ ] licensed-content attribution remains correct;
- [ ] no client-specific assumptions leak into the core;
- [ ] command/event versions remain compatible or migration is documented;
- [ ] observable failures produce actionable structured logs;
- [ ] concurrency/idempotency behavior is tested;
- [ ] milestone exit criteria are demonstrated through public APIs.

---

# 42. First implementation slice

The first implementation PR should remain intentionally small and prove the architecture rather than importing large content catalogs.

Suggested scope:

```text
src/rpg_engine_api/
    app.py
    config.py
    domain/
        ids.py
        definitions.py
        requirements.py
        choices.py
        visibility.py
        commands.py
        events.py
        dice.py
        campaign.py
        actor.py
    application/
        command_bus.py
    persistence/
        event_store.py
        outbox.py
    api/
        health.py
        commands.py

tests/
    unit/
    determinism/
    replay/
```

Prove at minimum:

```text
CreateCampaign command
    -> CampaignCreated event

CreateActor command
    -> ActorCreated event

RollDice internal operation
    -> DiceRolled event

replay(events)
    -> identical state hash

repeat command with same idempotency key
    -> no duplicate event

stale expected stream version
    -> deterministic state_conflict
```

Do not start by importing hundreds of spells, monsters, classes, or items. Prove the runtime seams first.

---

# 43. Deliberately post-v1.0 work

These are explicitly future scope, not unresolved placeholders:

- distributed zone/shard servers;
- large-world interest management across many processes;
- cross-region actor migration;
- massive-scale presence;
- advanced behavior trees/planners beyond the initial controller contract;
- rich procedural world-generation tooling;
- full visual map editor;
- marketplace/distribution service for third-party content packs;
- hosted billing/entitlements;
- advanced collaborative authoring;
- polished branching/alternate-timeline UX beyond underlying replay primitives;
- engine-specific Godot/Unity rendering integrations beyond reference SDK/client contracts.

A later large-world roadmap can build these on top of the v1.0 deterministic simulation/runtime boundary.

---

# 44. Long-term product goal

The finished engine should support configurations such as:

```text
ruleset = srd_5_2_1
combat_mode = turn_based
```

```text
ruleset = srd_5_2_1
combat_mode = timed_turn_based
turn_deadline = 15s
timeout_policy = forfeit_turn
```

```text
ruleset = srd_5_2_1
combat_mode = active_time
```

```text
ruleset = srd_5_2_1
combat_mode = real_time
```

without replacing the game-state model, rules runtime, action system, scheduler, persistence layer, or client API.

The central architectural constraint is therefore:

> **The engine understands time, events, actions, readiness, deadlines, resources, effects, space, knowledge, and rules—not one hard-coded notion of a turn or one hard-coded kind of client.**
