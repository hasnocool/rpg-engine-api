from fastapi import APIRouter, Request

from rpg_engine_api.api.contracts import api_response

router = APIRouter(prefix="/api/v1", tags=["observability"])


@router.get("/metrics")
async def metrics(request: Request) -> dict[str, object]:
    data = request.app.state.engine.metrics.snapshot()
    pending = getattr(request.app.state.engine.store, "pending_outbox_count", None)
    if pending is not None:
        data = {**data, "outbox_pending": await pending()}
    checkpoint = getattr(request.app.state.engine.store, "load_projection_checkpoint", None)
    if checkpoint is not None:
        data = {**data, "runtime_projection_checkpoint": await checkpoint("runtime")}
    return api_response(request, data)
