from typing import Any

from pydantic import BaseModel, Field

from rpg_engine_api.domain.effects import EffectDefinition, EffectOperationType
from rpg_engine_api.rules.requirements_runtime import RequirementContext, evaluate_requirement


class EffectTargetState(BaseModel):
    values: dict[str, int | float] = Field(default_factory=dict)
    resources: dict[str, int] = Field(default_factory=dict)
    resource_maximums: dict[str, int] = Field(default_factory=dict)
    conditions: set[str] = Field(default_factory=set)
    tags: set[str] = Field(default_factory=set)
    health: int = 0
    max_health: int = 0


class EffectApplicationResult(BaseModel):
    effect_id: str
    applied: bool
    operations_applied: int = 0
    changes: list[dict[str, Any]] = Field(default_factory=list)


def apply_effect(
    definition: EffectDefinition,
    state: EffectTargetState,
    *,
    requirement_context: RequirementContext | None = None,
) -> EffectApplicationResult:
    context = requirement_context or RequirementContext(
        conditions=set(state.conditions),
        resources=dict(state.resources),
        tags=set(state.tags),
    )
    if not evaluate_requirement(definition.requirements, context):
        return EffectApplicationResult(effect_id=definition.id, applied=False)

    changes: list[dict[str, Any]] = []
    for operation in definition.operations:
        if operation.operation == EffectOperationType.MODIFY_VALUE:
            amount = _numeric(operation.value)
            before = state.values.get(operation.target, 0)
            state.values[operation.target] = before + amount
            changes.append({"operation": operation.operation, "target": operation.target, "before": before, "after": state.values[operation.target]})
        elif operation.operation == EffectOperationType.GRANT_RESOURCE:
            amount = int(_numeric(operation.value))
            before = state.resources.get(operation.target, 0)
            maximum = state.resource_maximums.get(operation.target)
            after = before + amount
            if maximum is not None:
                after = min(maximum, after)
            state.resources[operation.target] = after
            changes.append({"operation": operation.operation, "target": operation.target, "before": before, "after": after})
        elif operation.operation == EffectOperationType.SPEND_RESOURCE:
            amount = int(_numeric(operation.value))
            before = state.resources.get(operation.target, 0)
            if before < amount:
                raise ValueError(f"insufficient resource: {operation.target}")
            state.resources[operation.target] = before - amount
            changes.append({"operation": operation.operation, "target": operation.target, "before": before, "after": before - amount})
        elif operation.operation == EffectOperationType.APPLY_CONDITION:
            before = operation.target in state.conditions
            state.conditions.add(operation.target)
            changes.append({"operation": operation.operation, "target": operation.target, "before": before, "after": True})
        elif operation.operation == EffectOperationType.REMOVE_CONDITION:
            before = operation.target in state.conditions
            state.conditions.discard(operation.target)
            changes.append({"operation": operation.operation, "target": operation.target, "before": before, "after": False})
        elif operation.operation == EffectOperationType.DEAL_DAMAGE:
            amount = int(_numeric(operation.value))
            before = state.health
            state.health = max(0, state.health - amount)
            changes.append({"operation": operation.operation, "target": "health", "before": before, "after": state.health})
        elif operation.operation == EffectOperationType.RESTORE_HEALTH:
            amount = int(_numeric(operation.value))
            before = state.health
            state.health = min(state.max_health, state.health + amount)
            changes.append({"operation": operation.operation, "target": "health", "before": before, "after": state.health})
        elif operation.operation == EffectOperationType.EMIT_TAG:
            before = operation.target in state.tags
            state.tags.add(operation.target)
            changes.append({"operation": operation.operation, "target": operation.target, "before": before, "after": True})
        else:
            raise ValueError(f"unsupported effect operation: {operation.operation}")
    return EffectApplicationResult(
        effect_id=definition.id,
        applied=True,
        operations_applied=len(changes),
        changes=changes,
    )


def _numeric(value: int | float | str | None) -> int | float:
    if isinstance(value, bool) or value is None:
        raise ValueError("effect operation requires numeric value")
    if isinstance(value, (int, float)):
        return value
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError("effect operation requires numeric value") from exc
