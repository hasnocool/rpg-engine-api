from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ControllerType(StrEnum):
    HUMAN = "human"
    SIMPLE_NPC = "simple_npc"
    UTILITY_AI = "utility_ai"
    SCRIPTED = "scripted"
    REMOTE_SERVICE = "remote_service"
    EXTERNAL_AGENT = "external_agent"
    SYSTEM = "system"


class ControllerAssignment(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.1"
    controller_type: ControllerType = ControllerType.HUMAN
    controller_version: str = "1"
    behavior_profile_ref: str | None = None
    enabled: bool = True
    fallback_controller_type: ControllerType | None = None
