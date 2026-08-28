# RPG Engine API — Executable End-to-End TODO

## Purpose

This file is the **day-to-day execution queue** for `rpg-engine-api`.

Authority order:

1. `PLAN.md` — architecture, roadmap, non-negotiable invariants, milestone scope.
2. Normative subsystem specifications under `docs/` — detailed contracts.
3. **`TODO.md` — ordered implementation work and completion evidence.**

`TODO.md` does not replace `PLAN.md`. If a TODO conflicts with the plan, the plan wins and the TODO must be corrected.

**Execution policy:** all runtime verification is performed by the designated local test agent. GitHub Actions and remote CI are not used. Any older phrase such as `local-agent/CI` is superseded by `PLAN.md` Section 50 and means **local-agent evidence only**.

The central delivery requirement is not merely to accumulate APIs. The repository must converge continuously toward a product that a real person can **launch, create or load a game, play through public interfaces, encounter autonomous non-human actors, save/reconnect/replay, and eventually author and evolve content**.

---

# 1. How agents use this TODO

Before starting repository work:

- read `PLAN.md`;
- read `AGENTS.md`;
- read the normative spec(s) relevant to the task;
- read this file;
- identify the earliest unchecked, unblocked item in the active roadmap milestone unless the user explicitly requests a later item;
- keep the change small enough to review and test;
- add tests/scenarios/evidence hooks in the same change where practical;
- never mark execution-verification items complete without exact-commit **local-agent** evidence;
- never add or rely on GitHub Actions workflows.

When an architectural discovery changes the correct sequence, update `PLAN.md` first if architecture changes, then update this TODO.

## Status convention

Use Markdown checkboxes plus an optional status suffix:

```text
[ ] not started
[ ] [IN PROGRESS] implementation is actively being changed
[ ] [AWAITING EVIDENCE] implementation exists but required local execution evidence is missing
[ ] [BLOCKED: reason] cannot proceed until a named dependency is resolved
[x] complete and supported by the required evidence/inspection
```

Do not use `[x]` for an execution gate because code merely looks correct.

---

# 2. Definition of “playable”

A build is **playable** at a given gate only if a programmatic human persona or reference client can use production-equivalent public interfaces to perform the gate’s complete journey without direct domain/database mutation.

A mature playable build must ultimately support this human journey:

```text
clean checkout
    -> install/configure
    -> start PostgreSQL + server
    -> health/readiness green
    -> discover rules/content
    -> create or load campaign
    -> join lobby/session
    -> create/select character
    -> enter world
    -> inspect visible state
    -> move/explore/interact
    -> talk/quest/trade/craft
    -> enter encounter
    -> fight autonomous NPCs
    -> react/use abilities/resources/items
    -> receive rewards/progress
    -> checkpoint
    -> disconnect/reconnect
    -> continue play
    -> close session
    -> inspect recap/journal/history
    -> replay to same canonical state
```

Creator/DM maturity extends the journey:

```text
create content workspace
    -> author content
    -> validate/reachability-check
    -> simulate/playtest
    -> publish immutable content pack
    -> create campaign from it
    -> operate live session
    -> propose content revision
    -> diff/impact/dry-run migration
    -> checkpoint + activate
    -> verify old/new replay
    -> rollback/branch if required
```

---

# 3. Playability ladder and release gates

These gates are cumulative. A later gate includes the earlier behavior unless explicitly superseded.

## P0 — Bootable engine

A clean environment can start the service and execute one deterministic public command.

Required proof:

```text
start service
GET health/readiness
CreateCampaign
CreateActor
submit one legal public command
observe receipt + event + projection
replay
same canonical hash
```

Local profile: `smoke`.

## P1 — Minimal playable command loop

A thin reference client can create a tiny game state, query what the actor can do, choose an advertised action, observe the resulting state/log, and repeat.

No combat is required yet, but the loop must feel interactive rather than being isolated API examples.

Local profile: `pr` plus a black-box playtest scenario.

## P2 — Playable combat slice

A human can play a complete basic encounter against at least one `SimpleNpcController` opponent:

```text
load Testing Grounds combat fixture
join/select character
start encounter
query visible state + available actions
move
attack/use representative resource action
NPC autonomously chooses legal action
open/resolve reaction if available
finish encounter
receive reward/result
inspect combat log
replay to same state
```

This is the first **game-like vertical slice** and must be protected as a permanent regression path.

Local profiles: `pr`, `playtest`, `replay`; `simulation` for AI-vs-AI smoke.

## P3 — Playable exploration slice

A human can move through a small world, perceive only known/visible information, discover something, interact with an object/container, travel, and enter the P2 encounter naturally from exploration state.

Local profiles: `playtest`, `replay`.

## P4 — Playable character/progression slice

A human can create a valid character through server-discovered choices, enter the game with that character, complete gameplay, gain advancement, and make a legal progression choice that changes available gameplay options.

Local profiles: `playtest`, `replay`, targeted `migration` when schemas evolve.

## P5 — Playable campaign session

A DM and player can create a campaign, join a lobby, complete ready flow, open a session, play town/social/quest/trade/travel/combat/reward/progression, checkpoint, disconnect/reconnect, close the session, and inspect recap/history.

Local profiles: `full`, plus relevant `simulation` and `replay`.

## P6 — Playable creator-to-game flow

A creator can author a small content pack, validate it, run reachability/simulation/playtest checks, publish it, create a campaign using it, and play the resulting content end to end.

Local profiles: `full`, `simulation`, `playtest`.

## P7 — Playable content-evolution flow

