from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/v1", tags=["content-evolution"])


@router.get("/campaigns/{campaign_id}/content-binding")
async def get_content_binding(campaign_id: str, request: Request) -> dict[str, object]:
    try:
        return request.app.state.engine.content_binding_projection(campaign_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="campaign content binding not found") from exc


@router.get("/content-revisions/{proposal_id}")
async def get_content_revision(proposal_id: str, request: Request) -> dict[str, object]:
    try:
        return request.app.state.engine.content_revision_projection(proposal_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="content revision not found") from exc
