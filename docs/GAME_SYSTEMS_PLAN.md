# RPG Engine API — Game Systems Plan

## Status

**Project:** `rpg-engine-api`  
**Purpose:** Expand the core architecture plan into concrete game-creation and gameplay systems.  
**Rules foundation:** SRD 5.2.1-compatible rules package with generic extension points.  
**Design goal:** Any client should be able to create characters, create campaigns, discover legal actions, move actors, play encounters, inspect logs, advance progression, and manage a persistent world entirely through the API.

---

## 1. Scope

This document plans the player-facing and campaign-facing systems that sit on top of the deterministic command/event runtime described in `PLAN.md`.

The engine should provide first-class support for:

- character creation;
- species/ancestry choices;
- backgrounds and origins;
- classes and subclasses/archetypes;
- D&D-style skills and proficiencies;
- extensible skill/talent/progression trees;
- feats and feature choices;
- ability scores;
- spells and powers;
- equipment and inventories;
- character advancement;
- campaign creation;
- world creation;
- campaign rules/options;
- player/DM roles;
- quests and objectives;
- movement and spatial actions;
- combat and non-combat actions;
- exploration;
- interaction and dialogue;
- event logs;
- combat/game logs;
- administrative audit logs;
- server/diagnostic logs;
- save/load/replay;
- deterministic branching and historical inspection.

These systems must remain client-independent. A Godot client, browser, TUI, mobile application, AI controller, or other client should all use the same command/query/event interfaces.

---

## 2. Official rules model and extension boundary

The initial compatible rules package should be based on the licensed **SRD 5.2.1** material.

Current 2024/5.5e-style character creation is organized around choosing a class, determining origin (background, species, and languages), determining ability scores, choosing alignment, and filling in character details. The engine should be able to model that workflow without hard-coding it as the only possible character-creation workflow.

Use current terminology in the SRD rules package:

```text
species
background
class
subclass
feat
skill proficiency
tool proficiency
language
ability score
feature
spell
```

For compatibility with custom/legacy rulesets, the generic engine may support aliases such as `race` or `ancestry`, but SRD 5.2.1-facing schemas and documentation should prefer `species`.

### Skill tree boundary

Traditional D&D character progression is not fundamentally a free-form videogame skill tree.

Therefore the engine should distinguish:

```text
Skill
    a rules-defined proficiency/check category

ProgressionGraph
    an extensible tree/graph of unlockable features, talents, feats, powers, upgrades, or choices
```

The SRD rules package can represent normal level-based class progression as a constrained progression graph, while custom rulesets can expose Final-Fantasy/WoW-style branching talent trees without changing the core engine.

### Licensing boundary

Only content licensed for redistribution should be stored in distributable rules packages. Publicly viewable D&D Beyond material is useful for understanding behavior but must not be treated as automatically reusable content.

Official references:

- https://www.dndbeyond.com/srd
- https://www.dndbeyond.com/sources/dnd/br-2024/creating-a-character
- https://www.dndbeyond.com/sources/dnd/br-2024/character-origins
- https://www.dndbeyond.com/sources/dnd/br-2024/playing-the-game
- https://creativecommons.org/licenses/by/4.0/

---

# Character Systems

## 3. Character creation must be a resumable workflow

Character creation should not be a single giant `POST /characters` request.

Use a server-authoritative **character creation session/draft**.

Conceptual state:

```text
CharacterCreationSession
    id
    owner_user_id
    campaign_id | null
    ruleset_id
    ruleset_version
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

A draft can be saved and resumed from any client.

### Why a workflow object matters

It supports:

- UI wizards;
- terminal clients;
- API clients;
- AI-assisted creation;
- optional campaign restrictions;
- partial saves;
- validation after each choice;
- ruleset-specific ordering;
- higher-level starting characters;
- multiclass characters;
- custom rulesets;
- deterministic event history.

---

## 4. Character creation step graph

Do not hard-code a fixed page order in the API.

A ruleset should expose a dependency graph similar to:

```text
ChooseClass
    |
