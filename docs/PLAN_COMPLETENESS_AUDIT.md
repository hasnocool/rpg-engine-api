# RPG Engine API — Plan Completeness Audit and Missing-System Specification

## Status

**Project:** `rpg-engine-api`  
**Document role:** Normative completeness addendum to `PLAN.md` and `docs/GAME_SYSTEMS_PLAN.md`.  
**Rules foundation:** SRD 5.2.1-compatible rules package plus generic extension points.  
**Target:** v1.0 must contain no undefined core gameplay/API placeholders required for a third-party client to create, run, save, replay, and administer a complete campaign.

If this document defines a contract that earlier planning documents only name abstractly, this document is the clarification. If there is a direct conflict, the more explicit contract in this document takes precedence until an ADR supersedes it.

Official rules references used during this audit:

- https://www.dndbeyond.com/srd
- https://www.dndbeyond.com/sources/dnd/br-2024
- https://www.dndbeyond.com/sources/dnd/br-2024/creating-a-character
- https://www.dndbeyond.com/sources/dnd/br-2024/playing-the-game
- https://creativecommons.org/licenses/by/4.0/

The project must continue to redistribute only material for which it has an appropriate license. Publicly readable Basic Rules pages are references for behavior, not an assumption of redistribution rights.

---

# 1. Audit result

The existing plans correctly establish the core direction: deterministic commands/events, first-class time, pluggable rulesets, authoritative actions/movement, character and campaign creation workflows, progression graphs, logging, replay, and thin clients.

The audit found the following systems were either placeholders, implied but not defined, or incomplete enough to create incompatible implementations.

| Gap | Previous state | Resolution in this document |
|---|---|---|
| Shared requirement/choice expression model | implied | defined |
| Feature/resource/spell/condition schemas | partial/placeholders | defined |
| Ruleset/content-pack dependency and conflict rules | missing | defined |
| House-rule model | named only | defined |
| Campaign content lock/version pinning | missing | defined |
| Character draft dependency invalidation | missing | defined |
| Higher-level and multiclass creation | partial | defined |
| Character lifecycle after creation | partial | defined |
| Party/group model | missing | defined |
| Game-session lifecycle | named only | defined |
| Adventure/scene/encounter lifecycle | partial | defined |
| NPC/creature template + actor instancing | partial | defined |
| World objects/interactables/containers | missing | defined |
| Perception, lighting, discovery, hidden state | partial | defined |
| Resource/cooldown/recovery semantics | partial | defined |
| Spell/power casting model | placeholder | defined |
| Health/temporary-health/recovery state | partial | defined |
| Rest lifecycle | named only | defined |
| Economy/currency/trade/vendor model | missing | defined |
| Crafting/recipe model | missing | defined |
| Loot/reward model | missing | defined |
| Calendar/weather/environment policies | partial | defined |
| Party travel/marching order | missing | defined |
| Dialogue state machine | partial | defined |
| Faction/reputation/relationship state | partial | defined |
| Action reservation/interruption/refund rules | missing | defined |
| Command conflict/simultaneity semantics | partial | defined |
| API error taxonomy | missing | defined |
| Cursor/snapshot/version query contracts | partial | defined |
| WebSocket handshake/resume/backpressure | partial | defined |
| Event schema upcasting and projection migration | missing | defined |
| Import/export package formats | placeholder | defined |
| Asset/media references | placeholder | defined |
| Localization/unit conventions | missing | defined |
| Backup/restore/disaster recovery | missing | defined |
| Data retention/privacy boundaries | missing | defined |
| Security/rate-limit/abuse boundaries | partial | defined |
| Full v1.0 end-to-end acceptance matrix | partial | expanded |

Anything deliberately postponed beyond v1.0 is listed explicitly in the final section; it must not be left as an ambiguous placeholder.

---

# 2. Shared domain primitives

Many systems currently use fields such as `prerequisites`, `grants`, `choices`, `visibility`, and `source_metadata`. They must share one typed model instead of inventing a different format in each subsystem.

## 2.1 Stable identifiers

Every durable entity uses opaque stable IDs and a separate human-readable key.

```text
EntityIdentity
    id                 # opaque UUID/ULID-like durable identity
    key                # namespaced stable content key
    display_name_key   # localization key
```

Content keys are namespaced:

```text
srd_5_2_1:class/fighter
my_pack:feature/arcane_training
campaign:homebrew/item/example
```

Display names are never identifiers.

## 2.2 Definition references

```text
DefinitionRef
    pack_id
    pack_version
    key
    content_hash
```

Persist resolved definition references in events that affect replay. A campaign must not silently resolve an old event against a newer rules definition.

## 2.3 Requirement expression

All prerequisites use a common declarative expression tree.

```text
RequirementExpr
    operator
    operands
```

Required operators:

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

A ruleset may register typed predicates, but arbitrary executable code must not be embedded in content payloads.

