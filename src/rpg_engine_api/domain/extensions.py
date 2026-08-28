from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ExtensionCapability(StrEnum):
    COMMAND_VALIDATOR = "command_validator"
    ACTION_PROVIDER = "action_provider"
    RECEIPT_OBSERVER = "receipt_observer"


class TrustedExtensionManifest(BaseModel):
    model_config = ConfigDict(frozen=True)
    schema_version: str = "1.0"
    extension_id: str
    version: str
    engine_api_range: str = ">=0.9,<2"
    capabilities: tuple[ExtensionCapability, ...] = ()
    deterministic: bool = True
    trusted: bool = True
    code_origin: str = "deployment"


class ExtensionInstallation(BaseModel):
    schema_version: str = "1.0"
    manifest: TrustedExtensionManifest
    enabled_requested: bool = False
    implementation_loaded: bool = False
    fault: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @property
    def active(self) -> bool:
        return self.enabled_requested and self.implementation_loaded and self.fault is None
