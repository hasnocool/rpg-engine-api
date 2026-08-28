from pydantic import BaseModel, Field

from .controllers import ControllerAssignment
from .events import DomainEvent


class ActorState(BaseModel):
    schema_version: str = "1.1"
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
    currency: int = 10
    inventory: list[str] = Field(default_factory=list)
    species: str | None = None
    background: str | None = None
    resources: dict[str, int] = Field(default_factory=dict)
    conditions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
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
            currency=int(event.payload.get("currency", 10)),
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
    elif event.event_type == "ItemPurchased":
        next_state.currency = int(event.payload["currency_after"])
        item_id = str(event.payload["item_id"])
        next_state.inventory.append(item_id)
        next_state.inventory.sort()
    elif event.event_type == "CharacterOriginApplied":
        next_state.species = str(event.payload["species"])
        next_state.background = str(event.payload["background"])
        for feature in event.payload.get("features", []):
            value = str(feature)
            if value not in next_state.features:
                next_state.features.append(value)
        for item in event.payload.get("items", []):
            next_state.inventory.append(str(item))
        next_state.features.sort()
        next_state.inventory.sort()
    elif event.event_type == "ItemCrafted":
        for ingredient in event.payload.get("ingredients", []):
            value = str(ingredient)
            if value in next_state.inventory:
                next_state.inventory.remove(value)
        next_state.inventory.append(str(event.payload["result_item_id"]))
        next_state.inventory.sort()
    elif event.event_type == "ControllerAssignmentChanged":
        next_state.controller = ControllerAssignment.model_validate(event.payload["controller"])
    elif event.event_type == "ActorResourceChanged":
        next_state.resources[str(event.payload["resource_id"])] = int(event.payload["current"])
    elif event.event_type == "ActorConditionApplied":
        condition = str(event.payload["condition_id"])
        if condition not in next_state.conditions:
            next_state.conditions.append(condition)
            next_state.conditions.sort()
    elif event.event_type == "ActorConditionRemoved":
        condition = str(event.payload["condition_id"])
        next_state.conditions = [item for item in next_state.conditions if item != condition]
    return next_state
