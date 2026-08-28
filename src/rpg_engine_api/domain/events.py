from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .ids import new_id


class DomainEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0"
    event_id: str = Field(default_factory=lambda: new_id("evt"))
    event_type: str
    campaign_id: str
    stream_id: str
    stream_version: int = 0
    sequence: int = 0
    simulation_time: int = 0
    server_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    actor_id: str | None = None
    command_id: str
    causation_id: str | None = None
    correlation_id: str | None = None
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    content_lock_hash: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
