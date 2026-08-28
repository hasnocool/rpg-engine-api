from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from rpg_engine_api.api.advanced import router as advanced_router
from rpg_engine_api.api.commands import router as command_router
from rpg_engine_api.api.creator import router as creator_router
from rpg_engine_api.api.evolution import router as evolution_router
from rpg_engine_api.api.health import router as health_router
from rpg_engine_api.api.observability import router as observability_router
from rpg_engine_api.api.production import router as production_router
from rpg_engine_api.api.queries import router as query_router
from rpg_engine_api.api.ws import router as ws_router
from rpg_engine_api.application.durable_service import DurableEngineService
from rpg_engine_api.config import Settings, get_settings
from rpg_engine_api.domain.ids import new_id
from rpg_engine_api.infrastructure.rate_limit import SlidingWindowRateLimiter
from rpg_engine_api.persistence.postgres import PostgresEventStore


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    store = PostgresEventStore(resolved.database_url) if resolved.postgres_configured and resolved.database_url else None
    engine = DurableEngineService(store=store)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if store is not None:
            await engine.rebuild_from_store()
        app.state.recovery_complete = True
        try:
            yield
        finally:
            if store is not None:
                await store.close()

    app = FastAPI(title="RPG Engine API", version="0.5.0-dev", description="Deterministic authoritative tabletop RPG simulation API", lifespan=lifespan)
    app.state.settings = resolved
    app.state.engine = engine
    app.state.rate_limiter = SlidingWindowRateLimiter(resolved.command_rate_limit_per_minute)
    app.state.recovery_complete = store is None

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or new_id("req")
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response

    app.include_router(health_router)
    app.include_router(command_router)
    app.include_router(query_router)
    app.include_router(creator_router)
    app.include_router(evolution_router)
    app.include_router(advanced_router)
    app.include_router(production_router)
    app.include_router(observability_router)
    app.include_router(ws_router)
    return app
