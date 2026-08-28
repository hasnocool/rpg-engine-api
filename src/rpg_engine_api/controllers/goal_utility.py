from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rpg_engine_api.controllers.simple_npc import SimpleNpcController


@dataclass(frozen=True, slots=True)
class GoalAwareUtilityController:
    """Deterministic bounded utility scorer using only the visible decision view."""

    controller_type: str = "utility_ai"
    controller_version: str = "2"
    max_candidates: int = 64
    goal_match_bonus: int = 30
    memory_match_bonus: int = 8
    activity_match_bonus: int = 12

    def choose_action(self, decision_view: dict[str, object]) -> dict[str, object]:
        raw = [dict(item) for item in decision_view.get("available_actions", []) if isinstance(item, dict)]
        if not raw:
            raise ValueError("controller has no advertised legal actions")
        raw.sort(key=self._stable_key)
        actions = raw[: max(1, self.max_candidates)]
        goal_tags = {str(item) for item in decision_view.get("goal_tags", ())}
        memory_tags = {str(item) for item in decision_view.get("memory_tags", ())}
        activity = str(decision_view.get("current_activity", ""))
        hp_ratio = float(decision_view.get("self_hp_ratio", 1.0))
        distance = int(decision_view.get("nearest_enemy_distance", 0))
        ally_hp = float(decision_view.get("lowest_ally_hp_ratio", 1.0))

        ranked: list[tuple[int, tuple[str, str], dict[str, object]]] = []
        for action in actions:
            action_id = str(action.get("action_id", ""))
            category = str(action.get("category", ""))
            tags = {str(item) for item in action.get("tags", ()) if isinstance(item, str)}
            score = {"attack": 45, "movement": 20, "defense": 25, "support": 35}.get(category, 0)
            if action_id == "power_attack": score += 18
            if action_id == "ranged_attack": score += 12
            if action_id in {"heal_ally", "healing_prayer"} and ally_hp < 0.65: score += 60
            if hp_ratio < 0.3 and (action_id in {"retreat", "guard"} or "retreat" in tags): score += 70
            if distance > 1 and action_id == "move_toward": score += 30
            score += self.goal_match_bonus * len(tags & goal_tags)
            score += self.memory_match_bonus * len(tags & memory_tags)
            if activity and activity in tags: score += self.activity_match_bonus
            ranked.append((score, self._stable_key(action), action))
        if not ranked:
            return SimpleNpcController(profile="balanced").choose_action(decision_view)
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return ranked[0][2]

    @staticmethod
    def _stable_key(action: dict[str, Any]) -> tuple[str, str]:
        return str(action.get("action_id", "")), str(action.get("target_id", ""))
