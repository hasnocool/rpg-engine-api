from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class VisibilityAudience(StrEnum):
    PUBLIC = "public"
    CAMPAIGN_MEMBERS = "campaign_members"
    PARTY = "party"
    CONTROLLER_ONLY = "controller_only"
    DM_ONLY = "dm_only"
    SERVICE_ONLY = "service_only"
    CUSTOM_ROLE = "custom_role"


class VisibilityPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0"
    audience: VisibilityAudience = VisibilityAudience.CAMPAIGN_MEMBERS
    discovery_requirement: str | None = None
    redact_fields: tuple[str, ...] = Field(default_factory=tuple)
    custom_role: str | None = None