## 2.4 Choice groups

All creation/progression/content selections use one model.

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

Selections record their source and resolved option ID so future validation can explain why a character has a capability.

## 2.5 Grant model

```text
Grant
    grant_type
    target_ref
    quantity_or_rank
    duration
    stacking_policy
    source_ref
```

Grant types include features, proficiencies, resources, actions, movement modes, senses, languages, items, spells/powers, progression currency, and tags.

## 2.6 Visibility model

```text
VisibilityPolicy
    audience
    discovery_requirement
    redact_fields
```

Audiences:

```text
public
campaign_members
party
controller_only
dm_only
service_only
custom_role
```

Visibility is enforced before serialization, not merely hidden in the client UI.

---

# 3. Rulesets, content packs, and house rules

## 3.1 Ruleset manifest

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

## 3.2 Content pack manifest

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

A pack may contain definitions for classes, species, backgrounds, features, progression graphs, actions, spells/powers, items, creatures, conditions, quests, dialogue, world templates, locations, recipes, and campaign templates.

## 3.3 Campaign content lock

Each finalized campaign receives an immutable content lock for each configuration revision.

```text
CampaignContentLock
    ruleset_ref
    pack_refs[]
    house_rule_set_ref
    schema_versions
    combined_hash
```

Replay always uses the lock active at the event sequence being reconstructed.

## 3.4 Dependency/conflict resolution

Installation must:

1. resolve dependency versions;
2. reject cycles unless explicitly supported;
3. reject incompatible engine/ruleset ranges;
4. reject duplicate un-namespaced keys;
5. apply explicit override precedence only when a pack declares it;
6. create a deterministic ordered lock;
7. validate all references before activation.

No silent last-write-wins behavior.

## 3.5 Mid-campaign pack changes

Installing, upgrading, disabling, or removing content from a live campaign is a privileged versioned command.

```text
ProposeContentRevision
ValidateContentRevision
ActivateContentRevision
RollbackContentRevision
```

Activation must either migrate affected state or fail with a detailed incompatibility report. Existing event history remains bound to its original definitions.

## 3.6 House rules

House rules are typed data, not arbitrary code patches.

```text
HouseRuleDefinition
    id
    target_rule_key
    operation
    parameters
    prerequisites
    compatibility
```

Operations may replace a policy, adjust a numeric parameter, enable/disable a capability, or register a ruleset-defined variant. Every active house-rule set is versioned and included in the campaign content lock.

---

# 4. Character creation and lifecycle completion

## 4.1 Draft dependency invalidation

Changing an upstream choice can invalidate downstream selections.

Example:

```text
class changed
    -> re-evaluate class options
    -> re-evaluate proficiencies
    -> re-evaluate equipment
    -> re-evaluate spell/power choices
    -> retain still-valid selections
    -> mark invalid selections unresolved
```

The server returns:

```text
DraftRevalidationResult
    retained_choices
    invalidated_choices
    new_required_choices
    warnings
```

Never silently discard a player's unrelated valid choices.

## 4.2 Ability-score generation policies

Character creation must support ruleset-defined policies such as:

```text
fixed_array
point_allocation
deterministic_random_roll
manual_dm_authorized
imported
custom
```

Random generation is server-side and produces auditable dice/random events.

## 4.3 Higher-level creation

A creation session may specify a target starting level.

The workflow must resolve, in order:

- level-by-level class allocation;
- subclass/archetype choices;
- feat/feature choices;
- resource progression;
- health progression;
- spell/power progression;
- higher-level starting equipment/wealth policy;
- all prerequisites at each level.

The result must be equivalent to valid sequential advancement under the pinned ruleset.

## 4.4 Multiclass creation and advancement

Use total character level plus per-class level state. Cross-class interactions are resolved by ruleset policies rather than duplicated client logic.

```text
CharacterProgressionState
    total_level
    class_levels[]
    progression_graph_states[]
    pending_advancement_session_id | null
```

## 4.5 Character lifecycle

Required states:

```text
draft
active
inactive
retired
unavailable
archived
```

Rulesets/campaigns may add temporary states. Character history is never deleted merely because the actor leaves active play.

Required lifecycle commands:

```text
ActivateCharacter
DeactivateCharacter
RetireCharacter
ArchiveCharacter
RestoreArchivedCharacter
TransferCharacterOwnership
```

Any rules-driven defeat/revival-style state is represented through conditions/status and campaign policy rather than deleting the character record.

## 4.6 Templates, clone, import, export

Character templates are definitions; characters are instances.

Imports go through a validation session and cannot inject authoritative IDs, permissions, or event history. Export includes the character snapshot, portable definition references, source provenance, and a schema version.

---

# 5. Feature, resource, spell/power, and condition definitions

## 5.1 Feature definition

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

## 5.2 Resource definition

