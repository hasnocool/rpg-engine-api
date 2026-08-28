from rpg_engine_api.application.production_service import ProductionEngineService
from rpg_engine_api.domain.commands import CommandEnvelope, PrincipalContext
from rpg_engine_api.infrastructure.backup import export_event_history, restore_event_history
from rpg_engine_api.persistence.event_store import InMemoryEventStore


async def test_event_history_backup_round_trip_preserves_replay() -> None:
    source_store = InMemoryEventStore()
    source = ProductionEngineService(store=source_store)
    principal = PrincipalContext(principal_id="owner")
    await source.execute(CommandEnvelope(command_type="CreateCampaign", payload={"campaign_id": "backup", "seed": 99}), principal)
    await source.execute(CommandEnvelope(command_type="CreateActor", campaign_id="backup", payload={"actor_id": "hero", "name": "Hero"}), principal)
    await source.execute(CommandEnvelope(command_type="RollDice", campaign_id="backup", payload={"expression": "1d20"}), principal)
    expected = await source.replay_snapshot("backup")

    backup = await export_event_history(source_store, campaign_id="backup")
    assert backup.verify()
    target_store = InMemoryEventStore()
    assert await restore_event_history(backup, target_store) == len(backup.events)
    restored = ProductionEngineService(store=target_store)
    await restored.rebuild_from_store()
    assert await restored.replay_snapshot("backup") == expected
    assert restored.live_snapshot("backup") == expected
