# Simulation and Content Quality Lab

## Status

**Project:** `rpg-engine-api`  
**Role:** Normative specification for deterministic simulation, balance evidence, content reachability, content-quality analysis, and creator-facing testing SDKs.  
**Execution policy:** simulation/quality profiles are executed by the designated local test agent only. GitHub Actions and remote CI are prohibited by `PLAN.md` Section 50.

`PLAN.md` remains authoritative. Simulation is never a second simplified game engine: it drives the same rules runtime, command/event paths, controllers, timing and content definitions used by normal gameplay.

---

# 1. Goals

The lab exists to answer questions such as:

```text
Can this encounter finish?
How often does each side win under controlled assumptions?
Which actions/resources dominate outcomes?
Can this quest/dialogue/progression graph be completed?
Is an item unobtainable?
Is an ability never legally usable?
Does a content/controller revision materially change outcomes?
Can a reported outlier be reproduced from its seed/configuration?
```

The lab provides evidence. It must not hide creator judgement behind one opaque universal “balance score.”

---

# 2. Reuse the real runtime

A simulation must instantiate and drive production-equivalent domain/runtime components.

```text
published or preview content
    -> campaign/encounter fixture
    -> ordinary command/action engine
    -> real rules/effects/resources
    -> real controller interface
    -> authoritative events/projections
    -> isolated simulation report
```

Do not create a lightweight combat formula that bypasses the actual engine merely to make large batches faster. Performance optimization may introduce isolated workers/caching, but semantic authority remains the same runtime.

---

# 3. Simulation run identity

Every run is reproducible from versioned inputs.

```text
SimulationRun
    schema_version
    simulation_id
    engine_revision
    ruleset_ref
    content_lock
    extension_versions
    controller_versions
    scenario_ref
    configuration
    seed_bundle
    iteration_count
    created_at
```

The local test evidence bundle should reference the simulation report/artifacts produced for the exact candidate commit.

---

# 4. Encounter simulation

Support deterministic single and batch encounter simulation.

Metrics should include where applicable:

```text
winner/outcome
objective completion
rounds/turns/simulation time
real execution duration
damage dealt/taken
healing
resource consumption
conditions/effects applied
action selection counts
target selection counts
actor defeats
remaining health/resources
controller fallback/error counts
```

Metrics are descriptive evidence. Balance thresholds must be explicit creator/project policy, not hidden magic numbers.

---

# 5. Matched-seed comparisons

When comparing two content/controller/runtime revisions, run equivalent seed/configuration sets where possible.

Examples:

```text
encounter v1 vs encounter v2
SimpleNpcController profile A vs B
old ability definition vs revised definition
old rules extension vs new version
turn-based translation vs active-time translation
```

Matched seeds make outcome deltas easier to interpret and reproduce.

---

# 6. Outlier preservation

Keep enough information to reproduce interesting or failing runs.

Examples:

- unexpectedly one-sided result;
- extreme duration;
- resource starvation;
- controller fallback loop;
- unreachable victory condition;
- nondeterministic mismatch;
- performance spike.

Promote important seeds/configurations into durable regression fixtures.

---

# 7. Static/reachability content analysis

Quality analysis should inspect authored/published graphs without needing to brute-force every game state.

Targets include:

```text
quest graphs
dialogue graphs
progression graphs
campaign creation graphs
character creation graphs
encounter objective graphs
content dependencies
item acquisition paths
ability prerequisites
crafting dependencies
```

Detect where practical:

- unreachable nodes;
- dead-end mandatory branches;
- impossible prerequisite combinations;
- circular dependencies;
- dangling definition refs;
- content with no acquisition path;
- abilities that can never become legally available;
- mutually exclusive requirements that accidentally block completion.

Static analysis is advisory when runtime conditions are intentionally dynamic/opaque.

---

# 8. Generated available-action exploration

Use server/runtime-advertised available actions to explore state without duplicating hidden rules.

```text
instantiate deterministic fixture
    -> ask actor/controller for visible available actions
    -> choose via deterministic exploration strategy
    -> submit ordinary command
    -> verify invariants
    -> repeat
```

