from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/v1", tags=["queries"])


@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str, request: Request) -> dict[str, object]:
    try:
        return request.app.state.engine.campaign_projection(campaign_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="campaign not found") from exc


@router.get("/actors/{actor_id}")
async def get_actor(actor_id: str, request: Request) -> dict[str, object]:
    try:
        return request.app.state.engine.actor_projection(actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="actor not found") from exc


@router.get("/character-creation/schema")
async def get_character_creation_schema(request: Request) -> dict[str, object]:
    return {"data": request.app.state.engine.character_creation_schema(), "meta": {"schema_version": "1.0"}}


@router.get("/character-creation/{creation_id}")
async def get_character_creation(creation_id: str, request: Request) -> dict[str, object]:
    try:
        return request.app.state.engine.character_creation_projection(creation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="character creation session not found") from exc


@router.get("/encounters/{encounter_id}")
async def get_encounter(encounter_id: str, request: Request) -> dict[str, object]:
    try:
        return request.app.state.engine.encounter_projection(encounter_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="encounter not found") from exc


@router.get("/worlds/{world_id}")
async def get_world(world_id: str, request: Request, actor_id: str | None = None) -> dict[str, object]:
    try:
        return request.app.state.engine.world_projection(world_id, actor_id=actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="world not found") from exc


@router.get("/actors/{actor_id}/available-actions")
async def available_actions(actor_id: str, request: Request) -> dict[str, object]:
    try:
        actions = request.app.state.engine.available_actions(actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="actor not found") from exc
    return {"data": actions, "meta": {"schema_version": "1.0"}}


@router.get("/campaigns/{campaign_id}/events")
async def campaign_events(campaign_id: str, request: Request) -> dict[str, object]:
    events = [event.model_dump(mode="json") for event in await request.app.state.engine.store.read_all() if event.campaign_id == campaign_id]
    return {"data": events, "meta": {"count": len(events)}}


@router.get("/campaigns/{campaign_id}/replay-hash")
async def replay_hash(campaign_id: str, request: Request) -> dict[str, object]:
    try:
        replay = await request.app.state.engine.canonical_hash(campaign_id)
        live = request.app.state.engine.live_hash(campaign_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="campaign not found") from exc
    return {"campaign_id": campaign_id, "canonical_hash": replay, "live_hash": live, "matches_live": replay == live}
