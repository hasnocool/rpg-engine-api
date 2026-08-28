from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1", tags=["observability"])


@router.get("/metrics")
async def metrics(request: Request) -> dict[str, object]:
    return {"data": request.app.state.engine.metrics.snapshot(), "meta": {"schema_version": "1.0"}}