This can discover unexpected state combinations while keeping legality server-authoritative.

---

# 9. Creator-facing ContentQualityReport

Produce machine-readable and human-readable quality output.

Conceptual shape:

```text
ContentQualityReport
    schema_version
    content_ref
    engine_revision
    validation_summary
    reference_errors[]
    reachability_findings[]
    simulation_summaries[]
    reproducible_outliers[]
    coverage_summary
    warnings[]
    blocking_findings[]
```

Publication policy may require some findings to be clear before a pack becomes publish-ready.

---

# 10. Content Testing SDK

Expose a scriptable Python/API/CLI surface for creators and the local test agent.

Target capabilities:

```text
validate_pack
validate_definition
instantiate_creature
instantiate_encounter
run_playtest_scenario
run_simulation
run_simulation_batch
compare_simulation_runs
analyze_quest_reachability
analyze_dialogue_reachability
analyze_progression_reachability
find_unobtainable_items
find_unusable_abilities
build_content_quality_report
```

The SDK must not mutate live production campaign streams unless explicitly invoking a normal authorized runtime command against a designated test campaign.

---

# 11. Isolation

Simulation jobs run in isolated/disposable state.

They must not:

- append events to real active campaigns;
- consume production RNG state;
- alter published definitions;
- hold locks that interfere with normal player operations;
- silently invoke external mutable services during deterministic replay.

Use bounded worker execution for CPU-heavy workloads when required.

---

# 12. Controller testing

The Simulation Lab is a major verification surface for NPC controllers.

For `SimpleNpcController`, test:

```text
aggressive melee behavior
ranged preferred-distance behavior
balanced/defensive behavior
support choices
passive/non-hostile behavior
flee threshold behavior
legal target selection
hidden target exclusion
deterministic tie-breaking
safe fallback behavior
AI-vs-AI reproducibility
```

Later advanced/external controllers are compared against the deterministic baseline, not allowed to replace its role as a reference/fallback.

---

# 13. Performance evidence

Simulation workloads are also useful for measured performance characterization.

Track:

```text
simulations/sec
commands/sec
events/sec
projection rebuild cost
memory growth
pathfinding cost
controller decision cost
batch size scaling
```

Performance claims require the canonical local `performance` profile and exact-commit evidence. Do not infer performance from code inspection.

---

# 14. Local execution profiles

Relevant canonical local profiles include:

```text
simulation
playtest
performance
full
nightly
release
```

`nightly` is a local profile name, not a GitHub Actions schedule. Broad simulation matrices may be invoked manually or through a user-controlled local scheduler.

No GitHub Actions workflow may run, schedule, or publish evidence for Simulation/Quality Lab work.

---

# 15. Failure artifacts

A failed/outlier run should retain enough information to reproduce:

```text
simulation/scenario ID
commit SHA
content lock
ruleset/extension/controller versions
seed bundle
configuration
iteration number
last relevant events/projections
assertion/finding
performance data when relevant
```

The designated local test agent packages these into or references them from `TestEvidenceBundle`.

---

# 16. Roadmap integration

```text
v0.1
    report/result schema seams
    deterministic seed/evidence foundations

v0.2
    timing/action simulation hooks

v0.3
    encounter simulation + AI-vs-AI deterministic smoke

v0.4
    effects/resources/abilities/progression metrics
    generated action exploration

v0.5
    spatial/perception invariants

v0.6
    character/progression reachability

v0.7
    creator-facing ContentQualityReport
    quest/dialogue/world/economy checks
    Content Testing SDK
    long-form Testing Grounds simulation/playtest composition

v0.8
    advanced/external controller comparisons

v0.9
    stable local SDK/CLI contracts

v1.0
    simulation/content-quality evidence is part of the local release profile
```

---

# 17. Completion rule

A simulation/content-quality feature is complete when:

- it uses the real runtime/definitions/controllers;
- inputs and seeds are versioned/reproducible;
- output is machine-readable;
- important failures/outliers can be replayed;
- it does not mutate live authoritative campaigns;
- the designated local test agent can execute its canonical profile and emit evidence;
- no GitHub Actions workflow is required or permitted.