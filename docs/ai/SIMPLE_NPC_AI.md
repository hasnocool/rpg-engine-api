# Simple NPC AI Controller Specification

## Status

**Project:** `rpg-engine-api`  
**Role:** Normative specification for the first non-human actor controller.  
**Goal:** Provide a small, deterministic, testable AI that can control NPCs and creatures through the same rules-valid command path as human-controlled actors.

`PLAN.md` remains the canonical roadmap. This document defines the initial controller in enough detail that agents do not invent incompatible NPC AI implementations.

---

# 1. Scope

The first NPC AI is deliberately simple.

It is **not**:

- an LLM;
- a chatbot;
- an external model/API dependency;
- a behavior tree system;
- a GOAP planner;
- a machine-learning model;
- a tactical search engine;
- an omniscient controller;
- a replacement for the rules engine.

It is a deterministic, one-decision-at-a-time policy controller.

Its purpose is to make non-human actors capable of participating in systematic end-to-end playtests and ordinary gameplay before advanced AI is implemented.

---

# 2. Core controller contract

The initial controller is named conceptually:

```text
SimpleNpcController
```

It receives only a controller-safe view:

```text
NpcDecisionView
    actor_id
    controller_profile_ref
    controller_version
    visible_actor_state
    visible_scene_state
    visible_targets
    available_actions
    timing_state
    current_schedule_step | null
```

It returns either:

```text
NpcDecision
    action_id
    targets
    parameters
    score
    reason_code
```

or:

```text
NoNpcDecision
    reason_code
```

The selected action is converted into the normal typed command and enters the same command validation/resolution pipeline used by human actors.

The controller cannot directly mutate HP, position, resources, conditions, encounter state, inventory, quest state, or any other authoritative game state.

---

# 3. Information boundary

The controller must not receive omniscient campaign state.

It may receive only information the controlled actor is allowed to know according to normal perception, discovery, visibility, and controller permissions.

Examples:

```text
allowed
    actor's own visible resources
    visible enemies/allies
    known positions
    available actions advertised by the server
    visible terrain/object information
    known conditions/effects
    current timing/action window
    assigned schedule step

not allowed
    hidden actors not perceived
    secret DM state
    undiscovered traps/locations
    another actor's private information
    hidden dice outcomes
    server-only rule traces
    future scheduled events that the actor cannot know
```

The AI must not get extra information merely because it runs on the server.

---

# 4. Determinism

Given the same:

```text
controller version
behavior profile version
visible decision view
available actions
rules/content lock
```

the controller must choose the same decision.

The MVP should prefer stable deterministic tie-breaking rather than randomness:

```text
highest score
    -> lowest/stable action key
    -> lowest/stable target key
    -> stable parameter ordering
```

Optional variation may later use a dedicated deterministic per-controller RNG stream, but it must never consume the authoritative combat/dice/loot/world RNG streams.

Human-play behavior RNG must also remain separate from NPC decision RNG.

---

# 5. Behavior profiles

Behavior is data, not custom code per creature.

Conceptual schema:

```text
NpcBehaviorProfile
    id
    version
    mode
    hostility_policy
    target_policy
    retreat_threshold_percent
    preferred_range
    preferred_action_tags[]
    discouraged_action_tags[]
    forbidden_action_tags[]
    reaction_policy
    movement_policy
    fallback_policy
```

Initial profiles:

```text
aggressive_melee
ranged
balanced
 defensive
support
passive
flee
```

The exact names are content keys; the controller algorithm is generic.

---

# 6. Initial combat decision policy

The MVP evaluates one decision when the actor becomes eligible to act.

Decision order:

```text
1. Query/receive current available actions.
2. If no actions are available, return NoNpcDecision.
3. If retreat/flee policy is active and health is at/below threshold:
       prefer legal flee/disengage/movement actions increasing distance from hostile actors.
4. If support profile and a legal support/healing action has a valid ally target:
       score support targets according to profile.
5. If a legal offensive action can affect a hostile target now:
       score offensive action/target candidates.
6. If no useful offensive action is currently in range:
       prefer legal movement that approaches the selected hostile target while respecting preferred range.
7. If a defensive action is legal and profile prefers defense:
       select it.
8. Otherwise use the profile fallback policy.
9. Resolve ties deterministically.
10. Submit the resulting normal command.
```

