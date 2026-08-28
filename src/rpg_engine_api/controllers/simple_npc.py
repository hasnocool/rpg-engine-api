from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SimpleNpcController:
    """Deterministic shallow controller using only server-advertised legal actions."""

    controller_type: str = "simple_npc"
    controller_version: str = "2"
    profile: str = "aggressive_melee"

    def choose_action(self, decision_view: dict[str, object]) -> dict[str, object]:
        raw = decision_view.get("available_actions", [])
        actions = [dict(item) for item in raw if isinstance(item, dict)]
        if not actions:
            raise ValueError("controller has no advertised legal actions")
        context = {
            "self_hp_ratio": float(decision_view.get("self_hp_ratio", 1.0)),
            "nearest_enemy_distance": int(decision_view.get("nearest_enemy_distance", 0)),
            "lowest_ally_hp_ratio": float(decision_view.get("lowest_ally_hp_ratio", 1.0)),
        }
        ranked = sorted(
            actions,
            key=lambda action: (-self._score(action, context), self._stable_key(action)),
        )
        return ranked[0]

    @staticmethod
    def _stable_key(action: dict[str, Any]) -> tuple[str, str]:
        return (str(action.get("action_id", "")), str(action.get("target_id", "")))

    def _score(self, action: dict[str, Any], context: dict[str, float | int]) -> int:
        action_id = str(action.get("action_id", ""))
        tags = {str(item) for item in action.get("tags", ()) if isinstance(item, str)}
        category = str(action.get("category", ""))
        hp_ratio = float(context["self_hp_ratio"])
        ally_hp_ratio = float(context["lowest_ally_hp_ratio"])
        distance = int(context["nearest_enemy_distance"])

        score = 0
        if action_id == "wait":
            score = 1
        elif action_id in {"guard", "dodge"} or "defense" in tags:
            score = 20
        elif action_id in {"move_toward", "approach"} or "approach" in tags:
            score = 30
        elif action_id in {"retreat", "flee"} or "retreat" in tags:
            score = 25
        elif action_id in {"attack", "ranged_attack"} or category == "attack":
            score = 50
        elif action_id == "power_attack" or "high_damage" in tags:
            score = 60
        elif action_id in {"heal_ally", "help"} or "support" in tags:
            score = 45

        if self.profile == "aggressive_melee":
            if action_id == "power_attack":
                score += 50
            if action_id == "attack":
                score += 40
            if action_id in {"move_toward", "approach"}:
                score += 30
        elif self.profile == "ranged":
            if action_id == "ranged_attack" or "ranged" in tags:
                score += 70
            if distance <= 1 and action_id in {"retreat", "guard", "dodge"}:
                score += 55
            if distance > 2 and action_id in {"move_toward", "approach"}:
                score += 10
        elif self.profile in {"balanced", "defensive"}:
            if action_id in {"guard", "dodge"}:
                score += 45 if self.profile == "defensive" else 20
            if action_id in {"attack", "ranged_attack"}:
                score += 30
            if hp_ratio < 0.35 and action_id in {"retreat", "guard", "dodge"}:
                score += 60
        elif self.profile == "support":
            if ally_hp_ratio < 0.6 and action_id == "heal_ally":
                score += 100
            if action_id in {"help", "guard"}:
                score += 45
            if action_id in {"attack", "ranged_attack"}:
                score += 10
        elif self.profile == "passive":
            if action_id in {"wait", "guard", "retreat"}:
                score += 100
            if action_id in {"attack", "power_attack", "ranged_attack"}:
                score -= 100
        elif self.profile == "flee":
            if action_id in {"retreat", "flee"}:
                score += 150
            if action_id in {"guard", "dodge"}:
                score += 40
            if action_id in {"attack", "power_attack", "ranged_attack"}:
                score -= 50
        return score
