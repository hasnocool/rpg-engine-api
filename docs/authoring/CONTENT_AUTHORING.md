# Creator and Content Authoring Specification

## Status

**Project:** `rpg-engine-api`  
**Role:** Normative specification for authoring, validating, testing, publishing, versioning, and consuming game content.  
**Covers:** content-authoring workflow, Creator/DM Studio API, encounter authoring, NPC social personality, and authored narration/presentation metadata.

`PLAN.md` remains the canonical roadmap. This document defines the creator-facing contracts in implementation-ready detail.

---

# 1. Design goals

The engine must make it possible to author almost all ordinary game content as versioned data rather than one-off Python code.

The same authoring pipeline should support:

```text
species
backgrounds
classes
subclasses
features
feats
progression graphs
skills/proficiencies
abilities/spells/powers
items/equipment
creature/NPC templates
NPC behavior profiles
NPC personality profiles
encounter templates
quests/objectives
dialogue graphs
factions/relationships
vendors/economy
loot/rewards
recipes/crafting
world/region/location/scene templates
world events
campaign templates
narration templates
```

Core principles:

1. Draft content never becomes live content merely because it was saved.
2. Published definitions are immutable within a version.
3. Every published definition retains provenance/license metadata.
4. References are validated before publication.
5. Creator tools produce the same schemas the runtime consumes.
6. Content packs remain data-only and cannot execute arbitrary Python.
7. Preview/test uses real rules/runtime paths, not editor-only approximations.
8. Publishing creates deterministic versioned artifacts that can be pinned by campaign content locks.

---

# 2. Authoring workspace

Content is edited inside a workspace rather than directly inside an installed content pack.

```text
AuthoringWorkspace
    id
    owner_principal_id
    name
    namespace
    target_ruleset_refs[]
    base_pack_refs[]
    status
    collaborators[]
    current_revision
    created_at
    updated_at
```

Statuses:

```text
active
read_only
archived
```

A workspace may contain many draft definitions and draft pack releases.

## 2.1 Draft definition

```text
DraftDefinition
    id
    workspace_id
    definition_type
    key
    schema_version
    revision
    payload
    source_metadata
    validation_status
    validation_issues[]
    created_by
    updated_by
    created_at
    updated_at
```

Draft definitions are mutable through optimistic revision checks. They are never referenced directly by a finalized campaign.

## 2.2 Draft lifecycle

```text
created
    -> editing
    -> validating
    -> valid | invalid
    -> previewing/testing
    -> publish_ready
    -> published
```

A later edit to a validated draft returns it to `editing` and invalidates prior validation/test evidence when affected fields changed.

## 2.3 Authoring commands

Conceptual commands:

```text
CreateAuthoringWorkspace
ArchiveAuthoringWorkspace
AddWorkspaceCollaborator
RemoveWorkspaceCollaborator
CreateDraftDefinition
UpdateDraftDefinition
CloneDefinitionToDraft
DeleteDraftDefinition
ValidateDraftDefinition
ValidateWorkspace
CreateDraftPackRelease
ValidateDraftPackRelease
RunContentPreview
RunContentPlaytest
MarkPublishReady
PublishContentPackVersion
DeprecateContentPackVersion
```

Draft CRUD is an authoring concern, not authoritative campaign gameplay. Publication and campaign activation remain explicit privileged operations.

---

# 3. Validation pipeline

Validation is layered so creators receive useful errors before playtesting.

```text
schema validation
    -> identity/namespace validation
    -> reference resolution
    -> ruleset compatibility
    -> license/provenance checks
    -> semantic validation
    -> graph/reachability validation
    -> runtime dry-run validation
    -> playtest/simulation evidence
```

## 3.1 Validation issue model

```text
ValidationIssue
    code
    severity
    definition_ref_or_draft_id
    field_path
    message
    related_refs[]
    suggested_fix | null
```

Severities:

```text
info
warning
error
blocking
```

Publication fails on blocking issues and policy-defined errors.

## 3.2 Cross-reference checks

The validator must detect at minimum:

- unresolved definition references;
- incompatible ruleset/version ranges;
- duplicate namespaced keys;
- cyclic dependencies where not allowed;
- invalid progression graph edges;
- unreachable progression nodes;
- quest/objective graph dead ends;
- dialogue choices pointing to missing nodes;
- encounter participants using missing templates/profiles;
- item/ability references that cannot resolve;
- invalid reward/loot references;
- location/scene links to missing destinations;
- content that depends on undeclared packs;
- missing required source/license metadata.

