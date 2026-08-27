import pytest

from rpg_engine_api.domain.commands import CommandStatus

from .harness import Persona, PlaytestClient


@pytest.mark.playtest
@pytest.mark.asyncio
async def test_human_can_finish_encounter_against_autonomous_npc() -> None:
    client = PlaytestClient(Persona(name="Human", principal_id="human"))
    try:
        assert (await client.get("/health"))["status"] == "ok"
        await client.command(
            "CreateCampaign",
            payload={"campaign_id": "cmp_p2", "name": "Testing Grounds", "seed": 2026},
        )
        await client.command(
            "CreateActor",
            campaign_id="cmp_p2",
            payload={
                "actor_id": "act_hero",
                "name": "Hero",
                "max_hp": 24,
                "attack_bonus": 8,
                "defense": 14,
                "controller": {"controller_type": "human", "controller_version": "1"},
            },
        )
        await client.command(
            "CreateActor",
            campaign_id="cmp_p2",
            payload={
                "actor_id": "act_goblin",
                "name": "Goblin",
                "max_hp": 8,
                "attack_bonus": 1,
                "defense": 10,
                "controller": {
                    "controller_type": "simple_npc",
                    "controller_version": "1",
                    "behavior_profile_ref": "aggressive_melee",
                },
            },
        )
        started = await client.command(
            "StartEncounter",
            campaign_id="cmp_p2",
            payload={
                "encounter_id": "enc_p2",
                "participants": [
                    {"actor_id": "act_hero", "side": "heroes", "position": 0},
                    {"actor_id": "act_goblin", "side": "enemies", "position": 3},
                ],
            },
        )
        assert started["status"] == CommandStatus.ACCEPTED

        for turn in range(30):
            encounter = (await client.get("/api/v1/encounters/enc_p2"))["data"]
            if encounter["status"] == "completed":
                break
            assert encounter["current_actor_id"] == "act_hero"
            actions = (await client.get("/api/v1/actors/act_hero/available-actions"))["data"]
            preferred = next(
                (item for item in actions if item["action_id"] == "power_attack"),
                next((item for item in actions if item["action_id"] == "attack"), actions[0]),
            )
            payload = {"encounter_id": "enc_p2", "action_id": preferred["action_id"]}
            if preferred.get("target_id"):
                payload["target_id"] = preferred["target_id"]
            receipt = await client.command(
                "PerformAction",
                campaign_id="cmp_p2",
                actor_id="act_hero",
                idempotency_key=f"human-turn-{turn}",
                payload=payload,
            )
            assert receipt["status"] == "accepted"
        else:
            pytest.fail("encounter did not complete within safety turn limit")

        final = (await client.get("/api/v1/encounters/enc_p2"))["data"]
        assert final["status"] == "completed"
        assert final["winner_side"] == "heroes"
        hashes = await client.get("/api/v1/campaigns/cmp_p2/replay-hash")
        assert hashes["matches_live"] == "true"
        events = (await client.get("/api/v1/campaigns/cmp_p2/events"))["data"]
        assert any(event["event_type"] == "AttackResolved" or event["event_type"] == "PowerAttackResolved" for event in events)
        assert any(event["actor_id"] == "act_goblin" and event["event_type"] in {"ActorMoved", "AttackResolved", "PowerAttackResolved", "GuardRaised"} for event in events)
    finally:
        await client.close()
