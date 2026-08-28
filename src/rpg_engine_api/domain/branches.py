from pydantic import BaseModel


class CampaignBranch(BaseModel):
    schema_version: str = "1.0"
    branch_id: str
    campaign_id: str
    parent_campaign_id: str
    source_checkpoint_id: str
    fork_sequence: int
    created_by: str
    reason: str = "manual_restore"
