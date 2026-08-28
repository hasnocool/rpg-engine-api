from fastapi import APIRouter, HTTPException, Request

from rpg_engine_api.api.contracts import api_response

router = APIRouter(prefix="/api/v1", tags=["creator"])


@router.get("/authoring/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str, request: Request) -> dict[str, object]:
    engine = request.app.state.engine
    workspace = engine.authoring_workspaces.get(workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    principal = await request.app.state.auth_provider.authenticate_headers(request.headers)
    if workspace.owner_id != principal.principal_id and not principal.roles.intersection({"admin", "service"}):
        raise HTTPException(status_code=403, detail="forbidden")
    projection = engine.authoring_workspace_projection(workspace_id)
    return api_response(request, projection.get("data", projection))


@router.get("/content-packs/{pack_id}/{version}")
async def get_published_pack(pack_id: str, version: str, request: Request) -> dict[str, object]:
    try:
        projection = request.app.state.engine.published_pack_projection(pack_id, version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="content pack not found") from exc
    return api_response(request, projection.get("data", projection))
