from rpg_engine_api.controllers.simple_npc import SimpleNpcController


def test_aggressive_npc_prefers_power_attack_then_attack() -> None:
    controller = SimpleNpcController(profile="aggressive_melee")
    chosen = controller.choose_action(
        {"available_actions": [{"action_id": "guard"}, {"action_id": "attack"}, {"action_id": "power_attack"}]}
    )
    assert chosen["action_id"] == "power_attack"


def test_npc_uses_only_advertised_actions() -> None:
    controller = SimpleNpcController()
    chosen = controller.choose_action({"available_actions": [{"action_id": "move_toward", "target_id": "hero"}]})
    assert chosen == {"action_id": "move_toward", "target_id": "hero"}
