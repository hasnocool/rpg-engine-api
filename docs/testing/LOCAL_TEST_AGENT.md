# Local Test Agent Execution and Evidence Contract

## Status

**Project:** `rpg-engine-api`  
**Role:** Normative specification for executing tests in a real local/deployment-like environment and returning trustworthy evidence to remote coding/review agents.  
**Goal:** Separate test design from test execution so no agent claims a change is verified without machine-produced evidence from an environment that actually ran the required suites.

`PLAN.md` remains the canonical roadmap. `docs/testing/HUMAN_PLAYTESTING.md` and `docs/testing/SIMULATION_QUALITY_LAB.md` define what should be tested; this document defines who may establish that it passed, how the tests are invoked, and what evidence must be returned.

---

# 1. Roles and authority

The project distinguishes two roles.

```text
remote development/review agents
    design architecture
    implement code
    write tests/scenarios
    review diffs
    reason about failures/evidence
    may run only tools actually available to them

local test agent / CI executor
    runs the repository in a real configured environment
    installs dependencies
    provisions required services
    executes test profiles
    captures artifacts
    reports exact pass/fail/skip state
```

The local test agent is the **test execution authority** for local-environment claims.

A remote agent may say:

```text
"tests were added"
"this is expected to satisfy scenario X"
"static inspection found no issue"
"CI/local evidence reports these suites passed"
```

A remote agent must not say:

```text
"all tests pass"
"verified locally"
"PostgreSQL integration tests pass"
"the Godot/client integration works"
"release suite is green"
```

unless current machine-produced evidence exists for the exact commit being discussed.

---

# 2. Evidence is commit-bound

Every execution result is bound to an exact source revision.

Conceptual bundle:

```text
TestEvidenceBundle
    schema_version
    evidence_id
    repository
    commit_sha
    branch | null
    dirty_worktree
    test_profile
    executor_kind
    executor_version
    environment
    started_at
    finished_at
    overall_status
    suites[]
    artifacts[]
    summary
```

Evidence for one commit must not be treated as proof for a later code-changing commit.

Documentation-only changes may reuse prior runtime evidence only when the change cannot affect runtime/test behavior and the merge policy explicitly allows it.

A dirty worktree must be recorded. Release evidence should normally require `dirty_worktree = false`.

---

# 3. Environment manifest

Record enough environment information to reproduce failures.

```text
TestEnvironment
    os
    architecture
    python_version
    package_manager
    dependency_lock_hash | null
    installed_package_fingerprint | null
    database_type
    database_version | null
    redis_version | null
    container_runtime | null
    engine_config_fingerprint
    locale
    timezone
    relevant_feature_flags
```

Do not capture secrets, passwords, API keys, access tokens, or private environment values.

For environment-sensitive integrations, record safe capability metadata such as service version, enabled backend, or connector type rather than credentials.

---

# 4. Suite result schema

Each executed suite records the command and outcome.

```text
TestSuiteResult
    suite_id
    category
    command
    status
    passed
    failed
    skipped
    xfailed
    xpassed
    duration_seconds
    exit_code
    artifact_refs[]
    failure_refs[]
```

Statuses:

```text
passed
failed
incomplete
blocked
not_applicable
```

`blocked` means the suite could not run because a required environment/service was unavailable. It does **not** count as passed.

Unexpected skips or xpasses should be visible in evidence and may fail stricter profiles.

---

# 5. Standard test entry point

The repository should converge on one scriptable entry point so every executor runs the same profiles.

Target interface:

```text
./scripts/test smoke
./scripts/test pr
./scripts/test unit
./scripts/test integration
./scripts/test playtest
./scripts/test simulation
./scripts/test migration
./scripts/test replay
./scripts/test performance
./scripts/test full
./scripts/test nightly
./scripts/test release
```

A Python equivalent is acceptable where cross-platform support requires it, for example:

```text
python -m rpg_engine_api.testing smoke
```

The entry point must:

