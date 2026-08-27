from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .requirements import RequirementExpr


class ChoiceOption(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    value: Any
    prerequisites: RequirementExpr | None = None


class ChoiceGroup(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0"
    id: str
    min_choices: int = Field(default=1, ge=0)
    max_choices: int = Field(default=1, ge=0)
    options: tuple[ChoiceOption, ...] = Field(default_factory=tuple)
    prerequisites: RequirementExpr | None = None
    uniqueness_policy: str = "unique"
    replacement_policy: str = "replace_invalid"

    @model_validator(mode="after")
    def validate_bounds(self) -> "ChoiceGroup":
        if self.max_choices < self.min_choices:
            raise ValueError("max_choices must be >= min_choices")
        if self.options and self.max_choices > len(self.options):
            raise ValueError("max_choices cannot exceed available options")
        return self
