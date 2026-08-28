from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/v1", tags=["creator"])


@router.get("/authoring/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str, request: Request) -> dict[str, object]:
    try:
        return request.app.state.engine.authoring_workspace_projection(workspace_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="workspace not found") from exc


@router.get("/content-packs/{pack_id}/{version}")
async def get_published_pack(pack_id: str, version: str, request: Request) -> dict[str, object]:
    try:
        return request.app.state.engine.published_pack_projection(pack_id, version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="content pack not found") from exc
