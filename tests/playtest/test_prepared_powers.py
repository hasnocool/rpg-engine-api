import pytest
from .harness import Persona,PlaytestClient

@pytest.mark.playtest
@pytest.mark.asyncio
async def test_prepared_arcane_power_is_advertised_spends_slot_and_resolves() -> None:
    client=PlaytestClient(Persona(name="Caster",principal_id="caster"))
    try:
        await client.command("CreateCampaign",payload={"campaign_id":"cmp_magic","seed":44});await client.command("StartCharacterCreation",campaign_id="cmp_magic",payload={"creation_id":"cc_magic"});await client.command("SelectCharacterName",campaign_id="cmp_magic",payload={"creation_id":"cc_magic","name":"Caster"});await client.command("SelectCharacterClass",campaign_id="cmp_magic",payload={"creation_id":"cc_magic","class_id":"mage"});await client.command("SelectCharacterPreparedAbilities",campaign_id="cmp_magic",payload={"creation_id":"cc_magic","prepared_abilities":["arcane_bolt","ward"]});await client.command("FinalizeCharacterCreation",campaign_id="cmp_magic",payload={"creation_id":"cc_magic","actor_id":"caster_magic"});await client.command("CreateActor",campaign_id="cmp_magic",payload={"actor_id":"target_magic","name":"Target","max_hp":30,"defense":1,"controller":{"controller_type":"human"}});await client.command("StartEncounter",campaign_id="cmp_magic",payload={"encounter_id":"enc_magic","participants":[{"actor_id":"caster_magic","side":"heroes","position":0},{"actor_id":"target_magic","side":"enemies","position":3}]})
        actions=(await client.get("/api/v1/actors/caster_magic/available-actions"))["data"];bolt=next(item for item in actions if item["action_id"]=="ability:arcane_bolt");before=(await client.get("/api/v1/actors/caster_magic"))["data"]["resources"]["spell_slots"];await client.command("PerformAction",campaign_id="cmp_magic",actor_id="caster_magic",payload={"encounter_id":"enc_magic","action_id":bolt["action_id"],"target_id":bolt["target_id"]});after=(await client.get("/api/v1/actors/caster_magic"))["data"]["resources"]["spell_slots"];assert after==before-1
    finally:await client.close()