DetermineOrigin
    +-- ChooseBackground
    +-- ChooseSpecies
    +-- ChooseLanguages
    |
DetermineAbilityScores
    |
ChooseClassOptions
    |
ChooseProficiencies
    |
ChooseEquipment
    |
ChooseSpellsOrPowers
    |
ChooseAlignment
    |
CharacterDetails
    |
Validate
    |
Finalize
```

The SRD package can expose its normal workflow while another ruleset might require a different order.

### Suggested commands

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

### Suggested events

```text
CharacterCreationStarted
CharacterClassSelected
CharacterSubclassSelected
CharacterSpeciesSelected
CharacterBackgroundSelected
CharacterLanguageSelected
CharacterAbilityScoresAssigned
CharacterProficiencySelected
CharacterEquipmentSelected
CharacterFeatSelected
CharacterFeatureOptionSelected
CharacterSpellSelected
CharacterIdentityUpdated
CharacterDraftValidated
CharacterCreationFinalized
CharacterCreationCancelled
```

Every choice should be auditable and replayable.

---

## 5. Character identity and descriptive data

Mechanical state and presentation metadata should be separated.

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

Rulesets should decide which fields have mechanical meaning.

Clients should be able to add presentation-only metadata without modifying rules calculations.

---

## 6. Species / ancestry model

Use a generic species definition:

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

Character state records the selected definition and resolved choices:

```text
CharacterSpecies
    species_id
    selected_size
    selected_traits
    selected_options
```

The engine should support custom rulesets that call this concept `ancestry`, `heritage`, or `race` without creating separate core implementations.

### Requirements

- species may grant features;
- species may expose choices;
- species may affect movement modes;
- species may define size choices;
- species may grant senses or passive capabilities;
- species grants must feed the normal effect/capability system;
- species must never require client-side rules logic.

---

## 7. Background / origin model

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

The SRD-compatible ruleset should be able to express current origin behavior through data rather than custom endpoints.

Character state should record both the selected background and each resolved option.

---

## 8. Ability scores and derived statistics

Core character data should distinguish base values, permanent grants, temporary modifiers, and derived values.

```text
AbilityState
    base_score
    permanent_adjustments
    temporary_modifiers
    effective_score
    modifier
```

The ruleset should calculate derived values such as:

```text
proficiency bonus
saving throw modifiers
skill modifiers
armor class
initiative
speed
passive values
hit point maximum
resource maximums
spellcasting values
```

Derived values should normally be projections/calculations, not independently editable fields.

---

## 9. Skills, proficiencies, expertise, and knowledge

D&D-style skills are distinct from progression trees.

Model rules skills generically:

```text
SkillDefinition
    id
    name
    governing_ability
    ruleset_id
    tags
```

Character proficiency state:

```text
ProficiencyState
    proficiency_id
    proficiency_type
    rank
    source_ids
```

Possible ranks:

```text
none
half
proficient
expert
custom
```

The rules runtime calculates the final modifier.

Also plan separate knowledge state:

```text
KnownFact
LoreEntry
DiscoveredLocation
IdentifiedCreature
IdentifiedItem
KnownLanguage
```

This allows campaigns to track what a character actually knows rather than assuming the client knows everything in the database.

---

## 10. Class and subclass model

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

Character class state:

```text
CharacterClassState
    class_id
    level
    subclass_id | null
    selected_options
    resources
```

Multiclassing should be represented as multiple `CharacterClassState` records if the active ruleset supports it.

---

# Progression and Skill Trees

## 11. Generalized progression graph

The engine should implement progression as a directed graph, not as class-specific `if level == ...` code.

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

Supported node types may include:

```text
class_feature
subclass_feature
feat
ability_score_improvement
skill_upgrade
spell_unlock
power
passive
action
reaction
resource_upgrade
movement_upgrade
weapon_mastery
custom
```

### Graph capabilities

The graph should support:

- linear level progression;
- branching trees;
- mutually exclusive branches;
- ranked nodes;
- prerequisite levels;
- prerequisite abilities;
- prerequisite proficiencies;
- prerequisite nodes;
- prerequisite quests/achievements for custom rulesets;
- resource costs such as talent points;
- respec rules;
- temporary unlocks;
- campaign-granted nodes;
- hidden nodes revealed by discovery.

### Standard SRD mapping

The SRD ruleset can use this structure conservatively:

```text
class level
    -> class feature grants
    -> subclass choice at rules-defined level
    -> feat/ability choices where applicable
    -> spell/resource progression
