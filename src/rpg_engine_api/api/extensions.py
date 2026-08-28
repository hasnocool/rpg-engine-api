from fastapi import APIRouter, HTTPException, Request
from rpg_engine_api.api.contracts import api_response
router=APIRouter(prefix="/api/v1/admin/extensions",tags=["trusted-extensions"])
@router.get("")
async def extensions(request:Request)->dict[str,object]:
    principal=await request.app.state.auth_provider.authenticate_headers(request.headers)
    if not principal.roles.intersection({"admin","service"}):raise HTTPException(403,"admin/service role required")
    data={key:value.model_dump(mode="json")|{"active":value.active} for key,value in sorted(request.app.state.engine.extensions.installations.items())};return api_response(request,data)
