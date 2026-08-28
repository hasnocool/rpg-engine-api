# Production deployment

## Supported baseline

- Python 3.12+
- PostgreSQL 17 (PostgreSQL 16+ is expected to work but should be locally verified)
- persistent PostgreSQL volume
- reverse proxy/TLS in front of the API for any non-local deployment
- a real authentication provider replacing `LocalHeaderAuthenticationProvider` before Internet exposure

The built-in local-header provider is for development/playtesting only.

## Container startup

```bash
export POSTGRES_PASSWORD='use-a-secret-manager-in-real-deployments'
docker compose -f compose.production.yaml build
docker compose -f compose.production.yaml up -d postgres
docker compose -f compose.production.yaml run --rm api alembic upgrade head
docker compose -f compose.production.yaml up -d api
```

Check `/health` and `/ready` before accepting traffic.

## Configuration

At minimum production should set `RPG_ENGINE_PERSISTENCE_BACKEND=postgres` and `RPG_ENGINE_DATABASE_URL`. Secrets must be injected at runtime and must never be committed, included in test evidence, audit payloads, or portable packages.

GitHub Actions are prohibited for this repository. Build, migration verification, release validation, and deployment evidence are executed locally or by explicitly approved operator tooling outside GitHub Actions.
