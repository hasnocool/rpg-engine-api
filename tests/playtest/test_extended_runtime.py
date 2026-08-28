import httpx
import pytest

from rpg_engine_api.app import create_app


async def _command(client: httpx.AsyncClient, command_type: str, *, campaign_id: str | None = None, actor_id: str | None = None, payload: dict[str, object] | None = None) -> dict[str, object]:
    response = await client.post("/api/v1/commands", headers={"X-Principal-Id": "player"}, json={"command_type": command_type, "campaign_id": campaign_id, "actor_id": actor_id, "payload": payload or {}})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"accepted", "already_processed"}, body
    return body


@pytest.mark.playtest
async def test_timed_character_dialogue_and_branch_flow() -> None:
    app = create_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        await _command(client, "CreateCampaign", payload={"campaign_id": "advanced", "name": "Advanced Testing Grounds", "seed": 7})
        await _command(client, "ConfigureCampaignTiming", campaign_id="advanced", payload={"mode": "timed_turn_based", "decision_duration": 5, "timeout_policy": "forfeit_turn"})

        creation = await _command(client, "StartCharacterCreation", campaign_id="advanced", payload={"creation_id": "hero_draft"})
        assert creation["result"]["creation_id"] == "hero_draft"
        await _command(client, "SelectCharacterName", campaign_id="advanced", payload={"creation_id": "hero_draft", "name": "Ari"})
        await _command(client, "SelectCharacterArchetype", campaign_id="advanced", payload={"creation_id": "hero_draft", "archetype": "guardian"})
        await _command(client, "SelectCharacterSpecies", campaign_id="advanced", payload={"creation_id": "hero_draft", "species": "dwarf"})
        await _command(client, "SelectCharacterBackground", campaign_id="advanced", payload={"creation_id": "hero_draft", "background": "artisan"})
        finalized = await _command(client, "FinalizeCharacterCreation", campaign_id="advanced", payload={"creation_id": "hero_draft", "actor_id": "hero"})
        assert finalized["result"]["species"] == "dwarf"
        actor = (await client.get("/api/v1/actors/hero")).json()["data"]
        assert actor["species"] == "dwarf"
        assert actor["background"] == "artisan"
        assert "craft_training" in actor["features"]

        await _command(client, "CreateActor", campaign_id="advanced", payload={"actor_id": "guide", "name": "Guide", "controller": {"controller_type": "simple_npc", "controller_version": "2", "behavior_profile_ref": "passive"}})
        dialogue_definition = {"id": "guide_intro", "start_node_id": "hello", "nodes": [{"id": "hello", "speaker_ref": "guide", "text_key": "guide.hello", "choices": [{"id": "continue", "label": "Continue", "next_node_id": "done", "consequence_tags": ["guide_met"]}]}, {"id": "done", "speaker_ref": "guide", "text_key": "guide.done", "terminal": True}]}
        await _command(client, "RegisterDialogue", campaign_id="advanced", payload={"definition": dialogue_definition})
        started = await _command(client, "StartDialogue", campaign_id="advanced", actor_id="hero", payload={"dialogue_id": "guide_intro", "npc_id": "guide"})
        dialogue_session_id = started["result"]["dialogue_session_id"]
        projection = (await client.get(f"/api/v1/dialogues/sessions/{dialogue_session_id}")).json()["data"]
        assert [choice["id"] for choice in projection["available_choices"]] == ["continue"]
        await _command(client, "ChooseDialogue", campaign_id="advanced", actor_id="hero", payload={"dialogue_session_id": dialogue_session_id, "choice_id": "continue"})

        await _command(client, "CreateCheckpoint", campaign_id="advanced", payload={"checkpoint_id": "before_forest", "name": "Before forest"})
        branched = await _command(client, "CreateCampaignBranch", campaign_id="advanced", payload={"checkpoint_id": "before_forest", "branch_id": "branch_one"})
        assert branched["result"]["branch"]["source_checkpoint_id"] == "before_forest"
        assert (await client.get("/api/v1/branches/branch_one")).status_code == 200


@pytest.mark.playtest
async def test_timed_turn_timeout_and_autonomous_enemy() -> None:
    app = create_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        await _command(client, "CreateCampaign", payload={"campaign_id": "timed", "seed": 4})
        await _command(client, "ConfigureCampaignTiming", campaign_id="timed", payload={"mode": "timed_turn_based", "decision_duration": 5, "timeout_policy": "forfeit_turn"})
        await _command(client, "CreateActor", campaign_id="timed", payload={"actor_id": "hero", "name": "Hero"})
        await _command(client, "CreateActor", campaign_id="timed", payload={"actor_id": "enemy", "name": "Archer", "controller": {"controller_type": "simple_npc", "controller_version": "2", "behavior_profile_ref": "ranged"}})
        await _command(client, "StartEncounter", campaign_id="timed", payload={"encounter_id": "duel", "participants": [{"actor_id": "hero", "side": "heroes", "position": 0}, {"actor_id": "enemy", "side": "enemies", "position": 3}]})
        timeline = (await client.get("/api/v1/campaigns/timed/timeline")).json()["data"]
        assert timeline["mode"] == "timed_turn_based"
        assert any(window["actor_id"] == "hero" and window["status"] == "open" for window in timeline["windows"])
        await _command(client, "AdvanceSimulationTime", campaign_id="timed", payload={"target_time": 5})
        events = (await client.get("/api/v1/campaigns/timed/events")).json()["data"]
        assert any(event["event_type"] == "TurnTimedOut" for event in events)
        encounter = (await client.get("/api/v1/encounters/duel")).json()["data"]
        assert encounter["status"] in {"active", "completed"}
