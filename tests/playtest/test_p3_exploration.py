import pytest

from .harness import Persona, PlaytestClient


@pytest.mark.playtest
@pytest.mark.asyncio
async def test_exploration_discovery_interaction_flows_into_combat() -> None:
    client = PlaytestClient(Persona(name="Explorer", principal_id="explorer"))
    try:
        await client.command("CreateCampaign", payload={"campaign_id": "cmp_p3", "name": "Testing Grounds", "seed": 303})
        await client.command("CreateActor", campaign_id="cmp_p3", payload={"actor_id": "hero_p3", "name": "Explorer", "max_hp": 24, "attack_bonus": 8, "defense": 14})
        await client.command("CreateActor", campaign_id="cmp_p3", payload={"actor_id": "goblin_p3", "name": "Goblin", "max_hp": 8, "attack_bonus": 1, "defense": 10, "controller": {"controller_type": "simple_npc", "controller_version": "1", "behavior_profile_ref": "aggressive_melee"}})
        await client.command(
            "CreateWorld",
            campaign_id="cmp_p3",
            payload={
                "world_id": "world_p3",
                "locations": [
                    {"id": "town", "name": "Town", "connections": ["road"], "objects": [{"id": "notice", "name": "Notice Board", "interaction": "read"}]},
                    {"id": "road", "name": "Road", "connections": ["town", "hidden_path", "camp"]},
                    {"id": "hidden_path", "name": "Hidden Path", "connections": ["road"], "hidden": True, "objects": [{"id": "cache", "name": "Hidden Cache", "hidden": True, "interaction": "open"}]},
                    {"id": "camp", "name": "Goblin Camp", "connections": ["road"]},
                ],
            },
        )
        await client.command("PlaceActorInWorld", campaign_id="cmp_p3", actor_id="hero_p3", payload={"world_id": "world_p3", "location_id": "town"})
        town_actions = (await client.get("/api/v1/actors/hero_p3/available-actions"))["data"]
        notice = next(item for item in town_actions if item.get("object_id") == "notice")
        await client.command(notice["command_type"], campaign_id="cmp_p3", actor_id="hero_p3", payload={"world_id": "world_p3", "object_id": "notice"})
        travel = next(item for item in town_actions if item.get("destination_id") == "road")
        await client.command(travel["command_type"], campaign_id="cmp_p3", actor_id="hero_p3", payload={"world_id": "world_p3", "destination_id": "road"})
        road_actions = (await client.get("/api/v1/actors/hero_p3/available-actions"))["data"]
        assert not any(item.get("destination_id") == "hidden_path" for item in road_actions)
        search = next(item for item in road_actions if item["action_id"] == "search")
        await client.command(search["command_type"], campaign_id="cmp_p3", actor_id="hero_p3", payload={"world_id": "world_p3"})
        visible = (await client.get("/api/v1/worlds/world_p3?actor_id=hero_p3"))["data"]
        assert "hidden_path" in visible["discovered_locations"]
        road_actions = (await client.get("/api/v1/actors/hero_p3/available-actions"))["data"]
        assert any(item.get("destination_id") == "hidden_path" for item in road_actions)
        await client.command("TravelActor", campaign_id="cmp_p3", actor_id="hero_p3", payload={"world_id": "world_p3", "destination_id": "camp"})
        await client.command("StartEncounter", campaign_id="cmp_p3", payload={"encounter_id": "enc_p3", "participants": [{"actor_id": "hero_p3", "side": "heroes", "position": 0}, {"actor_id": "goblin_p3", "side": "enemies", "position": 2}]})
        for turn in range(30):
            encounter = (await client.get("/api/v1/encounters/enc_p3"))["data"]
            if encounter["status"] == "completed":
                break
            actions = (await client.get("/api/v1/actors/hero_p3/available-actions"))["data"]
            chosen = next((item for item in actions if item["action_id"] == "power_attack"), next((item for item in actions if item["action_id"] == "attack"), actions[0]))
            payload = {"encounter_id": "enc_p3", "action_id": chosen["action_id"]}
            if chosen.get("target_id"):
                payload["target_id"] = chosen["target_id"]
            await client.command("PerformAction", campaign_id="cmp_p3", actor_id="hero_p3", idempotency_key=f"p3-{turn}", payload=payload)
        assert (await client.get("/api/v1/encounters/enc_p3"))["data"]["status"] == "completed"
        assert (await client.get("/api/v1/campaigns/cmp_p3/replay-hash"))["matches_live"] is True
    finally:
        await client.close()
