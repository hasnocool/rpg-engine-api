from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from rpg_engine_api.domain.requirements import RequirementExpr


class RequirementContext(BaseModel):
    level: int = 1
    class_levels: dict[str, int] = Field(default_factory=dict)
    abilities: dict[str, int] = Field(default_factory=dict)
    features: set[str] = Field(default_factory=set)
    proficiencies: set[str] = Field(default_factory=set)
    items: set[str] = Field(default_factory=set)
    tags: set[str] = Field(default_factory=set)
    conditions: set[str] = Field(default_factory=set)
    resources: dict[str, int] = Field(default_factory=dict)
    quest_states: dict[str, str] = Field(default_factory=dict)
    faction_reputation: dict[str, int] = Field(default_factory=dict)
    world_flags: dict[str, Any] = Field(default_factory=dict)
    campaign_settings: dict[str, Any] = Field(default_factory=dict)
    predicates: dict[str, Callable[..., bool]] = Field(default_factory=dict, exclude=True)

    model_config = {"arbitrary_types_allowed": True}


def evaluate_requirement(expr: RequirementExpr | None, context: RequirementContext) -> bool:
    if expr is None:
        return True
    operands = expr.operands
    operator = expr.operator
    if operator == "all":
        return all(evaluate_requirement(RequirementExpr.model_validate(item), context) for item in operands)
    if operator == "any":
        return any(evaluate_requirement(RequirementExpr.model_validate(item), context) for item in operands)
    if operator == "not":
        if len(operands) != 1:
            raise ValueError("not requires exactly one operand")
        return not evaluate_requirement(RequirementExpr.model_validate(operands[0]), context)
    if operator == "level_at_least":
        return context.level >= int(operands[0])
    if operator == "class_level_at_least":
        return context.class_levels.get(str(operands[0]), 0) >= int(operands[1])
    if operator == "ability_at_least":
        return context.abilities.get(str(operands[0]), 0) >= int(operands[1])
    if operator == "has_feature":
        return str(operands[0]) in context.features
    if operator == "has_proficiency":
        return str(operands[0]) in context.proficiencies
    if operator == "has_item":
        return str(operands[0]) in context.items
    if operator == "has_tag":
        return str(operands[0]) in context.tags
    if operator == "has_condition":
        return str(operands[0]) in context.conditions
    if operator == "resource_at_least":
        return context.resources.get(str(operands[0]), 0) >= int(operands[1])
    if operator == "quest_state":
        return context.quest_states.get(str(operands[0])) == str(operands[1])
    if operator == "faction_reputation_at_least":
        return context.faction_reputation.get(str(operands[0]), 0) >= int(operands[1])
    if operator == "world_flag":
        return context.world_flags.get(str(operands[0])) == operands[1]
    if operator == "campaign_setting":
        return context.campaign_settings.get(str(operands[0])) == operands[1]
    if operator == "ruleset_predicate":
        predicate_id = str(operands[0])
        predicate = context.predicates.get(predicate_id)
        if predicate is None:
            return False
        return bool(predicate(*operands[1:]))
    raise ValueError(f"unsupported requirement operator: {operator}")