This is intentionally shallow. It does not search several turns ahead.

---

# 7. Simple scoring model

Each legal action candidate receives an integer score.

Suggested shape:

```text
score =
    profile_base_score(action_tags)
    + target_priority_score
    + range_score
    + resource_affordability_score
    + self_preservation_score
    + ally_support_score
    + objective_score
    - discouraged_action_penalty
```

Only information present in `NpcDecisionView` may contribute to scoring.

Do not duplicate the rules engine inside the AI. The server-provided `available_actions` already establishes legality, costs, valid target schemas, and capability constraints.

The controller may rank legal choices; it must not independently decide whether an illegal action should become legal.

---

# 8. Initial target policies

Support a small set of deterministic target policies:

```text
nearest_hostile
lowest_visible_health_hostile
highest_visible_threat
nearest_ally_needing_support
lowest_visible_health_ally
current_focus_target
stable_first_valid
```

`highest_visible_threat` may initially be a simple rules/content-provided numeric hint. It must not require an advanced threat simulation.

If target information required by a policy is not visible, the controller falls back to another configured policy.

---

# 9. Movement policy

Initial movement intents:

```text
approach_target
maintain_preferred_range
increase_distance
follow_actor
hold_position
move_to_assigned_point
```

The controller does not calculate illegal paths itself.

It asks the spatial/action system for legal movement options or submits a movement intent that the authoritative movement system validates and resolves.

For large continuous spaces, candidate movement points should come from server-provided/action-query helpers rather than brute-force search inside the controller.

---

# 10. Reactions

Initial reaction policies:

```text
never
always_if_legal
highest_score_if_legal
protect_self
protect_ally
```

When a reaction window opens, the controller evaluates only actions advertised for that reaction window.

If no reaction exceeds the profile's minimum reaction score, it declines the reaction.

Reaction decisions use the same deterministic tie-breaking rules.

---

# 11. Out-of-combat behavior

The initial AI does not attempt general autonomous roleplay.

Out of combat it supports only simple controller states:

```text
idle
follow_actor
hold_position
execute_schedule_step
move_to_assigned_location
```

NPC schedules/world events remain authoritative scheduler data.

For example:

```text
09:00 -> move_to_assigned_location(shop)
09:05 -> hold_position
18:00 -> move_to_assigned_location(home)
```

The AI may perform the legal movement/actions required by the schedule step, but it does not invent long-term goals.

Dialogue content remains authored/rules-driven. The simple controller may select a deterministic configured dialogue option for scripted NPC-to-NPC scenarios, but natural-language generation is out of scope.

---

# 12. Controller assignment

Actor state should reference controller configuration rather than embedding behavior code.

Conceptual state:

```text
ControllerAssignment
    controller_type
    controller_version
    behavior_profile_ref
    enabled
    fallback_controller_type | null
```

Initial types:

```text
human
simple_npc
scripted
system
```

Later additions may include:

```text
utility_ai
behavior_tree
external_agent
llm
```

but they must continue to use the same command/rules boundary.

---

# 13. Controller lifecycle

The controller is invoked only when the actor is eligible to make a decision.

Examples:

```text
ActorReady
ActionWindowOpened
ReactionWindowOpened
ScheduleStepReady
ControllerHandoffCompleted
```

The controller does not run a busy polling loop.

It should be event-driven and async-safe.

For the MVP, the decision should normally be computed immediately. Artificial NPC think delays are optional presentation/game-policy behavior and must use scheduler/clock abstractions rather than blocking sleeps.

---

# 14. Failure/fallback behavior

The controller must fail safely.

If decision evaluation fails:

```text
1. record structured diagnostic context without secrets;
2. do not mutate game state;
3. apply configured fallback policy;
4. optionally choose a safe legal fallback action;
5. otherwise decline/end/forfeit according to encounter policy.
```

Initial fallback policies:

```text
choose_stable_first_legal
prefer_defend
end_turn_or_noop
forfeit
controller_error
```

A controller exception must never crash the authoritative scheduler or corrupt campaign state.

---

# 15. Decision tracing

For testing/debugging, produce a non-authoritative structured decision trace:

```text
NpcDecisionTrace
    actor_id
    controller_version
    profile_ref
    decision_sequence
    visible_input_hash
    candidate_count
    candidate_scores[]
    selected_action
    selected_targets
    reason_code
```

The trace is diagnostic/audit information, not the authoritative source of game state.

Replay authority remains the accepted command and resulting domain events.

Do not expose hidden server information in player-visible traces.

---

# 16. Testing requirements

The simple NPC AI must be tested at three levels.

## Unit

Test deterministic scoring, profile behavior, target selection, retreat thresholds, stable tie-breaking, reaction policies, and fallback behavior.

## Integration

Test that the selected command goes through normal authorization, timing, rules validation, event persistence, and replay.

## Human-play / black-box

Use NPC AI in the canonical `Testing Grounds` scenarios so non-human combatants act without the test harness directly scripting every enemy command.

Required scenarios eventually include:

```text
aggressive melee NPC approaches and attacks
ranged NPC maintains range when possible
low-health NPC retreats under flee profile
support NPC helps an eligible ally
passive NPC does not initiate hostile action
NPC reaction policy uses/declines a legal reaction
NPC cannot act on hidden/unperceived target
same state/profile/version -> same decision
NPC command rejected by rules -> safe fallback/no corruption
human player versus AI-controlled encounter
AI versus AI deterministic encounter smoke test
```

A replay of the resulting authoritative command/event history must produce the same canonical game state.

---

# 17. Relationship to human playtesting

The programmatic human-play harness and NPC AI serve different roles:

```text
human-play persona
    simulates a client/user
    uses public REST/WebSocket interfaces
    has independent behavior RNG

SimpleNpcController
    server-side actor controller
    controls non-human actors
    sees only actor-visible/controller-safe state
    submits through the normal command path
```

The human-play harness should not bypass the NPC controller by directly choosing enemy actions in scenarios intended to prove autonomous NPC behavior.

Scenarios may still use explicitly scripted NPC commands when the purpose is testing a precise rules edge case rather than AI behavior.

---

# 18. Milestone placement

The **controller interface and `SimpleNpcController` should be introduced earlier than advanced AI** because they are needed for realistic playtesting.

Recommended milestone split:

```text
v0.1
    ControllerAssignment primitive/interface seam

v0.2
    eligibility/event hooks for controller decisions

v0.3
    SimpleNpcController combat MVP
    aggressive_melee / ranged / defensive / passive / flee profiles
    reaction policy foundation
    human-vs-NPC playtests

v0.5
    movement/perception integration
    visible-target-only behavior
    follow/hold/move-to-point

v0.7
    schedule-step integration
    simple out-of-combat NPC movement/activity

v0.8
    advanced controller work
    utility AI
    richer goals/memory/tactical scoring
    optional external/LLM adapters
```

Do not delay the simple NPC controller until advanced AI work if doing so forces playtests to manually puppeteer every non-human actor.

---

# 19. Upgrade boundary

Future AI systems may become more sophisticated, but they must preserve these invariants:

1. controller is not authoritative rules logic;
2. controller receives only permitted information;
3. controller chooses from/submits normal legal command surfaces;
4. rules engine validates every command;
5. controller version/configuration is explicit;
6. deterministic/replayable operation is available for tests;
7. external model failure cannot corrupt authoritative state;
8. LLM text cannot directly mutate game state;
9. advanced AI remains replaceable per actor/campaign;
10. simple deterministic AI remains available as a baseline/reference controller.
