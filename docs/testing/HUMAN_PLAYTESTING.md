# Human Playtesting Architecture

> **Execution policy:** all executable human-play scenarios are run by the designated local test agent. GitHub Actions and remote CI are not used. This local-only policy is defined by `PLAN.md` Section 50 and `docs/testing/LOCAL_TEST_AGENT.md`.

## Purpose

The project must be testable as if real humans were using supported clients end to end. Programmatic personas exercise the same public REST/WebSocket surfaces as human clients, while the server remains authoritative for rules, timing, visibility, state and outcomes.

The playtest harness is a client/test driver, not a second rules engine.

## Core requirements

A human-play scenario must be able to:

- authenticate or use the configured local test identity mechanism;
- discover campaign/ruleset/client capabilities;
- discover visible state and legal actions;
- submit the same typed commands a supported client submits;
- receive command receipts;
- observe WebSocket events/projection changes;
- respect visibility boundaries;
- exercise timing/deadline behavior with controllable clocks;
- disconnect/reconnect/resume;
- replay the resulting authoritative history;
- capture deterministic seeds and enough evidence to reproduce failures.

Direct database/domain mutation does not count as end-to-end playtesting except when explicitly testing migrations/recovery internals.

## Personas

Initial reusable personas include:

```text
PlayerPersona
DmPersona
SpectatorPersona
SlowPlayerPersona
ReconnectingPlayerPersona
InvalidActionPersona
MultiDevicePlayerPersona
```

NPCs are not puppeted by the player harness once autonomous controllers exist. `SimpleNpcController` must independently drive canonical enemy turns from P2 onward.

## Human-like behavior model

Scenarios may model:

- think delays using controllable/fake clocks;
- actions just before deadlines;
- exact deadline boundaries;
- timeout/no-action;
- invalid action followed by correction;
- accept/decline reaction choices;
- disconnect/reconnect;
- retries and duplicate commands;
- stale version conflicts;
- multiple players acting concurrently where allowed.

Never use long real sleeps to simulate player thinking or game-time progression.

## Deterministic seed separation

Keep independent streams for:

```text
game dice
loot
world/procedural generation
encounter generation
controller variation when enabled
playtest persona behavior
```

Changing a persona think delay must not alter the next combat d20 result.

## Scenario representation

Use typed/versioned scenario definitions. Conceptually:

```text
PlayScenario
    schema_version
    scenario_id
    scenario_version
    description
    required_capabilities
    content_fixture
    seed_bundle
    personas[]
    steps[]
    expected_invariants[]
    required_artifacts[]
```

A step should represent an observable human/client action or expectation, not an internal implementation shortcut.

Example step kinds:

```text
connect
create_campaign
join_lobby
create_character
select_actor
query_projection
query_available_actions
submit_command
wait_for_event
advance_test_clock
disconnect
reconnect
assert_visible
assert_hidden
assert_error
assert_event
assert_projection
assert_replay_hash
```

## Thin-client rule

The playtest client may:

- understand public API schemas;
- query server-advertised options/actions;
- choose among advertised choices;
- retain public IDs/sequence cursors;
- assert expected visible outcomes.

It must not:

- duplicate attack legality formulas;
- calculate hidden perception state;
- decide whether a spell/action should legally exist when the server can advertise it;
- access private server aggregates to choose its next human action;
- patch authoritative state directly.

## Available-action walker

Provide a generated-play mode that:

```text
query visible state
query available legal actions
choose one advertised action using deterministic persona seed
submit action
observe result
repeat
```

This explores valid state space without embedding a duplicate rules engine in tests.

Generated walkers complement curated human journeys; they do not replace them.

## Negative/generated play

Systematically test rejected behavior such as:

```text
wrong target
out-of-range action
stale stream version
insufficient resource
expired decision window
unauthorized actor
invalid creation choice
invalid progression choice
hidden target/object reference
malformed payload
duplicate idempotency conflict
```

Rejections must be deterministic and machine-readable.

## Multiplayer playtests

Cover:

- concurrent players;
- player + DM commands;
- actor-control handoff;
- simultaneous reactions;
- spectator visibility;
- slow clients;
- multi-device conflicts;
- disconnect/reconnect during decision windows.

## Chaos/recovery playtests

Where implemented, local scenarios should exercise:

- transport disconnect;
- duplicate delivery/retry;
- slow WebSocket consumer;
- server restart;
- database reconnect;
- outbox delay;
- projection lag/rebuild;
- restart during scheduled/decision state.

The harness must distinguish product failures from intentionally injected infrastructure failures.

## Playtest transcript

Produce a readable step transcript such as:

```text
[001] player connects
[002] campaign projection sequence=14
[003] player queries available actions
[004] player chooses attack(target=goblin_1)
[005] receipt accepted
[006] AttackResolved observed
[007] NPC controller chooses move_toward
...
```

Transcripts should reference public commands/events/projections and remain safe to share without secrets.

## Failure replay bundle

When a scenario fails, preserve as applicable:

```text
scenario_id/version
engine commit SHA
content lock
ruleset/controller versions
seed bundle
personas
executed steps
REST requests/receipts
WebSocket event sequence
projection snapshots
canonical hashes
failed assertion
local environment fingerprint
```

This bundle should let a remote development agent diagnose the failure without access to the local machine.

## Feature coverage manifest

Maintain machine-readable coverage linking features to proof:

```text
feature_id
milestone
unit_tests[]
integration_tests[]
playtest_scenarios[]
simulation_checks[]
roles[]
timing_modes[]
spatial_adapters[]
negative_cases[]
visibility_cases[]
reconnect_cases[]
replay_cases[]
required_local_profiles[]
```

Every user-visible gameplay capability should have at least one public-interface human journey unless there is a documented reason it cannot.

## Local execution profiles

Canonical local test profiles include:

```text
smoke
pr
playtest
simulation
replay
full
nightly
release
```

`nightly` is a **local profile name**, not a GitHub Actions schedule. It may be run manually or by a user-controlled local scheduler.

No GitHub Actions workflow may be used to execute these scenarios.

## Regression rule

Any player-visible bug should gain a regression scenario at the narrowest useful level. If the bug appeared through a public human journey, add or extend a black-box playtest whenever practical.

## Testing Grounds

`Testing Grounds` is the canonical growing playable campaign fixture. It should eventually exercise one continuous journey:

```text
content install/publish
-> create campaign
-> join lobby/session
-> create/select hero
-> town dialogue/quest/trade
-> travel/discovery/object interaction
-> autonomous NPC encounter
-> rewards/progression
-> checkpoint
-> disconnect/reconnect/control restoration
-> session close/recap/journal
-> deterministic replay
-> content revision/migration/continued play
```

The same story should grow as milestones land instead of being replaced by disconnected endpoint fixtures.

## Milestone requirement

A gameplay milestone is not execution-complete until:

- required public scenarios exist;
- earlier cumulative playability scenarios remain intact;
- the designated local test agent executes the required canonical profile(s) against the exact candidate commit;
- a matching `TestEvidenceBundle` records the result.

Code review or remote reasoning can establish implementation readiness, not local execution success.