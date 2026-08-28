from pydantic import BaseModel


class CampaignCheckpoint(BaseModel):
    schema_version: str = "1.0"
    checkpoint_id: str
    campaign_id: str
    name: str
    source_sequence: int
    created_by: str
    content_lock_hash: str | None = None
