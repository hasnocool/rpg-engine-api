import pytest
from .harness import Persona,PlaytestClient

@pytest.mark.playtest
@pytest.mark.asyncio
async def test_actor_currency_and_encounter_health_persist_outside_combat() -> None:
    client=PlaytestClient(Persona(name="Owner",principal_id="owner"))
    try:
        await client.command("CreateCampaign",payload={"campaign_id":"cmp_persist","seed":123});await client.command("CreateActor",campaign_id="cmp_persist",payload={"actor_id":"hero_persist","name":"Hero","max_hp":20,"current_hp":12,"currency":37,"controller":{"controller_type":"human"}});await client.command("CreateActor",campaign_id="cmp_persist",payload={"actor_id":"enemy_persist","name":"Weak Enemy","max_hp":1,"current_hp":1,"defense":1,"controller":{"controller_type":"simple_npc","behavior_profile_ref":"passive"}})
        actor=(await client.get("/api/v1/actors/hero_persist"))["data"];assert actor["current_hp"]==12 and actor["currency"]==37
        await client.command("StartEncounter",campaign_id="cmp_persist",payload={"encounter_id":"enc_persist","participants":[{"actor_id":"hero_persist","side":"heroes","position":0},{"actor_id":"enemy_persist","side":"enemies","position":1}]});enc=(await client.get("/api/v1/encounters/enc_persist"))["data"];assert enc["participants"]["hero_persist"]["hp"]==12
        for turn in range(10):
            enc=(await client.get("/api/v1/encounters/enc_persist"))["data"]
            if enc["status"]=="completed":break
            actions=(await client.get("/api/v1/actors/hero_persist/available-actions"))["data"];attack=next(item for item in actions if item["action_id"] in {"power_attack","attack"});await client.command("PerformAction",campaign_id="cmp_persist",actor_id="hero_persist",idempotency_key=f"persist-{turn}",payload={"encounter_id":"enc_persist","action_id":attack["action_id"],"target_id":attack["target_id"]})
        actor=(await client.get("/api/v1/actors/hero_persist"))["data"];assert 0<=actor["current_hp"]<=actor["max_hp"] and actor["experience"]>=100
    finally:await client.close()