A creator/DM can revise published content, inspect semantic diff and campaign impact, dry-run migration, automatically checkpoint, activate the update, continue play, and verify replay across old/new content locks. Unsafe direct rollback must branch from the pre-upgrade checkpoint.

Local profiles: `migration`, `replay`, `full`.

## P8 — Release-quality playable platform

The exact release candidate passes the complete gameplay acceptance matrix, creator/session/quality acceptance set, visibility/security checks, recovery, migration/replay, deterministic simulation gates, and defined performance profile with one exact-commit local `release` `TestEvidenceBundle`.

Local profile: `release`.

---

# 4. Phase A — Repository and execution foundation (v0.1)

Goal: establish a clean modern Python project, deterministic core contracts, local test execution evidence, and P0/P1.

## A1. Project scaffold

- [ ] Add `pyproject.toml` targeting Python 3.12+.
- [ ] Establish `src/rpg_engine_api/` package layout from `PLAN.md`.
- [ ] Add application factory and configuration model.
- [ ] Add structured settings separation for runtime/test environments.
- [ ] Add basic lint/type/test tooling appropriate to the project.
- [ ] Add migration directory/Alembic scaffold before persistence schemas stabilize.
- [ ] Add `.gitignore` rules for virtualenvs, caches, local DB/test artifacts, secrets, and generated evidence.
- [ ] Add README quick-start sufficient for the local agent.
- [ ] Add health and readiness endpoints with distinct semantics.
- [ ] Ensure no import-time network/database side effects.
- [ ] Ensure `.github/workflows/` is absent/empty and no GitHub Actions dependency exists.

## A2. Canonical local test runner and evidence

- [ ] Create `scripts/test` as the single canonical local test entry point.
- [ ] Implement named profiles: `smoke`, `pr`, `unit`, `integration`, `playtest`, `simulation`, `migration`, `replay`, `performance`, `full`, `nightly`, `release`.
- [ ] Define a machine-readable test-profile manifest mapping each profile to required suites.
- [ ] Implement `TestEvidenceBundle` schema from `docs/testing/LOCAL_TEST_AGENT.md`.
- [ ] Record exact commit SHA and dirty-worktree state.
- [ ] Record safe environment/dependency/PostgreSQL/config fingerprints.
- [ ] Record per-suite command, exit code, counts, duration, status and artifact refs.
- [ ] Preserve required skips/blocks distinctly from pass.
- [ ] Add predictable output under `artifacts/test-evidence/<evidence_id>/`.
- [ ] Ensure secrets/tokens are redacted from evidence/logs.
- [ ] Add JUnit/coverage hooks where supported.
- [ ] Add a human-readable execution summary derived from the machine bundle.
- [ ] Add self-tests for the runner/evidence parser.
- [ ] Ensure all profile execution is local and no profile invokes GitHub Actions/remote CI.

## A3. Shared identifiers and definitions

- [ ] Implement opaque runtime IDs and namespaced content keys.
- [ ] Implement `DefinitionRef` with exact pack/version/key/hash semantics.
- [ ] Implement source/license metadata.
- [ ] Implement typed visibility policy primitives.
- [ ] Implement `RequirementExpr` AST/schema.
- [ ] Implement `ChoiceGroup`.
- [ ] Implement `Grant`.
- [ ] Implement definition/schema registry seam.
- [ ] Add round-trip serialization tests.
- [ ] Add schema-version fields from first release.

## A4. Controller assignment seam

- [ ] Implement `ControllerAssignment`.
- [ ] Support `human`, `simple_npc`, `scripted`, `remote_service`, `system` identifiers without advanced implementations.
- [ ] Add controller registry/interface boundary.
- [ ] Ensure domain state does not import external AI clients.
- [ ] Preserve controller version/profile refs for replay provenance.
- [ ] Add assignment serialization/validation tests.

## A5. Commands, receipts and errors

- [ ] Implement typed `CommandEnvelope`.
- [ ] Derive principal/permissions server-side, never from trusted payload fields.
- [ ] Implement `CommandReceipt` statuses.
- [ ] Implement stable machine error codes.
- [ ] Implement request/correlation/causation IDs.
- [ ] Add command schema versions.
- [ ] Add validation for idempotency key and expected stream version.
- [ ] Add API error envelope tests.

## A6. Events and deterministic RNG

- [ ] Implement immutable/versioned domain event envelope.
- [ ] Include campaign/stream sequence metadata.
- [ ] Implement deterministic RNG service.
- [ ] Separate named RNG streams at minimum: dice, loot, encounter, world, procedural generation.
- [ ] Keep playtest behavior RNG separate.
- [ ] Reserve controller RNG stream without requiring it for baseline AI.
- [ ] Implement auditable `DiceRolled` event.
- [ ] Add deterministic repeatability/golden tests.

## A7. Campaign and actor foundations

- [ ] Implement minimal campaign aggregate/state.
- [ ] Implement minimal actor aggregate/state.
- [ ] Implement `CreateCampaign -> CampaignCreated`.
- [ ] Implement `CreateActor -> ActorCreated`.
- [ ] Attach controller assignment to actor state.
- [ ] Implement canonical state serialization/hash.
- [ ] Add replay reducer/application seam.

## A8. Event store, idempotency and replay

- [ ] Implement append-only in-memory event store for tests.
- [ ] Enforce stream versions.
- [ ] Implement idempotent command receipt store.
- [ ] Reject stale expected version deterministically.
- [ ] Implement replay from stream start.
- [ ] Implement event upcaster interface.
- [ ] Implement snapshot interface/version metadata.
- [ ] Add projection version/checkpoint seam.
- [ ] Add transactional outbox interface.
- [ ] Add canonical replay hash tests.

## A9. PostgreSQL persistence

