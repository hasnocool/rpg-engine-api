from pydantic import BaseModel, ConfigDict, Field, field_validator

from .ids import validate_content_key


class SourceMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0"
    source_pack_id: str
    source_version: str
    license_id: str
    attribution_id: str | None = None
    source_reference: str | None = None
    content_hash: str = Field(min_length=8)


class DefinitionRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0"
    pack_id: str
    pack_version: str
    key: str
    content_hash: str = Field(min_length=8)

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        return validate_content_key(value)
