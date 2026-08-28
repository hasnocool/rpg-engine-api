from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class UtilityProfile:
    id: str
    category_weights: dict[str, int] = field(default_factory=dict)
    tag_weights: dict[str, int] = field(default_factory=dict)
    low_health_threshold: float = 0.3
    low_health_retreat_bonus: int = 75


DEFAULT_UTILITY_PROFILE = UtilityProfile(
    id="balanced_utility_v1",
    category_weights={"attack": 40, "movement": 20, "defense": 25, "support": 30},
    tag_weights={"high_damage": 15, "ranged": 8, "retreat": 5},
)


@dataclass(frozen=True, slots=True)
class UtilityController:
    """Deterministic utility scorer preserving the same available-action boundary."""

    profile: UtilityProfile = DEFAULT_UTILITY_PROFILE
    controller_type: str = "utility_ai"
    controller_version: str = "1"

    def choose_action(self, decision_view: dict[str, object]) -> dict[str, object]:
        raw = decision_view.get("available_actions", [])
        actions = [dict(item) for item in raw if isinstance(item, dict)]
        if not actions:
            raise ValueError("controller has no advertised legal actions")
        hp_ratio = float(decision_view.get("self_hp_ratio", 1.0))
        scored: list[tuple[int, tuple[str, str], dict[str, object]]] = []
        for action in actions:
            category = str(action.get("category", ""))
            tags = {str(tag) for tag in action.get("tags", ()) if isinstance(tag, str)}
            score = self.profile.category_weights.get(category, 0)
            score += sum(self.profile.tag_weights.get(tag, 0) for tag in tags)
            if hp_ratio <= self.profile.low_health_threshold and (
                "retreat" in tags or str(action.get("action_id")) in {"retreat", "flee"}
            ):
                score += self.profile.low_health_retreat_bonus
            stable = (str(action.get("action_id", "")), str(action.get("target_id", "")))
            scored.append((score, stable, action))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return scored[0][2]
