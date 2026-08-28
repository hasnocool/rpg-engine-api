from rpg_engine_api.domain.events import DomainEvent
from rpg_engine_api.infrastructure.outbox import drain_outbox
from rpg_engine_api.persistence.event_store import InMemoryEventStore


async def test_outbox_recovery_marks_only_successful_publications() -> None:
    store = InMemoryEventStore()
    event = DomainEvent(event_type="Example", campaign_id="cmp", stream_id="campaign:cmp", command_id="cmd")
    await store.append("campaign:cmp", 0, (event,))
    published: list[str] = []

    async def publisher(value: DomainEvent) -> None:
        published.append(value.event_id)

    result = await drain_outbox(store, publisher)
    assert result.published == 1
    assert published
    assert await store.pending_outbox_count() == 0
