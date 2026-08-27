import pytest

from rpg_engine_api.application.command_bus import EngineService
from rpg_engine_api.domain.commands import CommandEnvelope, CommandStatus, PrincipalContext


@pytest.mark.asyncio
async def test_create_campaign_actor_and_idempotent_roll() -> None:
    engine = EngineService()
    principal = PrincipalContext(principal_id="tester")
    campaign = await engine.execute(
        CommandEnvelope(
            command_type="CreateCampaign",
            payload={"campaign_id": "cmp_unit", "name": "Unit", "seed": 7},
        ),
        principal,
    )
    assert campaign.status == CommandStatus.ACCEPTED
    actor = await engine.execute(
        CommandEnvelope(
            command_type="CreateActor",
            campaign_id="cmp_unit",
            payload={"actor_id": "act_unit", "name": "Hero"},
        ),
        principal,
    )
    assert actor.status == CommandStatus.ACCEPTED
    before = len(await engine.store.read_all())
    first = await engine.execute(
        CommandEnvelope(
            command_type="RollDice",
            campaign_id="cmp_unit",
            actor_id="act_unit",
            idempotency_key="roll-once",
            payload={"expression": "1d20"},
        ),
        principal,
    )
    second = await engine.execute(
        CommandEnvelope(
            command_type="RollDice",
            campaign_id="cmp_unit",
            actor_id="act_unit",
            idempotency_key="roll-once",
            payload={"expression": "1d20"},
        ),
        principal,
    )
    assert first.status == CommandStatus.ACCEPTED
    assert second.status == CommandStatus.ALREADY_PROCESSED
    assert len(await engine.store.read_all()) == before + 1


@pytest.mark.asyncio
async def test_stale_version_rejected_before_rng_is_consumed() -> None:
    engine = EngineService()
    principal = PrincipalContext(principal_id="tester")
    await engine.execute(
        CommandEnvelope(
            command_type="CreateCampaign",
            payload={"campaign_id": "cmp_conflict", "seed": 88},
        ),
        principal,
    )
    stale = await engine.execute(
        CommandEnvelope(
            command_type="RollDice",
            campaign_id="cmp_conflict",
            expected_stream_version=0,
            payload={"expression": "1d20"},
        ),
        principal,
    )
    assert stale.status == CommandStatus.CONFLICT
    accepted = await engine.execute(
        CommandEnvelope(
            command_type="RollDice",
            campaign_id="cmp_conflict",
            payload={"expression": "1d20"},
        ),
        principal,
    )
    control = EngineService()
    await control.execute(
        CommandEnvelope(
            command_type="CreateCampaign",
            payload={"campaign_id": "cmp_control", "seed": 88},
        ),
        principal,
    )
    expected = await control.execute(
        CommandEnvelope(
            command_type="RollDice", campaign_id="cmp_control", payload={"expression": "1d20"}
        ),
        principal,
    )
    assert accepted.result["dice"]["total"] == expected.result["dice"]["total"]