- [ ] Design/create `event_streams`.
- [ ] Design/create `domain_events`.
- [ ] Design/create `command_receipts`.
- [ ] Design/create `snapshots`.
- [ ] Design/create projection checkpoint/version storage.
- [ ] Design/create transactional outbox.
- [ ] Add uniqueness constraints for event IDs, stream versions and idempotency.
- [ ] Add indexes for expected event/history queries.
- [ ] Implement SQLAlchemy 2.x async/asyncpg paths.
- [ ] Add Alembic migration.
- [ ] Add transaction rollback/failure tests.
- [ ] Add real PostgreSQL local-agent integration suite.

## A10. Public command/query path

- [ ] Add initial `/api/v1` routing.
- [ ] Add typed command endpoint/gateway.
- [ ] Add minimal campaign/actor projections.
- [ ] Add projection metadata including sequence/schema version.
- [ ] Add basic available-action/capability discovery seam.
- [ ] Ensure public API cannot patch authoritative state directly.
- [ ] Add ASGI-native async contract tests.

## A11. WebSocket seam

- [ ] Add campaign WebSocket endpoint skeleton.
- [ ] Define `client.hello/subscribe/unsubscribe/ack/ping` schemas.
- [ ] Define `server.ready/event/resync_required/error/pong` schemas.
- [ ] Add ordered sequence field.
- [ ] Add visibility-filter-before-enqueue seam.
- [ ] Add resume metadata/seam.
- [ ] Add bounded buffer/backpressure design tests.

## A12. Playtest harness foundation

- [ ] Create `tests/playtest/harness/`.
- [ ] Implement persona abstraction.
- [ ] Implement async REST client.
- [ ] Implement WebSocket client seam.
- [ ] Implement typed/versioned scenario + step schema.
- [ ] Implement scenario runner.
- [ ] Implement assertions helper library.
- [ ] Implement independent scenario behavior seed.
- [ ] Implement controllable test-clock abstraction.
- [ ] Implement transcript output.
- [ ] Implement failure replay bundle.
- [ ] Implement feature coverage manifest format.
- [ ] Create Testing Grounds fixture skeleton.

## A13. P0/P1 playable gate

- [ ] Start app from clean environment using documented command.
- [ ] Health/readiness pass.
- [ ] Public client creates campaign.
- [ ] Public client creates actor.
- [ ] Public client observes actor/campaign projection.
- [ ] Public client discovers at least one legal generic action/command.
- [ ] Public client performs it.
- [ ] Receipt/events/projection update are observed.
- [ ] Duplicate retry produces no duplicate authoritative event.
- [ ] Stale version produces deterministic conflict.
- [ ] Replay reaches identical canonical hash.
- [ ] Local `smoke` evidence exists for exact commit.
- [ ] Local `pr` evidence exists before v0.1 is declared execution-verified.

---

# 5. Phase B — Time and universal action runtime (v0.2)

Goal: one deterministic scheduler/action model supports all planned timing policies.

## B1. Simulation clock/timeline

- [ ] Implement `SimulationClock`.
- [ ] Implement timeline aggregate/state.
- [ ] Implement durable scheduled-event records.
- [ ] Implement deterministic priority/tie ordering.
- [ ] Implement schedule/cancel/reschedule.
- [ ] Implement pause/resume.
- [ ] Implement exact simulation-time advancement for tests.
- [ ] Keep wall-clock decision deadlines separate.

## B2. Timing policies

- [ ] Implement turn-based policy.
- [ ] Implement timed-turn-based policy.
- [ ] Implement active-time policy.
- [ ] Implement real-time-with-pause policy.
- [ ] Implement real-time policy foundation.
- [ ] Implement hybrid policy composition seam.
- [ ] Add timeout policy interface.
- [ ] Implement `forfeit_turn` baseline.
- [ ] Add hooks for auto-defend/AI-control/DM-decision variants.
- [ ] Add exact deadline-boundary tests with controllable clock.

## B3. Universal action transaction

- [ ] Implement `ActionDefinition`.
- [ ] Implement `ActionInstance` lifecycle.
- [ ] Implement prerequisites and action availability.
- [ ] Implement target schema/target validation seam.
- [ ] Implement cost reservation/payment/refund policies.
- [ ] Implement queued/windup/completion states.
- [ ] Implement cancel/interruption behavior.
- [ ] Implement cooldown/recovery scheduling.
- [ ] Implement movement action foundation.
- [ ] Implement simultaneous conflict ordering.
- [ ] Add rule that interruption does not generically roll back already-emitted effects.

## B4. Controller eligibility

- [ ] Emit/request controller decision when eligible actor becomes ready.
- [ ] Add reaction-window controller hook.
- [ ] Ensure event-driven operation; no controller polling loop.
- [ ] Add safe controller timeout/fallback seam.

## B5. Timing playtests

- [ ] Same sample action works under every timing mode.
- [ ] Timed human turn expires deterministically.
- [ ] Just-before-deadline action succeeds where policy says so.
- [ ] Exact-boundary behavior is specified/tested.
- [ ] Disconnect/reconnect during decision window is deterministic.
- [ ] Reservation/refund behavior is visible through public API.
- [ ] Multiple personas can submit competing actions without nondeterministic overwrite.
- [ ] Required local `pr`/`playtest` evidence captured.

---

# 6. Phase C — First real game: combat + SimpleNpcController (v0.3)

Goal: achieve **P2**, the first unmistakably game-like playable slice.

## C1. Encounter lifecycle

- [ ] Implement encounter definition/runtime separation.
- [ ] Implement `EncounterTemplate` schema.
- [ ] Implement start/active/complete/aborted states.
- [ ] Implement participant/controller assignments.
- [ ] Implement initiative/readiness mapping.
- [ ] Implement encounter objectives/completion policy.
- [ ] Implement reward-result seam.

