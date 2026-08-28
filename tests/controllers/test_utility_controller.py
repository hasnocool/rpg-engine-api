from rpg_engine_api.controllers.utility import UtilityController, UtilityProfile


def test_utility_controller_scores_tags_and_categories() -> None:
    controller = UtilityController(profile=UtilityProfile(id="test", category_weights={"attack": 10, "defense": 20}, tag_weights={"high_damage": 20}))
    action = controller.choose_action({"available_actions": [{"action_id": "guard", "category": "defense"}, {"action_id": "strike", "category": "attack", "tags": ["high_damage"]}]})
    assert action["action_id"] == "strike"


def test_utility_controller_retreats_at_low_health() -> None:
    controller = UtilityController()
    action = controller.choose_action({"self_hp_ratio": 0.2, "available_actions": [{"action_id": "attack", "category": "attack"}, {"action_id": "retreat", "category": "movement", "tags": ["retreat"]}]})
    assert action["action_id"] == "retreat"
