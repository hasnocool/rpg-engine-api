from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SimpleNpcController:
    """Deterministic shallow controller using only server-advertised legal actions."""

    controller_type: str = "simple_npc"
    controller_version: str = "1"
    profile: str = "aggressive_melee"

    def choose_action(self, decision_view: dict[str, object]) -> dict[str, object]:
        raw = decision_view.get("available_actions", [])
        actions = [dict(item) for item in raw if isinstance(item, dict)]
        if not actions:
            raise ValueError("controller has no advertised legal actions")
        by_id = {str(action["action_id"]): action for action in actions}
        priorities: tuple[str, ...]
        if self.profile == "passive":
            priorities = ("guard", "move_toward", "attack", "power_attack")
        elif self.profile == "defensive":
            priorities = ("guard", "attack", "move_toward", "power_attack")
        elif self.profile == "flee":
            priorities = ("guard", "move_toward", "attack", "power_attack")
        else:
            priorities = ("power_attack", "attack", "move_toward", "guard")
        for action_id in priorities:
            if action_id in by_id:
                return by_id[action_id]
        return sorted(actions, key=lambda item: str(item["action_id"]))[0]
