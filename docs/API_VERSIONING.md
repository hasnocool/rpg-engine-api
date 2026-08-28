# API versioning and deprecation

`/api/v1` is the stable transport namespace. Domain command/event/projection schemas carry their own schema versions and may evolve independently through compatible upcasters/migrations.

Within `v1`, additive fields/endpoints are permitted. Clients must ignore unknown response fields. Removing or changing required semantics requires an announced deprecation window or a new transport version.

Mutating requests should use an idempotency key when retry is possible. Reusing a key with a different semantic request is an `idempotency_conflict`.

History cursors are opaque. Clients must not parse them. Live clients resume by authoritative event sequence and must obey `resync_required` by requesting snapshot/delta synchronization.

The `/api/v1/discovery` endpoint is the client-facing source for current capability, creator, UI, localization, units, asset and live-sync conventions.

Release validation remains local-only. GitHub Actions are not part of API compatibility or release policy.