Resources must be generic enough for health, spell slots, class resources, stamina-like custom resources, charges, readiness, and cooldown tokens.

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

Changes are events; derived maxima are calculated from rules state.

## 5.3 Health state

Health-like state is modeled through typed resources and rules, not special client fields.

A convenience projection may expose:

```text
HealthProjection
    current
    maximum
    temporary
    status
    recovery_options
```

Rules determine what happens at zero, recovery, stabilization-like states, and campaign-specific consequences.

## 5.4 Spell/power definition

```text
AbilityDefinition
    id
    key
    ability_type       # spell, power, technique, custom
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

Character state separates:

```text
known
prepared_or_active_loadout
available_resources
cooldowns
```

The ruleset defines how those sets interact.

## 5.5 Condition definition

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

Condition state records source, start sequence/time, duration, stacks, and scheduled expiration.

## 5.6 Rule-resolution pipeline

All attack/check/save-like tests share a generic test-resolution primitive where the ruleset supplies semantics.

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

A debug rules trace is DM/developer-visible only unless campaign policy exposes it.

---

# 6. Party, session, adventure, scene, and encounter lifecycles

The existing plan jumps from campaign to actors/encounters. These intermediate structures are required.

## 6.1 Party/group

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

Party membership is independent of user membership. NPC companions can belong to a party.

Commands:

```text
CreateParty
AddPartyMember
RemovePartyMember
SetMarchingOrder
SetFormation
SetPartyLeader
```

## 6.2 Game session

A campaign can have many play sessions.

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

Session boundaries are useful for recaps and analytics but do not pause world simulation unless the campaign's clock policy says so.

## 6.3 Adventure/episode

Optional organizational object:

```text
Adventure
    id
    campaign_id
    title
    state
    quest_refs
    location_refs
    scene_refs
```

It groups content without becoming a new rules authority.

## 6.4 Scene

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

Scene types can include exploration, social, encounter, travel, downtime, and custom.

## 6.5 Encounter lifecycle

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

Required commands/events cover creation, participant joins/leaves, starting positions, start, pause/resume, end conditions, rewards, and cleanup.

Encounter completion must explicitly release reserved actions/resources, close reaction windows, reconcile movement, and return participants to the containing scene/world state.

---

# 7. NPCs, creatures, world objects, and interactables

## 7.1 Creature/NPC definitions and actor instances

Definitions are templates; actors are mutable instances.

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

NPCs, adversaries, companions, summoned entities, and player characters share the same actor component model where possible.

## 7.2 World objects

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

Object definitions may represent doors, containers, switches, signs, furniture, environmental features, quest objects, resource nodes, and other interactables.

## 7.3 Containers

Containers use the normal inventory system with access rules:

```text
ContainerState
    inventory_id
    access_policy
    open_state
    lock_state
    capacity
```

## 7.4 Hazards and environment effects

Hazards are rules-driven world effects with triggers, checks, conditions, and outcomes. The core does not hard-code specific real-world hazardous procedures; it only provides a generic game-effect framework.

```text
HazardDefinition
    trigger
    detection_rules
    avoidance_rules
    effects
    reset_policy
    visibility
```

## 7.5 Terrain

```text
TerrainDefinition
    movement_costs
    movement_mode_rules
    visibility_modifiers
    environmental_effects
    tags
```

---

# 8. Perception, visibility, stealth, and discovery

This is required for a server-authoritative RPG and cannot remain a UI concern.

## 8.1 Sense model

```text
SenseDefinition
    sense_type
    range
    precision
    requirements
    blockers
```

## 8.2 Lighting/environment visibility

Spatial instances expose environment visibility data through the adapter. A generic interface must answer:

```text
can_perceive(observer, subject)
perception_quality(observer, subject)
known_position(observer, subject)
visible_fields(observer, entity)
```

## 8.3 Hidden state

Hidden information is tracked separately from true authoritative state.

A client receives a **knowledge/visibility projection**, never the omniscient world aggregate.

## 8.4 Discovery

Discovery is event-driven:

```text
EntityDetected
EntityIdentified
LocationDiscovered
FactLearned
MapKnowledgeUpdated
```

Discovery state can be scoped to actor, party, or campaign.

## 8.5 Secret checks

Campaign policy may allow server/DM-only resolution where the existence or result of a test is hidden from players. The event still exists authoritatively with appropriate visibility metadata.

---

# 9. Inventory, currency, economy, trade, crafting, and rewards

## 9.1 Inventory ownership

Inventories may belong to actors, parties, containers, vendors, vehicles/transport, locations, or campaign services.

```text
Inventory
    id
    owner_ref
    slots_or_capacity_policy
    item_instances
    currency_wallet_id | null
```

## 9.2 Currency

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

Currency transfers are commands/events and cannot be client-edited.

## 9.3 Vendors and trade

```text
VendorState
    inventory_id
    pricing_policy
    availability_schedule
    relationship_modifiers
