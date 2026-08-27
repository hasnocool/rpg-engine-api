# Trusted Extensions and Content Migration Specification

## Status

**Project:** `rpg-engine-api`  
**Role:** Normative specification for the boundary between safe data-only content and trusted executable rules extensions, plus content compatibility, upgrade, migration, rollback, and creator-facing migration UX.

`PLAN.md` remains the canonical roadmap. This document closes the extension and content-evolution contracts that ordinary content packs must not improvise.

---

# 1. Two extension classes

The engine distinguishes two fundamentally different mechanisms:

```text
ContentPack
    data only
    declarative schemas/expressions
    safe to inspect/validate
    no arbitrary executable code

RulesExtension
    trusted executable code
    deployment-installed
    versioned extension API
    explicit permissions/capabilities
    never silently installed from a content pack
```

This distinction is non-negotiable.

A content author must not solve an unsupported mechanic by embedding Python, shell commands, dynamic imports, or arbitrary expressions into content JSON/YAML.

---

# 2. Data-only content packs

Content packs may contain validated definitions such as:

```text
classes/species/backgrounds
features/effects/actions
abilities/spells/powers
items/recipes/vendors
creatures/NPC profiles
encounters/quests/dialogues
locations/world templates
narration/localization/assets metadata
```

Allowed executable-like behavior is limited to the engine's typed/versioned declarative DSLs, such as:

```text
RequirementExpr
Grant
Modifier
Effect
Trigger
ActionDefinition
QuestPredicate
DialogueRequirement
```

Each DSL operation must be explicitly registered and validated by the engine/ruleset.

---

# 3. Trusted rules extensions

A trusted extension is code intentionally installed by the deployment operator.

```text
RulesExtensionManifest
    id
    version
    api_version
    engine_version_range
    ruleset_compatibility
    capabilities[]
    dependencies[]
    conflicts[]
    entrypoint
    permissions[]
    migration_refs[]
    provenance
```

Possible capabilities:

```text
rules_predicates
resolution_handlers
effect_operations
spatial_adapter
controller_provider
content_validator
projection_provider
import_export_adapter
custom_query_provider
```

Capabilities are explicit. Installing an extension does not automatically grant every integration point.

---

# 4. Extension interfaces

The core exposes narrow typed extension interfaces rather than arbitrary service-container access.

Examples:

```text
RulesPredicateProvider
ResolutionRuleProvider
EffectOperationProvider
SpatialAdapterProvider
ControllerProvider
ContentValidationProvider
MigrationProvider
```

Extensions should receive domain-safe contexts and return typed results.

They must not receive unrestricted database sessions, FastAPI internals, secret stores, or raw WebSocket connection objects merely for convenience.

---

# 5. Determinism and replay requirements

Any trusted extension that affects authoritative state must be replay-compatible.

It must declare:

```text
extension id/version
handler/operation version
schema compatibility
migration/upcast strategy when applicable
```

Authoritative events must retain enough extension/version metadata to reproduce historical interpretation.

An extension is invalid for deterministic authoritative use if the same pinned input can produce different results because it depends on uncontrolled current time, external mutable services, process-global randomness, or nondeterministic iteration.

If an extension calls an external service, the resulting authoritative decision/outcome must be captured as an event in a way that replay does not require re-calling that service.

---

# 6. Security boundary

Trusted does not mean unrestricted.

Deployment guidance should support:

- explicit administrator installation;
- package/signature/hash verification where available;
- version pinning;
- disabled-by-default privileged capabilities;
- resource/time limits for extension hooks;
- structured failure isolation;
- no automatic loading from user-uploaded pack archives;
- audit log entries for install/enable/disable/upgrade.

A malformed extension must fail its operation safely rather than corrupting the authoritative event store.

---

# 7. Extension lifecycle

```text
available
    -> validated
    -> installed
    -> enabled
    -> disabled
    -> upgraded
    -> removed
```

Removal is blocked while active campaign content/history requires the extension unless the deployment provides a compatible archival reader/migration path.

Commands/admin operations conceptually include:

```text
ValidateRulesExtension
InstallRulesExtension
EnableRulesExtension
DisableRulesExtension
UpgradeRulesExtension
RemoveRulesExtension
```

These are deployment/admin operations, not ordinary campaign commands.

---

# 8. Compatibility model

Content and extension compatibility is evaluated against:

```text
engine API version
payload/schema versions
ruleset version
content-pack dependencies
extension API version
required extension capabilities
campaign state/content lock
```

```text
CompatibilityReport
    subject_ref
    target_environment
    compatible
    blocking_issues[]
    warnings[]
    required_migrations[]
    affected_definition_refs[]
    affected_campaign_entities[]
```

Compatibility checks must be available before activation.

---

# 9. Content revision diff

Creators/DMs need a semantic diff, not only file-line changes.

```text
ContentRevisionDiff
    from_lock
    to_candidate_lock
    added_definitions[]
    removed_definitions[]
    changed_definitions[]
    dependency_changes[]
    extension_requirement_changes[]
    schema_changes[]
    migration_requirements[]
```

For each changed definition, classify relevant changes such as:

```text
presentation_only
additive_compatible
behavior_change
schema_change
reference_removed
state_migration_required
potentially_breaking
```

