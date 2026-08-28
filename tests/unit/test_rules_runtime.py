import pytest

from rpg_engine_api.domain.effects import EffectDefinition, EffectOperation, EffectOperationType
from rpg_engine_api.domain.requirements import RequirementExpr
from rpg_engine_api.rules.effects_runtime import EffectTargetState, apply_effect
from rpg_engine_api.rules.requirements_runtime import RequirementContext, evaluate_requirement


def test_nested_requirement_expression() -> None:
    expr = RequirementExpr(
        operator="all",
        operands=(
            {"operator": "level_at_least", "operands": (2,)},
            {"operator": "has_feature", "operands": ("shield_training",)},
        ),
    )
    assert evaluate_requirement(expr, RequirementContext(level=2, features={"shield_training"}))
    assert not evaluate_requirement(expr, RequirementContext(level=1, features={"shield_training"}))


def test_effect_pipeline_changes_resources_conditions_and_health() -> None:
    effect = EffectDefinition(
        id="battle_blessing",
        trigger="immediate",
        operations=(
            EffectOperation(operation=EffectOperationType.GRANT_RESOURCE, target="stamina", value=2),
            EffectOperation(operation=EffectOperationType.APPLY_CONDITION, target="inspired"),
            EffectOperation(operation=EffectOperationType.RESTORE_HEALTH, target="self", value=4),
        ),
    )
    state = EffectTargetState(resources={"stamina": 0}, resource_maximums={"stamina": 3}, health=5, max_health=10)
    result = apply_effect(effect, state)
    assert result.applied
    assert state.resources["stamina"] == 2
    assert "inspired" in state.conditions
    assert state.health == 9


def test_spending_missing_resource_is_rejected() -> None:
    effect = EffectDefinition(id="cost", trigger="immediate", operations=(EffectOperation(operation=EffectOperationType.SPEND_RESOURCE, target="mana", value=2),))
    with pytest.raises(ValueError):
        apply_effect(effect, EffectTargetState(resources={"mana": 1}))
