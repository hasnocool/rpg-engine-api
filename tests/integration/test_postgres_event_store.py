import os

import pytest

from rpg_engine_api.domain.events import DomainEvent
from rpg_engine_api.persistence.postgres import PostgresEventStore


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_append_and_replay() -> None:
    url = os.getenv("RPG_ENGINE_DATABASE_URL")
    if not url:
        pytest.skip("RPG_ENGINE_DATABASE_URL is required for PostgreSQL integration evidence")
    store = PostgresEventStore(url)
    await store.prepare()
    await store.clear_for_test()
    event = DomainEvent(
        event_type="CampaignCreated",
        campaign_id="cmp_pg",
        stream_id="campaign:cmp_pg",
        command_id="cmd_pg",
        payload={"name": "Postgres", "seed": 1, "owner_id": "tester"},
    )
    stored = await store.append("campaign:cmp_pg", 0, (event,))
    replayed = await store.read_stream("campaign:cmp_pg")
    assert replayed == stored
    await store.close()