## C2. Combat rules foundation

- [ ] Implement checks/saves/attack resolution contexts.
- [ ] Implement attack rolls and deterministic damage/healing.
- [ ] Implement health/down/defeated state.
- [ ] Implement modifiers.
- [ ] Implement basic conditions.
- [ ] Implement reactions/interrupt windows.
- [ ] Implement basic combat movement/target validation.
- [ ] Implement player-facing combat log projection.
- [ ] Implement rule traces suitable for debugging.

## C3. SimpleNpcController combat MVP

- [ ] Implement deterministic baseline controller.
- [ ] Implement aggressive-melee profile.
- [ ] Implement ranged profile.
- [ ] Implement balanced/defensive profile.
- [ ] Implement support profile.
- [ ] Implement passive profile.
- [ ] Implement flee profile.
- [ ] Use only visibility-filtered controller view.
- [ ] Use only server-advertised legal actions/targets.
- [ ] Deterministic stable tie-breaking.
- [ ] Safe fallback when preferred action fails/rejects.
- [ ] Controller decision does not consume combat/dice RNG.
- [ ] Persist controller/profile versions for replay provenance.

## C4. P2 Testing Grounds combat

- [ ] Create a canonical combat fixture.
- [ ] Human character enters encounter through public API.
- [ ] Human can inspect visible opponents.
- [ ] Human can query legal actions.
- [ ] Human can move.
- [ ] Human can make a basic attack.
- [ ] Human can exercise a representative limited resource/action.
- [ ] Autonomous NPC moves/attacks without harness puppeteering.
- [ ] Human/NPC reaction path executes.
- [ ] Encounter completes naturally.
- [ ] Reward/result is visible.
- [ ] Combat log is understandable.
- [ ] Full encounter replays to identical canonical hash.
- [ ] AI-vs-AI simulation is deterministic.
- [ ] Local `playtest`, `replay`, and `simulation` evidence captured.

---

# 7. Phase D — Effects, resources, abilities and progression (v0.4)

Goal: replace ad-hoc combat mechanics with reusable authored/data-driven systems while preserving P2.

## D1. Effect/runtime primitives

- [ ] Implement `EffectDefinition`/instances.
- [ ] Implement modifier pipeline.
- [ ] Implement trigger hooks.
- [ ] Implement durations.
- [ ] Implement stacking/replacement rules.
- [ ] Implement periodic effects.
- [ ] Implement maintenance/concentration-like resource hooks generically.
- [ ] Implement temporary grants.

## D2. Resources/abilities

- [ ] Implement `ResourceDefinition/State`.
- [ ] Implement recovery rules.
- [ ] Implement `AbilityDefinition`.
- [ ] Map abilities into universal actions.
- [ ] Implement representative ability/spell/power.
- [ ] Ensure human and NPC actors use same mechanics.

## D3. Progression primitives

- [ ] Implement progression graph/node/edge schemas.
- [ ] Implement prerequisites through `RequirementExpr`.
- [ ] Implement grants/revokes.
- [ ] Implement ranks.
- [ ] Implement exclusive branches.
- [ ] Implement progression currency.
- [ ] Implement respec policy seam.
- [ ] Add progression reachability analysis.

## D4. Authoring and simulation

- [ ] Add authoring schemas for effect/resource/ability/progression definitions.
- [ ] Validate/publish representative authored mechanics.
- [ ] Extend available-action walker to generated abilities.
- [ ] Add simulation metrics for ability/resource use.
- [ ] Preserve P2 combat with data-driven implementations.
- [ ] Capture required local playtest/simulation evidence.

---

# 8. Phase E — Spatial authority, perception and exploration (v0.5)

Goal: achieve **P3**: exploration/discovery naturally flows into P2 combat.

## E1. Spatial adapters

- [ ] Theater-of-mind adapter.
- [ ] Graph adapter.
- [ ] Square-grid adapter.
- [ ] Hex adapter.
- [ ] Continuous 2D adapter.
- [ ] Continuous 3D interface/contract even if full implementation is deferred.
- [ ] Distance/reach.
- [ ] Occupancy.
- [ ] Pathfinding.
- [ ] Terrain cost.
- [ ] LOS/cover.
- [ ] Area queries.

## E2. Movement

- [ ] Walk/run/crawl movement modes.
- [ ] Climb/swim movement seams.
- [ ] Fly/jump/teleport/forced movement policy seams.
- [ ] Server-authoritative trajectory representation for real-time modes.
- [ ] Movement interruption/collision policy.

## E3. Perception/knowledge

- [ ] Sense definitions.
- [ ] `can_perceive` rule contract.
- [ ] Detection vs identification.
- [ ] Known-position semantics.
- [ ] Discovery events.
- [ ] Hidden fields remain absent/redacted until known.
- [ ] Controller views use same knowledge boundary.

## E4. World objects/exploration

- [ ] Region/location/world schemas.
- [ ] Scene/map definitions.
- [ ] Object/container definitions/instances.
- [ ] Doors/barriers.
- [ ] Hazards/traps seam.
- [ ] Search/investigate/interact actions.
- [ ] Travel action.
- [ ] Marching-order foundation.

## E5. P3 Testing Grounds

- [ ] Town/road/forest/camp/ruins locations.
- [ ] Travel between visible locations.
- [ ] Hidden path initially absent from player projection.
- [ ] Discovery action reveals hidden path.
- [ ] Container/object interaction.
- [ ] NPC cannot target undiscovered/hidden actor.
- [ ] Travel to encounter location starts P2 combat naturally.
- [ ] Return state remains consistent after encounter.
- [ ] Replay produces identical knowledge/world state.
- [ ] Local playtest/replay evidence captured.

