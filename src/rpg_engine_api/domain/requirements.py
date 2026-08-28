from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RequirementOperator = Literal[
    "all",
    "any",
    "not",
    "level_at_least",
    "class_level_at_least",
    "ability_at_least",
    "has_feature",
    "has_proficiency",
    "has_item",
    "has_tag",
    "has_condition",
    "resource_at_least",
    "quest_state",
    "faction_reputation_at_least",
    "world_flag",
    "campaign_setting",
    "ruleset_predicate",
]


class RequirementExpr(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0"
    operator: RequirementOperator
    operands: tuple[Any, ...] = Field(default_factory=tuple)
