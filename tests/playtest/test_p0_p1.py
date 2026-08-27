import pytest
from httpx import ASGITransport, AsyncClient

from rpg_engine_api.app import create_app
from rpg_engine_api.config import Settings


@pytest.mark.playtest
@pytest.mark.asyncio
async def test_public_p0_p1_command_loop() -> None:
    app = create_app(Settings())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/health")).json()["status"] == "ok"
        assert (await client.get("/ready")).json()["status"] == "ready"

        campaign = (
            await client.post(
                "/api/v1/commands",
                json={
                    "command_type": "CreateCampaign",
                    "payload": {"campaign_id": "cmp_play", "name": "Testing Grounds", "seed": 12345},
                },
            )
        ).json()
        assert campaign["status"] == "accepted"

        actor = (
            await client.post(
                "/api/v1/commands",
                json={
                    "command_type": "CreateActor",
                    "campaign_id": "cmp_play",
                    "payload": {"actor_id": "act_hero", "name": "Hero"},
                },
            )
        ).json()
        assert actor["status"] == "accepted"

        actions = (await client.get("/api/v1/actors/act_hero/available-actions")).json()["data"]
        assert actions and actions[0]["command_type"] == "RollDice"
        before = (await client.get("/api/v1/campaigns/cmp_play/events")).json()["meta"]["count"]
        roll_command = {
            "command_type": actions[0]["command_type"],
            "campaign_id": "cmp_play",
            "actor_id": "act_hero",
            "idempotency_key": "p1-roll",
            "payload": actions[0]["payload_schema"],
        }
        first = (await client.post("/api/v1/commands", json=roll_command)).json()
        duplicate = (await client.post("/api/v1/commands", json=roll_command)).json()
        assert first["status"] == "accepted"
        assert duplicate["status"] == "already_processed"
        after = (await client.get("/api/v1/campaigns/cmp_play/events")).json()["meta"]["count"]
        assert after == before + 1
        replay = (await client.get("/api/v1/campaigns/cmp_play/replay-hash")).json()
        assert len(replay["canonical_hash"]) == 64
