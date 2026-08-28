from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from rpg_engine_api.api.contracts import api_response, decode_event_cursor, encode_event_cursor
from rpg_engine_api.application.visibility import can_read_actor, can_read_campaign, event_visible_to, visible_snapshot

router = APIRouter(prefix="/api/v1", tags=["queries"])


def _not_found(message: str, exc: KeyError | None = None) -> HTTPException:
    return HTTPException(status_code=404, detail=message)


def _forbidden(message: str = "forbidden") -> HTTPException:
    return HTTPException(status_code=403, detail=message)


async def _principal(request: Request):
    return await request.app.state.auth_provider.authenticate_headers(request.headers)


@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str, request: Request) -> dict[str, object]:
    principal = await _principal(request)
    if campaign_id not in request.app.state.engine.campaigns:
        raise _not_found("campaign not found")
    if not can_read_campaign(request.app.state.engine, campaign_id, principal):
        raise _forbidden()
    return api_response(request, request.app.state.engine.campaign_projection(campaign_id)["data"])


@router.get("/actors/{actor_id}")
async def get_actor(actor_id: str, request: Request) -> dict[str, object]:
    engine = request.app.state.engine
    if actor_id not in engine.actors:
        raise _not_found("actor not found")
    principal = await _principal(request)
    if not can_read_actor(engine, actor_id, principal):
        raise _forbidden("principal cannot read this actor")
    return api_response(request, engine.actor_projection(actor_id)["data"])


@router.get("/character-creation/schema")
async def get_character_creation_schema(request: Request) -> dict[str, object]:
    return api_response(request, request.app.state.engine.character_creation_schema())


@router.get("/character-creation/{creation_id}")
async def get_character_creation(creation_id: str, request: Request) -> dict[str, object]:
    engine = request.app.state.engine
    creation = engine.character_creations.get(creation_id)
    if creation is None:
        raise _not_found("character creation session not found")
    principal = await _principal(request)
    campaign = engine.campaigns[creation.campaign_id]
    if creation.principal_id != principal.principal_id and principal.principal_id != campaign.owner_id and not principal.roles.intersection({"dm", "owner", "admin"}):
        raise _forbidden()
    return api_response(request, engine.character_creation_projection(creation_id)["data"])


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, request: Request) -> dict[str, object]:
    engine = request.app.state.engine
    session = engine.sessions.get(session_id)
    if session is None:
        raise _not_found("session not found")
    principal = await _principal(request)
    if principal.principal_id not in session.members and not principal.roles.intersection({"dm", "owner", "admin"}):
        raise _forbidden()
    return api_response(request, engine.session_projection(session_id)["data"])


@router.get("/sessions/{session_id}/recap")
async def get_session_recap(session_id: str, request: Request) -> dict[str, object]:
    engine = request.app.state.engine
    session = engine.sessions.get(session_id)
    if session is None:
        raise _not_found("session not found")
    principal = await _principal(request)
    if principal.principal_id not in session.members and not principal.roles.intersection({"dm", "owner", "admin"}):
        raise _forbidden()
    return api_response(request, await engine.session_recap(session_id))


@router.get("/quests/{quest_id}")
async def get_quest(quest_id: str, request: Request) -> dict[str, object]:
    engine = request.app.state.engine
    quest = engine.quests.get(quest_id)
    if quest is None:
        raise _not_found("quest not found")
    principal = await _principal(request)
    if not can_read_campaign(engine, quest.campaign_id, principal):
        raise _forbidden()
    return api_response(request, engine.quest_projection(quest_id)["data"])


@router.get("/checkpoints/{checkpoint_id}")
async def get_checkpoint(checkpoint_id: str, request: Request) -> dict[str, object]:
    engine = request.app.state.engine
    checkpoint = engine.checkpoints.get(checkpoint_id)
    if checkpoint is None:
        raise _not_found("checkpoint not found")
    principal = await _principal(request)
    campaign = engine.campaigns[checkpoint.campaign_id]
    if principal.principal_id != campaign.owner_id and not principal.roles.intersection({"dm", "owner", "admin"}):
        raise _forbidden()
    return api_response(request, engine.checkpoint_projection(checkpoint_id)["data"])


@router.get("/encounters/{encounter_id}")
async def get_encounter(encounter_id: str, request: Request) -> dict[str, object]:
    engine = request.app.state.engine
    encounter = engine.encounters.get(encounter_id)
    if encounter is None:
        raise _not_found("encounter not found")
    principal = await _principal(request)
    if not can_read_campaign(engine, encounter.campaign_id, principal):
        raise _forbidden()
    return api_response(request, engine.encounter_projection(encounter_id)["data"])