---

# 9. Phase F — Complete character runtime and progression (v0.6)

Goal: achieve **P4**: create a real character, play it, earn progression and make a meaningful advancement choice.

## F1. Character creation discovery

- [ ] Ruleset character-creation schema endpoint.
- [ ] Step graph/dependencies.
- [ ] Dynamic choice groups.
- [ ] Human-readable descriptions/UI metadata.
- [ ] Validation errors/warnings.

## F2. Character creation session

- [ ] Start/resume/cancel/expire creation draft.
- [ ] Choose class.
- [ ] Choose species.
- [ ] Choose background/origin.
- [ ] Choose languages.
- [ ] Choose proficiencies.
- [ ] Choose equipment.
- [ ] Choose features/feats.
- [ ] Choose spells/powers where applicable.
- [ ] Identity/details.
- [ ] Ability-generation methods.
- [ ] Dependency invalidation/revalidation.
- [ ] Finalize transaction.

## F3. Character runtime

- [ ] Complete character sheet projection.
- [ ] Class/subclass tracks.
- [ ] Species/background traits.
- [ ] Proficiencies/skills.
- [ ] Inventory/equipment connection.
- [ ] Spell/power known/prepared state.
- [ ] Lifecycle states.
- [ ] Import/export validation boundary.
- [ ] Higher-level start.
- [ ] Multiclassing.

## F4. Advancement

- [ ] XP policy.
- [ ] Milestone policy.
- [ ] Quest/session reward hooks.
- [ ] Resumable advancement transaction.
- [ ] Progression choices.
- [ ] Recalculate projections from grants/effects.

## F5. P4 Testing Grounds

- [ ] Programmatic human creates character entirely from server-discovered schema.
- [ ] Character enters Testing Grounds.
- [ ] Character completes exploration/combat.
- [ ] Character gains XP/milestone/progression currency.
- [ ] Advancement becomes available.
- [ ] Player selects one legal progression choice.
- [ ] New ability/feature/action is visible and usable.
- [ ] Character replay remains deterministic.
- [ ] Creation/progression reachability analysis passes.
- [ ] Local playtest/replay evidence captured.

---

# 10. Phase G — Complete campaign composition / Creator Studio / DM operations (v0.7)

Goal: achieve **P5 and P6**: host a complete session and author playable content through one coherent platform.

## G1. Campaign creator

- [ ] Resumable campaign creation session.
- [ ] Ruleset/content-pack selection.
- [ ] Template selection.
- [ ] Timing/deadline/timeout policy configuration.
- [ ] Spatial configuration.
- [ ] Progression/rest/death/difficulty policies.
- [ ] World/calendar configuration.
- [ ] Visibility/logging policies.
- [ ] House rules.
- [ ] Validate/finalize campaign.

## G2. Membership/lobby/session

- [ ] Invitations.
- [ ] Membership roles.
- [ ] Lobby open/join/leave.
- [ ] Character/actor assignment.
- [ ] Actor control grants.
- [ ] Ready checks.
- [ ] Session open/pause/resume/close.
- [ ] Spectator role.
- [ ] Multi-device conflict policy.
- [ ] Disconnect grace/AFK policies.
- [ ] SimpleNpcController temporary handoff.
- [ ] Explicit human-control restoration.

## G3. Living world

- [ ] Calendar/time-of-day.
- [ ] World event scheduler.
- [ ] Weather/environment.
- [ ] Travel durations/events.
- [ ] NPC schedules.
- [ ] Idle/follow/hold/move-to-location controller states.

## G4. Social/dialogue

- [ ] Social actions.
- [ ] Dialogue graph definitions/runtime.
- [ ] Dialogue choices/requirements/effects.
- [ ] `NpcPersonalityProfile`.
- [ ] Relationship state.
- [ ] Faction reputation.
- [ ] Deterministic narration templates.
- [ ] Visibility-safe player messages.

## G5. Quests

- [ ] Quest definitions/instances.
- [ ] Sequential objectives.
- [ ] Parallel objectives.
- [ ] Optional objectives.
- [ ] Exclusive branches.
- [ ] Hidden/timed/repeatable objective seams.
- [ ] Quest rewards.
- [ ] Quest journal projection.
- [ ] Reachability analysis.

## G6. Inventory/economy

- [ ] Item definitions/instances.
- [ ] Containers.
- [ ] Equipment.
- [ ] Currency/wallets.
- [ ] Vendors.
- [ ] Buy/sell/trade transaction.
- [ ] Loot/reward tables.
- [ ] Acquisition-path analysis.

## G7. Crafting

- [ ] Recipe definitions.
- [ ] Ingredient/tool requirements.
- [ ] Scheduled crafting job.
- [ ] Completion/failure/cancel policies.
- [ ] Crafted-item grants.

## G8. Creator workspaces

- [ ] `AuthoringWorkspace`.
- [ ] `DraftDefinition`.
- [ ] Mutable draft lifecycle.
- [ ] Draft revision conflict control.
- [ ] Definition-type schema discovery.
- [ ] Schema validation.
- [ ] Namespace/reference validation.
- [ ] Ruleset compatibility validation.
- [ ] Provenance/license validation.
- [ ] Graph/reachability validation.
- [ ] Runtime preview/instantiation.
- [ ] Playtest/simulation gate references.
- [ ] Publish-ready state.
- [ ] Immutable versioned `PublishedContentPack`.
- [ ] Pack hashes/manifests/dependencies.

