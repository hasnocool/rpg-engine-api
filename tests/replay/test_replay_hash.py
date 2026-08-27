import pytest

from rpg_engine_api.application.command_bus import EngineService
from rpg_engine_api.domain.commands import CommandEnvelope, PrincipalContext


@pytest.mark.replay
@pytest.mark.asyncio
async def test_replay_is_stable() -> None:
    engine = EngineService()
    principal = PrincipalContext(principal_id="tester")
    await engine.execute(
        CommandEnvelope(
            command_type="CreateCampaign",
            payload={"campaign_id": "cmp_replay", "name": "Replay", "seed": 12},
        ),
        principal,
    )
    await engine.execute(
        CommandEnvelope(
            command_type="CreateActor",
            campaign_id="cmp_replay",
            payload={"actor_id": "act_replay", "name": "Hero"},
        ),
        principal,
    )
    first = await engine.canonical_hash("cmp_replay")
    second = await engine.canonical_hash("cmp_replay")
    assert first == second
