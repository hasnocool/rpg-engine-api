# rpg-engine-api

Headless, deterministic, event-driven tabletop RPG engine API. Architecture and milestone scope live in [`PLAN.md`](PLAN.md); the executable queue lives in [`TODO.md`](TODO.md).

## Local development

Requirements: Python 3.12+; PostgreSQL is optional for the initial in-memory P0/P1 path and required by the integration profile.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e '.[dev]'
cp .env.example .env
uvicorn rpg_engine_api.app:create_app --factory --reload
```

Then inspect:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

Canonical local test profiles are invoked through:

```bash
./scripts/test smoke
./scripts/test pr
```

The test runner writes revision-bound evidence under `artifacts/test-evidence/`. Do not claim a profile passed unless that exact commit's evidence says it passed.

## Minimal public command loop

Create a campaign:

```bash
curl -s http://127.0.0.1:8000/api/v1/commands \
  -H 'content-type: application/json' \
  -d '{"command_type":"CreateCampaign","payload":{"name":"Testing Grounds","seed":12345}}'
```

Use the returned `campaign_id` to create an actor, inspect `/api/v1/actors/{actor_id}/available-actions`, then submit the advertised command. See `examples/` and `tests/playtest/` as the executable client contract grows.
