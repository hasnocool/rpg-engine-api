# Simulation, Balance, and Content Quality Lab Specification

## Status

**Project:** `rpg-engine-api`  
**Role:** Normative specification for automated encounter simulation, balance evidence, content validation/testing SDKs, generated play, reachability analysis, and creator-facing quality reports.  
**Execution policy:** all canonical simulation/quality profiles are executed by the designated local test agent only. GitHub Actions and remote CI are prohibited by `PLAN.md` Section 50.

This specification builds on `docs/testing/HUMAN_PLAYTESTING.md` and `docs/ai/SIMPLE_NPC_AI.md`.

---

# 1. Purpose

The engine should not merely execute games; it should be able to systematically test authored content and gameplay combinations before a human encounters them.

The Simulation/Quality Lab provides evidence, not an automatic declaration that content is “fun” or “balanced.”

It should answer questions such as:

```text
Can this encounter finish?
How often does each side win under configured policies?
Which actions are never used?
Which resources are exhausted most often?
Which seed caused an extreme outcome?
Can every quest branch be reached?
Are any dialogue nodes unreachable?
Can every progression node ever become legal?
Can every required quest item be acquired?
Can a creature use all abilities it was authored with?
Does this campaign deadlock under a timing/controller combination?
```

---

# 2. Simulation run model

```text
SimulationRun
    id
    scenario_ref
    engine_revision
    ruleset_ref
    content_lock_ref
    seed_bundle
    controller_assignments[]
    timing_mode
    spatial_adapter
    run_policy
    status
    started_at
    completed_at | null
    result_ref | null
```

Statuses:

```text
queued
running
completed
failed
cancelled
```

Simulation jobs are operational workloads. They do not modify production campaigns.

## 2.1 Simulation batch

```text
SimulationBatch
    id
    scenario_template_ref
    sample_count
    seed_policy
    controller_matrix[]
    timing_mode_matrix[]
    parameter_sweep
    stop_conditions
```

Initial batches should support deterministic sequential seed allocation so any run is reproducible independently.

---

# 3. Encounter simulation

An encounter simulation uses the same runtime/rules/action/controller machinery as real gameplay.

Typical modes:

```text
simple_npc_vs_simple_npc
scripted_reference_party_vs_simple_npc
mixed_persona_vs_simple_npc
controller_profile_comparison
rules/content-version comparison
```

The lab must not contain a second combat simulator with simplified hidden formulas.

## 3.1 Encounter metrics

Capture at minimum:

```text
terminal outcome
winner/side outcome where applicable
simulation duration
round/turn/action count
wall-test execution duration
damage/healing totals
resource consumption
resource remaining
movement distance/actions
action usage counts
ability usage counts
condition/effect applications
reaction opportunities/uses
actor defeat/unavailable sequence
objective completion/failure
rewards produced
rule rejection counts
controller fallback counts
```

For each metric retain run IDs/seeds for outlier inspection.

## 3.2 Aggregate report

```text
EncounterSimulationReport
    sample_count
    completed_count
    failed_count
    outcome_distribution
    duration_distribution
    action_usage
    resource_statistics
    actor_contribution_statistics
    objective_statistics
    rejection_statistics
    controller_statistics
    outlier_runs[]
    warnings[]
```

Use descriptive evidence rather than a single opaque “balance score.”

---

# 4. Comparative experiments

Creators should be able to compare two or more versions/configurations.

Examples:

```text
encounter v1 vs v2
creature profile aggressive vs defensive
party size 3 vs 4
ruleset patch A vs B
item/ability before vs after edit
turn_based vs active_time
```

```text
SimulationComparison
    baseline_batch_ref
    candidate_batch_ref
    matched_seed_policy
    metric_deltas
    significance_metadata
    warnings
```

Matched seeds should be preferred when comparing deterministic content revisions so variance is easier to interpret.

The lab may calculate confidence intervals/statistics, but the underlying sample/run data must remain inspectable.

---

# 5. Reachability and graph analysis

Some quality problems can be detected statically or through bounded exploration.

## 5.1 Quest graph checks

Detect:

- unreachable objective nodes;
- objectives whose prerequisites can never coexist;
- dead-end states with no completion/failure resolution;
- cycles without explicit repeat policy;
- required item/fact/location references with no acquisition/discovery path in supplied content scope;
- timed objectives with impossible schedule relationships when provable.

## 5.2 Dialogue graph checks

Detect:

- unreachable nodes;
- transitions to missing nodes;
- choices whose requirements are impossible under declared fixtures;
- terminal nodes missing an explicit terminal policy;
- accidental infinite loops where repeat is not intentional.

## 5.3 Progression graph checks

Detect:

- unreachable nodes;
- impossible prerequisites;
- mutually exclusive prerequisites that make a node impossible;
- ranks with no acquisition path;
- circular prerequisites;
- orphan grants/references.

## 5.4 World/content path checks

Where enough authored data exists, detect:

- location graph components with no intended entry path;
- quest-critical items with no source;
- encounter templates referencing impossible spawn locations;
- vendors/recipes referencing absent currencies/items;
- abilities whose prerequisites can never be satisfied by their intended actor/class template.

Static analysis should report uncertainty rather than claiming impossibility when dynamic/custom predicates prevent proof.

---

# 6. Content Testing SDK

Provide a Python-facing testing SDK for creators, ruleset authors, the local test agent, and development agents designing tests.

Conceptual usage:

```text
validate_definition(...)
validate_pack(...)
instantiate_creature(...)
instantiate_encounter(...)
run_playtest_scenario(...)
simulate_encounter(...)
simulate_batch(...)
compare_batches(...)
check_quest_reachability(...)
check_dialogue_reachability(...)
check_progression_reachability(...)
find_unobtainable_items(...)
find_unusable_abilities(...)
generate_quality_report(...)
```

The SDK should expose public/test-support application interfaces, not private mutable domain shortcuts that bypass validation.

## 6.1 CLI surface

A CLI should eventually support commands like:

```text
rpg-engine validate pack ./my-pack
rpg-engine test-content encounter my_pack:encounter/bridge
rpg-engine simulate encounter my_pack:encounter/bridge --runs 100
rpg-engine analyze quest my_pack:quest/ruins
rpg-engine analyze dialogue my_pack:dialogue/merchant
rpg-engine compare-sim reports/a.json reports/b.json
```

CLI naming can change, but functionality should remain scriptable and friendly to the local test agent.

---

# 7. Generated/model-based play

The lab may build on available-action walkers from the human-play specification.

Generated actors/clients:

```text
query visible state
query available legal actions
choose from advertised actions using scenario RNG/policy
submit normal command
observe result
repeat until terminal/budget
```

Generated play must not implement hidden legality formulas.

## 7.1 Exploration objectives

Generated play can optimize for coverage goals such as:

```text
visit unseen state signatures
exercise unused action types
reach unseen quest/dialogue nodes
exercise controller profiles
exercise different timing paths
trigger negative/rejection cases
```

The search/exploration policy is test infrastructure and uses an independent RNG from authoritative game/controller RNG.

---

# 8. Invariants and property checks

Useful cross-run invariants include:

- inventory/currency conservation unless a typed source/sink event exists;
- resources remain within defined bounds;
- actor position remains valid under spatial authority;
- no action occurs without a corresponding legal command/event path;
- no hidden information appears in unauthorized projections;
- command idempotency holds under retries;
- event sequence/stream versions remain monotonic;
- snapshots/replay reach identical canonical state;
- controller decisions do not use hidden actors;
- quest objective states follow allowed transitions;
- published content refs resolve to pinned definitions.

---

# 9. Performance and scale experiments

The lab may run synthetic performance scenarios while preserving gameplay semantics.

Examples:

```text
large encounter actor counts
many concurrent campaigns
high WebSocket fanout
long event streams/replay
projection rebuild throughput
controller decision throughput
large content-pack validation
```

Separate correctness results from performance measurements.

Performance tests should record environment/build metadata so regressions are comparable.

---

# 10. Reproducibility

Every simulation result must be traceable to:

```text
engine revision
ruleset/content lock
scenario/template revision
controller versions/profiles
seed bundle
timing mode
spatial adapter
configuration
```

Failed or anomalous runs should be promotable into permanent regression fixtures.

Desired workflow:

```text
batch finds outlier
    -> save run artifact
    -> replay exact seed
    -> diagnose
    -> fix
    -> convert to regression scenario
```

---

# 11. Quality gates for publishing

Content publication policy may require selected checks.

Examples:

```text
schema/reference validation required
no blocking graph errors required
encounter smoke simulation required
quest reachability warnings reviewed
human-play scenario IDs required for major content
simulation threshold policy optional
```

Do not hard-code one global balance threshold into the engine. Different campaigns/content styles intentionally differ.

A pack can publish with warnings when policy permits; blocking structural errors cannot.

---

# 12. Reports and artifacts

```text
ContentQualityReport
    content_ref_or_draft_ref
    validation_summary
    static_analysis_summary
    playtest_results[]
    simulation_results[]
    coverage_summary
    warnings[]
    blocking_issues[]
    generated_at
    engine_revision
```

Artifacts should be JSON/machine-readable first, with optional human-readable Markdown/HTML renderers.

Never include secrets or private production campaign data in reusable quality artifacts.

---

# 13. Local execution integration

Canonical local test profiles should include appropriate jobs/suites such as:

```text
content-schema
content-references
content-static-analysis
playtest-smoke
simulation-smoke
simulation-nightly
quality-regressions
```

Changes to a definition should run affected validators/scenarios when dependency mapping can identify them.

Broader local `nightly`/`full` profiles should periodically run wider matrices to catch missing dependency metadata or cross-content interactions.

`nightly` is a local profile name and may be invoked manually or by a user-controlled local scheduler.

**Do not create or use GitHub Actions workflows, GitHub-hosted runners, Actions self-hosted runners, Actions artifacts, or remote CI status checks for these suites.**

---

# 14. Permissions and isolation

Simulation jobs require explicit authorization and resource limits when exposed outside a developer/test environment.

Simulation workers operate on isolated copies/fixtures/branches, never directly on a live production campaign stream.

Resource controls should include:

```text
max runs
max simulation steps
max actors
max wall execution time
max output artifact size
concurrency quotas
```

---

# 15. Milestone placement

```text
v0.1
    deterministic seed/artifact primitives
    quality-report schema seam

v0.3
    encounter smoke simulation using SimpleNpcController

v0.4
    ability/effect/resource metrics and generated-action exploration

v0.5
    spatial/perception invariants

v0.6
    progression reachability analysis

v0.7
    quest/dialogue/world/content reachability
    creator-facing content quality report
    initial Content Testing SDK

v0.8
    controller-comparison experiments

v0.9
    stable SDK/CLI contracts and local/containerized test targets

v1.0
    reference simulation lab workflows, regression artifact promotion, publishing quality gates, and local release-profile evidence
```

The lab is intended to make the engine easier to author and maintain, not to replace human design judgment.