@router.get("/worlds/{world_id}")
async def get_world(world_id: str, request: Request, actor_id: str | None = None) -> dict[str, object]:
    engine = request.app.state.engine
    world = engine.worlds.get(world_id)
    if world is None:
        raise _not_found("world not found")
    principal = await _principal(request)
    campaign = engine.campaigns[world.campaign_id]
    privileged = principal.principal_id == campaign.owner_id or bool(principal.roles.intersection({"dm", "owner", "admin"}))
    if actor_id is None and not privileged:
        raise _forbidden("non-DM world reads require actor_id")
    if actor_id is not None and not can_read_actor(engine, actor_id, principal):
        raise _forbidden("principal cannot read world knowledge for this actor")
    return api_response(request, engine.world_projection(world_id, actor_id=actor_id)["data"])


@router.get("/actors/{actor_id}/available-actions")
async def available_actions(actor_id: str, request: Request) -> dict[str, object]:
    engine = request.app.state.engine
    if actor_id not in engine.actors:
        raise _not_found("actor not found")
    principal = await _principal(request)
    if not can_read_actor(engine, actor_id, principal):
        raise _forbidden("principal cannot control/read this actor")
    return api_response(request, engine.available_actions(actor_id))


@router.get("/campaigns/{campaign_id}/events")
async def campaign_events(
    campaign_id: str,
    request: Request,
    cursor: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
) -> dict[str, Any]:
    engine = request.app.state.engine
    if campaign_id not in engine.campaigns:
        raise _not_found("campaign not found")
    principal = await _principal(request)
    if not can_read_campaign(engine, campaign_id, principal):
        raise _forbidden()
    try:
        scan_sequence = decode_event_cursor(cursor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    visible: list[Any] = []
    current = await engine.store.last_sequence(campaign_id=campaign_id)
    while len(visible) < limit and scan_sequence < current:
        batch = await engine.store.read_after(scan_sequence, campaign_id=campaign_id, limit=max(50, limit * 2))
        if not batch:
            break
        for event in batch:
            scan_sequence = event.sequence
            if event_visible_to(engine, event, principal):
                visible.append(event.model_dump(mode="json"))
                if len(visible) >= limit:
                    break
        if len(batch) < max(50, limit * 2):
            break
    has_more = scan_sequence < current
    return api_response(
        request,
        visible,
        count=len(visible),
        current_sequence=current,
        next_cursor=encode_event_cursor(scan_sequence) if has_more else None,
        has_more=has_more,
    )


@router.get("/campaigns/{campaign_id}/sync")
async def campaign_sync(
    campaign_id: str,
    request: Request,
    after_sequence: int | None = Query(default=None, ge=0),
) -> dict[str, Any]:
    engine = request.app.state.engine
    if campaign_id not in engine.campaigns:
        raise _not_found("campaign not found")
    principal = await _principal(request)
    if not can_read_campaign(engine, campaign_id, principal):
        raise _forbidden()
    current = await engine.store.last_sequence(campaign_id=campaign_id)
    if after_sequence is None or current - after_sequence > 1000:
        return api_response(
            request,
            {"mode": "snapshot", "snapshot": visible_snapshot(engine, campaign_id, principal), "events": []},
            current_sequence=current,
        )
    events = await engine.store.read_after(after_sequence, campaign_id=campaign_id, limit=1000)
    visible_events = [event.model_dump(mode="json") for event in events if event_visible_to(engine, event, principal)]
    return api_response(
        request,
        {"mode": "delta", "snapshot": None, "events": visible_events},
        current_sequence=current,
        from_sequence=after_sequence,
    )


@router.get("/campaigns/{campaign_id}/replay-hash")
async def replay_hash(campaign_id: str, request: Request) -> dict[str, object]:
    engine = request.app.state.engine
    if campaign_id not in engine.campaigns:
        raise _not_found("campaign not found")
    principal = await _principal(request)
    campaign = engine.campaigns[campaign_id]
    if principal.principal_id != campaign.owner_id and not principal.roles.intersection({"dm", "owner", "admin"}):
        raise _forbidden()
    replay = await engine.canonical_hash(campaign_id)
    live = engine.live_hash(campaign_id)
    return api_response(request, {"campaign_id": campaign_id, "canonical_hash": replay, "live_hash": live, "matches_live": replay == live})
