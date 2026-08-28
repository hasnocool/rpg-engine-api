import pytest

from rpg_engine_api.application.production_release_service import ProductionReleaseEngineService
from rpg_engine_api.domain.commands import CommandEnvelope, PrincipalContext


@pytest.mark.replay
@pytest.mark.asyncio
async def test_spell_rng_position_matches_after_runtime_rebuild() -> None:
    engine = ProductionReleaseEngineService(); principal = PrincipalContext(principal_id="owner", roles=frozenset({"owner"}))
    await engine.execute(CommandEnvelope(command_type="CreateCampaign", payload={"campaign_id":"cmp_magic_replay","seed":812}), principal)
    await engine.execute(CommandEnvelope(command_type="StartCharacterCreation", campaign_id="cmp_magic_replay", payload={"creation_id":"cc_magic"}), principal)
    await engine.execute(CommandEnvelope(command_type="SelectCharacterName", campaign_id="cmp_magic_replay", payload={"creation_id":"cc_magic","name":"Mage"}), principal)
    await engine.execute(CommandEnvelope(command_type="SelectCharacterClass", campaign_id="cmp_magic_replay", payload={"creation_id":"cc_magic","class_id":"mage"}), principal)
    await engine.execute(CommandEnvelope(command_type="SelectCharacterPreparedAbilities", campaign_id="cmp_magic_replay", payload={"creation_id":"cc_magic","prepared_abilities":["arcane_bolt"]}), principal)
    await engine.execute(CommandEnvelope(command_type="FinalizeCharacterCreation", campaign_id="cmp_magic_replay", payload={"creation_id":"cc_magic","actor_id":"mage"}), principal)
    await engine.execute(CommandEnvelope(command_type="CreateActor", campaign_id="cmp_magic_replay", payload={"actor_id":"target","name":"Target","max_hp":30,"defense":8,"controller":{"controller_type":"human"}}), principal)
    await engine.execute(CommandEnvelope(command_type="StartEncounter", campaign_id="cmp_magic_replay", payload={"encounter_id":"enc_magic","participants":[{"actor_id":"mage","side":"a","position":0},{"actor_id":"target","side":"b","position":2}]}), principal, drive_controllers=False)
    action = next(item for item in engine.available_actions("mage") if item["action_id"] == "ability:arcane_bolt")
    await engine.execute(CommandEnvelope(command_type="PerformAction", campaign_id="cmp_magic_replay", actor_id="mage", payload={"encounter_id":"enc_magic","action_id":action["action_id"],"target_id":action["target_id"]}), principal, drive_controllers=False)

    rebuilt = ProductionReleaseEngineService(store=engine.store); await rebuilt.rebuild_from_store()
    expected = engine._rng["cmp_magic_replay"].roll("1d20", stream="dice")
    actual = rebuilt._rng["cmp_magic_replay"].roll("1d20", stream="dice")
    assert actual.rolls == expected.rolls
    assert actual.rng_sequence == expected.rng_sequence
