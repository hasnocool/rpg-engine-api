from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuthoringWorkspaceStatus(StrEnum):
    OPEN = "open"
    VALID = "valid"
    PUBLISHED = "published"


class DraftDefinition(BaseModel):
    schema_version: str = "1.0"
    draft_id: str
    definition_type: str
    key: str
    data: dict[str, Any] = Field(default_factory=dict)
    source: dict[str, Any] = Field(default_factory=dict)
    revision: int = 1


class ValidationIssue(BaseModel):
    severity: str
    code: str
    message: str
    draft_id: str | None = None


class ContentQualityReport(BaseModel):
    schema_version: str = "1.0"
    workspace_id: str
    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    definitions_checked: int = 0


class AuthoringWorkspace(BaseModel):
    schema_version: str = "1.0"
    workspace_id: str
    namespace: str
    owner_id: str
    status: AuthoringWorkspaceStatus = AuthoringWorkspaceStatus.OPEN
    drafts: dict[str, DraftDefinition] = Field(default_factory=dict)
    last_quality_report: ContentQualityReport | None = None


class PublishedDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0"
    definition_type: str
    key: str
    data: dict[str, Any]
    source: dict[str, Any]


class PublishedContentPack(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0"
    pack_id: str
    namespace: str
    version: str
    content_hash: str
    definitions: tuple[PublishedDefinition, ...]

    def definition(self, key: str) -> PublishedDefinition:
        for definition in self.definitions:
            if definition.key == key:
                return definition
        raise KeyError(key)