```

A custom videogame ruleset could instead expose a broad talent tree without changing the core API.

### Commands

```text
SpendProgressionPoint
UnlockProgressionNode
IncreaseProgressionNodeRank
ChooseProgressionOption
RespecProgressionNode
ResetProgressionGraph
```

### Events

```text
ProgressionPointGranted
ProgressionNodeUnlocked
ProgressionNodeRankIncreased
ProgressionChoiceMade
ProgressionNodeRespecced
ProgressionGraphReset
FeatureGranted
FeatureRemoved
```

---

## 12. Leveling and advancement

Advancement should be policy-driven.

Potential policies:

```text
experience_points
milestone
session_based
quest_based
skill_use
custom
```

Core state:

```text
AdvancementState
    character_level
    experience
    advancement_points
    pending_level_ups
    progression_currency
```

Suggested commands:

```text
GrantExperience
GrantMilestone
BeginLevelUp
ChooseLevelUpOption
CompleteLevelUp
```

A level-up should be transactional: incomplete choices remain in a pending advancement session until the character is valid.

---

# Campaign Systems

## 13. Campaign creation as a resumable workflow

Campaign creation should mirror character creation.

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

### Commands

```text
BeginCampaignCreation
SetCampaignName
SetCampaignDescription
ChooseRuleset
ChooseCampaignTemplate
ConfigureCombatTiming
ConfigureTimeoutPolicy
ConfigureProgressionPolicy
ConfigureRestPolicy
ConfigureSpatialPolicy
ConfigureWorldClock
InstallContentPack
ConfigurePlayerSlots
ConfigureVisibilityPolicy
ConfigureLoggingPolicy
ValidateCampaignDraft
FinalizeCampaign
```

### Events

```text
CampaignCreationStarted
CampaignRulesetSelected
CampaignTimingConfigured
CampaignProgressionConfigured
CampaignSpatialPolicyConfigured
CampaignContentPackInstalled
CampaignDraftValidated
CampaignCreated
```

---

## 14. Campaign configuration model

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

Examples of timing configuration:

```text
turn_based

timed_turn_based
    decision_deadline = 15s
    timeout_policy = forfeit_turn

active_time
    readiness_policy = ruleset_default

real_time
    authoritative_cooldowns = true
```

Campaign rules should be versioned so replay knows exactly which settings were active when an event occurred.

---

## 15. Campaign templates

Templates can provide defaults without bypassing normal configuration.

Examples:

```text
classic_turn_based
fast_timed_turns
active_time_party_rpg
real_time_action_rpg
real_time_with_pause
sandbox_world
```

A template can configure:

- timing;
- default map adapter;
- progression;
- default content packs;
- visibility;
- rest behavior;
- logging;
- encounter defaults;
- world clock speed.

Templates should be ordinary versioned data.

---

## 16. World creation

Campaigns should contain a world model that may be minimal or extensive.

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

World creation should support:

- manually authored worlds;
- imported campaign packages;
- procedural generation;
- AI-assisted proposals validated into typed commands;
- empty worlds assembled incrementally.

---

## 17. Campaign membership and control

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

Actor control must be server-authoritative.

A client cannot submit an action for an actor unless its authenticated principal has a valid control grant or DM-level permission.

---

# Actions and Movement

## 18. Unified action model

Every action—combat or non-combat—should be described through a common definition.

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

Possible categories:

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

### Action lifecycle

```text
ActionProposed
    -> command validation
    -> ActionDeclared
    -> costs reserved/paid
    -> optional cast/windup
    -> optional reaction windows
    -> resolution
    -> effects/events
    -> cooldown/recovery
    -> ActionCompleted
