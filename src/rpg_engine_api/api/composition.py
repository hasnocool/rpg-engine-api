from fastapi import APIRouter, HTTPException, Request

from rpg_engine_api.api.contracts import api_response
from rpg_engine_api.application.visibility import can_read_actor, can_read_campaign
from rpg_engine_api.application.release_service import CAMPAIGN_TEMPLATES

router=APIRouter(prefix="/api/v1",tags=["campaign-composition"])

async def principal(request:Request): return await request.app.state.auth_provider.authenticate_headers(request.headers)

@router.get("/campaign-templates")
async def templates(request:Request)->dict[str,object]: return api_response(request,CAMPAIGN_TEMPLATES)

@router.get("/campaign-drafts/{draft_id}")
async def campaign_draft(draft_id:str,request:Request)->dict[str,object]:
    draft=request.app.state.engine.campaign_drafts.get(draft_id)
    if draft is None: raise HTTPException(404,"campaign draft not found")
    p=await principal(request)
    if p.principal_id!=draft.owner_id and not p.roles.intersection({"admin","service"}): raise HTTPException(403,"forbidden")
    return api_response(request,draft.model_dump(mode="json"))

async def _campaign_object(request:Request,collection:str,object_id:str):
    engine=request.app.state.engine; value=getattr(engine,collection).get(object_id)
    if value is None: raise HTTPException(404,"not found")
    p=await principal(request)
    if not can_read_campaign(engine,value.campaign_id,p): raise HTTPException(403,"forbidden")
    return value,p

@router.get("/parties/{party_id}")
async def party(party_id:str,request:Request)->dict[str,object]: value,_=await _campaign_object(request,"parties",party_id); return api_response(request,value.model_dump(mode="json"))
@router.get("/factions/{faction_id}")
async def faction(faction_id:str,request:Request)->dict[str,object]: value,_=await _campaign_object(request,"factions",faction_id); return api_response(request,value.model_dump(mode="json"))
@router.get("/vendors/{vendor_id}")
async def vendor(vendor_id:str,request:Request)->dict[str,object]: value,_=await _campaign_object(request,"vendors",vendor_id); return api_response(request,value.model_dump(mode="json"))
@router.get("/environments/{environment_id}")
async def environment(environment_id:str,request:Request)->dict[str,object]: value,_=await _campaign_object(request,"world_environments",environment_id); return api_response(request,request.app.state.engine.environment_projection(value.environment_id)["data"])

@router.get("/campaigns/{campaign_id}/journal")
async def campaign_journal(campaign_id:str,request:Request)->dict[str,object]:
    engine=request.app.state.engine; p=await principal(request)
    if campaign_id not in engine.campaigns: raise HTTPException(404,"campaign not found")
    if not can_read_campaign(engine,campaign_id,p): raise HTTPException(403,"forbidden")
    return api_response(request,await engine.campaign_journal(campaign_id))

@router.get("/actors/{actor_id}/journal")
async def actor_journal(actor_id:str,request:Request)->dict[str,object]:
    engine=request.app.state.engine; p=await principal(request)
    if actor_id not in engine.actors: raise HTTPException(404,"actor not found")
    if not can_read_actor(engine,actor_id,p): raise HTTPException(403,"forbidden")
    return api_response(request,await engine.character_journal(actor_id))
