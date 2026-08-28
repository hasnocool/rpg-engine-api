from contextlib import asynccontextmanager

from fastapi import FastAPI

from rpg_engine_api.api.advanced import router as advanced_router
from rpg_engine_api.api.commands import router as command_router
from rpg_engine_api.api.creator import router as creator_router
from rpg_engine_api.api.evolution import router as evolution_router
from rpg_engine_api.api.health import router as health_router
from rpg_engine_api.api.queries import router as query_router
from rpg_engine_api.api.ws import router as ws_router
from rpg_engine_api.application.recoverable_service import RecoverableEngineService
from rpg_engine_api.config import Settings, get_settings
from rpg_engine_api.persistence.postgres import PostgresEventStore


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    store = PostgresEventStore(resolved.database_url) if resolved.postgres_configured and resolved.database_url else None
    engine = RecoverableEngineService(store=store)

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

    app = FastAPI(title="RPG Engine API", version="0.3.0-dev", description="Deterministic authoritative tabletop RPG simulation API", lifespan=lifespan)
    app.state.settings = resolved
    app.state.engine = engine
    app.state.recovery_complete = store is None
    app.include_router(health_router)
    app.include_router(command_router)
    app.include_router(query_router)
    app.include_router(creator_router)
    app.include_router(evolution_router)
    app.include_router(advanced_router)
    app.include_router(ws_router)
    return app
