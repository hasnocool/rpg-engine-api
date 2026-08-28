from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rpg_engine_api.domain.ids import new_id
from rpg_engine_api.domain.requirements import RequirementExpr


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


class CostPolicy(StrEnum):
    PAY_ON_DECLARE = "pay_on_declare"
    RESERVE_ON_DECLARE_PAY_ON_EXECUTE = "reserve_on_declare_pay_on_execute"
    PAY_ON_SUCCESS = "pay_on_success"
    PAY_ON_COMPLETION = "pay_on_completion"


class ActionCost(BaseModel):
    model_config = ConfigDict(frozen=True)

    resource_id: str
    amount: int = Field(ge=0)
    policy: CostPolicy = CostPolicy.RESERVE_ON_DECLARE_PAY_ON_EXECUTE


class TargetingDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    target_kind: str = "actor"
    minimum_targets: int = Field(default=0, ge=0)
    maximum_targets: int = Field(default=1, ge=0)
    range: int = Field(default=0, ge=0)
    requires_line_of_sight: bool = False
    allowed_sides: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_count(self) -> "TargetingDefinition":
        if self.maximum_targets < self.minimum_targets:
            raise ValueError("maximum_targets cannot be less than minimum_targets")
        return self


class ActionDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.1"
    id: str
    name: str
    category: str
    requirements: RequirementExpr | None = None
    targeting: TargetingDefinition = Field(default_factory=TargetingDefinition)
    costs: tuple[ActionCost, ...] = ()
    duration: int = Field(default=0, ge=0)
    recovery: int = Field(default=0, ge=0)
    interruptible: bool = True
    movement: int = Field(default=0, ge=0)
    damage_expression: str | None = None
    effects: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    @property
    def range(self) -> int:
        return self.targeting.range

    @property
    def stamina_cost(self) -> int:
        return sum(cost.amount for cost in self.costs if cost.resource_id == "stamina")


class ActionInstance(BaseModel):
    schema_version: str = "1.1"
    action_instance_id: str = Field(default_factory=lambda: new_id("action"))
    definition_id: str
    actor_id: str
    targets: tuple[str, ...] = ()
    status: ActionStatus = ActionStatus.PROPOSED
    declared_sequence: int | None = None
    scheduled_start: int | None = None
    scheduled_completion: int | None = None
    reserved_costs: dict[str, int] = Field(default_factory=dict)
    paid_costs: dict[str, int] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    failure_reason: str | None = None

    def transition(self, target: ActionStatus) -> "ActionInstance":
        allowed: dict[ActionStatus, set[ActionStatus]] = {
            ActionStatus.PROPOSED: {ActionStatus.DECLARED, ActionStatus.CANCELLED, ActionStatus.FAILED},
            ActionStatus.DECLARED: {ActionStatus.QUEUED, ActionStatus.EXECUTING, ActionStatus.CANCELLED, ActionStatus.FAILED},
            ActionStatus.QUEUED: {ActionStatus.EXECUTING, ActionStatus.INTERRUPTED, ActionStatus.CANCELLED},
            ActionStatus.EXECUTING: {ActionStatus.WAITING_FOR_REACTION, ActionStatus.RESOLVED, ActionStatus.INTERRUPTED, ActionStatus.FAILED},
            ActionStatus.WAITING_FOR_REACTION: {ActionStatus.EXECUTING, ActionStatus.RESOLVED, ActionStatus.INTERRUPTED},
            ActionStatus.RESOLVED: {ActionStatus.COMPLETED, ActionStatus.FAILED},
            ActionStatus.INTERRUPTED: set(),
            ActionStatus.CANCELLED: set(),
            ActionStatus.COMPLETED: set(),
            ActionStatus.FAILED: set(),
        }
        if target not in allowed[self.status]:
            raise ValueError(f"illegal action transition: {self.status} -> {target}")
        self.status = target
        return self

    def reserve(self, resource_id: str, amount: int) -> None:
        if amount < 0:
            raise ValueError("reserved amount must be non-negative")
        self.reserved_costs[resource_id] = self.reserved_costs.get(resource_id, 0) + amount

    def pay_reserved(self) -> None:
        for resource_id, amount in self.reserved_costs.items():
            self.paid_costs[resource_id] = self.paid_costs.get(resource_id, 0) + amount
        self.reserved_costs.clear()

    def refund_reserved(self) -> dict[str, int]:
        refunded = dict(self.reserved_costs)
        self.reserved_costs.clear()
        return refunded
