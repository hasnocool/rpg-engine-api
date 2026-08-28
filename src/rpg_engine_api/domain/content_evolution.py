from pydantic import BaseModel, Field


class CampaignContentBinding(BaseModel):
    schema_version: str = "1.0"
    campaign_id: str
    pack_id: str
    version: str
    content_hash: str
    activated_sequence: int


class ContentRevisionDiff(BaseModel):
    schema_version: str = "1.0"
    pack_id: str
    from_version: str
    to_version: str
    added_keys: list[str] = Field(default_factory=list)
    removed_keys: list[str] = Field(default_factory=list)
    changed_keys: list[str] = Field(default_factory=list)


class CompatibilityReport(BaseModel):
    schema_version: str = "1.0"
    campaign_id: str
    pack_id: str
    from_version: str
    to_version: str
    compatible: bool
    requires_branch: bool = False
    reasons: list[str] = Field(default_factory=list)
    diff: ContentRevisionDiff


class ContentRevisionProposal(BaseModel):
    schema_version: str = "1.0"
    proposal_id: str
    campaign_id: str
    pack_id: str
    from_version: str
    to_version: str
    status: str = "proposed"
    report: CompatibilityReport | None = None
    pre_activation_checkpoint_id: str | None = None
