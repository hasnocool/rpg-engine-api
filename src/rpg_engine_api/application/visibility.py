from typing import Any

from rpg_engine_api.domain.commands import PrincipalContext
from rpg_engine_api.domain.events import DomainEvent
from rpg_engine_api.domain.session import SessionStatus


def _privileged(principal: PrincipalContext) -> bool:
    return bool(principal.roles & {"dm", "owner", "admin", "service"})


def can_read_campaign(engine: Any, campaign_id: str, principal: PrincipalContext) -> bool:
    campaign = engine.campaigns.get(campaign_id)
    if campaign is None:
        return False
    if principal.principal_id == campaign.owner_id or _privileged(principal):
        return True
    return any(
        session.campaign_id == campaign_id and principal.principal_id in session.members
        for session in engine.sessions.values()
    )


def controlled_actor_ids(engine: Any, campaign_id: str, principal: PrincipalContext) -> set[str]:
    campaign = engine.campaigns.get(campaign_id)
    if campaign is None:
        return set()
    if principal.principal_id == campaign.owner_id or _privileged(principal):
        return set(campaign.actor_ids)
    result: set[str] = set()
    for session in engine.sessions.values():
        if session.campaign_id != campaign_id or principal.principal_id not in session.members:
            continue
        for actor_id, controller in session.actor_controls.items():
            if controller == principal.principal_id:
                result.add(actor_id)
    return result


def can_read_actor(engine: Any, actor_id: str, principal: PrincipalContext) -> bool:
    actor = engine.actors.get(actor_id)
    if actor is None or not can_read_campaign(engine, actor.campaign_id, principal):
        return False
    campaign = engine.campaigns[actor.campaign_id]
    if principal.principal_id == campaign.owner_id or _privileged(principal):
        return True
    active = [
        session
        for session in engine.sessions.values()
        if session.campaign_id == actor.campaign_id
        and session.status in {SessionStatus.LOBBY, SessionStatus.OPEN, SessionStatus.PAUSED}
        and principal.principal_id in session.members
    ]
    if not active:
        return False
    return any(session.actor_controls.get(actor_id) == principal.principal_id for session in active)


def event_visible_to(engine: Any, event: DomainEvent, principal: PrincipalContext) -> bool:
    if not can_read_campaign(engine, event.campaign_id, principal):
        return False
    campaign = engine.campaigns[event.campaign_id]
    if principal.principal_id == campaign.owner_id or _privileged(principal):
        return True
    visibility = str(event.payload.get("visibility", "campaign_members"))
    if visibility in {"dm_only", "service_only"}:
        return False
    if visibility == "controller_only":
        return bool(event.actor_id and can_read_actor(engine, event.actor_id, principal))
    return True


def visible_snapshot(engine: Any, campaign_id: str, principal: PrincipalContext) -> dict[str, Any]:
    if not can_read_campaign(engine, campaign_id, principal):
        raise PermissionError("principal is not a campaign member")
    campaign = engine.campaigns[campaign_id]
    if principal.principal_id == campaign.owner_id or _privileged(principal):
        return engine.live_snapshot(campaign_id)

    actor_ids = controlled_actor_ids(engine, campaign_id, principal)
    sessions = {
        session_id: session.model_dump(mode="json")
        for session_id, session in sorted(engine.sessions.items())
        if session.campaign_id == campaign_id and principal.principal_id in session.members
    }
    actors = {
        actor_id: engine.actors[actor_id].model_dump(mode="json")
        for actor_id in sorted(actor_ids)
        if actor_id in engine.actors
    }
    encounters = {
        encounter_id: encounter.model_dump(mode="json")
        for encounter_id, encounter in sorted(engine.encounters.items())
        if encounter.campaign_id == campaign_id and actor_ids.intersection(encounter.participants)
    }
    worlds: dict[str, Any] = {}
    for world_id, world in sorted(engine.worlds.items()):
        if world.campaign_id != campaign_id:
            continue
        per_actor = {
            actor_id: engine.world_projection(world_id, actor_id=actor_id)["data"]
            for actor_id in sorted(actor_ids)
            if actor_id in world.actor_locations
        }
        if per_actor:
            worlds[world_id] = per_actor
    quests = {
        quest_id: quest.model_dump(mode="json")
        for quest_id, quest in sorted(engine.quests.items())
        if quest.campaign_id == campaign_id and (quest.actor_id is None or quest.actor_id in actor_ids)
    }
    creations = {
        creation_id: creation.model_dump(mode="json")
        for creation_id, creation in sorted(engine.character_creations.items())
        if creation.campaign_id == campaign_id and creation.principal_id == principal.principal_id
    }
    dialogues = {
        session_id: session.model_dump(mode="json")
        for session_id, session in sorted(engine.dialogue_sessions.items())
        if session.campaign_id == campaign_id and session.actor_id in actor_ids
    }
    timeline = engine.timelines.get(campaign_id)
    timing = None
    if timeline is not None:
        timing = {
            "mode": timeline.mode.value,
            "simulation_time": timeline.clock.now,
            "paused": timeline.clock.paused,
            "default_decision_duration": timeline.default_decision_duration,
            "timeout_policy": timeline.timeout_policy.value,
        }
    binding = engine.campaign_content_bindings.get(campaign_id)
    return {
        "campaign": campaign.model_dump(mode="json"),
        "actors": actors,
        "character_creations": creations,
        "worlds": worlds,
        "encounters": encounters,
        "sessions": sessions,
        "quests": quests,
        "dialogues": dialogues,
        "timing": timing,
        "content_binding": binding.model_dump(mode="json") if binding else None,
    }
