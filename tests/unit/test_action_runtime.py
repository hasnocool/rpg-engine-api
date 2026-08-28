import pytest

from rpg_engine_api.domain.actions import (
    ActionCost,
    ActionDefinition,
    ActionInstance,
    ActionStatus,
    CostPolicy,
    TargetingDefinition,
)


def test_action_definition_exposes_compatibility_properties() -> None:
    definition = ActionDefinition(
        id="power_attack",
        name="Power Attack",
        category="attack",
        targeting=TargetingDefinition(minimum_targets=1, maximum_targets=1, range=1),
        costs=(ActionCost(resource_id="stamina", amount=1, policy=CostPolicy.PAY_ON_DECLARE),),
        damage_expression="1d6+2",
    )
    assert definition.range == 1
    assert definition.stamina_cost == 1


def test_action_instance_lifecycle_and_reserved_refund() -> None:
    action = ActionInstance(definition_id="cast", actor_id="hero")
    action.transition(ActionStatus.DECLARED)
    action.reserve("mana", 2)
    action.transition(ActionStatus.QUEUED)
    assert action.refund_reserved() == {"mana": 2}
    action.transition(ActionStatus.CANCELLED)
    assert action.status == ActionStatus.CANCELLED


def test_action_rejects_illegal_terminal_transition() -> None:
    action = ActionInstance(definition_id="attack", actor_id="hero")
    action.transition(ActionStatus.CANCELLED)
    with pytest.raises(ValueError):
        action.transition(ActionStatus.EXECUTING)


def test_targeting_rejects_inverted_bounds() -> None:
    with pytest.raises(ValueError):
        TargetingDefinition(minimum_targets=2, maximum_targets=1)
