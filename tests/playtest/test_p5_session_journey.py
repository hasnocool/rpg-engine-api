import pytest

from .harness import Persona, PlaytestClient


@pytest.mark.playtest
@pytest.mark.asyncio
async def test_long_form_session_social_trade_quest_combat_checkpoint_reconnect_recap() -> None:
    owner = Persona(name="DM Player", principal_id="owner")
    client = PlaytestClient(owner)
    app = client.app
    try:
        await client.command("CreateCampaign", payload={"campaign_id": "cmp_p5", "name": "Testing Grounds", "seed": 505})
        await client.command("CreateGameSession", campaign_id="cmp_p5", payload={"session_id": "session_p5"})
        await client.command("StartCharacterCreation", campaign_id="cmp_p5", payload={"creation_id": "cc_p5"})
        await client.command("SelectCharacterName", campaign_id="cmp_p5", payload={"creation_id": "cc_p5", "name": "Session Hero"})
        await client.command("SelectCharacterArchetype", campaign_id="cmp_p5", payload={"creation_id": "cc_p5", "archetype": "guardian"})
        await client.command("FinalizeCharacterCreation", campaign_id="cmp_p5", payload={"creation_id": "cc_p5", "actor_id": "hero_p5"})
        await client.command("CreateActor", campaign_id="cmp_p5", payload={"actor_id": "questgiver_p5", "name": "Quest Giver", "controller": {"controller_type": "simple_npc", "controller_version": "1", "behavior_profile_ref": "passive"}})
        await client.command("CreateActor", campaign_id="cmp_p5", payload={"actor_id": "enemy_p5", "name": "Camp Raider", "max_hp": 6, "attack_bonus": 0, "defense": 8, "controller": {"controller_type": "simple_npc", "controller_version": "1", "behavior_profile_ref": "aggressive_melee"}})
        await client.command("GrantActorControl", campaign_id="cmp_p5", payload={"session_id": "session_p5", "actor_id": "hero_p5", "principal_id": "owner"})
        await client.command("SetSessionReady", campaign_id="cmp_p5", payload={"session_id": "session_p5", "ready": True})
        await client.command("OpenGameSession", campaign_id="cmp_p5", payload={"session_id": "session_p5"})

        await client.command("TalkToNpc", campaign_id="cmp_p5", actor_id="hero_p5", payload={"npc_id": "questgiver_p5", "topic": "camp_raiders"})
        await client.command("CreateQuest", campaign_id="cmp_p5", payload={"quest_id": "quest_p5", "title": "Clear the Camp", "objective": "Defeat the camp raider"})
        await client.command("AcceptQuest", campaign_id="cmp_p5", actor_id="hero_p5", payload={"quest_id": "quest_p5"})
        await client.command("TradeItem", campaign_id="cmp_p5", actor_id="hero_p5", payload={"item_id": "testing:item/travel_ration", "price": 2, "vendor_id": "questgiver_p5"})
        assert "testing:item/travel_ration" in (await client.get("/api/v1/actors/hero_p5"))["data"]["inventory"]

        await client.command("CreateWorld", campaign_id="cmp_p5", payload={"world_id": "world_p5", "locations": [{"id": "town", "name": "Town", "connections": ["road"]}, {"id": "road", "name": "Road", "connections": ["town", "camp"]}, {"id": "camp", "name": "Camp", "connections": ["road"]}]})
        await client.command("PlaceActorInWorld", campaign_id="cmp_p5", actor_id="hero_p5", payload={"world_id": "world_p5", "location_id": "town"})
        await client.command("TravelActor", campaign_id="cmp_p5", actor_id="hero_p5", payload={"world_id": "world_p5", "destination_id": "road"})
        await client.command("TravelActor", campaign_id="cmp_p5", actor_id="hero_p5", payload={"world_id": "world_p5", "destination_id": "camp"})
        await client.command("StartEncounter", campaign_id="cmp_p5", payload={"encounter_id": "enc_p5", "participants": [{"actor_id": "hero_p5", "side": "heroes", "position": 0}, {"actor_id": "enemy_p5", "side": "enemies", "position": 1}]})
        for turn in range(30):
            encounter = (await client.get("/api/v1/encounters/enc_p5"))["data"]
            if encounter["status"] == "completed":
                break
            actions = (await client.get("/api/v1/actors/hero_p5/available-actions"))["data"]
            chosen = next((item for item in actions if item["action_id"] == "power_attack"), next(item for item in actions if item["action_id"] == "attack"))
            await client.command("PerformAction", campaign_id="cmp_p5", actor_id="hero_p5", idempotency_key=f"p5-turn-{turn}", payload={"encounter_id": "enc_p5", "action_id": chosen["action_id"], "target_id": chosen["target_id"]})
        await client.command("CompleteQuest", campaign_id="cmp_p5", actor_id="hero_p5", payload={"quest_id": "quest_p5", "required_encounter_id": "enc_p5"})
        assert (await client.get("/api/v1/quests/quest_p5"))["data"]["status"] == "completed"

        hero = (await client.get("/api/v1/actors/hero_p5"))["data"]
        if hero["progression_points"]:
            await client.command("AdvanceActor", campaign_id="cmp_p5", actor_id="hero_p5", payload={"choice": "precision"})
        await client.command("CreateCheckpoint", campaign_id="cmp_p5", payload={"checkpoint_id": "checkpoint_p5", "name": "After Camp"})
        assert (await client.get("/api/v1/checkpoints/checkpoint_p5"))["data"]["source_sequence"] > 0

        await client.close()
        reconnected = PlaytestClient(owner, app=app)
        client = reconnected
        session = (await client.get("/api/v1/sessions/session_p5"))["data"]
        assert session["status"] == "open"
        assert session["actor_controls"]["hero_p5"] == "owner"
        await client.command("CloseGameSession", campaign_id="cmp_p5", payload={"session_id": "session_p5"})
        recap = (await client.get("/api/v1/sessions/session_p5/recap"))["data"]
        assert recap["event_count"] > 0
        assert recap["event_type_counts"].get("QuestCompleted", 0) == 1
        assert (await client.get("/api/v1/campaigns/cmp_p5/replay-hash"))["matches_live"] is True
    finally:
        await client.close()
