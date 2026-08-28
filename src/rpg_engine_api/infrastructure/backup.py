import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from rpg_engine_api.domain.authoring import PublishedContentPack
from rpg_engine_api.domain.events import DomainEvent


class EventHistoryBackup(BaseModel):
    schema_version: str = "1.0"
    repository_format: str = "rpg-engine-api-event-history"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    campaign_id: str | None = None
    source_last_sequence: int = 0
    events: tuple[dict[str, Any], ...] = ()
    content_packs: tuple[dict[str, Any], ...] = ()
    digest: str

    def verify(self) -> bool:
        return self.digest == backup_digest(self.events, self.content_packs, self.campaign_id, self.source_last_sequence)


def backup_digest(events: tuple[dict[str, Any], ...], content_packs: tuple[dict[str, Any], ...], campaign_id: str | None, source_last_sequence: int) -> str:
    canonical = json.dumps({"campaign_id": campaign_id, "source_last_sequence": source_last_sequence, "events": events, "content_packs": content_packs}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def export_event_history(store: Any, *, campaign_id: str | None = None, content_packs: tuple[PublishedContentPack, ...] = ()) -> EventHistoryBackup:
    all_events = await store.read_all()
    selected = tuple(event for event in all_events if campaign_id is None or event.campaign_id == campaign_id)
    event_data = tuple(event.model_dump(mode="json") for event in selected)
    pack_data = tuple(pack.model_dump(mode="json") for pack in sorted(content_packs, key=lambda item: (item.pack_id, item.version)))
    last_sequence = selected[-1].sequence if selected else 0
    digest = backup_digest(event_data, pack_data, campaign_id, last_sequence)
    return EventHistoryBackup(campaign_id=campaign_id, source_last_sequence=last_sequence, events=event_data, content_packs=pack_data, digest=digest)


async def restore_event_history(backup: EventHistoryBackup, store: Any, *, require_empty: bool = True) -> int:
    if not backup.verify():
        raise ValueError("backup integrity digest does not match contents")
    if require_empty and await store.last_sequence() != 0:
        raise ValueError("restore target is not empty")
    restored = 0
    for raw in backup.events:
        event = DomainEvent.model_validate(raw)
        expected = await store.current_version(event.stream_id)
        if expected != event.stream_version - 1:
            raise ValueError(f"backup stream version gap for {event.stream_id}")
        stored = await store.append(event.stream_id, expected, (event,))
        restored_event = stored[0]
        if restored_event.event_id != event.event_id or restored_event.stream_version != event.stream_version:
            raise ValueError("restored event identity/version mismatch")
        restored += 1
    return restored
