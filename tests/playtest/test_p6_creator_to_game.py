import pytest

from .harness import Persona, PlaytestClient


@pytest.mark.playtest
@pytest.mark.asyncio
async def test_creator_can_validate_publish_simulate_and_play_authored_encounter() -> None:
    client = PlaytestClient(Persona(name="Creator", principal_id="creator"))
    try:
        await client.command("CreateAuthoringWorkspace", payload={"workspace_id": "ws_p6", "namespace": "demo"})
        await client.command("UpsertDraftDefinition", payload={"workspace_id": "ws_p6", "draft_id": "npc", "definition_type": "npc_template", "key": "demo:npc/raider", "source": {"license_id": "CC0-1.0"}, "data": {"name": "Demo Raider", "max_hp": 7, "attack_bonus": 1, "defense": 9, "behavior_profile": "aggressive_melee"}})
        await client.command("UpsertDraftDefinition", payload={"workspace_id": "ws_p6", "draft_id": "encounter", "definition_type": "encounter_template", "key": "demo:encounter/roadside", "source": {"license_id": "CC0-1.0"}, "data": {"enemy_ref": "demo:npc/raider", "player_side": "heroes", "enemy_side": "enemies", "player_position": 0, "enemy_position": 2}})
        validation = await client.command("ValidateAuthoringWorkspace", payload={"workspace_id": "ws_p6"})
        assert validation["result"]["quality_report"]["valid"] is True
        published = await client.command("PublishAuthoringWorkspace", payload={"workspace_id": "ws_p6", "version": "1.0.0"})
        assert len(published["result"]["content_hash"]) == 64
        pack = (await client.get("/api/v1/content-packs/demo/1.0.0"))["data"]
        assert len(pack["definitions"]) == 2
        simulation = await client.command("SimulateEncounterTemplate", payload={"pack_id": "demo", "version": "1.0.0", "encounter_key": "demo:encounter/roadside", "runs": 3})
        assert simulation["result"]["runs"] == 3
        assert sum(simulation["result"]["outcomes"].values()) == 3

        await client.command("CreateCampaign", payload={"campaign_id": "cmp_p6", "name": "Creator Campaign", "seed": 606})
        await client.command("CreateActor", campaign_id="cmp_p6", payload={"actor_id": "hero_p6", "name": "Creator Hero", "max_hp": 24, "attack_bonus": 8, "defense": 14})
        instantiated = await client.command("InstantiateEncounterTemplate", campaign_id="cmp_p6", payload={"pack_id": "demo", "version": "1.0.0", "encounter_key": "demo:encounter/roadside", "player_actor_id": "hero_p6", "enemy_actor_id": "raider_p6", "encounter_id": "enc_p6"})
        assert instantiated["result"]["encounter_id"] == "enc_p6"
        for turn in range(30):
            encounter = (await client.get("/api/v1/encounters/enc_p6"))["data"]
            if encounter["status"] == "completed":
                break
            actions = (await client.get("/api/v1/actors/hero_p6/available-actions"))["data"]
            chosen = next((item for item in actions if item["action_id"] == "power_attack"), next((item for item in actions if item["action_id"] == "attack"), actions[0]))
            payload = {"encounter_id": "enc_p6", "action_id": chosen["action_id"]}
            if chosen.get("target_id"):
                payload["target_id"] = chosen["target_id"]
            await client.command("PerformAction", campaign_id="cmp_p6", actor_id="hero_p6", idempotency_key=f"p6-{turn}", payload=payload)
        assert (await client.get("/api/v1/encounters/enc_p6"))["data"]["status"] == "completed"
        assert (await client.get("/api/v1/campaigns/cmp_p6/replay-hash"))["matches_live"] is True
    finally:
        await client.close()