```

This lifecycle works for turn-based, timed, active-time, and real-time play.

---

## 19. Available action discovery

Clients should never have to guess which buttons/actions are legal.

```http
GET /api/v1/actors/{actor_id}/available-actions
```

Conceptual response:

```json
{
  "actor_id": "actor-1",
  "sequence": 1834,
  "simulation_time": 241.5,
  "decision_deadline": null,
  "actions": [
    {
      "action_id": "move",
      "category": "movement",
      "target_schema": "position",
      "constraints": {
        "remaining_distance": 30
      }
    },
    {
      "action_id": "attack",
      "category": "attack",
      "target_schema": "actor",
      "valid_targets": ["enemy-1"]
    }
  ]
}
```

The response may contain capability schemas rather than exhaustive targets when target sets are large.

---

## 20. Movement must be an authoritative action

Movement should not be a client-side position patch.

Bad:

```http
PATCH /actors/actor-1
{
  "x": 120,
  "y": 450
}
```

Good:

```text
MoveActor
    actor_id
    destination | path | direction
    movement_mode
    client_command_id
```

### Movement modes

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

Rulesets determine which modes an actor can currently use.

### Movement lifecycle

Turn/grid mode:

```text
MoveDeclared
    -> path validation
    -> opportunity/reaction checks
    -> movement cost calculation
    -> ActorMoved
```

Real-time mode:

```text
MovementStarted
    -> authoritative trajectory/path
    -> optional significant waypoint events
    -> interrupts/collisions/effects
    -> MovementCompleted
```

Do not require an authoritative domain event for every rendered frame.

The server should be able to describe a deterministic movement segment/trajectory while clients interpolate presentation locally.

### Spatial adapters

Movement commands must work against:

```text
TheaterOfMindSpace
GraphSpace
SquareGridSpace
HexSpace
Continuous2DSpace
Continuous3DSpace
```

---

## 21. Exploration actions

Plan built-in generic exploration intents such as:

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

The ruleset decides which are explicit actions and which are aliases/compositions.

Exploration can generate:

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

---

## 22. Social and interaction actions

Plan generic commands:

```text
Talk
Influence
Trade
OfferItem
RequestItem
AskQuestion
Intimidate
Persuade
Deceive
Perform
UseObject
ActivateObject
```

Dialogue text and UI choices should not be the authority for game consequences. Consequences resolve through typed actions and rules.

---

# Inventory and Equipment

## 23. Item model

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
    owner/container
    quantity
    durability | null
    charges | null
    custom_state
```

Commands:

```text
AcquireItem
DropItem
TransferItem
EquipItem
UnequipItem
UseItem
ConsumeItem
SplitStack
MergeStack
StoreItem
RetrieveItem
```

Items should be able to grant actions and progression/effect capabilities without client-side implementation.

---

# Quests, Objectives, and Campaign Events

## 24. Quest model

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

Objectives should be event predicates, not UI checkboxes.

Examples:

```text
visit_location
interact_with_actor
acquire_item
defeat_actor
survive_until
discover_fact
complete_dialogue_branch
reach_reputation
world_time_reached
custom_predicate
```

Quest state is projected from authoritative game events.

---

## 25. Campaign/world event model

Distinguish domain events from authored world events.

```text
WorldEventDefinition
    id
    trigger
    prerequisites
    scheduled_time | null
    actions/effects
    visibility
    repeat_policy
```

Examples:

- scheduled weather change;
- NPC departure;
- shop opening;
- faction response;
- quest deadline;
- encounter opportunity;
- environmental change.

The scheduler executes these using the same deterministic timeline as combat.

---

# Logging and History

## 26. Four separate log systems

Do not use one table/file called `logs` for everything.

### 26.1 Domain event log — authoritative

Purpose:

- replay;
- save/load;
- state reconstruction;
- deterministic verification;
- branching history;
- audit of gameplay state transitions.

Examples:

```text
CampaignCreated
CharacterCreated
ActorMoved
AttackResolved
DamageApplied
ItemTransferred
QuestCompleted
WorldTimeAdvanced
```

This is append-only authoritative history.

### 26.2 Player-facing game/combat log

Purpose:

