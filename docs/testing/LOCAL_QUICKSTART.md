# Local Test Agent Quick Start

This repository uses **local test execution only**. GitHub Actions are prohibited and `.github/workflows/` should remain absent/empty.

The designated local test agent is the sole execution authority for claims that a candidate commit actually passed its required profiles.

## 1. Prepare the repository

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e '.[dev]'
```

## 2. Run the core local profiles

```bash
./scripts/test smoke
./scripts/test pr
./scripts/test simulation
```

Each profile should emit a commit-bound `TestEvidenceBundle` under `artifacts/test-evidence/`.

## 3. Start local PostgreSQL

```bash
./scripts/local-env up
export RPG_ENGINE_DATABASE_URL="postgresql+asyncpg://rpg:rpg@127.0.0.1:5432/rpg_engine"
alembic upgrade head
```

Then run:

```bash
./scripts/test integration
./scripts/test migration
./scripts/test replay
./scripts/test full
```

## 4. Exercise the game-like Testing Grounds example

Start the API:

```bash
uvicorn rpg_engine_api.app:create_app --factory
```

In another shell:

```bash
python examples/play_testing_grounds.py
```

## 5. Evidence rules

For any pass/fail claim, report at least:

```text
commit SHA
profile
status
suite counts
failed/blocked/skipped suites
evidence bundle path/id
reproducible failure artifacts where applicable
```

A later code-changing commit invalidates earlier green evidence for the new candidate.

Do not create GitHub Actions workflows as a fallback when local execution is unavailable. The correct state is `not executed` / `[AWAITING EVIDENCE]` until the local agent runs the required profile.