from pydantic import BaseModel

from .controllers import ControllerAssignment
from .events import DomainEvent


class ActorState(BaseModel):
    schema_version: str = "1.0"
    actor_id: str
    campaign_id: str
    name: str
    controller: ControllerAssignment
    max_hp: int = 10
    attack_bonus: int = 2
    defense: int = 10
    stream_version: int = 0


def reduce_actor(state: ActorState | None, event: DomainEvent) -> ActorState:
    if event.event_type != "ActorCreated":
        if state is None:
            raise ValueError("actor stream must start with ActorCreated")
        return state.model_copy(update={"stream_version": event.stream_version})
    return ActorState(
        actor_id=str(event.payload["actor_id"]),
        campaign_id=event.campaign_id,
        name=str(event.payload["name"]),
        controller=ControllerAssignment.model_validate(event.payload["controller"]),
        max_hp=int(event.payload.get("max_hp", 10)),
        attack_bonus=int(event.payload.get("attack_bonus", 2)),
        defense=int(event.payload.get("defense", 10)),
        stream_version=event.stream_version,
    )