## G9. Creator/DM Studio APIs

- [ ] Creature/NPC editor API.
- [ ] Item/equipment editor API.
- [ ] Ability/spell/power editor API.
- [ ] Class/species/background editor API.
- [ ] Progression-tree editor API.
- [ ] Encounter editor API.
- [ ] Quest editor API.
- [ ] Dialogue editor API.
- [ ] World/location/scene editor API.
- [ ] Vendor/economy editor API.
- [ ] Recipe editor API.
- [ ] Behavior/personality profile editor API.
- [ ] Campaign-template editor API.
- [ ] Narration-template editor API.

## G10. Encounter authoring

- [ ] Participant groups.
- [ ] Spawn rules/positions.
- [ ] Controller/profile assignments.
- [ ] Waves.
- [ ] Triggers.
- [ ] Objectives.
- [ ] Environmental effects.
- [ ] Reinforcements.
- [ ] Escape/failure/completion conditions.
- [ ] Rewards.
- [ ] Scaling policy.
- [ ] Preview resolved participants/actions/map validity.

## G11. Simulation Quality Lab

- [ ] Simulation-run schema.
- [ ] Engine/content/controller/seed provenance.
- [ ] Single encounter simulation.
- [ ] Batch deterministic simulation.
- [ ] Outcome/duration/turn metrics.
- [ ] Damage/healing/resource metrics.
- [ ] Action-selection frequency.
- [ ] Objective completion metrics.
- [ ] Controller/profile comparison.
- [ ] Matched-seed content-version comparison.
- [ ] Outlier preservation/reproduction.
- [ ] No opaque universal balance score.

## G12. Content Testing SDK

- [ ] Validate pack.
- [ ] Instantiate creature.
- [ ] Instantiate encounter.
- [ ] Run scenario.
- [ ] Run simulation batch.
- [ ] Analyze quest reachability.
- [ ] Analyze dialogue reachability.
- [ ] Analyze progression reachability.
- [ ] Detect unobtainable item.
- [ ] Detect unusable ability.
- [ ] Produce machine-readable `ContentQualityReport`.

## G13. Checkpoints/branches

- [ ] Named checkpoint schema/API.
- [ ] Reference sequence/time/content lock.
- [ ] Automatic session-boundary checkpoint policy.
- [ ] Branch from checkpoint.
- [ ] Branch from arbitrary permitted sequence.
- [ ] Preserve parent/fork metadata.
- [ ] Verify identical canonical state at fork.
- [ ] Checkpoint deletion deletes only reference.

## G14. Recaps/journals

- [ ] Session recap projection.
- [ ] Character journal.
- [ ] Quest journal.
- [ ] Discovery journal.
- [ ] Campaign chronicle.
- [ ] NPC encounter history.
- [ ] Visibility filtering.
- [ ] Optional AI summary seam operating only on structured visible facts.

## G15. P5 long-form Testing Grounds session

- [ ] DM creates campaign.
- [ ] Player joins lobby.
- [ ] Player creates/selects hero.
- [ ] Ready check.
- [ ] Session opens.
- [ ] Player enters town.
- [ ] Player talks to Tavern NPC.
- [ ] Player accepts quest.
- [ ] Player visits merchant/blacksmith.
- [ ] Player buys/sells/receives an item.
- [ ] Player leaves through gate.
- [ ] Player travels road/forest.
- [ ] Player discovers hidden path.
- [ ] Player interacts with object/container/hazard.
- [ ] Player reaches Goblin Camp.
- [ ] Autonomous NPC encounter completes.
- [ ] Player earns rewards/quest progress.
- [ ] Player advances character.
- [ ] DM/player creates checkpoint.
- [ ] Player disconnects.
- [ ] Optional temporary NPC-controller handoff executes if configured.
- [ ] Player reconnects and regains control.
- [ ] Session closes cleanly.
- [ ] Recap/journals are generated.
- [ ] Full campaign replays deterministically.
- [ ] Local `full`/`replay` evidence captured.

## G16. P6 creator-to-game flow

- [ ] Creator opens workspace.
- [ ] Creator drafts NPC + personality + behavior profile.
- [ ] Creator drafts item/ability.
- [ ] Creator drafts quest/dialogue.
- [ ] Creator drafts encounter/world content.
- [ ] Invalid version fails validation with useful diagnostics.
- [ ] Creator fixes invalid data.
- [ ] Reachability/static quality checks pass.
- [ ] Encounter simulation runs.
- [ ] Creator reproduces selected outlier seed.
- [ ] Human playtest scenario runs against draft preview.
- [ ] Content pack publishes immutably.
- [ ] Campaign created from published pack.
- [ ] P5 session plays authored content end to end.
- [ ] Local full/simulation/playtest evidence captured.

---

# 11. Phase H — Advanced/external controllers (v0.8)

Goal: add richer intelligence without destabilizing SimpleNpcController or earlier playable gates.

## H1. Advanced controller framework

- [ ] Rich utility scoring.
- [ ] Explicit goals.
- [ ] Persistent bounded memories.
- [ ] Tactical scoring.
- [ ] Schedule integration.
- [ ] Controller budget/deadline.
- [ ] Deterministic fallback to SimpleNpcController.

## H2. External/LLM controller seam

- [ ] Typed visible controller context.
- [ ] Typed response/intent schema.
- [ ] Translator to ordinary commands.
- [ ] Timeout/circuit breaker.
- [ ] Invalid-output handling.
- [ ] No direct authoritative state mutation.
- [ ] No hidden/omniscient context.
- [ ] Replay does not require recalling service.
- [ ] External result provenance/versioning where required.
- [ ] Local tests use fixtures/fakes; no external model required for core release tests.

