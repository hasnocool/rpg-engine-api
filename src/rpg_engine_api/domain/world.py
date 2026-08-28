from pydantic import BaseModel, ConfigDict, Field

from rpg_engine_api.domain.events import DomainEvent


class WorldObjectDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    hidden: bool = False
    interaction: str = "inspect"


class LocationDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    connections: tuple[str, ...] = ()
    hidden: bool = False
    objects: tuple[WorldObjectDefinition, ...] = ()


class WorldState(BaseModel):
    schema_version: str = "1.0"
    world_id: str
    campaign_id: str
    locations: dict[str, LocationDefinition] = Field(default_factory=dict)
    actor_locations: dict[str, str] = Field(default_factory=dict)
    discovered_locations: dict[str, list[str]] = Field(default_factory=dict)
    discovered_objects: dict[str, list[str]] = Field(default_factory=dict)
    interactions: list[dict[str, str]] = Field(default_factory=list)
    stream_version: int = 0


def _add_unique(mapping: dict[str, list[str]], actor_id: str, value: str) -> None:
    values = mapping.setdefault(actor_id, [])
    if value not in values:
        values.append(value)
        values.sort()


def reduce_world(state: WorldState | None, event: DomainEvent) -> WorldState:
    if event.event_type == "WorldCreated":
        locations = {
            item["id"]: LocationDefinition.model_validate(item)
            for item in event.payload["locations"]
        }
        return WorldState(
            world_id=str(event.payload["world_id"]),
            campaign_id=event.campaign_id,
            locations=locations,
            stream_version=event.stream_version,
        )
    if state is None:
        raise ValueError("world stream must start with WorldCreated")
    next_state = state.model_copy(deep=True)
    next_state.stream_version = event.stream_version
    actor_id = str(event.actor_id or event.payload.get("actor_id", ""))
    if event.event_type == "ActorPlacedInWorld":
        location_id = str(event.payload["location_id"])
        next_state.actor_locations[actor_id] = location_id
        _add_unique(next_state.discovered_locations, actor_id, location_id)
    elif event.event_type == "ActorTravelled":
        location_id = str(event.payload["destination_id"])
        next_state.actor_locations[actor_id] = location_id
        _add_unique(next_state.discovered_locations, actor_id, location_id)
    elif event.event_type == "LocationDiscovered":
        _add_unique(next_state.discovered_locations, actor_id, str(event.payload["location_id"]))
    elif event.event_type == "WorldObjectDiscovered":
        _add_unique(next_state.discovered_objects, actor_id, str(event.payload["object_id"]))
    elif event.event_type == "WorldObjectInteracted":
        next_state.interactions.append(
            {
                "actor_id": actor_id,
                "location_id": str(event.payload["location_id"]),
                "object_id": str(event.payload["object_id"]),
                "interaction": str(event.payload["interaction"]),
            }
        )
    return next_state
