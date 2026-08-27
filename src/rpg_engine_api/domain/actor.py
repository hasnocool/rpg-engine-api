from pydantic import BaseModel, Field

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
    level: int = 1
    experience: int = 0
    progression_points: int = 0
    features: list[str] = Field(default_factory=list)
    stream_version: int = 0


def reduce_actor(state: ActorState | None, event: DomainEvent) -> ActorState:
    if event.event_type == "ActorCreated":
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
    if state is None:
        raise ValueError("actor stream must start with ActorCreated")
    next_state = state.model_copy(deep=True)
    next_state.stream_version = event.stream_version
    if event.event_type == "ExperienceGranted":
        next_state.experience += int(event.payload["experience"])
        next_state.progression_points += int(event.payload.get("progression_points", 0))
        next_state.level = max(next_state.level, int(event.payload.get("new_level", next_state.level)))
    elif event.event_type == "ProgressionChoiceApplied":
        feature = str(event.payload["feature"])
        if feature not in next_state.features:
            next_state.features.append(feature)
            next_state.features.sort()
        next_state.progression_points = int(event.payload["progression_points"])
        next_state.max_hp += int(event.payload.get("max_hp_delta", 0))
        next_state.attack_bonus += int(event.payload.get("attack_bonus_delta", 0))
        next_state.defense += int(event.payload.get("defense_delta", 0))
    return next_state
