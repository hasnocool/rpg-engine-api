import os

import pytest

from rpg_engine_api.domain.events import DomainEvent
from rpg_engine_api.persistence.postgres import PostgresEventStore


@pytest.mark.integration
async def test_postgres_outbox_checkpoint_and_snapshot_round_trip() -> None:
    url = os.getenv("RPG_ENGINE_DATABASE_URL")
    if not url:
        pytest.skip("RPG_ENGINE_DATABASE_URL is not configured")
    store = PostgresEventStore(url)
    await store.clear_for_test()
    event = DomainEvent(event_type="OperationalTest", campaign_id="cmp", stream_id="campaign:cmp", command_id="cmd")
    stored = await store.append("campaign:cmp", 0, (event,))
    assert await store.pending_outbox_count() == 1
    await store.mark_outbox_published(stored[0].event_id)
    assert await store.pending_outbox_count() == 0
    await store.save_projection_checkpoint("runtime", schema_version="1.0", last_sequence=stored[0].sequence)
    checkpoint = await store.load_projection_checkpoint("runtime")
    assert checkpoint and checkpoint["last_sequence"] == stored[0].sequence
    await store.save_snapshot("checkpoint:test", stream_version=1, schema_version="1.0", value={"ok": True})
    snapshot = await store.load_snapshot("checkpoint:test")
    assert snapshot and snapshot["value"] == {"ok": True}
    await store.close()