1. resolve the profile manifest;
2. print the exact revision/environment being tested;
3. run required suites in deterministic order where ordering matters;
4. preserve individual suite exit states;
5. generate machine-readable evidence;
6. return non-zero when required gates fail.

Agents must not silently replace the canonical profile with a shorter hand-picked command while claiming the canonical profile passed.

---

# 6. Test profiles

## `smoke`

Fast confidence for environment/startup/core command paths.

Typical content:

- import/startup/application factory;
- health/readiness;
- minimal deterministic command/event/replay test;
- minimal public API playtest.

## `pr`

Primary pre-merge profile.

Includes:

- all affected unit/integration suites;
- core deterministic/replay regressions;
- required public human-play scenarios;
- relevant controller tests;
- relevant authoring validation tests;
- relevant migration/compatibility checks;
- changed-feature coverage manifest validation.

Affected-test selection may reduce runtime, but mandatory core regressions cannot be omitted.

## `unit`

Pure/fast domain, rules, controller, schema, validation, and utility tests.

## `integration`

Configured service integration including PostgreSQL and other required infrastructure.

## `playtest`

Public REST/WebSocket human-play scenarios defined by `HUMAN_PLAYTESTING.md`.

## `simulation`

Simulation Quality Lab batches, invariants, reproducibility, and content-quality analysis.

## `migration`

Database migrations, event upcasters, projection rebuilds, content migrations, controller/profile migrations, and trusted-extension compatibility fixtures.

## `replay`

Golden history replays, canonical state hashes, snapshot/from-start equivalence, old-schema fixtures, and selected branch/checkpoint verification.

## `performance`

Measured benchmark profile. Performance regressions are reported against defined baselines/budgets rather than hidden thresholds.

## `full`

Complete deterministic correctness suite excluding only explicitly expensive scheduled/chaos/performance work.

## `nightly`

Full suite plus broader generated/property/fuzz/simulation matrices and selected recovery/chaos cases.

## `release`

Strict release gate including:

- clean revision/environment metadata;
- full correctness suite;
- complete required v1.0 acceptance scenarios for released capabilities;
- migration/replay compatibility;
- visibility/security checks;
- backup/restore/restart recovery where available;
- required simulation/content-quality gates;
- required performance profile;
- no unexplained required-suite skips or blocked results.

---

# 7. Merge and release gates

Code being logically complete and code being mergeable are separate states.

Conceptually:

```text
implementation_ready
    tests/scenarios written
    static review complete
    docs/migrations updated

execution_verified
    required TestEvidenceBundle exists
    evidence commit_sha matches candidate commit
    required profile completed
    mandatory suites passed
    no disallowed skips/blocks

mergeable
    implementation_ready
    + execution_verified
    + review/policy requirements
```

Default expectation:

- ordinary behavior-changing PR: `pr` evidence;
- migration/persistence-sensitive PR: `pr` + relevant `migration`/`replay` evidence;
- performance-sensitive change: `pr` + targeted `performance` evidence;
- release candidate: `release` evidence.

The exact merge policy may evolve, but missing required evidence must never be silently treated as success.

---

# 8. Evidence artifacts

Machine-readable evidence should live in a predictable output tree, for example:

```text
artifacts/test-evidence/<evidence_id>/
    evidence.json
    junit/
    coverage/
    playtest/
    replay/
    simulation/
    migration/
    performance/
    logs/
```

Artifacts may be uploaded to CI, attached to a PR, published by the local agent, or stored elsewhere according to deployment policy.

Large/generated evidence should not automatically be committed to the source repository. The repository should retain only durable golden fixtures/regressions that are intentionally version-controlled.

---

# 9. Human-play failure artifacts

For failed public play scenarios, preserve the contract from `HUMAN_PLAYTESTING.md`:

```text
scenario_id/version
commit_sha
content lock
seed bundle
personas/controllers
executed steps
REST receipts
WebSocket events
projection snapshots
authoritative sequence range
canonical hashes
failed assertion
```

