from fastapi import FastAPI

from rpg_engine_api.api.commands import router as command_router
from rpg_engine_api.api.creator import router as creator_router
from rpg_engine_api.api.health import router as health_router
from rpg_engine_api.api.queries import router as query_router
from rpg_engine_api.api.ws import router as ws_router
from rpg_engine_api.application.full_service import FullEngineService
from rpg_engine_api.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    app = FastAPI(
        title="RPG Engine API",
        version="0.1.0-dev",
        description="Deterministic authoritative tabletop RPG simulation API",
    )
    app.state.settings = resolved
    app.state.engine = FullEngineService()
    app.include_router(health_router)
    app.include_router(command_router)
    app.include_router(query_router)
    app.include_router(creator_router)
    app.include_router(ws_router)
    return app
