# RPG Engine API — Executable End-to-End TODO

## Purpose

This file is the **day-to-day execution queue** for `rpg-engine-api`.

Authority order:

1. `PLAN.md` — architecture, roadmap, non-negotiable invariants, milestone scope.
2. Normative subsystem specifications under `docs/` — detailed contracts.
3. **`TODO.md` — ordered implementation work and completion evidence.**

`TODO.md` does not replace `PLAN.md`. If a TODO conflicts with the plan, the plan wins and the TODO must be corrected.

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
- never mark execution-verification items complete without exact-commit local-agent/CI evidence.

When an architectural discovery changes the correct sequence, update `PLAN.md` first if architecture changes, then update this TODO.

## Status convention

Use Markdown checkboxes plus an optional status suffix:

```text
[ ] not started
[ ] [IN PROGRESS] implementation is actively being changed
[ ] [AWAITING EVIDENCE] implementation exists but required local/CI execution evidence is missing
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

The exact release candidate passes the complete gameplay acceptance matrix, creator/session/quality acceptance set, visibility/security checks, recovery, migration/replay, deterministic simulation gates, and defined performance profile with one exact-commit `release` `TestEvidenceBundle`.

Local profile: `release`.

---

# 4. Phase A — Repository and execution foundation (v0.1)

Goal: establish a clean modern Python project, deterministic core contracts, test execution evidence, and P0/P1.

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

## A2. Canonical test runner and evidence

- [ ] Create `scripts/test` as the single canonical test entry point.
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

Goal: achieve **P2**, the first unmistakably game-like playable vertical slice.

## C1. Ruleset/runtime combat foundation

- [ ] Implement ruleset manifest/registry.
- [ ] Add correctly attributed SRD-compatible package foundation.
- [ ] Implement generic resolution context/outcome.
- [ ] Implement ability/check/save foundation.
- [ ] Implement initiative/readiness translation.
- [ ] Implement turn/action resources.
- [ ] Implement attacks.
- [ ] Implement deterministic attack/check dice flow.
- [ ] Implement damage/healing.
- [ ] Implement health projection.
- [ ] Implement modifier advantage/disadvantage-style framework where licensed.
- [ ] Implement critical-result framework where licensed.
- [ ] Implement conditions foundation.
- [ ] Implement reactions/interrupts.
- [ ] Implement Ready-style trigger seam where licensed.

## C2. Encounter runtime

- [ ] Implement encounter aggregate/state machine.
- [ ] Implement participant join/leave.
- [ ] Implement factions/sides.
- [ ] Implement starting positions.
- [ ] Implement encounter start/pause/resume/end.
- [ ] Implement victory/failure/completion hooks.
- [ ] Implement cleanup of reserved actions/reactions/resources.
- [ ] Implement reward hook.
- [ ] Implement encounter history projection.
- [ ] Implement combat log projection.
- [ ] Add rule-trace diagnostics with proper visibility.

## C3. Encounter authoring foundation

- [ ] Implement `EncounterTemplate` schema.
- [ ] Define participant groups.
- [ ] Define controller assignments.
- [ ] Define spawn/starting-position data.
- [ ] Define objective/completion policy.
- [ ] Define reward reference.
- [ ] Define basic scaling seam.
- [ ] Validate references and instantiation.
- [ ] Add preview endpoint/service.

## C4. SimpleNpcController combat MVP

- [ ] Implement visibility-filtered `NpcDecisionView`.
- [ ] Implement `NpcBehaviorProfile` schema/version.
- [ ] Implement aggressive-melee profile.
- [ ] Implement ranged profile.
- [ ] Implement balanced/defensive profile.
- [ ] Implement support profile.
- [ ] Implement passive profile.
- [ ] Implement flee profile.
- [ ] Implement one-decision-at-a-time candidate scoring.
- [ ] Use only server-advertised legal actions/targets.
- [ ] Implement deterministic stable tie-breaking.
- [ ] Implement retreat threshold behavior.
- [ ] Implement reaction policy baseline.
- [ ] Implement safe fallback policy.
- [ ] Implement non-authoritative decision trace.
- [ ] Ensure hidden/unperceived actors cannot affect decisions.

## C5. Testing Grounds combat fixture

- [ ] Add a small encounter location/scene fixture.
- [ ] Add one playable pre-generated character.
- [ ] Add at least one autonomous hostile NPC/creature.
- [ ] Add at least one movement choice.
- [ ] Add at least one attack/action choice.
- [ ] Add at least one resource-bearing action where runtime supports it.
- [ ] Add reward/result.
- [ ] Add human-readable combat log messages.

## C6. P2 playable combat gate

- [ ] Reference client can load/create Testing Grounds combat state.
- [ ] Human persona selects/controls the player actor.
- [ ] Available actions are discovered from server.
- [ ] Human moves legally.
- [ ] Human attacks/uses representative action.
- [ ] NPC autonomously chooses and submits action.
- [ ] Human can observe NPC result without hidden decision leakage.
- [ ] Reaction/interrupt path is exercised if supported by current SRD slice.
- [ ] Encounter completes without test harness puppeting NPC turns.
- [ ] Reward/result is projected.
- [ ] Combat log is readable.
- [ ] Full encounter replay reaches same canonical hash.
- [ ] AI-vs-AI smoke simulation is deterministic.
- [ ] Exact-commit `playtest` evidence captured.
- [ ] Exact-commit `replay` evidence captured.
- [ ] Exact-commit `simulation` evidence captured.

---

# 7. Phase D — Data-driven mechanics and progression primitives (v0.4)

## D1. Effects and modifiers

- [ ] Implement generic effect definition/instance.
- [ ] Implement triggers.
- [ ] Implement modifiers.
- [ ] Implement durations/expiration.
- [ ] Implement stacking policies.
- [ ] Implement periodic effects.
- [ ] Implement area-effect seam.
- [ ] Implement removal/reversal rules where explicitly defined.

## D2. Resources/features/abilities

- [ ] Implement `ResourceDefinition/State`.
- [ ] Implement `FeatureDefinition`.
- [ ] Implement `AbilityDefinition`.
- [ ] Implement resource costs/recovery.
- [ ] Implement maintenance/concentration-style seam.
- [ ] Implement temporary grants.
- [ ] Integrate conditions with effect pipeline.
- [ ] Ensure available-action discovery includes newly legal abilities.
- [ ] Ensure SimpleNpcController can rank action tags without spell-specific hidden code.

## D3. Progression graph

- [ ] Implement graph/node/edge schemas.
- [ ] Implement prerequisite evaluation.
- [ ] Implement ranked nodes.
- [ ] Implement mutually exclusive choices.
- [ ] Implement grant/revoke.
- [ ] Implement progression currency seam.
- [ ] Implement respec policy seam.
- [ ] Implement progression schema/version migration seam.

## D4. Authoring/quality

- [ ] Add authoring schemas for effects/features/resources/abilities/progression.
- [ ] Add layered validation.
- [ ] Add unusable ability detection where feasible.
- [ ] Add progression reachability analysis.
- [ ] Add generated available-action exploration.
- [ ] Add representative simulation metrics for resources/ability usage.

## D5. Playable regression

- [ ] P2 combat still passes.
- [ ] Player can use at least one data-driven ability/resource.
- [ ] NPC can use at least one advertised data-driven ability through generic profile scoring.
- [ ] Effect/condition visibly changes subsequent legal play.
- [ ] Replay remains deterministic.

---

# 8. Phase E — Spatial authority, perception and exploration (v0.5)

Goal: achieve P3.

## E1. Spatial adapters

- [ ] Define `SpatialAdapter` contract.
- [ ] Implement theater-of-mind adapter.
- [ ] Implement graph adapter.
- [ ] Implement square-grid adapter.
- [ ] Implement continuous-2D adapter.
- [ ] Add hex/continuous-3D later if not needed for initial acceptance.
- [ ] Implement occupancy/distance.
- [ ] Implement path validation/pathfinding hooks.
- [ ] Implement terrain cost.
- [ ] Implement LOS/cover.
- [ ] Implement area queries.

## E2. Movement

- [ ] Validate movement through action model.
- [ ] Implement trajectories/meaningful movement events.
- [ ] Add forced/teleport/custom movement seams.
- [ ] Prevent direct coordinate patches.

## E3. Perception/knowledge

- [ ] Implement senses.
- [ ] Implement can-perceive/perception-quality/known-position interfaces.
- [ ] Implement visibility-filtered entity fields.
- [ ] Implement discovery facts/events.
- [ ] Implement actor/party/campaign knowledge scopes.
- [ ] Add golden no-leak tests.
- [ ] Build controller decision view from same perception layer.

## E4. World objects and hazards

- [ ] Implement world object definitions/instances.
- [ ] Implement containers/open/lock/access state.
- [ ] Implement terrain definitions.
- [ ] Implement hazard definitions/triggers/detection.
- [ ] Implement scene lifecycle.

## E5. Exploration/travel

- [ ] Implement move/travel/search/study/scout/interact/open/close/use foundations.
- [ ] Implement location enter/exit/discovery.
- [ ] Implement fact/object/path discovery.
- [ ] Implement marching order/formation seam.

## E6. NPC spatial behavior

- [ ] Approach visible target.
- [ ] Maintain preferred range.
- [ ] Increase distance/flee.
- [ ] Follow actor.
- [ ] Hold position.
- [ ] Move to assigned point.
- [ ] Never use hidden targets for movement decisions.

## E7. P3 playable exploration gate

- [ ] Testing Grounds Town/Forest graph exists.
- [ ] Player enters location.
- [ ] Player sees only perceived entities.
- [ ] Player moves through at least two locations.
- [ ] Player discovers a hidden path/fact/object via rules-driven play.
- [ ] Player interacts with a world object/container.
- [ ] Player travels into the combat encounter naturally.
- [ ] Same fixture can be validated under at least two spatial adapters where practical.
- [ ] Visibility tests show NPC and player hidden-state isolation.
- [ ] `playtest` + `replay` evidence captured.

---

# 9. Phase F — Complete character runtime (v0.6)

Goal: achieve P4.

## F1. Character creation sessions

- [ ] Implement resumable creation session state.
- [ ] Implement ruleset-driven creation step graph.
- [ ] Implement upstream-choice revalidation.
- [ ] Implement class/subclass choices.
- [ ] Implement species/background/languages.
- [ ] Implement ability generation/assignment policies.
- [ ] Implement skills/tool proficiencies.
- [ ] Implement starting equipment.
- [ ] Implement feats/features.
- [ ] Implement spells/powers/loadouts.
- [ ] Implement identity/appearance/biography fields.
- [ ] Implement validate/finalize.

## F2. Higher-level/multiclass

- [ ] Implement sequentially valid higher-level creation.
- [ ] Implement class-level/total-level state.
- [ ] Implement multiclass prerequisites.
- [ ] Ensure result equals valid sequential advancement.

## F3. Character projections/lifecycle

- [ ] Implement complete character sheet projection.
- [ ] Implement skills/features/resources/inventory/spellcasting/action projections.
- [ ] Implement character history.
- [ ] Implement active/inactive/retired/archived lifecycle.
- [ ] Implement import staging/validation.
- [ ] Implement portable export without auth/control grants.

## F4. Advancement

- [ ] Implement advancement session.
- [ ] Implement XP/milestone/progression-point policies.
- [ ] Map representative SRD class progression into graph.
- [ ] Implement branching custom progression seam.

## F5. Character authoring/quality

- [ ] Add schemas for classes/subclasses/species/backgrounds/templates/progression.
- [ ] Add validation/preview.
- [ ] Add systematic creation matrix.
- [ ] Add unreachable progression detection.
- [ ] Add representative legal/illegal creation playtests.

## F6. P4 playable character/progression gate

- [ ] Player creates character without client-side hidden rules.
- [ ] Character enters Testing Grounds.
- [ ] Character has legal actions derived from choices.
- [ ] Character completes exploration/combat.
- [ ] Character gains progression reward.
- [ ] Player opens advancement session.
- [ ] Player makes valid progression choice.
- [ ] Character sheet/available actions update.
- [ ] Replay preserves progression.
- [ ] `playtest` + `replay` evidence captured.

---

# 10. Phase G — Campaign, world, social, economy, Creator Studio and sessions (v0.7)

Goal: achieve P5 and P6.

## G1. Campaign creator

- [ ] Implement campaign creation session/draft.
- [ ] Implement template selection.
- [ ] Configure timing/timeout.
- [ ] Configure progression/rest.
- [ ] Configure spatial/world clock.
- [ ] Configure visibility/logging.
- [ ] Configure content packs/house rules.
- [ ] Configure baseline NPC controller defaults.
- [ ] Validate/finalize campaign.

## G2. Membership/lobby/session

- [ ] Implement campaign memberships/roles.
- [ ] Implement invitations.
- [ ] Implement lobby open/join/leave.
- [ ] Implement actor selection/control grants.
- [ ] Implement ready checks.
- [ ] Implement session open/pause/resume/close.
- [ ] Implement spectator presence.
- [ ] Implement multi-device control conflict policy.
- [ ] Implement disconnect grace/AFK policy.
- [ ] Implement explicit temporary SimpleNpcController handoff.
- [ ] Implement explicit control restoration on reconnect.

## G3. Party/world/time

- [ ] Implement party model.
- [ ] Implement marching order/formation.
- [ ] Implement world/region/location hierarchy.
- [ ] Implement calendar projection.
- [ ] Implement world-clock policies.
- [ ] Implement travel process.
- [ ] Implement weather/environment state.
- [ ] Implement NPC schedules.
- [ ] Implement simple schedule-step controller behavior.

## G4. Social/dialogue/personality

- [ ] Implement dialogue state machine.
- [ ] Implement typed social actions.
- [ ] Implement `NpcPersonalityProfile` distinct from combat AI profile.
- [ ] Implement disposition/goals/loyalties/fears/interests/tags.
- [ ] Implement relationship/aggression/assistance thresholds.
- [ ] Ensure personality uses visible/known relationship/faction/quest context.
- [ ] Keep natural-language generation optional/non-authoritative.

## G5. Quests/factions/relationships

- [ ] Implement quest definition/objective graph.
- [ ] Implement accept/advance/complete/fail flows.
- [ ] Implement sequential/parallel/optional/exclusive/hidden/timed objectives.
- [ ] Implement faction state.
- [ ] Implement reputation/relationship state.
- [ ] Project quest state from events.

## G6. Inventory/economy/crafting

- [ ] Complete item definition/instance model.
- [ ] Complete inventories/containers.
- [ ] Implement currency/wallet.
- [ ] Implement vendors/pricing/schedules.
- [ ] Implement atomic trade.
- [ ] Implement deterministic loot/rewards.
- [ ] Implement recipe/crafting scheduled process.
- [ ] Add acquisition-path quality checks.

## G7. Authoring workspace and publish pipeline

- [ ] Implement `AuthoringWorkspace`.
- [ ] Implement mutable draft definitions with revision/concurrency control.
- [ ] Implement schema validation.
- [ ] Implement namespace/reference/dependency validation.
- [ ] Implement ruleset compatibility validation.
- [ ] Implement provenance/license validation.
- [ ] Implement graph reachability/static semantic validation.
- [ ] Implement runtime preview/instantiation validation.
- [ ] Attach required playtest/simulation evidence.
- [ ] Implement publish-ready state.
- [ ] Implement immutable versioned content-pack publication.
- [ ] Ensure finalized campaigns never reference mutable drafts.

## G8. Creator/DM Studio API foundations

- [ ] Add authoring schema discovery.
- [ ] Add draft CRUD/revision APIs for non-authoritative authoring state.
- [ ] Add validation APIs.
- [ ] Add preview/test APIs.
- [ ] Add publication APIs.
- [ ] Add editor projections for creature/NPC.
- [ ] Add encounter editor projection.
- [ ] Add quest graph editor projection.
- [ ] Add dialogue graph editor projection.
- [ ] Add world/location/scene editor projection.
- [ ] Add vendor/recipe/campaign-template editors.
- [ ] Ensure editor convenience views map to canonical runtime schemas.

## G9. Narration

- [ ] Define deterministic narration template schema.
- [ ] Create visibility-filtered `GameMessage` projection.
- [ ] Link messages to source event IDs/sequence ranges.
- [ ] Add localization-ready text references.
- [ ] Ensure narration cannot mutate state.
- [ ] Keep optional future LLM narrator restricted to paraphrasing visible facts.

## G10. Checkpoints/branches

- [ ] Implement named `CampaignCheckpoint`.
- [ ] Store sequence/time/content-lock/snapshot reference.
- [ ] Make checkpoint deletion remove only reference.
- [ ] Implement branch-from-checkpoint.
- [ ] Implement branch-from-sequence.
- [ ] Preserve parent/fork metadata.
- [ ] Add automatic session-boundary/pre-migration checkpoint hooks.

## G11. Recaps/journals

- [ ] Implement `SessionRecap`.
- [ ] Implement `CharacterJournal`.
- [ ] Implement `QuestJournal`.
- [ ] Implement `DiscoveryJournal`.
- [ ] Implement `CampaignChronicle`.
- [ ] Implement NPC encounter history.
- [ ] Enforce role/visibility filtering.
- [ ] Keep optional AI summaries non-authoritative.

## G12. Simulation Quality Lab + Content Testing SDK foundation

- [ ] Implement isolated simulation job model.
- [ ] Reuse exact production rules/runtime/controllers.
- [ ] Implement deterministic seed matrix.
- [ ] Implement encounter batch runner.
- [ ] Collect outcome/duration/action/resource/controller/objective metrics.
- [ ] Preserve outlier seeds.
- [ ] Implement matched-seed comparison across revisions/profiles.
- [ ] Implement quest reachability analysis.
- [ ] Implement dialogue reachability analysis.
- [ ] Implement progression reachability analysis.
- [ ] Implement unobtainable item detection where feasible.
- [ ] Implement unusable ability detection where feasible.
- [ ] Implement `ContentQualityReport`.
- [ ] Add programmatic Content Testing SDK entry points.
- [ ] Promote important failures/outliers to regression fixtures.

## G13. Testing Grounds full content

- [ ] Town: Tavern.
- [ ] Town: Merchant.
- [ ] Town: Blacksmith.
- [ ] Town: Gate.
- [ ] Forest: Road.
- [ ] Forest: Hidden Path.
- [ ] Forest: Goblin Camp.
- [ ] Forest: Ruins.
- [ ] Add 2–3 authored NPCs with personality profiles.
- [ ] Add at least one vendor.
- [ ] Add at least one crafting recipe.
- [ ] Add at least two quests.
- [ ] Add faction/reputation consequence.
- [ ] Add dialogue branch.
- [ ] Add hidden/discovery content.
- [ ] Add scheduled world/NPC event.
- [ ] Add normal encounter.
- [ ] Add timed encounter variant.
- [ ] Connect reward/progression loop.

## G14. P5 playable campaign-session gate

- [ ] DM creates campaign from public Creator/Campaign APIs.
- [ ] Player is invited/joins.
- [ ] Player selects/creates character.
- [ ] Ready check completes.
- [ ] DM opens session.
- [ ] Player enters town.
- [ ] Player talks to NPC.
- [ ] Player accepts quest.
- [ ] Player trades/acquires item.
- [ ] Player travels/explores/discovers.
- [ ] Player enters autonomous-NPC encounter.
- [ ] Player completes encounter and reward.
- [ ] Quest/faction/progression state updates.
- [ ] Checkpoint created.
- [ ] Player disconnects.
- [ ] Temporary control handoff occurs if configured.
- [ ] Player reconnects and control is explicitly restored.
- [ ] Session closes cleanly.
- [ ] Recap/journal/history are visible appropriately.
- [ ] Full journey replays deterministically.
- [ ] Exact-commit `full` evidence captured.

## G15. P6 creator-to-game gate

- [ ] Creator opens workspace.
- [ ] Creator drafts at least NPC/encounter/quest/item or ability content.
- [ ] Invalid reference is caught and corrected.
- [ ] Reachability/static checks run.
- [ ] Encounter simulation runs.
- [ ] Human playtest runs against candidate content.
- [ ] Pack becomes publish-ready only after gates.
- [ ] Immutable pack version is published.
- [ ] Campaign is created using published pack.
- [ ] Player completes authored content through public gameplay interfaces.
- [ ] Quality report/evidence points to exact content/version.
- [ ] Exact-commit `full` + `simulation` evidence captured.

---

# 11. Phase H — Advanced/external AI controllers (v0.8)

- [ ] Implement richer utility controller using same visible decision view.
- [ ] Add goals/tactical scoring beyond baseline one-step profiles.
- [ ] Add optional memory constrained to actor-permitted knowledge.
- [ ] Add richer schedule/planning policy seams.
- [ ] Implement external controller intent-to-command adapter.
- [ ] Add timeout/circuit breaker.
- [ ] Add fallback to SimpleNpcController.
- [ ] Add controller handoff/reconnect semantics.
- [ ] Add AI DM privileged-command surface with normal authorization/audit.
- [ ] Add optional LLM adapter only behind controller boundary.
- [ ] Ensure LLM output cannot mutate state directly.
- [ ] Add deterministic scripted fixtures for external-controller tests.
- [ ] Add simulation comparisons simple vs advanced controller with matched seeds.
- [ ] Preserve SimpleNpcController as reference/fallback.
- [ ] Capture targeted local evidence.

---

# 12. Phase I — Stable universal APIs/SDKs (v0.9)

## I1. Game client API

- [ ] Stabilize `/api/v1` command/query surface.
- [ ] Stabilize error/version/deprecation contract.
- [ ] Complete OpenAPI examples.
- [ ] Complete auth/authorization.
- [ ] Complete character/campaign creator discovery.
- [ ] Complete available-action/target discovery.
- [ ] Complete historical cursor/as-of queries.
- [ ] Complete WebSocket subscribe/resume/backpressure/snapshot+delta.
- [ ] Complete movement trajectory contract.
- [ ] Complete localization/units/accessibility metadata.
- [ ] Complete asset refs/import/export.
- [ ] Complete rate-limit/idempotent retry semantics.

## I2. Creator/operations APIs

- [ ] Stabilize authoring/workspace/schema-discovery APIs.
- [ ] Stabilize lobby/session/control APIs.
- [ ] Stabilize checkpoint/branch APIs.
- [ ] Stabilize recap/journal APIs.
- [ ] Stabilize simulation/quality job APIs.
- [ ] Stabilize content diff/impact/migration-preview APIs.
- [ ] Stabilize extension capability/admin APIs.

## I3. SDKs/reference clients

- [ ] Build Python SDK.
- [ ] Add generated/open contract tests.
- [ ] Build reference terminal client.
- [ ] Build reference WebSocket client.
- [ ] Ensure reference clients contain presentation/workflow logic but not hidden rules.
- [ ] Add Creator/Content Testing SDK/CLI commands.

## I4. Stable testing interface

- [ ] Stabilize `scripts/test` CLI.
- [ ] Stabilize profile manifest format.
- [ ] Stabilize `TestEvidenceBundle` schema/version.
- [ ] Support in-process target.
- [ ] Support normal local server target.
- [ ] Support containerized target.
- [ ] Support authorized remote test target if configured.
- [ ] Ensure the same scenario definitions can run across targets.

---

# 13. Phase J — Content migration and evolution (v0.9-v1.0)

Goal: achieve P7.

## J1. Semantic diff/compatibility

- [ ] Resolve candidate content lock.
- [ ] Generate semantic definition diff.
- [ ] Classify additive/changed/removed definitions.
- [ ] Detect ruleset/engine incompatibilities.
- [ ] Generate `CompatibilityReport`.
- [ ] Generate `CampaignContentImpactReport`.
- [ ] Identify affected actors/items/quests/progression/encounters/controllers.

## J2. Migration plan/dry run

- [ ] Define typed `ContentMigrationPlan`.
- [ ] Define state transformations separately from DB/event schema migrations.
- [ ] Validate extension/controller compatibility.
- [ ] Create isolated copy/branch for dry run.
- [ ] Run migration.
- [ ] Rebuild projections.
- [ ] Run targeted replay.
- [ ] Run required human-play scenarios.
- [ ] Run simulation/quality checks.
- [ ] Produce dry-run evidence report.

## J3. Activation/recovery

- [ ] Create automatic pre-upgrade checkpoint.
- [ ] Atomically activate content revision/lock.
- [ ] Preserve old history under old lock.
- [ ] Verify new events use new lock.
- [ ] Verify replay crosses lock boundary correctly.
- [ ] Implement safe reverse migration only where explicitly valid.
- [ ] Otherwise require branch from pre-upgrade checkpoint.
- [ ] Audit content activation and rollback/branch operations.

## J4. P7 content-evolution gate

- [ ] Play campaign before update.
- [ ] Propose updated pack.
- [ ] Review semantic diff/impact.
- [ ] Dry-run migration.
- [ ] Run required play/simulation checks.
- [ ] Create automatic checkpoint.
- [ ] Activate revision.
- [ ] Continue play using new revision.
- [ ] Inspect old and new history with correct definitions.
- [ ] Replay full campaign deterministically across boundary.
- [ ] Demonstrate safe rollback or branch path.
- [ ] Capture exact-commit `migration` + `replay` + `full` evidence.

---

# 14. Phase K — Production hardening (v1.0)

## K1. Security/visibility

- [ ] Complete permission matrix.
- [ ] Complete visibility golden tests.
- [ ] Prove spectators/players/controllers cannot see hidden DM data.
- [ ] Validate all imported/authored content as untrusted data.
- [ ] Prove ordinary content packs cannot execute code.
- [ ] Prove trusted extensions require explicit authorized installation.
- [ ] Ensure secrets are absent from events/logs/exports/evidence.
- [ ] Add abuse/rate-limit tests.

## K2. Reliability/recovery

- [ ] Document backup procedure.
- [ ] Automate backup.
- [ ] Automate clean restore verification.
- [ ] Verify event/projection hashes after restore.
- [ ] Test restart with pending scheduled events.
- [ ] Test restart during decision window.
- [ ] Test restart while NPC controller is eligible.
- [ ] Test outbox recovery/no duplicate publication consequences.
- [ ] Test DB reconnect behavior.
- [ ] Test WebSocket reconnect/resync.

## K3. Observability

- [ ] Structured operational logging.
- [ ] Request/correlation/command/event trace continuity.
- [ ] Metrics for command/event/projection/scheduler/controller/WebSocket paths.
- [ ] Metrics for authoring validation/simulation/migration/test execution.
- [ ] Health/readiness reflects critical dependency state.
- [ ] Add actionable failure diagnostics without hidden data leakage.

## K4. Performance

- [ ] Define benchmark fixtures/workloads.
- [ ] Measure command p50/p95/p99.
- [ ] Measure event append throughput.
- [ ] Measure replay throughput.
- [ ] Measure projection lag.
- [ ] Measure WebSocket fanout/backpressure.
- [ ] Measure controller decision latency.
- [ ] Measure simulation throughput.
- [ ] Define acceptable target profile from measured evidence.
- [ ] Prevent unbounded CPU/memory use in simulation/import/replay paths.

## K5. Documentation/release

- [ ] README from clean checkout to playable session.
- [ ] Architecture docs current.
- [ ] API docs/examples current.
- [ ] Creator docs current.
- [ ] Local test-agent docs current.
- [ ] Deployment/backup/migration docs current.
- [ ] License/attribution correct.
- [ ] Release/version/deprecation policy documented.
- [ ] Sample campaign/content included.
- [ ] Reference terminal client included.
- [ ] Known limitations explicitly documented.

---

# 15. P8 release acceptance

The exact release candidate must demonstrate all required behavior through machine-produced evidence.

## Gameplay

- [ ] Rules/content discovery and lock creation.
- [ ] Campaign creation/configuration.
- [ ] Lobby/membership/ready/session lifecycle.
- [ ] Character creation and higher-level/progression paths.
- [ ] Exploration/perception/discovery/world objects.
- [ ] Dialogue/social/quests/factions.
- [ ] Inventory/trade/crafting/rewards.
- [ ] Combat/action/reaction/timing modes.
- [ ] SimpleNpcController autonomy/visibility/fallback.
- [ ] Disconnect/reconnect/control handoff.
- [ ] Logs/history/replay.
- [ ] WebSocket resume/resync/backpressure.

## Creator/quality

- [ ] Authoring workspace/draft lifecycle.
- [ ] Validation errors detected/corrected.
- [ ] Encounter/NPC/personality/controller authoring.
- [ ] Reachability/content quality checks.
- [ ] Deterministic simulation batch/outlier reproduction.
- [ ] Immutable publication.
- [ ] Published content playable end to end.

## Evolution/extensions

- [ ] Data-only pack code-execution prohibition demonstrated.
- [ ] Trusted extension admin/capability boundary demonstrated.
- [ ] Semantic diff/impact report demonstrated.
- [ ] Migration dry run demonstrated.
- [ ] Automatic checkpoint + activation demonstrated.
- [ ] Replay across content lock boundary demonstrated.
- [ ] Safe rollback/branch behavior demonstrated.

## Recovery/performance

- [ ] Backup/restore verification.
- [ ] Restart recovery.
- [ ] Persistence/outbox recovery.
- [ ] Visibility/security audit scenarios.
- [ ] Defined performance profile passes or documented release thresholds are met.

## Evidence

- [ ] `release` TestEvidenceBundle exists.
- [ ] Evidence commit SHA exactly equals release candidate.
- [ ] Dirty worktree is false.
- [ ] No mandatory suite is blocked.
- [ ] No unexpected mandatory test is skipped.
- [ ] Failure/outlier artifacts are reproducible.
- [ ] Coverage manifest has no unexplained user-visible feature gaps.

---

# 16. Continuous Testing Grounds story

Do not allow Testing Grounds to become disconnected fixtures. Maintain one cumulative story whose steps grow with the engine:

```text
1. Creator publishes/installs required rules/content.
2. DM creates Testing Grounds campaign.
3. DM invites player.
4. Player creates/selects hero.
5. Ready check and session open.
6. Hero appears in Town.
7. Hero enters Tavern and speaks with NPC.
8. Hero accepts a quest.
9. Hero visits Merchant/Blacksmith and trades/acquires useful item.
10. Hero leaves through Gate.
11. Hero travels Road and discovers Hidden Path or fact.
12. Hero interacts with object/container/hazard.
13. Hero reaches Goblin Camp.
14. Encounter begins with autonomous SimpleNpcController opponents.
15. Hero moves/attacks/uses ability/resource/item.
16. NPCs independently move/attack/react using visible legal information only.
17. Hero intentionally exercises one timeout/reconnect edge case in a dedicated variant.
18. Encounter completes and rewards apply.
19. Quest/faction/relationship state updates.
20. Hero advances/unlocks progression.
21. Campaign checkpoint is created.
22. Player disconnects; optional temporary AI control occurs.
23. Player reconnects; control is explicitly restored.
24. Party returns/continues into Ruins or town follow-up.
25. DM closes session.
26. Recap/journal/chronicle are generated as projections.
27. Campaign replay reaches identical canonical state.
28. In creator-evolution variant, content update is diffed/dry-run/activated and play continues.
```

Every milestone that touches one of these steps should extend or strengthen the same long-form scenario rather than replacing it with unrelated one-off tests.

---

# 17. Agent completion checklist per TODO item

Before checking a TODO item complete:

- [ ] The implementation matches `PLAN.md` and relevant normative spec.
- [ ] Types/schemas are explicit and versioned where required.
- [ ] Async paths are non-blocking.
- [ ] No direct gameplay DB/state mutation bypass was introduced.
- [ ] Visibility/security boundary is correct.
- [ ] Determinism/replay implications were considered.
- [ ] Unit/integration test exists where appropriate.
- [ ] Human-play scenario exists when user-visible.
- [ ] NPC controller scenario exists when autonomy changes.
- [ ] Authoring validation exists when content schemas change.
- [ ] Simulation/reachability check exists when content quality can be checked programmatically.
- [ ] Migration/upcaster fixture exists when persistent interpretation changes.
- [ ] Coverage manifest was updated.
- [ ] Required canonical local profile was identified.
- [ ] Exact-commit execution evidence exists for verification checkboxes.
- [ ] No unsupported claim of “tests pass” was made.
- [ ] Documentation/examples were updated if public workflow changed.

---

# 18. What agents must not do

- Do not skip directly to large content imports before runtime schemas/tests exist.
- Do not implement a second hidden rules engine in clients, playtests, NPC AI, or simulation tooling.
- Do not make baseline NPC gameplay depend on an LLM or cloud API.
- Do not give NPC controllers omniscient state.
- Do not use real sleeps to represent game time in tests.
- Do not let Creator Studio mutate live gameplay state as an editor shortcut.
- Do not let mutable drafts enter finalized campaign locks.
- Do not let ordinary content packs execute arbitrary code.
- Do not destructively rewrite history for “save restore.”
- Do not silently auto-upgrade active campaign mechanics.
- Do not hide required skipped/blocked tests.
- Do not mark execution gates done without revision-matched evidence.
- Do not replace the continuous Testing Grounds journey with isolated happy-path API calls.
- Do not mark a milestone complete while its required playable gate is broken.

---

# 19. Immediate next work

Unless the user explicitly directs otherwise, begin with **Phase A / A1**, then proceed in order toward P0 and P1.

The first implementation objective is therefore:

```text
bootable Python/FastAPI project
    -> canonical test runner/evidence skeleton
    -> deterministic IDs/commands/events/RNG
    -> minimal campaign/actor
    -> event store/replay/idempotency
    -> public command/query path
    -> black-box playtest harness
    -> P0/P1 locally evidenced
```

Only after that foundation is stable should the project proceed into the v0.2 scheduler and then the v0.3 **P2 playable human-vs-autonomous-NPC combat slice**.