```

Trade is transactional: validate both sides, reserve items/currency, commit atomically, then emit events.

## 9.4 Loot/rewards

```text
RewardDefinition
    currency
    item_grants
    progression_grants
    reputation_changes
    feature_grants
    custom_effects
```

Loot generation uses deterministic RNG when random and records the resulting definition refs.

## 9.5 Crafting

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

Crafting schedules work on the simulation timeline; it must not block an async request for the duration of game time.

---

# 10. World, travel, calendar, weather, and environment

## 10.1 Calendar

```text
CalendarDefinition
    units
    eras
    formatting
```

World time is stored as a canonical simulation timestamp plus calendar projection.

## 10.2 World clock policy

Policies define whether time advances:

```text
explicit_only
while_session_open
always_simulated
scaled_real_time
custom
```

No policy may require a request handler to sleep.

## 10.3 Travel

Travel is an action/process with:

```text
origin
destination
route
party
pace
estimated_simulation_duration
encounter/event hooks
resource effects
```

Travel can be summarized or resolved in finer segments depending on campaign policy.

## 10.4 Marching order and formation

Travel and encounter-start positioning can consume party marching order/formation, allowing the engine to establish deterministic relative positions without client-specific logic.

## 10.5 Weather/environment state

Weather is a versioned world-state component with scheduled transitions and effect hooks. Rulesets/content packs decide whether weather has mechanical consequences.

---

# 11. Quests, dialogue, factions, reputation, and relationships

## 11.1 Quest objective graph

Quest objectives use a graph rather than a flat list.

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

## 11.2 Dialogue state machine

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

A choice can emit typed commands/effects; text never directly mutates state.

## 11.3 Factions

```text
Faction
    id
    relationships_to_factions
    tags
```

## 11.4 Reputation/relationship

Use a generic relationship metric model so campaigns can define numeric or tiered reputation.

```text
RelationshipState
    subject_ref
    object_ref
    metrics
    discovered_traits
    history_summary
```

Changes come from domain events and are rules/content-driven.

---

# 12. Action transaction semantics

The earlier action lifecycle needs explicit state transitions.

## 12.1 Action instance

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

## 12.2 Cost lifecycle

Every cost declares one of:

```text
pay_on_declare
reserve_on_declare_pay_on_execute
pay_on_success
pay_on_completion
```

Each action defines refund behavior for validation failure, cancellation, interruption, and server conflict.

## 12.3 Interruption

Interruption does not mean generic rollback. The action definition/ruleset must specify which already-emitted effects remain and which reservations are released.

## 12.4 Simultaneous commands

The authoritative ordering key is:

```text
simulation_time
scheduler_priority
stream_sequence/tie_breaker
```

Wall-clock arrival time alone must not determine rules outcomes where the timing policy defines simultaneity.

## 12.5 Command conflicts

Use expected stream/projection version where appropriate. A stale command is either safely revalidated against current state or rejected with `state_conflict`; it must never overwrite newer state.

---

# 13. Rest, recovery, cooldowns, and scheduled resource regeneration

Rest is a first-class process/action, not an instant patch.

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

Rules determine recovery grants at start, during, or completion.

Cooldowns and regeneration are scheduled state transitions. Real-time mode may expose `ready_at`; turn-based mode may expose remaining rounds/turns. Both derive from the same timeline model.

---

# 14. Logging, replay, retention, and historical correctness

## 14.1 Event immutability

Domain events are append-only. Corrections are new compensating/admin events, never destructive edits to history.

## 14.2 Event schema versioning

Each event has `event_type` and `schema_version`.

Old events are read through deterministic upcasters:

```text
stored event v1
    -> upcast v2
    -> upcast v3
    -> current domain reader
```

Never rewrite historical event payloads solely to upgrade application code unless a controlled migration explicitly records that action.

## 14.3 Projection versioning

Each projection records:

```text
projection_type
schema_version
last_event_sequence
build_version
```

Projections are rebuildable from authoritative events.

## 14.4 Human-readable game log renderer

Game-log formatting is versioned independently from domain events. Re-rendering old events with a new renderer is allowed, but stored snapshots/exports may retain the renderer version used at export time.

## 14.5 Audit integrity

Administrative audit entries include authenticated principal, request/correlation ID, before/after references where appropriate, reason, timestamp, and resulting domain events.

## 14.6 Retention

Define separate policies for:

- authoritative campaign events;
- audit logs;
- operational logs;
- transient WebSocket delivery buffers;
- analytics.

Authoritative events required for campaign replay cannot be expired while the campaign remains restorable unless a documented archival/compaction format preserves replay semantics.

---

# 15. API contract completion

## 15.1 Command envelope

```text
CommandEnvelope
    command_id
    command_type
    schema_version
    campaign_id
    actor_id | null
    principal_context
    expected_stream_version | null
    idempotency_key
    client_sequence | null
    payload
