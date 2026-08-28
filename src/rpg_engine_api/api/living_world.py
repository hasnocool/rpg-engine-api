from fastapi import APIRouter, HTTPException, Request
from rpg_engine_api.api.contracts import api_response
from rpg_engine_api.application.visibility import can_read_actor, can_read_campaign
router=APIRouter(prefix="/api/v1",tags=["living-world"])
async def _principal(request:Request):return await request.app.state.auth_provider.authenticate_headers(request.headers)
@router.get("/npcs/{actor_id}/runtime")
async def npc_runtime(actor_id:str,request:Request)->dict[str,object]:
    engine=request.app.state.engine;runtime=engine.npc_runtimes.get(actor_id)
    if runtime is None:raise HTTPException(404,"NPC runtime not found")
    p=await _principal(request)
    if not can_read_campaign(engine,runtime.campaign_id,p):raise HTTPException(403,"forbidden")
    return api_response(request,runtime.model_dump(mode="json"))
@router.get("/containers/{container_id}")
async def container(container_id:str,request:Request)->dict[str,object]:
    engine=request.app.state.engine;value=engine.containers.get(container_id)
    if value is None:raise HTTPException(404,"container not found")
    p=await _principal(request)
    if not can_read_campaign(engine,value.campaign_id,p):raise HTTPException(403,"forbidden")
    if value.owner_actor_id and not can_read_actor(engine,value.owner_actor_id,p) and not p.roles.intersection({"dm","owner","admin"}):raise HTTPException(403,"forbidden")
    return api_response(request,value.model_dump(mode="json"))
