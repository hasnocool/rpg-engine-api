import pytest

from .harness import Persona, PlaytestClient


async def publish_version(client: PlaytestClient, workspace_id: str, version: str, hp: int) -> None:
    await client.command("CreateAuthoringWorkspace", payload={"workspace_id": workspace_id, "namespace": "evo"})
    await client.command("UpsertDraftDefinition", payload={"workspace_id": workspace_id, "draft_id": "npc", "definition_type": "npc_template", "key": "evo:npc/raider", "source": {"license_id": "CC0-1.0"}, "data": {"name": "Evolving Raider", "max_hp": hp, "attack_bonus": 1, "defense": 9, "behavior_profile": "aggressive_melee"}})
    await client.command("UpsertDraftDefinition", payload={"workspace_id": workspace_id, "draft_id": "enc", "definition_type": "encounter_template", "key": "evo:encounter/camp", "source": {"license_id": "CC0-1.0"}, "data": {"enemy_ref": "evo:npc/raider", "enemy_position": 2}})
    assert (await client.command("ValidateAuthoringWorkspace", payload={"workspace_id": workspace_id}))["result"]["quality_report"]["valid"] is True
    await client.command("PublishAuthoringWorkspace", payload={"workspace_id": workspace_id, "version": version})


@pytest.mark.playtest
@pytest.mark.asyncio
async def test_safe_content_revision_checkpoint_activate_and_continue_playing() -> None:
    client = PlaytestClient(Persona(name="Evolution Creator", principal_id="creator"))
    try:
        await publish_version(client, "ws_evo_1", "1.0.0", 6)
        await publish_version(client, "ws_evo_2", "1.1.0", 8)
        await client.command("CreateCampaign", payload={"campaign_id": "cmp_p7", "name": "Evolution", "seed": 707})
        await client.command("CreateActor", campaign_id="cmp_p7", payload={"actor_id": "hero_p7", "name": "Hero", "max_hp": 24, "attack_bonus": 8, "defense": 14})
        await client.command("BindCampaignContent", campaign_id="cmp_p7", payload={"pack_id": "evo", "version": "1.0.0"})
        proposed = await client.command("ProposeContentRevision", campaign_id="cmp_p7", payload={"proposal_id": "rev_p7", "to_version": "1.1.0"})
        assert proposed["status"] == "accepted"
        dry = await client.command("DryRunContentRevision", campaign_id="cmp_p7", payload={"proposal_id": "rev_p7"})
        report = dry["result"]["compatibility_report"]
        assert report["compatible"] is True
        assert "evo:npc/raider" in report["diff"]["changed_keys"]
        activated = await client.command("ActivateContentRevision", campaign_id="cmp_p7", payload={"proposal_id": "rev_p7", "checkpoint_id": "cp_p7"})
        assert activated["result"]["version"] == "1.1.0"
        binding = (await client.get("/api/v1/campaigns/cmp_p7/content-binding"))["data"]
        assert binding["version"] == "1.1.0"
        assert (await client.get("/api/v1/checkpoints/cp_p7"))["data"]["source_sequence"] > 0

        await client.command("InstantiateEncounterTemplate", campaign_id="cmp_p7", payload={"pack_id": "evo", "version": "1.1.0", "encounter_key": "evo:encounter/camp", "player_actor_id": "hero_p7", "enemy_actor_id": "enemy_p7", "encounter_id": "enc_p7"})
        for turn in range(30):
            encounter = (await client.get("/api/v1/encounters/enc_p7"))["data"]
            if encounter["status"] == "completed":
                break
            actions = (await client.get("/api/v1/actors/hero_p7/available-actions"))["data"]
            chosen = next((item for item in actions if item["action_id"] == "power_attack"), next((item for item in actions if item["action_id"] == "attack"), actions[0]))
            payload = {"encounter_id": "enc_p7", "action_id": chosen["action_id"]}
            if chosen.get("target_id"):
                payload["target_id"] = chosen["target_id"]
            await client.command("PerformAction", campaign_id="cmp_p7", actor_id="hero_p7", idempotency_key=f"p7-{turn}", payload=payload)
        assert (await client.get("/api/v1/encounters/enc_p7"))["data"]["status"] == "completed"
        assert (await client.get("/api/v1/campaigns/cmp_p7/replay-hash"))["matches_live"] is True
    finally:
        await client.close()