- readable history;
- combat log UI;
- narration feeds;
- spectator feed;
- accessibility.

This should be a **projection** of domain events, not a second authority.

Example entries:

```text
12:04:31  Aria moved 20 ft toward the doorway.
12:04:34  Goblin attacked Aria.
12:04:34  Attack missed.
12:04:38  Aria used an action.
```

Support verbosity levels:

```text
minimal
normal
detailed
debug_rules
```

### 26.3 Administrative audit log

Purpose:

- DM overrides;
- permission changes;
- campaign configuration changes;
- content pack changes;
- moderation/admin operations;
- actor-control changes.

Example:

```text
DungeonMasterOverrideApplied
CampaignRuleChanged
ActorControlGranted
ContentPackInstalled
TimelinePausedByDM
```

Audit entries should record authenticated principal and reason where appropriate.

### 26.4 Application/operational logs

Purpose:

- API diagnostics;
- performance;
- infrastructure failures;
- database errors;
- WebSocket issues;
- tracing.

Use structured logging with fields such as:

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

Operational logs are not game state and must not be needed for replay.

---

## 27. Event log query API

Plan query endpoints:

```text
GET /api/v1/campaigns/{campaign_id}/events
GET /api/v1/campaigns/{campaign_id}/game-log
GET /api/v1/encounters/{encounter_id}/combat-log
GET /api/v1/characters/{character_id}/history
GET /api/v1/campaigns/{campaign_id}/audit-log
```

Filters:

```text
from_sequence
to_sequence
from_simulation_time
to_simulation_time
event_type
actor_id
encounter_id
correlation_id
visibility
limit
cursor
```

Player-facing APIs must apply visibility/redaction rules so hidden DM information is not leaked.

---

## 28. Replay, snapshots, and branching

A campaign should support:

```text
ReplayFromStart
ReplayFromSnapshot
InspectStateAtSequence
InspectStateAtSimulationTime
CreateBranchFromSequence
CompareBranches
```

Post-v1.0, branching can support:

- alternate outcomes;
- debugging;
- GM experimentation;
- simulations;
- AI evaluation;
- spectator replay.

The original event stream remains immutable.

---

# API Surface Expansion

## 29. Character API domains

Plan endpoints around commands/queries rather than arbitrary mutation:

```text
/api/v1/character-creation-sessions
/api/v1/characters
/api/v1/characters/{id}/sheet
/api/v1/characters/{id}/available-actions
/api/v1/characters/{id}/skills
/api/v1/characters/{id}/features
/api/v1/characters/{id}/progression
/api/v1/characters/{id}/inventory
/api/v1/characters/{id}/spells
/api/v1/characters/{id}/history
```

Rules/catalog discovery:

```text
/api/v1/rulesets/{id}/character-creation
/api/v1/rulesets/{id}/classes
/api/v1/rulesets/{id}/species
/api/v1/rulesets/{id}/backgrounds
/api/v1/rulesets/{id}/skills
/api/v1/rulesets/{id}/feats
/api/v1/rulesets/{id}/progression-graphs
```

---

## 30. Campaign API domains

```text
/api/v1/campaign-creation-sessions
/api/v1/campaigns
/api/v1/campaigns/{id}/config
/api/v1/campaigns/{id}/members
/api/v1/campaigns/{id}/events
/api/v1/campaigns/{id}/game-log
/api/v1/campaigns/{id}/audit-log
/api/v1/campaigns/{id}/timeline
/api/v1/campaigns/{id}/world
/api/v1/campaigns/{id}/quests
/api/v1/campaigns/{id}/sessions
```

---

## 31. Action API domains

```text
GET  /api/v1/actors/{id}/available-actions
GET  /api/v1/actions/{action_id}/schema
POST /api/v1/commands
GET  /api/v1/commands/{command_id}
```

Prefer one typed command gateway over dozens of mutating endpoints when possible.

A command receipt should include:

```text
command_id
status
accepted_sequence | null
rejection_code | null
rejection_details | null
resulting_event_ids
```

---

# Client Experience

## 32. Dynamic UI metadata

