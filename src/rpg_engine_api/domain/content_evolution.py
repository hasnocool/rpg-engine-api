from pydantic import BaseModel, Field


class CampaignContentBinding(BaseModel):
    schema_version: str = "1.0"
    campaign_id: str
    pack_id: str
    version: str
    content_hash: str
    activated_sequence: int


class ContentRevisionDiff(BaseModel):
    schema_version: str = "1.1"
    pack_id: str
    from_version: str
    to_version: str
    added_keys: list[str] = Field(default_factory=list)
    removed_keys: list[str] = Field(default_factory=list)
    changed_keys: list[str] = Field(default_factory=list)
    mechanic_changed_keys: list[str] = Field(default_factory=list)
    presentation_changed_keys: list[str] = Field(default_factory=list)
    provenance_changed_keys: list[str] = Field(default_factory=list)


class CompatibilityReport(BaseModel):
    schema_version: str = "1.1"
    campaign_id: str
    pack_id: str
    from_version: str
    to_version: str
    compatible: bool
    requires_branch: bool = False
    reasons: list[str] = Field(default_factory=list)
    diff: ContentRevisionDiff


class CampaignImpactReport(BaseModel):
    schema_version: str = "1.0"
    campaign_id: str
    proposal_id: str
    affected_keys: list[str] = Field(default_factory=list)
    matched_paths: dict[str, list[str]] = Field(default_factory=dict)
    affected_categories: dict[str, list[str]] = Field(default_factory=dict)
    future_mechanics_affected: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ContentMigrationOperation(BaseModel):
    operation: str
    source_ref: str | None = None
    target_ref: str | None = None
    path: str | None = None
    reversible: bool = False
    notes: str | None = None


class ContentMigrationPlan(BaseModel):
    schema_version: str = "1.0"
    proposal_id: str
    campaign_id: str
    operations: list[ContentMigrationOperation] = Field(default_factory=list)
    unresolved_keys: list[str] = Field(default_factory=list)
    executable_in_place: bool = False
    reversible: bool = False


class ContentRevisionProposal(BaseModel):
    schema_version: str = "1.1"
    proposal_id: str
    campaign_id: str
    pack_id: str
    from_version: str
    to_version: str
    status: str = "proposed"
    report: CompatibilityReport | None = None
    impact_report: CampaignImpactReport | None = None
    migration_plan: ContentMigrationPlan | None = None
    pre_activation_checkpoint_id: str | None = None