## 3.3 Runtime semantic checks

Where the runtime exists, validate that definitions can be instantiated and queried through normal rules interfaces.

Examples:

```text
creature template -> actor instance can be created
ability -> appears as a legal available action under a valid fixture
encounter -> can instantiate all participants
quest -> objective graph can enter a legal initial state
vendor -> inventory/pricing references resolve
recipe -> inputs/outputs are valid items/resources
```

---

# 4. Publication and immutable releases

Content is published as a versioned pack release.

```text
PublishedContentPack
    manifest
    definition_index
    definitions[]
    localization_resources
    declared_assets[]
    migration_descriptors[]
    validation_report_ref
    playtest_report_refs[]
    content_hash
    published_at
    published_by
```

Publication guarantees:

- the release is immutable;
- all internal references resolve;
- its manifest dependencies/conflicts are deterministic;
- content hash is stable;
- schemas/engine compatibility are explicit;
- attribution/license requirements are preserved;
- campaigns can pin the exact release.

A changed definition requires a new pack version.

---

# 5. Creator / DM Studio API

The backend should expose creator-oriented APIs so a browser, Godot tool, desktop editor, TUI, or automation agent can build content without direct DB access.

Suggested domains:

```text
/api/v1/authoring/workspaces
/api/v1/authoring/drafts
/api/v1/authoring/validation
/api/v1/authoring/previews
/api/v1/authoring/playtests
/api/v1/authoring/releases
/api/v1/authoring/encounters
/api/v1/authoring/quests
/api/v1/authoring/dialogues
/api/v1/authoring/world
/api/v1/authoring/progression
/api/v1/authoring/npcs
/api/v1/authoring/items
/api/v1/authoring/abilities
```

These are authoring APIs, not alternate gameplay mutation APIs.

## 5.1 Schema discovery for editors

Generic editors should be able to query definition schemas and presentation hints.

```text
DefinitionAuthoringSchema
    definition_type
    schema_version
    fields
    enum/options
    reference_constraints
    validation_rules
    editor_hints
```

This lets a creator UI dynamically build forms while specialized editors can provide richer experiences.

## 5.2 Specialized editor projections

Useful projections include:

```text
CreatureEditorView
ItemEditorView
AbilityEditorView
ProgressionGraphEditorView
QuestGraphEditorView
DialogueGraphEditorView
EncounterEditorView
WorldGraphEditorView
VendorEditorView
NpcProfileEditorView
```

Editor projections may combine several underlying definitions for convenience but never become the canonical published format.

---

# 6. Encounter authoring

Runtime `Encounter` is an instance. `EncounterTemplate` is authored content.

```text
EncounterTemplate
    id
    key
    name
    ruleset_compatibility
    scene_template_ref | null
    participant_groups[]
    starting_position_policy
    encounter_type
    timing_policy_override | null
    triggers[]
    waves[]
    objectives[]
    environmental_effect_refs[]
    reinforcement_rules[]
    escape_rules
    completion_rules
    failure_rules
    rewards
    scaling_policy
    narration_refs[]
    source_metadata
```

## 6.1 Participant group

```text
EncounterParticipantGroup
    id
    actor_template_ref
    count
    side_or_faction
    controller_assignment
    spawn_policy
    starting_location_selector
    scaling_tags[]
```

## 6.2 Spawn/wave model

```text
EncounterWave
    id
    trigger
    participant_groups[]
    entry_location_selector
    announcements[]
```

Triggers can be typed conditions such as encounter start, simulation time elapsed, objective state, actor/resource threshold, world flag, or previous wave completion.

## 6.3 Encounter objectives

Encounter objectives are explicit so an encounter need not mean “defeat every opponent.”

Examples:

```text
protect_actor
reach_location
survive_until_time
interact_with_object
escape_scene
complete_task
opponent_retreats
custom_typed_predicate
```

## 6.4 Scaling policy

```text
EncounterScalingPolicy
    mode
    inputs
    allowed_adjustments
    bounds
```

Initial modes can include:

```text
fixed
party_level_band
party_size
content_defined_variant
```

Scaling resolves deterministically to concrete participant definitions before the encounter starts and records the chosen variant in authoritative events.

