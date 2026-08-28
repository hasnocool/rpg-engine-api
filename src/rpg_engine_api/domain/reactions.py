from enum import StrEnum

from pydantic import BaseModel, Field

from rpg_engine_api.domain.ids import new_id


class ReactionWindowStatus(StrEnum):
    OPEN = "open"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ReactionOption(BaseModel):
    action_id: str
    actor_id: str
    target_ids: tuple[str, ...] = ()
    label: str


class ReactionWindow(BaseModel):
    schema_version: str = "1.0"
    reaction_window_id: str = Field(default_factory=lambda: new_id("reaction"))
    triggering_action_instance_id: str
    eligible_actor_ids: tuple[str, ...]
    opened_at: int
    deadline_at: int | None = None
    options: tuple[ReactionOption, ...] = ()
    status: ReactionWindowStatus = ReactionWindowStatus.OPEN
    selected_action_id: str | None = None
    selected_actor_id: str | None = None

    def accept(self, actor_id: str, action_id: str) -> None:
        if self.status != ReactionWindowStatus.OPEN:
            raise ValueError("reaction window is not open")
        if actor_id not in self.eligible_actor_ids:
            raise ValueError("actor is not eligible for this reaction")
        if not any(option.actor_id == actor_id and option.action_id == action_id for option in self.options):
            raise ValueError("reaction action is not available")
        self.status = ReactionWindowStatus.ACCEPTED
        self.selected_actor_id = actor_id
        self.selected_action_id = action_id

    def decline(self, actor_id: str) -> None:
        if self.status != ReactionWindowStatus.OPEN:
            raise ValueError("reaction window is not open")
        if actor_id not in self.eligible_actor_ids:
            raise ValueError("actor is not eligible for this reaction")
        self.status = ReactionWindowStatus.DECLINED
