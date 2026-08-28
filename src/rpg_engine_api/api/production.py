from fastapi import APIRouter, HTTPException, Request

from rpg_engine_api.api.contracts import api_response
from rpg_engine_api.domain.authoring import PublishedContentPack
from rpg_engine_api.infrastructure.backup import EventHistoryBackup, restore_event_history

router = APIRouter(prefix="/api/v1/admin", tags=["production-operations"])


@router.post("/restore")
async def restore_backup(backup: EventHistoryBackup, request: Request) -> dict[str, object]:
    principal = await request.app.state.auth_provider.authenticate_headers(request.headers)
    if "admin" not in principal.roles:
        raise HTTPException(status_code=403, detail="admin role required")
    engine = request.app.state.engine
    try:
        restored = await restore_event_history(backup, engine.store, require_empty=True)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    for raw in backup.content_packs:
        pack = PublishedContentPack.model_validate(raw)
        engine.published_packs[(pack.pack_id, pack.version)] = pack
        save_pack = getattr(engine.store, "save_content_pack", None)
        if save_pack is not None:
            await save_pack(pack.model_dump(mode="json"))
    await engine.rebuild_from_store()
    return api_response(request, {"restored_events": restored, "campaign_id": backup.campaign_id, "digest": backup.digest})
