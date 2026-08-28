from pydantic import BaseModel, Field

from rpg_engine_api.domain.events import DomainEvent


class NpcPersonalityProfile(BaseModel):
    disposition: str = "neutral"
    goals: tuple[str, ...] = ()
    loyalties: tuple[str, ...] = ()
    fears: tuple[str, ...] = ()
    aggression_threshold: int = 50
    assistance_threshold: int = 50


class NpcScheduleStep(BaseModel):
    step_id: str
    minute_of_day: int = Field(ge=0)
    world_id: str
    location_id: str
    activity: str = "idle"


class NpcRuntimeState(BaseModel):
    schema_version: str = "1.0"
    actor_id: str
    campaign_id: str
    personality: NpcPersonalityProfile = Field(default_factory=NpcPersonalityProfile)
    schedule: list[NpcScheduleStep] = Field(default_factory=list)
    completed_steps: list[dict[str, object]] = Field(default_factory=list)
    stream_version: int = 0


class ContainerState(BaseModel):
    schema_version: str = "1.0"
    container_id: str
    campaign_id: str
    name: str
    owner_actor_id: str | None = None
    world_id: str | None = None
    location_id: str | None = None
    items: list[str] = Field(default_factory=list)
    locked: bool = False
    stream_version: int = 0


def reduce_npc_runtime(state: NpcRuntimeState | None, event: DomainEvent) -> NpcRuntimeState:
    if event.event_type == "NpcRuntimeCreated":
        return NpcRuntimeState(actor_id=str(event.payload["actor_id"]), campaign_id=event.campaign_id, stream_version=event.stream_version)
    if state is None:
        raise ValueError("NPC runtime stream must start with NpcRuntimeCreated")
    next_state = state.model_copy(deep=True); next_state.stream_version = event.stream_version
    if event.event_type == "NpcPersonalityConfigured":
        next_state.personality = NpcPersonalityProfile.model_validate(event.payload["personality"])
    elif event.event_type == "NpcScheduleConfigured":
        next_state.schedule = [NpcScheduleStep.model_validate(item) for item in event.payload.get("schedule", [])]
    elif event.event_type == "NpcScheduleStepCompleted":
        next_state.completed_steps.append({"step_id": str(event.payload["step_id"]), "simulation_time": int(event.payload["simulation_time"]), "location_id": str(event.payload["location_id"]), "activity": str(event.payload.get("activity", "idle"))})
    return next_state


def reduce_container(state: ContainerState | None, event: DomainEvent) -> ContainerState:
    if event.event_type == "ContainerCreated":
        return ContainerState(container_id=str(event.payload["container_id"]), campaign_id=event.campaign_id, name=str(event.payload.get("name", "Container")), owner_actor_id=event.payload.get("owner_actor_id"), world_id=event.payload.get("world_id"), location_id=event.payload.get("location_id"), items=sorted(str(item) for item in event.payload.get("items", [])), locked=bool(event.payload.get("locked", False)), stream_version=event.stream_version)
    if state is None:
        raise ValueError("container stream must start with ContainerCreated")
    next_state = state.model_copy(deep=True); next_state.stream_version = event.stream_version
    if event.event_type == "ItemStoredInContainer":
        next_state.items.append(str(event.payload["item_id"])); next_state.items.sort()
    elif event.event_type == "ItemTakenFromContainer":
        item_id = str(event.payload["item_id"])
        if item_id in next_state.items: next_state.items.remove(item_id)
    elif event.event_type == "ContainerLockChanged":
        next_state.locked = bool(event.payload["locked"])
    return next_state
