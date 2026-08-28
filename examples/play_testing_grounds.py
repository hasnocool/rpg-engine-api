"""Tiny terminal P2 client for a locally running server.

Run the API first, then:
    python examples/play_testing_grounds.py
"""
import asyncio
from uuid import uuid4

import httpx

BASE = "http://127.0.0.1:8000"


async def command(client: httpx.AsyncClient, command_type: str, **kwargs: object) -> dict[str, object]:
    response = await client.post(f"{BASE}/api/v1/commands", json={"command_type": command_type, **kwargs})
    response.raise_for_status()
    payload = response.json()
    if payload["status"] not in {"accepted", "already_processed"}:
        raise RuntimeError(payload)
    return payload


async def main() -> None:
    suffix = uuid4().hex[:8]
    campaign_id = f"cmp_demo_{suffix}"
    hero_id = f"hero_{suffix}"
    npc_id = f"goblin_{suffix}"
    encounter_id = f"enc_{suffix}"
    async with httpx.AsyncClient() as client:
        print("health:", (await client.get(f"{BASE}/health")).json())
        await command(client, "CreateCampaign", payload={"campaign_id": campaign_id, "name": "Testing Grounds", "seed": 2026})
        await command(client, "CreateActor", campaign_id=campaign_id, payload={"actor_id": hero_id, "name": "Hero", "max_hp": 24, "attack_bonus": 8, "defense": 14, "controller": {"controller_type": "human", "controller_version": "1"}})
        await command(client, "CreateActor", campaign_id=campaign_id, payload={"actor_id": npc_id, "name": "Goblin", "max_hp": 8, "attack_bonus": 1, "defense": 10, "controller": {"controller_type": "simple_npc", "controller_version": "1", "behavior_profile_ref": "aggressive_melee"}})
        await command(client, "StartEncounter", campaign_id=campaign_id, payload={"encounter_id": encounter_id, "participants": [{"actor_id": hero_id, "side": "heroes", "position": 0}, {"actor_id": npc_id, "side": "enemies", "position": 3}]})
        turn = 0
        while True:
            state = (await client.get(f"{BASE}/api/v1/encounters/{encounter_id}")).json()["data"]
            hero = state["participants"][hero_id]
            goblin = state["participants"][npc_id]
            print(f"round {state['round']}: hero hp={hero['hp']} goblin hp={goblin['hp']}")
            if state["status"] == "completed":
                print("winner:", state["winner_side"])
                break
            actions = (await client.get(f"{BASE}/api/v1/actors/{hero_id}/available-actions")).json()["data"]
            print("available:", [item["action_id"] for item in actions])
            chosen = next((item for item in actions if item["action_id"] == "power_attack"), next((item for item in actions if item["action_id"] == "attack"), actions[0]))
            payload: dict[str, object] = {"encounter_id": encounter_id, "action_id": chosen["action_id"]}
            if chosen.get("target_id"):
                payload["target_id"] = chosen["target_id"]
            await command(client, "PerformAction", campaign_id=campaign_id, actor_id=hero_id, idempotency_key=f"demo-{suffix}-{turn}", payload=payload)
            turn += 1
        hashes = (await client.get(f"{BASE}/api/v1/campaigns/{campaign_id}/replay-hash")).json()
        print("replay matches live:", hashes["matches_live"])


if __name__ == "__main__":
    asyncio.run(main())
