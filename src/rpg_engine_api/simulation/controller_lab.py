from __future__ import annotations

from collections import Counter
from typing import Any

from rpg_engine_api.application.production_release_service import ProductionReleaseEngineService
from rpg_engine_api.domain.commands import CommandEnvelope, PrincipalContext


async def run_controller_match(seed: int, left: str, right: str) -> dict[str, Any]:
    engine = ProductionReleaseEngineService(); principal = PrincipalContext(principal_id="lab", roles=frozenset({"owner"}))
    campaign_id = f"lab_{seed}_{left}_{right}"; await engine.execute(CommandEnvelope(command_type="CreateCampaign", payload={"campaign_id": campaign_id, "seed": seed}), principal)
    for actor_id, controller in (("left", left), ("right", right)):
        await engine.execute(CommandEnvelope(command_type="CreateActor", campaign_id=campaign_id, payload={"actor_id": actor_id, "name": actor_id, "max_hp": 14, "attack_bonus": 4, "defense": 10, "controller": {"controller_type": controller, "controller_version": "2"}}), principal)
    await engine.execute(CommandEnvelope(command_type="StartEncounter", campaign_id=campaign_id, payload={"encounter_id": "match", "participants": [{"actor_id": "left", "side": "left", "position": 0}, {"actor_id": "right", "side": "right", "position": 2}]}), principal)
    encounter = engine.encounters["match"]; events = [event for event in await engine.store.read_all() if event.campaign_id == campaign_id]
    return {"seed": seed, "left": left, "right": right, "winner": encounter.winner_side, "rounds": encounter.round, "event_count": len(events), "replay_matches_live": await engine.canonical_hash(campaign_id) == engine.live_hash(campaign_id)}


async def run_controller_quality_lab(seeds: list[int] | tuple[int, ...], controller_a: str = "simple_npc", controller_b: str = "utility_ai") -> dict[str, Any]:
    wins: Counter[str] = Counter(); matches: list[dict[str, Any]] = []
    for seed in seeds:
        for left, right in ((controller_a, controller_b), (controller_b, controller_a)):
            match = await run_controller_match(int(seed), left, right); matches.append(match)
            if match["winner"] == "left": wins[left] += 1
            elif match["winner"] == "right": wins[right] += 1
            else: wins["draw"] += 1
    return {"schema_version": "1.0", "controllers": [controller_a, controller_b], "seeds": [int(seed) for seed in seeds], "matched_role_swaps": True, "wins": dict(sorted(wins.items())), "matches": matches, "all_replayable": all(bool(item["replay_matches_live"]) for item in matches)}
