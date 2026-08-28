import pytest

from rpg_engine_api.domain.events import DomainEvent
from rpg_engine_api.infrastructure.outbox import InMemoryIdempotentPublisher, drain_outbox
from rpg_engine_api.persistence.event_store import InMemoryEventStore


@pytest.mark.asyncio
async def test_outbox_retry_deduplicates_with_event_id_aware_publisher() -> None:
    store = InMemoryEventStore()
    event = DomainEvent(event_type="Test", campaign_id="cmp", stream_id="cmp:1", command_id="cmd")
    stored = (await store.append("cmp:1", 0, (event,)))[0]
    publisher = InMemoryIdempotentPublisher()
    await publisher.publish(stored)  # simulates publish succeeding immediately before a crash
    result = await drain_outbox(store, publisher)
    assert result.published == 0
    assert result.deduplicated == 1
    assert len(publisher.events) == 1
    assert await store.pending_outbox_count() == 0
