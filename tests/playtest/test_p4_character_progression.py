import pytest

from .harness import Persona, PlaytestClient


@pytest.mark.playtest
@pytest.mark.asyncio
async def test_character_creation_gameplay_reward_and_progression() -> None:
    client = PlaytestClient(Persona(name="Builder", principal_id="builder"))
    try:
        await client.command("CreateCampaign", payload={"campaign_id": "cmp_p4", "name": "Testing Grounds", "seed": 404})
        schema = (await client.get("/api/v1/character-creation/schema"))["data"]
        archetypes = {option["id"] for step in schema["steps"] if step["id"] == "archetype" for option in step["options"]}
        assert "guardian" in archetypes
        started = await client.command("StartCharacterCreation", campaign_id="cmp_p4", payload={"creation_id": "cc_p4"})
        assert started["status"] == "accepted"
        await client.command("SelectCharacterName", campaign_id="cmp_p4", payload={"creation_id": "cc_p4", "name": "Test Hero"})
        await client.command("SelectCharacterArchetype", campaign_id="cmp_p4", payload={"creation_id": "cc_p4", "archetype": "guardian"})
        draft = (await client.get("/api/v1/character-creation/cc_p4"))["data"]
        assert draft["valid_for_finalize"] is True
        finalized = await client.command("FinalizeCharacterCreation", campaign_id="cmp_p4", payload={"creation_id": "cc_p4", "actor_id": "hero_p4"})
        assert finalized["result"]["actor_id"] == "hero_p4"
        hero_before = (await client.get("/api/v1/actors/hero_p4"))["data"]
        assert hero_before["max_hp"] == 22
        await client.command("CreateActor", campaign_id="cmp_p4", payload={"actor_id": "enemy_p4", "name": "Training Foe", "max_hp": 6, "attack_bonus": 0, "defense": 8, "controller": {"controller_type": "simple_npc", "controller_version": "1", "behavior_profile_ref": "aggressive_melee"}})
        await client.command("StartEncounter", campaign_id="cmp_p4", payload={"encounter_id": "enc_p4", "participants": [{"actor_id": "hero_p4", "side": "heroes", "position": 0}, {"actor_id": "enemy_p4", "side": "enemies", "position": 1}]})
        for turn in range(30):
            encounter = (await client.get("/api/v1/encounters/enc_p4"))["data"]
            if encounter["status"] == "completed":
                break
            actions = (await client.get("/api/v1/actors/hero_p4/available-actions"))["data"]
            chosen = next((item for item in actions if item["action_id"] == "power_attack"), next(item for item in actions if item["action_id"] == "attack"))
            await client.command("PerformAction", campaign_id="cmp_p4", actor_id="hero_p4", idempotency_key=f"p4-turn-{turn}", payload={"encounter_id": "enc_p4", "action_id": chosen["action_id"], "target_id": chosen["target_id"]})
        hero_rewarded = (await client.get("/api/v1/actors/hero_p4"))["data"]
        assert hero_rewarded["experience"] >= 100
        assert hero_rewarded["progression_points"] >= 1
        old_attack = hero_rewarded["attack_bonus"]
        advancement = next(item for item in (await client.get("/api/v1/actors/hero_p4/available-actions"))["data"] if item["action_id"] == "advance_precision")
        await client.command(advancement["command_type"], campaign_id="cmp_p4", actor_id="hero_p4", payload={"choice": advancement["choice"]})
        hero_after = (await client.get("/api/v1/actors/hero_p4"))["data"]
        assert hero_after["attack_bonus"] == old_attack + 1
        assert "precision_training" in hero_after["features"]
        assert (await client.get("/api/v1/campaigns/cmp_p4/replay-hash"))["matches_live"] is True
    finally:
        await client.close()
