from fastapi import APIRouter, Request

router = APIRouter(tags=["system"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    return {
        "status": "ready",
        "persistence_backend": settings.persistence_backend,
        "postgres_configured": settings.postgres_configured,
    }
