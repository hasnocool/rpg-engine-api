# RPG Engine API — Canonical Planning Index

This file defines the planning set for `rpg-engine-api`.

## Read in this order

1. [`PLAN.md`](PLAN.md) — core architecture, timing model, deterministic command/event runtime, ruleset boundary, persistence, API direction, and v0.1-v1.0 roadmap.
2. [`docs/GAME_SYSTEMS_PLAN.md`](docs/GAME_SYSTEMS_PLAN.md) — character creation, species/background/class modeling, progression trees, campaign creation, movement/actions, inventory, quests, logs, projections, and player-facing systems.
3. [`docs/PLAN_COMPLETENESS_AUDIT.md`](docs/PLAN_COMPLETENESS_AUDIT.md) — normative audit that closes the remaining placeholders and gaps: shared primitives, content-pack/version rules, house rules, character lifecycle, party/session/scene/encounter lifecycles, resources/spells/conditions, perception/visibility, economy/crafting, API/WebSocket contracts, migrations, import/export, reliability, and the full v1.0 acceptance matrix.

## Precedence

The documents are complementary. When an older document names a concept abstractly and the completeness audit gives a concrete contract, use the concrete contract in `docs/PLAN_COMPLETENESS_AUDIT.md`.

If a future implementation decision intentionally changes one of these contracts, add an Architecture Decision Record (ADR) and update the affected planning document rather than silently diverging from the plan.

## Definition of planning-complete

A core subsystem is not planning-complete until it defines:

- authoritative state;
- content/definition schema;
- commands;
- events;
- queries/projections;
- lifecycle/state machine;
- permissions;
- visibility rules;
- concurrency/idempotency behavior;
- persistence/replay behavior;
- migration/version behavior;
- errors/failure behavior;
- live/WebSocket behavior when relevant;
- import/export behavior when relevant;
- automated tests and milestone exit criteria;
- source/license provenance for redistributable rules/content.

The v1.0 acceptance matrix in `docs/PLAN_COMPLETENESS_AUDIT.md` is the final integration definition of done.

## Implementation order

Implementation should still proceed in milestone order rather than attempting to implement all systems at once:

```text
v0.1  Deterministic Core + shared primitives/versioning
v0.2  First-Class Time + universal action transactions
v0.3  SRD combat runtime + encounter lifecycle
v0.4  Effects/resources/spells + progression primitives
v0.5  Spatial authority + perception/exploration/world objects
v0.6  Complete character creation/runtime/progression
v0.7  Campaign creator + parties/sessions/living world/economy
v0.8  Intelligent/scripted controllers
v0.9  Stable universal REST/WebSocket/client contracts
v1.0  SRD-compatible production-ready reference engine
```

Post-v1.0 distributed/MMO-scale work remains deliberately scoped as future work and is not an unresolved v1.0 placeholder.