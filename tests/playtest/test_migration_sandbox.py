import pytest

from .harness import Persona, PlaytestClient


async def publish(client: PlaytestClient, workspace: str, version: str, hp: int) -> None:
    await client.command("CreateAuthoringWorkspace", payload={"workspace_id": workspace, "namespace": "sandbox"})
    await client.command("UpsertDraftDefinition", payload={"workspace_id": workspace, "draft_id": "npc", "definition_type": "npc_template", "key": "sandbox:npc/raider", "source": {"license_id": "CC0-1.0"}, "data": {"name": "Raider", "max_hp": hp, "attack_bonus": 1, "defense": 9}})
    await client.command("UpsertDraftDefinition", payload={"workspace_id": workspace, "draft_id": "enc", "definition_type": "encounter_template", "key": "sandbox:encounter/camp", "source": {"license_id": "CC0-1.0"}, "data": {"enemy_ref": "sandbox:npc/raider"}})
    await client.command("ValidateAuthoringWorkspace", payload={"workspace_id": workspace})
    await client.command("PublishAuthoringWorkspace", payload={"workspace_id": workspace, "version": version})


@pytest.mark.playtest
@pytest.mark.asyncio
async def test_content_revision_dry_run_uses_isolated_replayable_sandbox() -> None:
    client = PlaytestClient(Persona(name="Creator", principal_id="creator", role="owner"))
    try:
        await publish(client, "sandbox_ws1", "1.0.0", 6)
        await publish(client, "sandbox_ws2", "1.1.0", 8)
        await client.command("CreateCampaign", payload={"campaign_id": "cmp_sandbox", "name": "Sandbox", "seed": 11})
        await client.command("BindCampaignContent", campaign_id="cmp_sandbox", payload={"pack_id": "sandbox", "version": "1.0.0"})
        await client.command("ProposeContentRevision", campaign_id="cmp_sandbox", payload={"proposal_id": "sandbox_rev", "to_version": "1.1.0"})
        dry = await client.command("DryRunContentRevision", campaign_id="cmp_sandbox", payload={"proposal_id": "sandbox_rev"})
        sandbox = dry["result"]["sandbox_report"]
        assert sandbox["isolated"] is True
        assert sandbox["target_quality"]["valid"] is True
        assert sandbox["compatible"] is True
        assert sandbox["activation_status"] == "accepted"
        assert sandbox["target_binding_version"] == "1.1.0"
        assert sandbox["pre_replay_matches_live"] is True
        assert sandbox["post_replay_matches_live"] is True
        live_binding = (await client.get("/api/v1/campaigns/cmp_sandbox/content-binding"))["data"]
        assert live_binding["version"] == "1.0.0"
    finally:
        await client.close()
