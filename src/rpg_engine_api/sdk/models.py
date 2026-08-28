from typing import Any

from pydantic import BaseModel, Field


class EventPage(BaseModel):
    events: list[dict[str, Any]] = Field(default_factory=list)
    next_cursor: str | None = None
    has_more: bool = False
    current_sequence: int = 0


class SyncResult(BaseModel):
    mode: str
    current_sequence: int
    snapshot: dict[str, Any] | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)
