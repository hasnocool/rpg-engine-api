from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .requirements import RequirementExpr


class EffectOperationType(StrEnum):
    MODIFY_VALUE = "modify_value"
    GRANT_RESOURCE = "grant_resource"
    SPEND_RESOURCE = "spend_resource"
    APPLY_CONDITION = "apply_condition"
    REMOVE_CONDITION = "remove_condition"
    DEAL_DAMAGE = "deal_damage"
    RESTORE_HEALTH = "restore_health"
    EMIT_TAG = "emit_tag"


class EffectOperation(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation: EffectOperationType
    target: str
    value: int | float | str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class EffectDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0"
    id: str
    source_ref: str | None = None
    trigger: str
    requirements: RequirementExpr | None = None
    operations: tuple[EffectOperation, ...] = ()
    duration: str | None = None
    stacking_policy: str = "replace"
    expiration: str | None = None


class ResourceDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0"
    id: str
    name: str
    minimum: int = 0
    maximum: int
    reset_policy: str | None = None


class ResourceState(BaseModel):
    definition_id: str
    current: int
    maximum: int


class ConditionDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0"
    id: str
    name: str
    restrictions: tuple[str, ...] = ()
    effects: tuple[EffectDefinition, ...] = ()
    stacking_policy: str = "replace"
    duration_policy: str | None = None
    removal_policy: str | None = None
    visibility: str = "public"
