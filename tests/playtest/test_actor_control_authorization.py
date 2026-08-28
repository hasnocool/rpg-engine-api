import httpx
import pytest

from rpg_engine_api.app import create_app


async def command(client: httpx.AsyncClient, principal: str, command_type: str, *, campaign_id: str | None = None, actor_id: str | None = None, payload: dict[str, object] | None = None, roles: str = "player") -> dict[str, object]:
    response = await client.post("/api/v1/commands", headers={"X-Principal-Id": principal, "X-Principal-Roles": roles}, json={"command_type": command_type, "campaign_id": campaign_id, "actor_id": actor_id, "payload": payload or {}})
    assert response.status_code == 200
    return response.json()


@pytest.mark.playtest
async def test_active_session_actor_control_is_enforced() -> None:
    app = create_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await command(client, "owner", "CreateCampaign", payload={"campaign_id": "auth"}))["status"] == "accepted"
        assert (await command(client, "owner", "CreateActor", campaign_id="auth", payload={"actor_id": "hero", "name": "Hero"}))["status"] == "accepted"
        created = await command(client, "owner", "CreateGameSession", campaign_id="auth", payload={"session_id": "session"})
        assert created["status"] == "accepted"
        assert (await command(client, "player", "JoinGameSession", campaign_id="auth", payload={"session_id": "session"}))["status"] == "accepted"
        await command(client, "owner", "SetSessionReady", campaign_id="auth", payload={"session_id": "session", "ready": True})
        await command(client, "player", "SetSessionReady", campaign_id="auth", payload={"session_id": "session", "ready": True})
        await command(client, "owner", "GrantActorControl", campaign_id="auth", payload={"session_id": "session", "actor_id": "hero", "principal_id": "player"})
        await command(client, "owner", "OpenGameSession", campaign_id="auth", payload={"session_id": "session"})

        forbidden = await command(client, "intruder", "CraftItem", campaign_id="auth", actor_id="hero", payload={"ingredients": [], "result_item_id": "fake"})
        assert forbidden["status"] == "rejected"
        assert forbidden["error"]["code"] == "forbidden"

        allowed = await command(client, "player", "CraftItem", campaign_id="auth", actor_id="hero", payload={"ingredients": [], "result_item_id": "token"})
        assert allowed["status"] == "accepted"


@pytest.mark.playtest
async def test_owner_level_command_rejects_unprivileged_intruder() -> None:
    app = create_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        await command(client, "owner", "CreateCampaign", payload={"campaign_id": "owner-only"})
        denied = await command(client, "intruder", "ConfigureCampaignTiming", campaign_id="owner-only", payload={"mode": "turn_based"})
        assert denied["status"] == "rejected"
        assert denied["error"]["code"] == "forbidden"
