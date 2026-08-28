# rpg-engine-api

Headless, deterministic, event-driven fantasy tabletop RPG engine API.

The architecture and implementation roadmap live in [`PLAN.md`](PLAN.md). The ordered execution queue and cumulative playable-product gates live in [`TODO.md`](TODO.md). Repository-wide agent rules live in [`AGENTS.md`](AGENTS.md).

## Test execution policy

This repository uses **local test execution only**. GitHub Actions are intentionally prohibited and `.github/workflows/` should remain absent/empty.

The designated local test agent runs canonical profiles through `./scripts/test` and produces exact-commit `TestEvidenceBundle` artifacts under `artifacts/test-evidence/`. Remote coding/review agents may write and review tests, but they do not claim execution success without matching local evidence.

Use `./scripts/test-all` for the full local profile sweep; it boots local PostgreSQL if needed and runs the canonical profiles programmatically.

See [`docs/testing/LOCAL_TEST_AGENT.md`](docs/testing/LOCAL_TEST_AGENT.md) and [`docs/testing/LOCAL_QUICKSTART.md`](docs/testing/LOCAL_QUICKSTART.md).

## Local development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e '.[dev]'

./scripts/test smoke
./scripts/test pr
./scripts/test-all
```

For PostgreSQL-backed local testing:

```bash
./scripts/local-env up
export RPG_ENGINE_DATABASE_URL="postgresql+asyncpg://rpg:rpg@127.0.0.1:5432/rpg_engine"
alembic upgrade head
./scripts/test integration
```

Run the API:

```bash
uvicorn rpg_engine_api.app:create_app --factory
```

In another shell, exercise the game-like Testing Grounds example:

```bash
python examples/play_testing_grounds.py
```

No GitHub Actions workflow is required for any of these tasks.