## 6.5 Encounter preview

Creator preview should show:

- resolved participants/controller profiles;
- expected available starting actions;
- map/spawn validity;
- unresolved references;
- estimated simulation complexity;
- linked rewards/objectives;
- simulation-lab results when available.

---

# 7. NPC social personality

Combat controller behavior and social/personality data are separate.

```text
NpcPersonalityProfile
    id
    version
    disposition
    temperament_tags[]
    goals[]
    loyalties[]
    fears[]
    interests[]
    conversation_topic_tags[]
    relationship_thresholds
    aggression_threshold
    assistance_threshold
    trade_preferences
    dialogue_style_tags[]
```

This profile does not directly mutate relationships or invent dialogue outcomes.

It supplies typed context to dialogue/social rules and later optional narration/AI systems.

## 7.1 Social decision inputs

A simple social rules evaluator may use:

```text
visible/known actor identity
faction relationship
reputation metrics
active quest relationships
known facts
current dialogue node
personality thresholds/tags
legal dialogue/social actions
```

The authoritative consequence always resolves through typed commands/effects.

## 7.2 Compatibility with SimpleNpcController

`NpcBehaviorProfile` answers “how does this actor choose gameplay actions?”

`NpcPersonalityProfile` answers “what social preferences/thresholds characterize this NPC?”

A template may reference both.

---

# 8. Narration and presentation metadata

Authoritative events are facts. Player-facing narration is a projection.

```text
DomainEvent
    -> visibility filtering
    -> NarrationContext
    -> deterministic template/localization renderer
    -> GameMessage
```

```text
NarrationContext
    event_ref
    visible_actor_refs
    visible_object_refs
    location_ref | null
    audience
    locale
    verbosity
    content_lock_hash
```

```text
NarrationTemplate
    id
    event_type_or_tag
    audience_policy
    text_key
    fallback_template
    variables_schema
    priority
```

The deterministic renderer is the baseline. An optional later LLM narrator may paraphrase visible facts but may not create authoritative events or hidden facts.

## 8.1 Game message

```text
GameMessage
    id
    source_event_ids[]
    audience
    category
    text
    semantic_tags[]
    simulation_time
    sequence_range
```

Categories can include combat, exploration, social, quest, system, narration, and recap.

---

# 9. Creator permissions and audit

Authoring permissions are separate from campaign-playing permissions.

Examples:

```text
authoring.workspace.create
authoring.workspace.edit
authoring.validate
authoring.playtest
authoring.publish
content.install
content.deprecate
```

Publication/deprecation actions are auditable.

Never let an ordinary campaign player publish or activate repository-wide content merely because they can create campaign-local drafts.

---

# 10. Persistence and concurrency

Draft authoring data may use conventional mutable persistence with optimistic revisions because it is not authoritative campaign gameplay history.

Published definitions remain immutable/versioned.

Important distinction:

```text
authoring draft
    mutable collaboration state

published definition
    immutable content artifact

campaign state
    event-sourced authoritative gameplay state
```

Do not event-source every keystroke in an editor.

---

# 11. Required tests

Authoring tests must cover:

- schema validation;
- cross-reference failures;
- graph reachability/dead ends;
- license/source validation;
- optimistic edit conflicts;
- publish immutability;
- deterministic pack hashes;
- cloning/version publication;
- encounter instantiation;
- NPC behavior/personality reference resolution;
- narration template variable validation;
- authoring permissions;
- preview using real runtime interfaces;
- publication rejected when required playtest policy fails.

Creator-facing bugs that could publish invalid content require regression tests.

---

# 12. Milestone placement

```text
v0.1
    definition schema registry seams
    immutable published-definition identity/versioning

v0.3
    creature/NPC and EncounterTemplate authoring schemas sufficient for Testing Grounds combat

v0.4
    ability/feature/effect/progression authoring schemas

v0.5
    scene/world-object/location/spatial authoring schemas

v0.6
    class/species/background/character-template authoring schemas

v0.7
    full authoring workspace + quest/dialogue/vendor/recipe/world/campaign templates
    NPC personality profiles
    baseline narration templates
    publish/version workflow

v0.9
    stable Creator/DM Studio API and schema-discovery contracts

v1.0
    complete authoring validation/publish workflow with reference creator examples
```

A full polished visual editor UI is not required for v1.0, but the APIs/contracts needed to build one are.