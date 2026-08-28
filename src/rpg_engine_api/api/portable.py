from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from rpg_engine_api.api.contracts import api_response
from rpg_engine_api.application.visibility import can_read_actor
from rpg_engine_api.domain.authoring import PublishedContentPack
from rpg_engine_api.infrastructure.backup import restore_event_history
from rpg_engine_api.infrastructure.portable import PortableCampaignPackage

router = APIRouter(prefix="/api/v1", tags=["portable-and-audit"])


async def _principal(request: Request):
    return await request.app.state.auth_provider.authenticate_headers(request.headers)


def _privileged(principal) -> bool:
    return bool(principal.roles.intersection({"dm", "owner", "admin", "service"}))


@router.get("/campaigns/{campaign_id}/export-package")
async def export_campaign(campaign_id: str, request: Request) -> dict[str, object]:
    engine = request.app.state.engine
    campaign = engine.campaigns.get(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="campaign not found")
    principal = await _principal(request)
    if principal.principal_id != campaign.owner_id and not _privileged(principal):
        raise HTTPException(status_code=403, detail="campaign export requires owner/DM privilege")
    package = await engine.export_campaign_package(campaign_id)
    return api_response(request, package.model_dump(mode="json"))


@router.get("/actors/{actor_id}/export-package")
async def export_character(actor_id: str, request: Request) -> dict[str, object]:
    engine = request.app.state.engine
    if actor_id not in engine.actors:
        raise HTTPException(status_code=404, detail="actor not found")
    principal = await _principal(request)
    if not can_read_actor(engine, actor_id, principal):
        raise HTTPException(status_code=403, detail="principal cannot export this actor")
    package = engine.export_character_package(actor_id)
    return api_response(request, package.model_dump(mode="json"))


@router.post("/imports/campaign/validate")
async def validate_campaign_package(package: PortableCampaignPackage, request: Request) -> dict[str, object]:
    return api_response(request, package.validation_report())


@router.post("/admin/imports/campaign/restore")
async def restore_campaign_package(package: PortableCampaignPackage, request: Request) -> dict[str, object]:
    principal = await _principal(request)
    if not principal.roles.intersection({"admin", "service"}):
        raise HTTPException(status_code=403, detail="admin/service role required")
    report = package.validation_report()
    if not report["valid"]:
        raise HTTPException(status_code=422, detail=report)
    engine = request.app.state.engine
    try:
        restored = await restore_event_history(package.backup, engine.store, require_empty=True)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    for raw in package.backup.content_packs:
        pack = PublishedContentPack.model_validate(raw)
        engine.published_packs[(pack.pack_id, pack.version)] = pack
        save_pack = getattr(engine.store, "save_content_pack", None)
        if save_pack is not None:
            await save_pack(pack.model_dump(mode="json"))
    await engine.rebuild_from_store()
    return api_response(request, {"restored_events": restored, "campaign_id": package.backup.campaign_id, "digest": package.digest})


@router.get("/admin/audit")
async def audit_records(request: Request, limit: int = Query(default=200, ge=1, le=1000), principal_id: str | None = None, campaign_id: str | None = None) -> dict[str, object]:
    principal = await _principal(request)
    if not principal.roles.intersection({"admin", "service"}):
        raise HTTPException(status_code=403, detail="admin/service role required")
    data = await request.app.state.engine.audit_records(limit=limit, principal_id=principal_id, campaign_id=campaign_id)
    return api_response(request, data, count=len(data))
