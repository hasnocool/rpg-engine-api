from fastapi import APIRouter, HTTPException, Request

from rpg_engine_api.api.contracts import api_response
from rpg_engine_api.application.visibility import can_read_actor, can_read_campaign

router = APIRouter(prefix="/api/v1", tags=["advanced-runtime"])


async def _principal(request: Request):
    return await request.app.state.auth_provider.authenticate_headers(request.headers)


@router.get("/capabilities")
async def capabilities(request: Request) -> dict[str, object]:
    projection = request.app.state.engine.capability_projection()
    return api_response(request, projection.get("data", projection))


@router.get("/campaigns/{campaign_id}/timeline")
async def timeline(campaign_id: str, request: Request) -> dict[str, object]:
    engine = request.app.state.engine
    if campaign_id not in engine.campaigns:
        raise HTTPException(status_code=404, detail="campaign not found")
    principal = await _principal(request)
    if not can_read_campaign(engine, campaign_id, principal):
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        projection = engine.timeline_projection(campaign_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="campaign timeline not found") from exc
    return api_response(request, projection.get("data", projection))


@router.get("/reactions/{reaction_window_id}")
async def reaction(reaction_window_id: str, request: Request) -> dict[str, object]:
    engine = request.app.state.engine
    window = engine.reaction_windows.get(reaction_window_id)
    if window is None:
        raise HTTPException(status_code=404, detail="reaction window not found")
    principal = await _principal(request)
    eligible = [actor_id for actor_id in window.eligible_actor_ids if actor_id in engine.actors and can_read_actor(engine, actor_id, principal)]
    if not eligible and not principal.roles.intersection({"dm", "owner", "admin"}):
        raise HTTPException(status_code=403, detail="forbidden")
    projection = engine.reaction_projection(reaction_window_id)
    return api_response(request, projection.get("data", projection))


@router.get("/dialogues/sessions/{dialogue_session_id}")
async def dialogue(dialogue_session_id: str, request: Request) -> dict[str, object]:
    engine = request.app.state.engine
    session = engine.dialogue_sessions.get(dialogue_session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="dialogue session not found")
    principal = await _principal(request)
    if not can_read_actor(engine, session.actor_id, principal):
        raise HTTPException(status_code=403, detail="forbidden")
    projection = engine.dialogue_projection(dialogue_session_id)
    return api_response(request, projection.get("data", projection))


@router.get("/branches/{branch_id}")
async def branch(branch_id: str, request: Request) -> dict[str, object]:
    engine = request.app.state.engine
    value = engine.branches.get(branch_id)
    if value is None:
        raise HTTPException(status_code=404, detail="branch not found")
    principal = await _principal(request)
    campaign = engine.campaigns.get(value.parent_campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="parent campaign not found")
    if principal.principal_id != campaign.owner_id and not principal.roles.intersection({"dm", "owner", "admin"}):
        raise HTTPException(status_code=403, detail="forbidden")
    projection = engine.branch_projection(branch_id)
    return api_response(request, projection.get("data", projection))