```

Authenticated principal data is derived by the server; clients cannot self-assert roles through payload fields.

## 15.2 Command receipt

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

`pending_external_resolution` is allowed only for explicitly asynchronous external integrations; ordinary game commands should resolve to an authoritative acceptance/rejection without background promises to clients.

## 15.3 Error taxonomy

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

Errors return a stable code, human-readable message, correlation ID, and structured details. Do not expose stack traces to ordinary clients.

## 15.4 Queries

Queries include `as_of_sequence` where historical inspection is supported and return:

```text
campaign_id
projection_sequence
projection_schema_version
content_lock_hash
payload
```

## 15.5 Pagination

All unbounded collections use opaque cursor pagination. Cursors are scoped to filters and ordering; clients must not construct them manually.

## 15.6 API versioning

`/api/v1` is transport-contract versioning. Payload schemas have their own versions. Additive fields are preferred; breaking changes require a new API/schema version and a documented deprecation window.

---

# 16. WebSocket/live protocol completion

## 16.1 Handshake

Client connects, authenticates, then sends subscription interests including campaign, channels, and last acknowledged sequence.

Server responds with:

```text
ConnectionReady
    connection_id
    campaign_sequence
    heartbeat_interval
    resync_required
```

## 16.2 Ordered delivery

Campaign-visible events carry a monotonic visible sequence or a pair of authoritative sequence + redaction-safe ordering token.

## 16.3 Resume

If the server retains all missed events, it replays from the client's last acknowledged sequence. Otherwise it returns `resync_required` with a snapshot/query cursor.

## 16.4 Snapshot + delta

A reconnecting client can:

1. fetch current projection snapshot;
2. record snapshot sequence;
3. subscribe from `snapshot_sequence + 1`;
4. apply deltas in order.

## 16.5 Backpressure

Connections have bounded outbound buffers. Policy is explicit:

- coalesce replaceable projection notifications;
- never silently drop authoritative game events;
- disconnect slow clients with a resumable reason when necessary;
- allow reconnect/resync.

## 16.6 Heartbeats and presence

Heartbeats detect stale connections. Presence is ephemeral and not authoritative gameplay history unless a campaign rule explicitly turns connectivity into a game event.

## 16.7 Visibility

Events are filtered/redacted before enqueueing to a connection. A spectator or player must never receive DM-only payloads and rely on the UI not to show them.

---

# 17. Persistence, transactions, and migrations

## 17.1 Atomic command commit

For a single authoritative command, commit together where feasible:

```text
command receipt
new domain events
stream version update
transactional outbox records
critical projection updates required for read-your-writes
```

WebSocket publication occurs after durable commit through the outbox/event publisher.

## 17.2 Async/non-blocking requirements

All request-path DB/network operations use async-safe drivers. CPU-heavy pathfinding, simulation batches, imports, exports, and large replays are isolated from the event loop through bounded worker execution or offline job infrastructure.

Do not use blocking sleeps for simulation time.

## 17.3 Database migrations

Alembic migrations change storage schema. Event upcasters change historical event read compatibility. Content-pack migrations change campaign/content definitions. These are separate migration domains and must not be conflated.

## 17.4 Projection rebuilds

Every projection has a deterministic rebuild path and can be rebuilt into a shadow table/version before atomic activation for large migrations.

## 17.5 Integrity

Persist event stream sequence uniqueness and optional chained/hash checkpoints for detecting corruption. Canonical state hashes are test/verification artifacts, not substitutes for access control.

---

# 18. Authentication, authorization, security, and abuse controls

## 18.1 Principal model

```text
Principal
    user | service
    authenticated_identity
    campaign_memberships
    actor_control_grants
```

Authorization evaluates both role and resource scope.

## 18.2 Permission examples

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

DM is a role bundle, not a magical bypass in database code.

## 18.3 Rate limits

Apply configurable limits to authentication attempts, command submission, expensive queries, history exports, and WebSocket subscriptions. Limits must not cause duplicate actions when a client retries with the same idempotency key.

## 18.4 Input safety

Treat imported content, biographies, dialogue, asset metadata, and third-party pack text as untrusted input. Validate schemas, sizes, references, and allowed markup. Never execute content-pack text as server code.

## 18.5 Secrets

No secrets, API keys, auth tokens, or private connector credentials belong in campaign events, game logs, exported content packs, or client-visible error details.

---

# 19. Assets, localization, accessibility metadata, and units

## 19.1 Asset references

The engine stores references, not client-engine-specific objects.

```text
AssetRef
    id
    media_type
    uri_or_storage_key
    content_hash
    license_metadata
    variants
```

Possible uses: portraits, map backgrounds, icons, audio references, handouts, and scene art.

Rules must never depend on a particular asset existing unless the content pack validates it as a required dependency.

## 19.2 Localization

User-facing content supports localization keys plus optional fallback text.

```text
LocalizedTextRef
    key
    fallback
