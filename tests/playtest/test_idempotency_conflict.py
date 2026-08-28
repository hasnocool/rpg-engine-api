import httpx
import pytest

from rpg_engine_api.app import create_app


@pytest.mark.playtest
async def test_same_idempotency_key_with_different_request_conflicts() -> None:
    app = create_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        campaign = await client.post("/api/v1/commands", json={"command_type": "CreateCampaign", "payload": {"campaign_id": "idem", "seed": 1}})
        assert campaign.json()["status"] == "accepted"
        first = {"command_type": "RollDice", "campaign_id": "idem", "idempotency_key": "roll-1", "payload": {"expression": "1d20"}}
        assert (await client.post("/api/v1/commands", json=first)).json()["status"] == "accepted"
        retry = {**first, "command_id": "retry_command"}
        assert (await client.post("/api/v1/commands", json=retry)).json()["status"] == "already_processed"
        changed = {**retry, "command_id": "changed_command", "payload": {"expression": "2d20"}}
        conflict = (await client.post("/api/v1/commands", json=changed)).json()
        assert conflict["status"] == "conflict"
        assert conflict["error"]["code"] == "idempotency_conflict"