## H3. Controller quality lab

- [ ] Simple-vs-utility matched-seed comparison.
- [ ] Profile comparisons.
- [ ] Fallback scenarios.
- [ ] External timeout/error scenarios.
- [ ] Human-vs-advanced-controller playtest.
- [ ] Ensure all P0–P6 gates remain green locally.

---

# 12. Phase I — Stable universal client / creator / operations API (v0.9)

Goal: stabilize interfaces so independent clients/tools can depend on them.

## I1. REST stability

- [ ] `/api/v1` stable routing.
- [ ] OpenAPI quality/review.
- [ ] API response envelopes.
- [ ] API error schema.
- [ ] Opaque cursor pagination.
- [ ] Request/correlation IDs.
- [ ] Version/deprecation rules.
- [ ] Idempotent retry documentation.

## I2. Authentication/authorization

- [ ] Authentication provider boundary.
- [ ] Campaign membership authorization.
- [ ] Actor-control authorization.
- [ ] DM/admin permissions.
- [ ] Authoring/publish permissions.
- [ ] Simulation permissions.
- [ ] Extension administration permissions.
- [ ] Audit coverage.
- [ ] Rate limiting/abuse-control seam.

## I3. WebSocket stability

- [ ] Connection handshake.
- [ ] Subscription model.
- [ ] Ordered event delivery.
- [ ] ACK/resume.
- [ ] Snapshot+delta resync.
- [ ] Visibility filtering before queue.
- [ ] Bounded buffers.
- [ ] Coalescing replaceable projection updates.
- [ ] Never silently drop authoritative events.
- [ ] Slow-client disconnect/resume behavior.

## I4. Client discovery

- [ ] Ruleset/capabilities endpoint.
- [ ] Character-creation schema.
- [ ] Available actions/targets.
- [ ] Creator schema discovery.
- [ ] Session/lobby status.
- [ ] Controller assignment/status without hidden decision data.
- [ ] Localization/UI metadata.
- [ ] Unit metadata.
- [ ] Asset refs.

## I5. SDK/reference clients

- [ ] Python SDK.
- [ ] Terminal reference client.
- [ ] WebSocket example client.
- [ ] Creator/Content Testing CLI.
- [ ] All clients remain thin.
- [ ] Same local playtest scenarios can target reference clients where practical.

## I6. Local test execution stability

- [ ] Stable local `scripts/test` CLI.
- [ ] Stable profile manifest.
- [ ] Stable TestEvidenceBundle schema.
- [ ] In-process target.
- [ ] Local-server target.
- [ ] Containerized local target.
- [ ] No GitHub Actions or remote CI target.

---

# 13. Phase J — Content evolution/migrations (v0.9/P7)

Goal: achieve **P7**, safely update live campaign content without destroying replayability.

## J1. Semantic content diff

- [ ] Added definitions.
- [ ] Removed definitions.
- [ ] Changed definitions.
- [ ] Dependency changes.
- [ ] Ruleset compatibility changes.
- [ ] License/provenance changes.
- [ ] Mechanic-affecting vs presentation-only classification.

## J2. Campaign impact report

- [ ] Affected actors.
- [ ] Affected character progression.
- [ ] Affected items/inventories.
- [ ] Affected quests/dialogue.
- [ ] Affected encounters/world state.
- [ ] Affected controller profiles.
- [ ] Affected scheduled events/effects.
- [ ] Unsafe/ambiguous conditions surfaced.

## J3. Migration plan

- [ ] Typed content migration descriptors.
- [ ] Character/content-reference remaps.
- [ ] State transformations.
- [ ] Controller-profile transformations.
- [ ] Validation before execution.
- [ ] Reverse migration declared when valid.

## J4. Dry-run

- [ ] Resolve candidate content lock.
- [ ] Create isolated copy/branch.
- [ ] Apply migration.
- [ ] Rebuild projections.
- [ ] Run replay validation.
- [ ] Run affected playtests.
- [ ] Run affected simulation/reachability checks.
- [ ] Produce machine-readable report.

## J5. Activation/recovery

- [ ] Automatic pre-upgrade checkpoint.
- [ ] Atomic content-lock activation.
- [ ] Persist migration metadata.
- [ ] Verify post-activation replay.
- [ ] Rollback when reverse migration is valid.
- [ ] Otherwise branch from pre-upgrade checkpoint.
- [ ] Never silently auto-upgrade active campaign mechanics.

## J6. P7 Testing Grounds

- [ ] Play existing campaign under old pack.
- [ ] Publish new pack version.
- [ ] Generate semantic diff.
- [ ] Generate impact report.
- [ ] Dry-run migration.
- [ ] Required simulations/playtests pass locally.
- [ ] Automatic checkpoint created.
- [ ] Activate revision.
- [ ] Continue playing updated content.
- [ ] Replay pre-change history with old definitions.
- [ ] Replay post-change history with new definitions.
- [ ] Demonstrate rollback or safe branch behavior.
- [ ] Local migration/replay/full evidence captured.

---

# 14. Phase K — Production/release hardening (v1.0/P8)

Goal: achieve **P8**, a production-ready playable platform whose release is proven locally.

## K1. Reliability

- [ ] Backup process.
- [ ] Automated restore test.
- [ ] Crash/restart during idle campaign.
- [ ] Crash/restart during scheduled action.
- [ ] Crash/restart during decision window.
- [ ] Outbox recovery without duplicate publication.
- [ ] Projection rebuild/recovery.
- [ ] Database reconnect/error behavior.

## K2. Security

