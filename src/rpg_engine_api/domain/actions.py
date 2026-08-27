from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ActionStatus(StrEnum):
    PROPOSED = "proposed"
    DECLARED = "declared"
    QUEUED = "queued"
    EXECUTING = "executing"
    WAITING_FOR_REACTION = "waiting_for_reaction"
    INTERRUPTED = "interrupted"
    CANCELLED = "cancelled"
    RESOLVED = "resolved"
    COMPLETED = "completed"
    FAILED = "failed"


class ActionDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0"
    id: str
    name: str
    category: str
    range: int = Field(default=0, ge=0)
    stamina_cost: int = Field(default=0, ge=0)
    movement: int = Field(default=0, ge=0)
    damage_expression: str | None = None
    tags: tuple[str, ...] = ()


class ActionInstance(BaseModel):
    schema_version: str = "1.0"
    action_instance_id: str
    definition_id: str
    actor_id: str
    targets: tuple[str, ...] = ()
    status: ActionStatus = ActionStatus.PROPOSED
    declared_sequence: int | None = None
    scheduled_start: int | None = None
    scheduled_completion: int | None = None
    reserved_costs: dict[str, int] = Field(default_factory=dict)
