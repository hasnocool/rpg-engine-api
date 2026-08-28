from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/v1", tags=["advanced-runtime"])


@router.get("/capabilities")
async def capabilities(request: Request) -> dict[str, object]:
    return request.app.state.engine.capability_projection()


@router.get("/campaigns/{campaign_id}/timeline")
async def timeline(campaign_id: str, request: Request) -> dict[str, object]:
    try:
        return request.app.state.engine.timeline_projection(campaign_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="campaign/timeline not found") from exc


@router.get("/reactions/{reaction_window_id}")
async def reaction(reaction_window_id: str, request: Request) -> dict[str, object]:
    try:
        return request.app.state.engine.reaction_projection(reaction_window_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="reaction window not found") from exc


@router.get("/dialogues/sessions/{dialogue_session_id}")
async def dialogue(dialogue_session_id: str, request: Request) -> dict[str, object]:
    try:
        return request.app.state.engine.dialogue_projection(dialogue_session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="dialogue session not found") from exc


@router.get("/branches/{branch_id}")
async def branch(branch_id: str, request: Request) -> dict[str, object]:
    try:
        return request.app.state.engine.branch_projection(branch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="branch not found") from exc
