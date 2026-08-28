from enum import StrEnum

from pydantic import BaseModel, Field, computed_field

from rpg_engine_api.domain.events import DomainEvent


class EncounterStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class EncounterantState(BaseModel):
    actor_id: str
    side: str
    hp: int
    max_hp: int
    position: int = 0
    stamina: int = 1
    max_stamina: int = 1
    guard: int = 0
    reaction_points: int = 1
    conditions: list[str] = Field(default_factory=list)
    fled: bool = False

    @computed_field
    @property
    def alive(self) -> bool:
        return self.hp > 0 and not self.fled

    @computed_field
    @property
    def hp_ratio(self) -> float:
        return 0.0 if self.max_hp <= 0 else self.hp / self.max_hp


class EncounterState(BaseModel):
    schema_version: str = "1.1"
    encounter_id: str
    campaign_id: str
    status: EncounterStatus = EncounterStatus.ACTIVE
    participants: dict[str, EncounterantState] = Field(default_factory=dict)
    turn_order: list[str] = Field(default_factory=list)
    turn_index: int = 0
    round: int = 1
    stream_version: int = 0
    winner_side: str | None = None

    @computed_field
    @property
    def current_actor_id(self) -> str | None:
        if self.status != EncounterStatus.ACTIVE or not self.turn_order:
            return None
        return self.turn_order[self.turn_index]


def reduce_encounter(state: EncounterState | None, event: DomainEvent) -> EncounterState:
    if event.event_type == "EncounterStarted":
        participants = {
            item["actor_id"]: EncounterantState.model_validate(item)
            for item in event.payload["participants"]
        }
        return EncounterState(
            encounter_id=str(event.payload["encounter_id"]),
            campaign_id=event.campaign_id,
            participants=participants,
            turn_order=list(event.payload["turn_order"]),
            turn_index=0,
            round=1,
            stream_version=event.stream_version,
        )
    if state is None:
        raise ValueError("encounter stream must start with EncounterStarted")
    next_state = state.model_copy(deep=True)
    next_state.stream_version = event.stream_version
    if event.event_type == "ActorMoved":
        next_state.participants[str(event.payload["actor_id"])].position = int(event.payload["position"])
    elif event.event_type == "ActorRetreated":
        participant = next_state.participants[str(event.payload["actor_id"])]
        participant.position = int(event.payload.get("position", participant.position))
        participant.fled = bool(event.payload.get("fled", False))
    elif event.event_type == "GuardRaised":
        next_state.participants[str(event.payload["actor_id"])].guard = int(event.payload["guard"])
    elif event.event_type in {"AttackResolved", "PowerAttackResolved", "RangedAttackResolved"}:
        attacker = next_state.participants[str(event.payload["actor_id"])]
        target = next_state.participants[str(event.payload["target_id"])]
        attacker.stamina = int(event.payload.get("attacker_stamina", attacker.stamina))
        target.hp = int(event.payload["target_hp"])
        target.guard = 0
    elif event.event_type == "HealingApplied":
        target = next_state.participants[str(event.payload["target_id"])]
        target.hp = min(target.max_hp, int(event.payload["target_hp"]))
    elif event.event_type == "ConditionApplied":
        target = next_state.participants[str(event.payload["target_id"])]
        condition_id = str(event.payload["condition_id"])
        if condition_id not in target.conditions:
            target.conditions.append(condition_id)
            target.conditions.sort()
    elif event.event_type == "ConditionRemoved":
        target = next_state.participants[str(event.payload["target_id"])]
        condition_id = str(event.payload["condition_id"])
        target.conditions = [item for item in target.conditions if item != condition_id]
    elif event.event_type == "ReactionSpent":
        target = next_state.participants[str(event.payload["actor_id"])]
        target.reaction_points = max(0, target.reaction_points - int(event.payload.get("amount", 1)))
    elif event.event_type == "TurnAdvanced":
        next_state.turn_index = int(event.payload["turn_index"])
        next_state.round = int(event.payload["round"])
        current = next_state.current_actor_id
        if current is not None:
            participant = next_state.participants[current]
            participant.reaction_points = 1
            participant.stamina = min(participant.max_stamina, participant.stamina + 1)
    elif event.event_type == "EncounterCompleted":
        next_state.status = EncounterStatus.COMPLETED
        next_state.winner_side = str(event.payload["winner_side"])
    return next_state
