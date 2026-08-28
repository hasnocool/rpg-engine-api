from fastapi import APIRouter, Header, HTTPException, Request

from rpg_engine_api.domain.authoring import PublishedContentPack
from rpg_engine_api.infrastructure.backup import EventHistoryBackup, restore_event_history

router = APIRouter(prefix="/api/v1/admin", tags=["production-operations"])


def _roles(raw: str | None) -> set[str]:
    return {role.strip().lower() for role in (raw or "").split(",") if role.strip()}


@router.post("/restore")
async def restore_backup(backup: EventHistoryBackup, request: Request, x_principal_roles: str | None = Header(default=None)) -> dict[str, object]:
    if "admin" not in _roles(x_principal_roles):
        raise HTTPException(status_code=403, detail="admin role required")
    engine = request.app.state.engine
    try:
        restored = await restore_event_history(backup, engine.store, require_empty=True)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    for raw in backup.content_packs:
        pack = PublishedContentPack.model_validate(raw)
        engine.published_packs[(pack.pack_id, pack.version)] = pack
    await engine.rebuild_from_store()
    return {"data": {"restored_events": restored, "campaign_id": backup.campaign_id, "digest": backup.digest}, "meta": {"schema_version": "1.0"}}