- [ ] Permission matrix tests.
- [ ] Visibility leak audit.
- [ ] Controller-view leak audit.
- [ ] Import validation/security.
- [ ] Content pack cannot execute code.
- [ ] Trusted extension capability audit.
- [ ] Rate-limit/abuse tests.
- [ ] Secret/log redaction tests.

## K3. Observability

- [ ] Structured command/event logging.
- [ ] Correlation IDs.
- [ ] Scheduler metrics.
- [ ] Controller metrics.
- [ ] WebSocket metrics.
- [ ] Simulation metrics.
- [ ] Migration metrics.
- [ ] Health/readiness meaningful dependencies.

## K4. Performance

- [ ] Define representative benchmark campaigns.
- [ ] Command throughput benchmark.
- [ ] Event append benchmark.
- [ ] Projection rebuild benchmark.
- [ ] Replay benchmark.
- [ ] WebSocket fanout benchmark.
- [ ] Scheduler benchmark.
- [ ] Simulation throughput benchmark.
- [ ] Establish budgets/baselines.
- [ ] Local performance evidence reproducible.

## K5. Packaging/deployment

- [ ] Reproducible package/container build.
- [ ] Production configuration documentation.
- [ ] Migration/rollback operating procedure.
- [ ] Backup/restore operating procedure.
- [ ] Health/readiness deployment example.
- [ ] License/attribution package.
- [ ] Version/release policy.
- [ ] No GitHub Actions release/deployment automation.

## K6. P8 release acceptance

- [ ] All P0–P7 gates still pass locally.
- [ ] Complete gameplay acceptance matrix executable.
- [ ] Complete creator/session/quality acceptance executable.
- [ ] Security/visibility suite passes locally.
- [ ] Backup/restore/recovery suite passes locally.
- [ ] Migration/replay suite passes locally.
- [ ] Simulation/content-quality gates pass locally.
- [ ] Performance profile satisfies documented release budgets.
- [ ] Exact release commit has local `release` TestEvidenceBundle.
- [ ] Release evidence uses clean worktree.
- [ ] No unexplained required-suite skips/blocks.
- [ ] `.github/workflows/` absent/empty.

---

# 15. Continuous Testing Grounds story

The reference campaign must evolve cumulatively rather than being replaced by disconnected fixtures.

Target story:

```text
The Testing Grounds

Town
├── Tavern
│   ├── Quest giver
│   └── social/dialogue checks
├── Merchant
│   └── buy/sell/trade
├── Blacksmith
│   └── equipment/crafting hook
└── Gate
    ↓
Road
├── travel/time event
├── hidden path discovery
└── Forest
    ├── interactable container/object
    └── Goblin Camp
        ├── SimpleNpcController enemies
        ├── combat objective
        └── quest/reward
            ↓
Ruins
├── hazard/object
├── second encounter
└── progression/content-evolution hooks
```

Required cumulative human story:

```text
create campaign
-> create hero
-> join/open session
-> talk in tavern
-> accept quest
-> trade/equip
-> travel
-> discover hidden path
-> interact with world object
-> fight autonomous enemies
-> receive reward
-> progress hero
-> checkpoint
-> disconnect/reconnect
-> close session
-> inspect recap
-> replay
-> later upgrade content and continue play
```

Every major subsystem should attach to this story when practical.

---

# 16. Feature coverage manifest

Maintain a machine-readable mapping from implemented feature to proof.

Conceptual record:

```text
FeatureCoverage
    feature_id
    milestone
    implementation_paths[]
    unit_tests[]
    integration_tests[]
    playtest_scenarios[]
    controller_tests[]
    simulation_checks[]
    reachability_checks[]
    migration_fixtures[]
    roles[]
    timing_modes[]
    spatial_adapters[]
    visibility_cases[]
    negative_cases[]
    reconnect_cases[]
    replay_cases[]
    required_local_profiles[]
    last_local_evidence_id | null
```

A feature with no applicable public-play or negative-path proof must state why.

---

# 17. Definition of done for a TODO implementation item

A normal implementation checkbox may be checked when:

- implementation exists;
- schemas/types/docs required by the item exist;
- tests/scenarios required by that item exist;
- relevant static review has been performed;
- it does not knowingly break an earlier playability gate.

If the checkbox itself says evidence/pass/verified, or is a playability/milestone execution gate, it additionally requires exact-commit local test evidence.

Never convert `[AWAITING EVIDENCE]` to `[x]` merely because another remote agent says it should pass.

---

# 18. Local execution handoff checklist

Before asking the local test agent to run a candidate:

- [ ] Candidate commit SHA is known.
- [ ] Required profile(s) are named.
- [ ] Environment prerequisites are documented.
- [ ] PostgreSQL/other local services required are documented.
- [ ] Seed/content/controller fixtures are versioned.
- [ ] Expected artifacts are specified.
- [ ] Evidence output path is deterministic.
- [ ] No secrets are required in evidence.
- [ ] No GitHub Actions workflow is required or present.

Local-agent result should provide:

```text
commit SHA
profile
status
suite counts
failed/blocked/skipped suites
reproducible failure artifacts
playtest/simulation seeds
canonical replay hashes where applicable
evidence bundle path/id
```

---

# 19. Final product acceptance

The project is not finished when all data models exist.

It is finished when a clean deployment can be used by a real or reference client to:

- create/load a game;
- create/control a character;
- play through exploration, social, quest, economy and combat loops;
- encounter autonomous non-human actors;
- progress and persist;
- disconnect/reconnect/recover;
- inspect history/recaps;
- replay deterministically;
- create/test/publish custom content;
- safely evolve that content in a running campaign;
- and prove all of this with reproducible exact-commit **local** execution evidence.

That is what the implementation queue is optimizing for.