The local agent should surface the smallest reproducible bundle sufficient for a remote agent to diagnose the failure without local-machine access.

---

# 10. Determinism and simulation evidence

Simulation/replay evidence must include the exact:

```text
engine commit
content lock
ruleset versions
controller/profile versions
extension versions
seed bundle
scenario/simulation configuration
```

When a failure/outlier matters, preserve or promote its seed/configuration as a durable regression fixture.

Do not report aggregate percentages without preserving enough configuration to reproduce representative failing/outlier runs.

---

# 11. Failure classification

The local agent should distinguish at least:

```text
product_failure
    code/test assertion failed

test_failure
    invalid/broken test or fixture

environment_failure
    database/service/runtime unavailable or misconfigured

flaky_or_nondeterministic
    repeated identical run does not reproduce consistently

performance_regression
    defined measured budget/baseline violated
```

Do not automatically retry until green and hide the first failure.

Retries may be used diagnostically, but the evidence should show that retries occurred and retain the original failing result when relevant.

---

# 12. Local test agent workflow

Recommended iteration:

```text
1. fetch/checkout candidate commit
2. verify worktree/revision
3. provision declared environment
4. run requested canonical profile
5. collect machine-readable evidence
6. if failure:
       classify failure
       preserve reproducible artifacts
       report exact failing suite/scenario/seed
7. if pass:
       report exact profile + commit + environment
8. attach/publish evidence for review
```

When a remote agent submits a fix, the local agent must test the new commit rather than assuming the previous evidence still applies.

---

# 13. Local agent permissions

The test agent may:

- install repository dependencies in its controlled environment;
- create disposable test databases/services;
- launch local API processes/containers;
- advance controllable test clocks;
- execute repository test/simulation/migration scripts;
- capture logs and test artifacts;
- reset disposable test data between runs.

It must not make hidden production-game mutations merely to force tests to pass.

If testing against a real shared deployment is ever supported, destructive operations require an explicitly designated disposable test scope/environment.

---

# 14. No fabricated verification

This is a repository-wide governance rule.

Agents must never fabricate:

- commands they did not execute;
- test counts they did not observe;
- green suite status without evidence;
- screenshots/logs/output they did not receive;
- local-environment behavior inferred only from code inspection.

When evidence is unavailable, say **not executed** or **execution evidence unavailable** and identify which local profile should run.

---

# 15. Evidence consumption by remote agents

A remote agent reviewing evidence should verify:

1. `commit_sha` matches the code under review;
2. requested profile is the profile actually executed;
3. required suites are present;
4. failures/skips/blocks are not hidden in aggregate status;
5. deterministic seeds/configuration are captured for relevant scenarios;
6. migrations/replay evidence exists when persistence interpretation changed;
7. performance evidence exists when a performance claim is being made.

The remote agent can then diagnose failures and prepare fixes using the artifact data without claiming direct local execution.

---

# 16. Roadmap integration

Implementation should start small:

```text
v0.1
    TestEvidenceBundle schema
    canonical test profile manifest/runner seam
    smoke/pr profile foundations
    JUnit/evidence artifact output

v0.2-v0.6
    add timing/controller/combat/spatial/character suites to canonical profiles

v0.7
    add authoring/session/simulation/content-quality profiles
    add local-agent long-form Testing Grounds execution

v0.8
    add advanced-controller/external-controller evidence

v0.9
    stabilize CLI/profile/evidence schemas
    support local/containerized/remote test deployment targets

v1.0
    release profile is a mandatory release artifact
    full gameplay + creator + operations + migration + replay + quality evidence
```

---

# 17. Completion rule

A feature can be **implemented** before it is **execution-verified**.

It cannot be described as locally tested/passing, and should not satisfy a milestone's execution gate, until matching local-agent or CI evidence exists for the candidate revision.

The project optimizes for reproducible proof rather than confidence-by-assertion.