The classifier may be conservative; uncertainty should become a warning/blocking review item rather than silently assuming compatibility.

---

# 10. Campaign impact analysis

Before a live campaign changes content versions, compute which existing state is affected.

```text
CampaignContentImpactReport
    campaign_id
    current_lock
    candidate_lock
    impacted_actors[]
    impacted_characters[]
    impacted_items[]
    impacted_abilities[]
    impacted_quests[]
    impacted_encounters[]
    impacted_world_objects[]
    impacted_progression_state[]
    impacted_scheduled_events[]
    migration_plan
    warnings[]
```

Examples:

- an actor references a removed creature template;
- a character owns a feature whose schema changed;
- an item instance references a removed definition;
- a quest objective predicate changed;
- a progression node moved/was removed;
- an active encounter uses a changed AI profile;
- a scheduled world event references removed content.

---

# 11. Migration plan

```text
ContentMigrationPlan
    id
    from_lock
    to_lock
    steps[]
    reversible
    validation_checks[]
    dry_run_supported
```

```text
ContentMigrationStep
    id
    migration_type
    affected_refs[]
    handler_ref
    preconditions
    postconditions
    rollback_handler_ref | null
```

Migration types can include:

```text
definition_ref_remap
state_schema_transform
resource_recalculation
progression_node_remap
quest_state_transform
scheduled_event_transform
custom_trusted_extension_migration
```

Ordinary declarative pack migration descriptors must remain constrained/typed. Arbitrary executable state migration requires a trusted extension or engine-supported migration handler.

---

# 12. Dry run and preview UX

Content upgrade flow should be:

```text
select candidate versions
    -> resolve candidate content lock
    -> semantic diff
    -> compatibility report
    -> campaign impact report
    -> generate migration plan
    -> dry run against isolated branch/copy
    -> run required validation/playtests
    -> review results
    -> create automatic checkpoint
    -> activate revision
    -> verify projections/replay
```

The API should return structured data usable by a future Creator/DM Studio.

---

# 13. Activation semantics

Conceptual commands already planned:

```text
ProposeContentRevision
ValidateContentRevision
ActivateContentRevision
RollbackContentRevision
```

Activation must be atomic from the campaign's perspective.

It should record:

```text
previous content lock
new content lock
migration plan/version
checkpoint/branch reference
principal
resulting events/state migrations
```

Historical events before activation continue resolving with the old pinned definitions.

---

# 14. Rollback semantics

Rollback is only allowed when a valid reverse path exists.

Possible outcomes:

```text
safe direct rollback
rollback via reverse migration
branch from pre-upgrade checkpoint
rollback impossible -> branch required
```

The reference UX should prefer preserving both histories rather than destructive rewriting.

If new gameplay events have occurred after an incompatible migration, branching from the pre-upgrade checkpoint may be safer than attempting to mutate history backward.

---

# 15. Upgrade policies

Campaigns may configure:

```text
manual_only
notify_available
allow_patch_if_compatible
custom_admin_policy
```

The reference engine should default to `manual_only` for active campaign content changes.

No automatic background upgrade may silently change authoritative mechanics.

---

# 16. Migration validation

Before activation, verify:

- all definition refs resolve under candidate lock;
- all migration steps complete in dry-run copy/branch;
- canonical invariants hold;
- required projections rebuild;
- required rules/content playtests pass;
- no unauthorized hidden data appears;
- replay before/after lock boundary works;
- old history still resolves through old versions;
- newly active state resolves through new versions.

A migration that cannot reproduce/replay across its activation boundary is not acceptable for v1.0.

---

# 17. Creator-facing migration APIs

Possible endpoints/projections:

```text
/api/v1/content-revisions/resolve
/api/v1/content-revisions/diff
/api/v1/campaigns/{id}/content-impact
/api/v1/campaigns/{id}/content-migration-plan
/api/v1/campaigns/{id}/content-migration-dry-run
```

State changes still occur through authorized content revision commands.

---

# 18. Testing

Required extension/migration tests:

- data-only packs cannot execute code;
- undeclared extension capability use is rejected;
- extension version pinned in relevant authoritative interpretation;
- deterministic extension handler fixture replay;
- extension failure isolation;
- content semantic diff fixtures;
- impact detection for actors/items/quests/progression/events;
- migration dry run;
- activation atomicity;
- old-history/new-history replay around lock boundary;
- rollback when reversible;
- forced branch workflow when rollback is unsafe;
- missing extension/dependency compatibility failures;
- permissions/audit for extension installation and content activation.

---

# 19. Milestone placement

```text
v0.1
    extension/version metadata seams
    declarative-content-only invariant

v0.4
    extension points for predicates/effect operations if needed

v0.5
    optional spatial adapter provider seam

v0.7
    semantic content diff/impact report foundations
    typed content migration descriptors
    checkpoint-before-upgrade workflow

v0.8
    controller-provider/external integration extension seams

v0.9
    stable trusted-extension API and content migration preview APIs

v1.0
    documented extension boundary
    upgrade dry-run/activation/rollback-or-branch workflow
    cross-version replay fixtures
```

The marketplace/distribution of third-party executable extensions remains post-v1.0. The v1.0 goal is a safe, explicit extension boundary—not an open plugin marketplace.