import pytest

from rpg_engine_api.application.command_bus import EngineService
from rpg_engine_api.domain.commands import CommandEnvelope, PrincipalContext


@pytest.mark.performance
@pytest.mark.asyncio
async def test_replay_handles_small_event_batch() -> None:
    engine = EngineService()
    principal = PrincipalContext(principal_id="perf")
    await engine.execute(
        CommandEnvelope(
            command_type="CreateCampaign", payload={"campaign_id": "cmp_perf", "seed": 5}
        ),
        principal,
    )
    for index in range(100):
        await engine.execute(
            CommandEnvelope(
                command_type="RollDice",
                campaign_id="cmp_perf",
                idempotency_key=f"perf-{index}",
                payload={"expression": "1d20"},
            ),
            principal,
        )
    assert len(await engine.canonical_hash("cmp_perf")) == 64
