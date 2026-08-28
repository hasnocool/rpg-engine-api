import pytest

from rpg_engine_api.application.command_bus import EngineService
from rpg_engine_api.domain.commands import CommandEnvelope, PrincipalContext


@pytest.mark.simulation
@pytest.mark.asyncio
async def test_ai_vs_ai_encounter_completes_deterministically() -> None:
    engine = EngineService()
    principal = PrincipalContext(principal_id="simulation")
    await engine.execute(CommandEnvelope(command_type="CreateCampaign", payload={"campaign_id": "cmp_ai", "seed": 77}), principal)
    for actor_id in ("npc_a", "npc_b"):
        await engine.execute(
            CommandEnvelope(
                command_type="CreateActor",
                campaign_id="cmp_ai",
                payload={
                    "actor_id": actor_id,
                    "name": actor_id,
                    "max_hp": 10,
                    "attack_bonus": 4,
                    "defense": 10,
                    "controller": {"controller_type": "simple_npc", "controller_version": "1", "behavior_profile_ref": "aggressive_melee"},
                },
            ),
            principal,
        )
    receipt = await engine.execute(
        CommandEnvelope(
            command_type="StartEncounter",
            campaign_id="cmp_ai",
            payload={
                "encounter_id": "enc_ai",
                "participants": [
                    {"actor_id": "npc_a", "side": "a", "position": 0},
                    {"actor_id": "npc_b", "side": "b", "position": 2},
                ],
            },
        ),
        principal,
    )
    assert receipt.status.value == "accepted"
    assert engine.encounters["enc_ai"].status.value == "completed"
    assert engine.encounters["enc_ai"].winner_side in {"a", "b"}
    assert await engine.canonical_hash("cmp_ai") == engine.live_hash("cmp_ai")
