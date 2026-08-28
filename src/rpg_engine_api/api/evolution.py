from fastapi import APIRouter, HTTPException, Request

from rpg_engine_api.api.contracts import api_response
from rpg_engine_api.application.visibility import can_read_campaign

router = APIRouter(prefix="/api/v1", tags=["content-evolution"])


@router.get("/campaigns/{campaign_id}/content-binding")
async def get_content_binding(campaign_id: str, request: Request) -> dict[str, object]:
    engine = request.app.state.engine
    if campaign_id not in engine.campaigns:
        raise HTTPException(status_code=404, detail="campaign not found")
    principal = await request.app.state.auth_provider.authenticate_headers(request.headers)
    if not can_read_campaign(engine, campaign_id, principal):
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        projection = engine.content_binding_projection(campaign_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="campaign content binding not found") from exc
    return api_response(request, projection.get("data", projection))


@router.get("/content-revisions/{proposal_id}")
async def get_content_revision(proposal_id: str, request: Request) -> dict[str, object]:
    engine = request.app.state.engine
    proposal = engine.content_revision_proposals.get(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="content revision not found")
    principal = await request.app.state.auth_provider.authenticate_headers(request.headers)
    campaign = engine.campaigns[proposal.campaign_id]
    if principal.principal_id != campaign.owner_id and not principal.roles.intersection({"dm", "owner", "admin", "service"}):
        raise HTTPException(status_code=403, detail="forbidden")
    projection = engine.content_revision_projection(proposal_id)
    return api_response(request, projection.get("data", projection))
