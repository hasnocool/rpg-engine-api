from rpg_engine_api.application.recoverable_service import RecoverableEngineService
from rpg_engine_api.domain.commands import CommandEnvelope, PrincipalContext
from rpg_engine_api.persistence.event_store import InMemoryEventStore


async def test_rebuild_restores_gameplay_timing_and_rng_position() -> None:
    store = InMemoryEventStore()
    principal = PrincipalContext(principal_id="owner")
    original = RecoverableEngineService(store=store)
    await original.execute(CommandEnvelope(command_type="CreateCampaign", payload={"campaign_id": "rebuild", "seed": 42}), principal)
    await original.execute(CommandEnvelope(command_type="ConfigureCampaignTiming", campaign_id="rebuild", payload={"mode": "timed_turn_based", "decision_duration": 10}), principal)
    await original.execute(CommandEnvelope(command_type="RollDice", campaign_id="rebuild", payload={"expression": "1d20"}), principal)
    await original.execute(CommandEnvelope(command_type="CreateActor", campaign_id="rebuild", payload={"actor_id": "hero", "name": "Hero"}), principal)

    restored = RecoverableEngineService(store=store)
    await restored.rebuild_from_store()
    assert restored.campaigns["rebuild"].name == original.campaigns["rebuild"].name
    assert restored.actors["hero"].model_dump(mode="json") == original.actors["hero"].model_dump(mode="json")
    assert restored.timelines["rebuild"].mode.value == "timed_turn_based"
    assert restored._rng["rebuild"].sequence("dice") == 1
    assert restored.live_snapshot("rebuild") == await restored.replay_snapshot("rebuild")
