from typing import Any

from rpg_engine_api.domain.commands import PrincipalContext
from rpg_engine_api.domain.events import DomainEvent
from rpg_engine_api.domain.session import SessionStatus


def _privileged(principal: PrincipalContext) -> bool: return bool(principal.roles & {"dm", "owner", "admin", "service"})

def can_read_campaign(engine: Any, campaign_id: str, principal: PrincipalContext) -> bool:
    campaign=engine.campaigns.get(campaign_id)
    if campaign is None:return False
    if principal.principal_id==campaign.owner_id or _privileged(principal):return True
    return any(session.campaign_id==campaign_id and principal.principal_id in session.members for session in engine.sessions.values())

def controlled_actor_ids(engine:Any,campaign_id:str,principal:PrincipalContext)->set[str]:
    campaign=engine.campaigns.get(campaign_id)
    if campaign is None:return set()
    if principal.principal_id==campaign.owner_id or _privileged(principal):return set(campaign.actor_ids)
    result:set[str]=set()
    for session in engine.sessions.values():
        if session.campaign_id==campaign_id and principal.principal_id in session.members:
            result.update(actor_id for actor_id,controller in session.actor_controls.items() if controller==principal.principal_id)
    return result

def can_read_actor(engine:Any,actor_id:str,principal:PrincipalContext)->bool:
    actor=engine.actors.get(actor_id)
    if actor is None or not can_read_campaign(engine,actor.campaign_id,principal):return False
    campaign=engine.campaigns[actor.campaign_id]
    if principal.principal_id==campaign.owner_id or _privileged(principal):return True
    active=[session for session in engine.sessions.values() if session.campaign_id==actor.campaign_id and session.status in {SessionStatus.LOBBY,SessionStatus.OPEN,SessionStatus.PAUSED} and principal.principal_id in session.members]
    return any(session.actor_controls.get(actor_id)==principal.principal_id for session in active)

def event_visible_to(engine:Any,event:DomainEvent,principal:PrincipalContext)->bool:
    if not can_read_campaign(engine,event.campaign_id,principal):return False
    campaign=engine.campaigns[event.campaign_id]
    if principal.principal_id==campaign.owner_id or _privileged(principal):return True
    visibility=str(event.payload.get("visibility","campaign_members"))
    if visibility in {"dm_only","service_only"}:return False
    if visibility=="controller_only":return bool(event.actor_id and can_read_actor(engine,event.actor_id,principal))
    return True

def visible_snapshot(engine:Any,campaign_id:str,principal:PrincipalContext)->dict[str,Any]:
    if not can_read_campaign(engine,campaign_id,principal):raise PermissionError("principal is not a campaign member")
    campaign=engine.campaigns[campaign_id]
    if principal.principal_id==campaign.owner_id or _privileged(principal):return engine.live_snapshot(campaign_id)
    actor_ids=controlled_actor_ids(engine,campaign_id,principal)
    sessions={sid:s.model_dump(mode="json") for sid,s in sorted(engine.sessions.items()) if s.campaign_id==campaign_id and principal.principal_id in s.members}
    actors={aid:engine.actors[aid].model_dump(mode="json") for aid in sorted(actor_ids) if aid in engine.actors}
    encounters={eid:e.model_dump(mode="json") for eid,e in sorted(engine.encounters.items()) if e.campaign_id==campaign_id and actor_ids.intersection(e.participants)}
    worlds:dict[str,Any]={}
    for wid,world in sorted(engine.worlds.items()):
        if world.campaign_id==campaign_id:
            per_actor={aid:engine.world_projection(wid,actor_id=aid)["data"] for aid in sorted(actor_ids) if aid in world.actor_locations}
            if per_actor:worlds[wid]=per_actor
    quests={qid:q.model_dump(mode="json") for qid,q in sorted(engine.quests.items()) if q.campaign_id==campaign_id and (q.actor_id is None or q.actor_id in actor_ids)}
    creations={cid:c.model_dump(mode="json") for cid,c in sorted(engine.character_creations.items()) if c.campaign_id==campaign_id and c.principal_id==principal.principal_id}
    dialogues={sid:s.model_dump(mode="json") for sid,s in sorted(engine.dialogue_sessions.items()) if s.campaign_id==campaign_id and s.actor_id in actor_ids}
    timeline=engine.timelines.get(campaign_id); timing=None if timeline is None else {"mode":timeline.mode.value,"simulation_time":timeline.clock.now,"paused":timeline.clock.paused,"default_decision_duration":timeline.default_decision_duration,"timeout_policy":timeline.timeout_policy.value}
    binding=engine.campaign_content_bindings.get(campaign_id)
    parties={pid:p.model_dump(mode="json") for pid,p in sorted(getattr(engine,"parties",{}).items()) if p.campaign_id==campaign_id and actor_ids.intersection(p.member_actor_ids)}
    factions={fid:f.model_dump(mode="json") for fid,f in sorted(getattr(engine,"factions",{}).items()) if f.campaign_id==campaign_id}
    vendors={vid:v.model_dump(mode="json") for vid,v in sorted(getattr(engine,"vendors",{}).items()) if v.campaign_id==campaign_id}
    environments={eid:engine.environment_projection(eid)["data"] for eid,e in sorted(getattr(engine,"world_environments",{}).items()) if e.campaign_id==campaign_id}
    return {"campaign":campaign.model_dump(mode="json"),"actors":actors,"character_creations":creations,"worlds":worlds,"encounters":encounters,"sessions":sessions,"quests":quests,"dialogues":dialogues,"timing":timing,"content_binding":binding.model_dump(mode="json") if binding else None,"parties":parties,"factions":factions,"vendors":vendors,"world_environments":environments}
