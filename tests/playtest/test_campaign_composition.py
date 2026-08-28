import pytest

from .harness import Persona, PlaytestClient


@pytest.mark.playtest
@pytest.mark.asyncio
async def test_campaign_draft_invitation_party_vendor_faction_weather_and_journals() -> None:
    owner=Persona(name="DM",principal_id="owner"); player=Persona(name="Player",principal_id="player"); dm=PlaytestClient(owner)
    try:
        await dm.command("CreateCampaignDraft",payload={"draft_id":"draft_comp","campaign_id":"cmp_comp","name":"Composition Grounds","seed":909,"template_id":"fast_timed_turns"})
        result=await dm.command("ValidateCampaignDraft",payload={"draft_id":"draft_comp"}); assert result["result"]["valid"] is True
        await dm.command("FinalizeCampaignDraft",payload={"draft_id":"draft_comp"})
        await dm.command("CreateGameSession",campaign_id="cmp_comp",payload={"session_id":"session_comp"})
        invite=await dm.command("CreateSessionInvitation",campaign_id="cmp_comp",payload={"session_id":"session_comp","principal_id":"player"}); invitation_id=invite["result"]["invitation_id"]
        player_client=PlaytestClient(player,app=dm.app)
        await player_client.command("AcceptSessionInvitation",campaign_id="cmp_comp",payload={"session_id":"session_comp","invitation_id":invitation_id})
        await dm.command("CreateActor",campaign_id="cmp_comp",payload={"actor_id":"hero_comp","name":"Hero","currency":20,"controller":{"controller_type":"human"}})
        await dm.command("GrantActorControl",campaign_id="cmp_comp",payload={"session_id":"session_comp","actor_id":"hero_comp","principal_id":"player"})
        await dm.command("CreateParty",campaign_id="cmp_comp",payload={"party_id":"party_comp","name":"Heroes","member_actor_ids":["hero_comp"],"leader_actor_id":"hero_comp"})
        await dm.command("CreateVendor",campaign_id="cmp_comp",payload={"vendor_id":"vendor_comp","name":"Smith","stock":{"testing:item/rope":2},"prices":{"testing:item/rope":4},"currency":100})
        await player_client.command("BuyFromVendor",campaign_id="cmp_comp",actor_id="hero_comp",payload={"vendor_id":"vendor_comp","item_id":"testing:item/rope"})
        actor=(await player_client.get("/api/v1/actors/hero_comp"))["data"]; vendor=(await player_client.get("/api/v1/vendors/vendor_comp"))["data"]; assert actor["currency"]==16 and "testing:item/rope" in actor["inventory"] and vendor["stock"]["testing:item/rope"]==1
        await player_client.command("SellToVendor",campaign_id="cmp_comp",actor_id="hero_comp",payload={"vendor_id":"vendor_comp","item_id":"testing:item/rope"})
        await dm.command("CreateFaction",campaign_id="cmp_comp",payload={"faction_id":"town_comp","name":"Town Watch"}); await dm.command("ChangeFactionReputation",campaign_id="cmp_comp",payload={"faction_id":"town_comp","actor_id":"hero_comp","delta":10})
        await dm.command("ConfigureWorldEnvironment",campaign_id="cmp_comp",payload={"environment_id":"env_comp","day_length":60,"weather":"clear"}); await dm.command("ScheduleCampaignEvent",campaign_id="cmp_comp",payload={"delay":5,"kind":"weather_roll","event_payload":{"environment_id":"env_comp"}}); await dm.command("AdvanceSimulationTime",campaign_id="cmp_comp",payload={"delta":5})
        environment=(await player_client.get("/api/v1/environments/env_comp"))["data"]; assert environment["simulation_time"]==5 and environment["weather"] in {"storm","rain","fog","clear","wind"}
        journal=(await player_client.get("/api/v1/actors/hero_comp/journal"))["data"]; assert journal["actor_id"]=="hero_comp"
        await player_client.close()
    finally:
        await dm.close()
