from fastapi import APIRouter, Request

router = APIRouter(tags=["system"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    recovered = bool(getattr(request.app.state, "recovery_complete", False))
    reachable = True
    last_sequence = 0
    try:
        last_sequence = await request.app.state.engine.store.last_sequence()
    except Exception:
        reachable = False
    status = "ready" if recovered and reachable else "not_ready"
    return {"status": status, "persistence_backend": settings.persistence_backend, "postgres_configured": settings.postgres_configured, "recovery_complete": recovered, "persistence_reachable": reachable, "last_sequence": last_sequence}
