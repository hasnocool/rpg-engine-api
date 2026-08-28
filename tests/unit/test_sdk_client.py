import httpx

from rpg_engine_api.app import create_app
from rpg_engine_api.domain.commands import CommandEnvelope, CommandStatus
from rpg_engine_api.sdk import AsyncRpgClient


async def test_sdk_uses_public_api_without_rules_logic() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with AsyncRpgClient(base_url="http://test", principal_id="owner", transport=transport) as client:
        receipt = await client.command(CommandEnvelope(command_type="CreateCampaign", payload={"campaign_id": "sdk"}))
        assert receipt.status == CommandStatus.ACCEPTED
        campaign = await client.campaign("sdk")
        assert campaign["campaign_id"] == "sdk"
        capabilities = await client.capabilities()
        assert "timing_modes" in capabilities
