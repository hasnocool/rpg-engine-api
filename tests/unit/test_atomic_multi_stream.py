import pytest

from rpg_engine_api.domain.events import DomainEvent
from rpg_engine_api.persistence.event_store import InMemoryEventStore, StreamVersionConflict


async def test_append_many_is_atomic_across_streams() -> None:
    store = InMemoryEventStore()
    first = DomainEvent(event_type="ActorDebited", campaign_id="cmp", stream_id="actor:a", command_id="cmd")
    second = DomainEvent(event_type="VendorCredited", campaign_id="cmp", stream_id="vendor:v", command_id="cmd")
    stored = await store.append_many((("actor:a", 0, (first,)), ("vendor:v", 0, (second,))))
    assert stored["actor:a"][0].sequence < stored["vendor:v"][0].sequence
    assert await store.current_version("actor:a") == 1
    assert await store.current_version("vendor:v") == 1


async def test_append_many_rejects_all_streams_if_one_version_is_stale() -> None:
    store = InMemoryEventStore()
    seed = DomainEvent(event_type="Seed", campaign_id="cmp", stream_id="vendor:v", command_id="seed")
    await store.append("vendor:v", 0, (seed,))
    first = DomainEvent(event_type="ActorDebited", campaign_id="cmp", stream_id="actor:a", command_id="cmd")
    second = DomainEvent(event_type="VendorCredited", campaign_id="cmp", stream_id="vendor:v", command_id="cmd")
    with pytest.raises(StreamVersionConflict):
        await store.append_many((("actor:a", 0, (first,)), ("vendor:v", 0, (second,))))
    assert await store.current_version("actor:a") == 0
    assert await store.current_version("vendor:v") == 1