```

Rules identifiers remain locale-independent.

## 19.3 Units

Store canonical internal units per ruleset/spatial adapter and expose conversion metadata. Do not mix display units with authoritative numeric state.

## 19.4 Accessibility metadata

Action/feature/content definitions may include concise descriptions, semantic categories, and non-visual labels so clients can build keyboard-, screen-reader-, and text-friendly interfaces without reinterpreting game rules.

---

# 20. Import/export and portable campaign packages

## 20.1 Character export

Contains:

```text
format_version
character_snapshot
content_refs
source_metadata
required_pack_refs
optional presentation metadata
```

No auth/session/control-grant data.

## 20.2 Campaign export

Two modes:

```text
snapshot_export
full_replay_export
```

Full replay includes event streams, snapshots/checkpoints, pinned content-lock references, campaign configuration revisions, and necessary locally owned content definitions where licensing permits.

## 20.3 Content-pack archive

Pack archive includes manifest, definitions, migrations, localization resources, and declared assets. Installation validates hashes, schemas, licensing metadata, dependencies, and namespaces before activation.

## 20.4 Import staging

Imports land in a staging/validation state first. They never mutate a live campaign until explicit validation and activation succeed.

---

# 21. Reliability, backup, restore, and disaster recovery

## 21.1 Backups

Back up at minimum:

- PostgreSQL authoritative data;
- content-pack storage;
- campaign-local assets needed for restoration;
- migration metadata;
- encryption/key references as appropriate to deployment.

## 21.2 Restore test

A backup is not considered valid until an automated restore test can reconstruct campaigns and verify event/projection integrity.

## 21.3 Recovery targets

Deployments should document target RPO/RTO rather than hard-code one policy in the engine.

## 21.4 Crash recovery

On restart:

1. load durable scheduler/timeline state;
2. rebuild/verify pending scheduled events;
3. re-open or expire wall-clock decision windows according to campaign reconnect policy;
4. resume outbox publication;
5. verify projection lag;
6. accept traffic only after readiness checks pass.

Wall-clock deadlines must store enough durable information to recover after process restart.

---

# 22. Observability and analytics boundaries

Required metrics now include:

```text
command_acceptance_latency
command_rejection_by_code
event_append_latency
projection_lag
scheduler_lag
ready_actor_count
action_window_expirations
websocket_delivery_lag
websocket_resync_count
outbox_backlog
DB_pool_saturation
replay_events_per_second
content_validation_failures
```

Analytics consume events through a separate pipeline and may never become required for authoritative command processing.

Tracing should propagate request/correlation/command IDs from API ingress through rules resolution, persistence, outbox publication, and WebSocket delivery.

---

# 23. Testing matrix required for completeness

## 23.1 Rules conformance

Maintain a feature matrix mapping every implemented SRD rules/content category to tests and source provenance.

## 23.2 Creation workflows

Test:

- every valid character creation path;
- invalid choices;
- changing upstream choices;
- higher-level starts;
- multiclass prerequisites;
- cancel/resume/expire drafts;
- campaign-specific restrictions.

## 23.3 Action/timing matrix

Representative actions must run under every timing mode supported by their ruleset:

```text
turn_based
timed_turn_based
active_time
real_time_with_pause
real_time
hybrid
```

Test interruptions, timeouts, reconnects, simultaneous actions, stale commands, and idempotent retries.

## 23.4 Visibility tests

Golden tests assert that player, party, spectator, DM, and service projections never leak fields outside their visibility policy.

## 23.5 Content compatibility

Test install, dependency resolution, upgrade, rollback, missing dependency, conflict, migration, and content-lock replay.

## 23.6 Replay/migration

Keep golden historical event streams from older schema versions and prove current code can upcast/replay them to expected canonical state.

## 23.7 Persistence failure tests

Inject transaction failure, outbox delay, duplicate delivery, projection rebuild, restart during a decision window, and DB reconnect scenarios.

## 23.8 API contract tests

OpenAPI schemas, command/event examples, pagination, error codes, auth boundaries, idempotency, and WebSocket resumption all require automated contract tests.

## 23.9 Performance targets

Before v1.0 define measurable budgets for command p50/p95/p99, event append throughput, replay throughput, WebSocket fanout, active campaign count, and projection lag. The exact numbers are deployment targets, but the benchmark harness is a v1.0 requirement.

---

# 24. Revised milestone closure checklist

This supplements the milestone lists in the existing plans.

## v0.1 — Deterministic Core

Must additionally close:

- [ ] stable ID/key/reference primitives;
- [ ] common requirement expression;
- [ ] common choice/grant models;
- [ ] command envelope and error taxonomy;
- [ ] event schema versioning/upcaster interface;
- [ ] transactional outbox interface;
- [ ] projection version model;
- [ ] content/rules definition references in events;
- [ ] integrity/replay golden test fixture.

## v0.2 — Time + Universal Actions

Must additionally close:

- [ ] `ActionInstance` state machine;
- [ ] cost reserve/pay/refund policies;
- [ ] interruption semantics;
- [ ] durable wall-clock deadline recovery;
- [ ] simultaneous-command deterministic ordering;
- [ ] cooldown/regeneration scheduling;
- [ ] rest-process foundation.

## v0.3 — Combat Runtime

Must additionally close:

- [ ] generic test-resolution primitive;
- [ ] health/recovery projection;
- [ ] condition definition/state;
- [ ] encounter lifecycle and cleanup;
- [ ] participant join/leave rules;
- [ ] reward hook;
- [ ] rule-trace debugging surface.

## v0.4 — Effects + Progression

Must additionally close:

- [ ] `FeatureDefinition`;
- [ ] `ResourceDefinition`;
- [ ] `AbilityDefinition` for spells/powers/techniques;
- [ ] unified requirement/choice/grant integration;
- [ ] resource recovery policies;
- [ ] temporary grants and expiration;
- [ ] progression graph migration/versioning.

## v0.5 — Spatial + Exploration

Must additionally close:

- [ ] senses/perception API;
- [ ] hidden-state projection;
- [ ] discovery scopes;
- [ ] terrain definitions;
- [ ] world objects/interactables;
- [ ] containers;
- [ ] environmental/hazard effect hooks;
- [ ] scene lifecycle;
- [ ] party marching order/formation.

## v0.6 — Complete Character Runtime

Must additionally close:

- [ ] draft dependency invalidation;
- [ ] ability-generation policies;
- [ ] higher-level creation;
- [ ] multiclass creation/advancement;
- [ ] character lifecycle states;
- [ ] template/import/export validation;
- [ ] resource/spell/power projections;
- [ ] creation compatibility tests against pinned content lock.

## v0.7 — Campaign Creator + Living World

Must additionally close:

- [ ] party model;
- [ ] game-session model;
- [ ] optional adventure grouping;
- [ ] content-pack dependency resolver;
- [ ] campaign content lock;
- [ ] house-rule sets;
- [ ] campaign content revisions;
- [ ] calendar/clock policies;
- [ ] travel process;
- [ ] economy/currency/vendor model;
- [ ] crafting/recipes;
- [ ] loot/reward model;
- [ ] full dialogue state machine;
- [ ] faction/relationship model.

## v0.8 — Intelligent Actors

Must additionally close:

- [ ] AI controllers receive only visibility-filtered knowledge;
- [ ] AI intent cannot bypass action availability;
- [ ] controller handoff/reconnect semantics;
- [ ] deterministic scripted-controller fixtures;
- [ ] external-controller timeouts/circuit breakers.

## v0.9 — Universal Client API

Must additionally close:

- [ ] complete API error contract;
- [ ] cursor/history contracts;
- [ ] snapshot + delta client sync;
- [ ] WebSocket handshake/resume/backpressure;
- [ ] generated/open SDK contract tests;
- [ ] localization and units metadata;
- [ ] asset-reference APIs;
- [ ] import/export APIs;
- [ ] rate-limit semantics;
- [ ] API deprecation/version policy.

## v1.0 — Production-Ready Reference Engine

Must additionally close:

- [ ] backup/restore procedure and automated restore test;
- [ ] event upcast fixtures across released schemas;
- [ ] projection rebuild tooling;
- [ ] content-pack upgrade/rollback tests;
- [ ] security/authorization audit;
- [ ] visibility leak tests;
- [ ] load/latency benchmark harness and documented target profile;
- [ ] crash recovery of decision windows/timeline;
- [ ] full reference campaign acceptance matrix below.

---

# 25. Expanded v1.0 end-to-end acceptance matrix

A v1.0 release is not complete until automated reference scenarios prove all of the following through public interfaces.

## 25.1 Rules/content setup

1. Discover engine/API versions.
2. Discover installed rulesets.
3. Validate/install compatible content packs.
4. Resolve dependencies into a deterministic campaign content lock.
5. Configure a typed house-rule set.

## 25.2 Campaign creation

6. Begin/resume a campaign draft.
7. Choose ruleset/template.
8. Configure combat timing and timeout behavior.
9. Configure world clock, rest, progression, visibility, logging, spatial, and content policies.
10. Create world/region/location/scene data.
11. Finalize the campaign.
12. Add members and roles.
13. Create a party and marching order.
14. Open a game session.

## 25.3 Character creation

15. Begin/resume a character draft.
16. Choose class/origin/species/background/languages as supported by the selected ruleset.
17. Assign abilities/proficiencies/equipment/features/spells-or-powers.
18. Change an upstream selection and prove downstream invalidation/revalidation works.
19. Create a higher-level character through sequentially valid advancement choices.
20. Validate/finalize character.
21. Add the character to the party.
22. Query the complete visibility-filtered character sheet.

## 25.4 Exploration/world interaction

23. Enter a scene/location.
24. Query perceived entities rather than omniscient state.
25. Move using authoritative movement.
26. Discover a hidden/unknown world fact through rules-driven play.
27. Interact with a world object/container.
28. Transfer/store/retrieve inventory items.
29. Complete a trade transaction.
30. Start and complete a crafting process on simulation time.
31. Travel with party marching order and world-time advancement.
32. Observe a scheduled world/environment event.

## 25.5 Social/quest systems

33. Start a dialogue state machine.
34. Resolve a conditional dialogue choice.
35. Change faction/reputation/relationship state through events.
36. Accept a quest.
37. Advance parallel/conditional objective nodes.
38. Complete/fail a time-sensitive objective deterministically.

## 25.6 Encounter/action/timing systems

39. Create/start an encounter from scene state.
40. Establish participants/positions.
41. Query available actions and valid target schemas.
42. Execute movement and a rules action.
43. Spend/reserve/recover resources.
44. Apply/remove a condition/effect.
45. Open and resolve an interrupt/reaction window.
46. Interrupt/cancel an action and verify refund policy.
47. Exercise a timed decision window that expires deterministically.
48. Exercise reconnect/recovery during an active decision window.
49. Exercise simultaneous/conflicting commands and deterministic ordering.
50. Complete encounter cleanup and rewards.

## 25.7 Progression

51. Grant XP/milestone/progression currency according to campaign policy.
52. Begin an advancement session.
53. Unlock/choose progression nodes.
54. Validate a mutually exclusive/prerequisite choice.
55. Complete advancement and update derived projections.

## 25.8 Logs/history/replay

56. Query player game log.
57. Query combat log.
58. Query character history.
59. Query DM/admin audit log with proper authorization.
60. Inspect state at an earlier sequence.
61. Rebuild projections from events.
62. Replay from snapshot and from start to identical canonical state.
63. Replay an older-schema golden event stream through upcasters.

## 25.9 Live client sync

64. Connect WebSocket and subscribe.
65. Receive ordered visibility-filtered events.
66. Disconnect, miss events, reconnect, and resume.
67. Force buffer exhaustion and verify resumable resync rather than silent event loss.
68. Fetch snapshot + delta without a race gap.

## 25.10 Content evolution and recovery

69. Propose a content-pack revision.
70. Validate dependency/migration compatibility.
71. Activate the new campaign content revision.
72. Replay old history using the old pinned definitions and new history with the new revision.
73. Roll back a failed content revision when allowed.
74. Back up the deployment.
75. Restore into a clean environment and verify campaign/event/projection hashes.
76. Restart during scheduled/decision state and recover without duplicate actions.

If all 76 scenarios pass without a thin client embedding hidden game rules or mutating authoritative state, the v1.0 architecture is complete.

---

# 26. Definition of a complete subsystem

A subsystem is not considered planned merely because an interface name exists. Before implementation, each core subsystem must define:

- authoritative state;
- definitions/content schema;
- commands;
- events;
- queries/projections;
- permissions;
- visibility rules;
- lifecycle/state machine;
- concurrency/idempotency behavior;
- persistence/replay behavior;
- migration/version behavior;
- failure/error behavior;
- WebSocket/live implications where relevant;
- import/export implications where relevant;
- tests and exit criteria;
- source/license provenance for distributable content.

This checklist should be applied to every future system added to the roadmap.

---

# 27. Deliberately post-v1.0 work — not placeholders

These are intentionally out of the v1.0 completeness boundary and therefore should not block the first stable engine:

- distributed zone/shard servers;
- large-world interest management across many server processes;
- cross-region actor migration;
- massive-scale presence;
- advanced behavior trees/planners beyond the initial controller contract;
- rich procedural world-generation tooling;
- full visual map editor;
- marketplace/distribution service for third-party content packs;
- hosted billing/entitlements;
- advanced collaborative authoring;
- optional branching/alternate-timeline UX beyond the underlying replay primitives;
- engine-specific Godot/Unity rendering integrations beyond reference clients/SDK contracts.

They are scoped future features, not unresolved architecture holes.

---

# 28. Audit conclusion

With `PLAN.md`, `docs/GAME_SYSTEMS_PLAN.md`, and this normative completeness addendum, the project now has explicit definitions for the core systems required to build a complete API-driven fantasy RPG engine through v1.0.

Future planning should not add a noun such as `resource`, `session`, `spell`, `content pack`, `house rule`, `scene`, `visibility`, `import`, or `log` without applying the complete-subsystem checklist above.

The next implementation step remains v0.1, but v0.1 must now establish the shared primitives, versioning, command/error contracts, and migration seams needed by later milestones so those later systems do not require architectural rewrites.