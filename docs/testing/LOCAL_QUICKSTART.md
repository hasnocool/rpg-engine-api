# Local implementation test quick-start

This is a convenience companion to the normative [`LOCAL_TEST_AGENT.md`](LOCAL_TEST_AGENT.md). The evidence contract there remains authoritative.

## Prepare

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e '.[dev]'
```

For database-backed tests:

```bash
./scripts/local-env up
export RPG_ENGINE_DATABASE_URL="postgresql+asyncpg://rpg:rpg@127.0.0.1:5432/rpg_engine"
alembic upgrade head
```

## Recommended first pass

Run profiles separately so a failure bundle is easy to diagnose:

```bash
./scripts/test smoke
./scripts/test pr
./scripts/test simulation
./scripts/test integration
./scripts/test migration
./scripts/test replay
```

Then run the composed profile:

```bash
./scripts/test full
```

Every invocation writes a commit-bound evidence directory under `artifacts/test-evidence/`.

## Manual playable P2 check

Terminal 1:

```bash
uvicorn rpg_engine_api.app:create_app --factory
```

Terminal 2:

```bash
python examples/play_testing_grounds.py
```

The example is intentionally a thin HTTP client. It discovers/uses public API state and allows `SimpleNpcController` to drive the opponent.

## Important interpretation

A skip because PostgreSQL is not configured is not a database pass. The canonical runner treats an all-skipped required suite as blocked. Preserve failing evidence instead of retrying until green without recording the original failure.
