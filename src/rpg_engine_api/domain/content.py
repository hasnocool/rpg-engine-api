from pydantic import BaseModel, ConfigDict, Field, model_validator

from .definitions import DefinitionRef, SourceMetadata


class RulesetManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0"
    id: str
    version: str
    engine_api_range: str
    license: str
    attribution: str | None = None
    capabilities: frozenset[str] = frozenset()
    entry_pack_ids: tuple[str, ...] = ()


class ContentPackManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0"
    id: str
    version: str
    namespace: str
    ruleset_compatibility: tuple[str, ...] = ()
    engine_api_range: str = ">=0.1,<1"
    dependencies: tuple[str, ...] = ()
    optional_dependencies: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    load_after: tuple[str, ...] = ()
    license: str
    attribution: str | None = None
    content_hash: str = Field(min_length=8)
    source: SourceMetadata | None = None


class CampaignContentLock(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0"
    ruleset_ref: str
    pack_refs: tuple[DefinitionRef, ...] = ()
    house_rule_set_ref: str | None = None
    schema_versions: dict[str, str] = Field(default_factory=dict)
    combined_hash: str = Field(min_length=8)

    @model_validator(mode="after")
    def unique_pack_versions(self) -> "CampaignContentLock":
        identities = [(item.pack_id, item.pack_version) for item in self.pack_refs]
        if len(identities) != len(set(identities)):
            raise ValueError("content lock cannot repeat the same pack/version")
        return self