Ruleset definitions may optionally include presentation hints:

```text
label
description
icon_key
category
sort_order
ui_group
recommended_control
```

These hints are not authoritative rules.

A generic client should be able to generate:

- character-creation forms;
- progression trees;
- action bars;
- inventory screens;
- campaign setup forms;
- combat logs;
- quest journals;

from API schemas and capability metadata.

---

## 33. Character sheet projection

Expose a server-computed character-sheet projection:

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

This is a projection, not a mutable aggregate payload.

---

## 34. Campaign dashboard projection

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
    scheduled_world_events_visible_to_user
    connected_members
```

Different roles receive different projections based on visibility policy.

---

# Data and Source Metadata

## 35. Every rules/content record needs provenance

Definitions should include source metadata:

```text
SourceMetadata
    source_pack_id
    source_version
    license_id
    attribution_id
    source_reference
    content_hash
```

This allows the engine to mix:

- SRD content;
- original project content;
- third-party licensed packs;
- campaign-local homebrew;

while keeping provenance visible.

---

# Revised Milestones

## 36. v0.1 — Deterministic Core

Add foundational schemas needed by later systems:

- [ ] command receipts;
- [ ] source metadata primitive;
- [ ] projection version primitive;
- [ ] visibility metadata;
- [ ] authoritative domain event log;
- [ ] structured correlation/causation identifiers.

---

## 37. v0.2 — Time + Universal Actions

In addition to scheduler work:

- [ ] generic `ActionDefinition`;
- [ ] action lifecycle;
- [ ] action costs;
- [ ] action prerequisites;
- [ ] action targeting schema;
- [ ] action discovery query;
- [ ] movement action foundation.

---

## 38. v0.3 — SRD Combat + Movement

Add:

- [ ] server-authoritative movement;
- [ ] movement modes;
- [ ] Move/Dash/Disengage/Dodge-style action integration where licensed;
- [ ] combat-log projection;
- [ ] encounter history query;
- [ ] legal target discovery.

---

## 39. v0.4 — Effects + Progression Primitives

Add:

- [ ] `FeatureDefinition`;
- [ ] `FeatDefinition`;
- [ ] `ProgressionGraph`;
- [ ] `ProgressionNode`;
- [ ] prerequisite evaluator;
- [ ] grant/revoke semantics;
- [ ] ranked nodes;
- [ ] mutually exclusive choices;
- [ ] respec policy interface.

---

## 40. v0.5 — Spatial + Exploration

Add:

- [ ] movement path validation;
- [ ] travel/exploration commands;
- [ ] location discovery;
- [ ] interaction targets;
- [ ] line-of-sight/visibility projection;
- [ ] real-time movement trajectory contract.

---

## 41. v0.6 — Complete Character Creator

This milestone should be significantly expanded.

### Character creation

- [ ] character-creation sessions/drafts;
- [ ] ruleset-driven creation step graph;
- [ ] class selection;
- [ ] subclass support;
- [ ] species selection;
- [ ] background selection;
- [ ] language selection;
- [ ] ability-score assignment/generation;
- [ ] skill/tool proficiency choices;
- [ ] starting equipment choices;
- [ ] feats;
- [ ] class feature choices;
- [ ] spells/powers;
- [ ] identity/appearance/biography;
- [ ] validation;
- [ ] finalization;
- [ ] import/export schema.

### Character runtime

- [ ] character sheet projection;
- [ ] skills projection;
- [ ] feature projection;
- [ ] equipment/inventory projection;
- [ ] spellcasting projection;
- [ ] available-action projection;
- [ ] character history.

### Progression

- [ ] level advancement session;
- [ ] XP policy;
- [ ] milestone policy;
- [ ] progression points;
- [ ] skill/talent tree API;
- [ ] SRD class progression mapped to progression graphs;
- [ ] custom branching trees;
- [ ] prerequisite validation;
- [ ] respec hooks.

### Exit criteria

A generic client can discover the current ruleset's creation schema, create a complete level-1 character, render the resulting character sheet, inspect its legal actions and progression graph, and advance it without implementing rules locally.

---

## 42. v0.7 — Campaign Creator + Living World

This milestone should include a complete campaign-creation workflow.

### Campaign creation

- [ ] campaign-creation sessions/drafts;
- [ ] ruleset selection;
- [ ] campaign templates;
- [ ] combat timing configuration;
- [ ] timeout policy configuration;
- [ ] progression configuration;
- [ ] spatial model selection;
- [ ] world clock/calendar selection;
- [ ] content-pack selection;
- [ ] visibility policy;
- [ ] player slots/membership defaults;
- [ ] logging policy;
- [ ] validation/finalization.

### World runtime

- [ ] world/region/location hierarchy;
- [ ] world time;
- [ ] travel;
- [ ] NPC schedules;
- [ ] factions/reputation;
- [ ] quests;
- [ ] dialogue;
- [ ] environmental state;
- [ ] scheduled world events.

### Logging/history

- [ ] player game-log projection;
- [ ] campaign event history query;
- [ ] character history query;
- [ ] administrative audit log;
- [ ] role-aware visibility/redaction.

### Exit criteria

A client can create a campaign from nothing, configure its rules/timing, create or attach characters, enter a location, move/interact, start an encounter, complete a quest objective, and inspect a readable historical log entirely through the API.

---

## 43. v0.8 — Intelligent Actors

AI and scripted actors should consume:

- available-action discovery;
- movement/path queries;
- progression state;
- known facts;
- visible world state;
- quest/faction state.

They submit the same commands as human-controlled actors.

---

## 44. v0.9 — Universal Client API

Add stable contracts for:

- [ ] character creator schema discovery;
- [ ] campaign creator schema discovery;
- [ ] progression tree rendering;
- [ ] character sheet projection;
- [ ] campaign dashboard projection;
- [ ] game/combat log streams;
- [ ] event history pagination;
- [ ] movement/trajectory events;
- [ ] content/rules provenance;
- [ ] role-aware visibility.

---

## 45. v1.0 acceptance scenario

A reference integration test should prove this complete flow:

```text
1. Create campaign draft.
2. Choose SRD 5.2.1-compatible ruleset.
3. Configure timed-turn combat with a decision deadline and forfeit policy.
4. Create the world and starting location.
5. Finalize campaign.
6. Begin character creation.
7. Choose class.
8. Choose species.
9. Choose background.
10. Assign ability scores.
11. Resolve skill/tool/language/equipment choices.
12. Finalize character.
13. Add character to campaign.
14. Query character sheet.
15. Query available actions.
16. Move through the world.
17. Interact with an NPC/object.
18. Receive a quest.
19. Enter an encounter.
20. Move during combat.
21. Attack/use abilities under the configured timing model.
22. Handle a turn timeout deterministically.
23. Complete the encounter.
24. Progress a quest objective.
25. Gain advancement.
26. Unlock/choose progression options.
27. Query character history.
28. Query combat log.
29. Query campaign game log.
30. Replay the event stream and verify the same canonical state hash.
```

If a thin client can perform that scenario without embedding game rules, the platform architecture is working.

---

# Design Rules Added by This Plan

1. **Character creation is a workflow, not CRUD.**
2. **Campaign creation is a workflow, not CRUD.**
3. **Species/background/class/features are ruleset data with typed behavior.**
4. **D&D skills and videogame-style skill trees are separate concepts.**
5. **Progression is a generic graph capable of representing normal class levels and custom talent trees.**
6. **Movement is an authoritative action, never a client position patch.**
7. **Real-time movement transmits authoritative paths/trajectories; clients interpolate presentation.**
8. **Available actions are discoverable from the server.**
9. **The domain event log is authoritative; readable logs are projections.**
10. **Audit logs and operational logs are separate from gameplay history.**
11. **Hidden information is protected by role-aware projections and log redaction.**
12. **Every rules/content definition carries source/license provenance.**
13. **All creation, progression, movement, and campaign changes use commands/events.**
14. **No feature in this document should require a particular client engine.**
15. **All asynchronous API/database/network paths must remain non-blocking and concurrency-safe.**
