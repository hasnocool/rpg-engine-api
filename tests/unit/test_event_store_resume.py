from rpg_engine_api.domain.events import DomainEvent
from rpg_engine_api.persistence.event_store import InMemoryEventStore


async def test_read_after_filters_campaign_and_tracks_last_sequence() -> None:
    store = InMemoryEventStore()
    await store.append("campaign:a", 0, (DomainEvent(event_type="A", campaign_id="a", stream_id="campaign:a", command_id="1"),))
    await store.append("campaign:b", 0, (DomainEvent(event_type="B", campaign_id="b", stream_id="campaign:b", command_id="2"),))
    await store.append("campaign:a", 1, (DomainEvent(event_type="C", campaign_id="a", stream_id="campaign:a", command_id="3"),))
    assert [event.event_type for event in await store.read_after(1, campaign_id="a")] == ["C"]
    assert await store.last_sequence(campaign_id="a") == 3


async def test_overflow_marks_subscriber_without_breaking_append() -> None:
    store = InMemoryEventStore()
    queue = store.subscribe(maxsize=1)
    await store.append("campaign:a", 0, (DomainEvent(event_type="A", campaign_id="a", stream_id="campaign:a", command_id="1"),))
    await store.append("campaign:a", 1, (DomainEvent(event_type="B", campaign_id="a", stream_id="campaign:a", command_id="2"),))
    assert store.subscription_overflowed(queue)
    assert (await queue.get()).event_type == "A"
