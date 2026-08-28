from rpg_engine_api.controllers.goal_utility import GoalAwareUtilityController
from rpg_engine_api.domain.controller_mind import ControllerGoal, ControllerMemory, ControllerMindState


def test_bounded_mind_and_goal_aware_scoring_are_deterministic() -> None:
    mind = ControllerMindState(actor_id="npc", campaign_id="cmp", max_memories=2, goals={"protect": ControllerGoal(goal_id="protect", description="protect allies", desired_tags=("support",), priority=80)}, memories=[ControllerMemory(memory_id="m1", summary="ally hurt", tags=("support",), observed_sequence=1)])
    view = {"available_actions": [{"action_id":"attack","category":"attack","tags":[]},{"action_id":"heal_ally","category":"support","tags":["support"],"target_id":"ally"}],"goal_tags":mind.active_goal_tags(),"memory_tags":mind.memory_tags(),"self_hp_ratio":1.0,"lowest_ally_hp_ratio":0.5}
    first = GoalAwareUtilityController().choose_action(view); second = GoalAwareUtilityController().choose_action(view)
    assert first == second
    assert first["action_id"] == "heal_ally"
