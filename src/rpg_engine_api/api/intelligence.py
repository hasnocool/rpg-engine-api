from fastapi import APIRouter, HTTPException, Request

from rpg_engine_api.api.contracts import api_response
from rpg_engine_api.application.visibility import can_read_actor

router = APIRouter(prefix="/api/v1", tags=["controller-intelligence"])

@router.get("/controller-minds/{actor_id}")
async def controller_mind(actor_id: str, request: Request) -> dict[str, object]:
    engine = request.app.state.engine
    if actor_id not in engine.actors: raise HTTPException(404, "actor not found")
    principal = await request.app.state.auth_provider.authenticate_headers(request.headers)
    if not can_read_actor(engine, actor_id, principal): raise HTTPException(403, "forbidden")
    mind = engine.controller_minds.get(actor_id)
    return api_response(request, None if mind is None else mind.model_dump(mode="json"))
