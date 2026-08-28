from rpg_engine_api.controllers.simple_npc import SimpleNpcController


def test_aggressive_prefers_power_attack() -> None:
    controller = SimpleNpcController(profile="aggressive_melee")
    action = controller.choose_action({"available_actions": [{"action_id": "guard"}, {"action_id": "attack"}, {"action_id": "power_attack"}]})
    assert action["action_id"] == "power_attack"


def test_ranged_retreats_when_enemy_is_close() -> None:
    controller = SimpleNpcController(profile="ranged")
    action = controller.choose_action({"nearest_enemy_distance": 1, "available_actions": [{"action_id": "attack"}, {"action_id": "retreat"}, {"action_id": "guard"}]})
    assert action["action_id"] == "retreat"


def test_support_heals_low_ally() -> None:
    controller = SimpleNpcController(profile="support")
    action = controller.choose_action({"lowest_ally_hp_ratio": 0.25, "available_actions": [{"action_id": "attack"}, {"action_id": "heal_ally"}]})
    assert action["action_id"] == "heal_ally"


def test_flee_profile_prefers_retreat() -> None:
    controller = SimpleNpcController(profile="flee")
    action = controller.choose_action({"available_actions": [{"action_id": "attack"}, {"action_id": "retreat"}]})
    assert action["action_id"] == "retreat"


def test_tie_breaking_is_stable() -> None:
    controller = SimpleNpcController(profile="balanced")
    action = controller.choose_action({"available_actions": [{"action_id": "attack", "target_id": "z"}, {"action_id": "attack", "target_id": "a"}]})
    assert action["target_id"] == "a"
