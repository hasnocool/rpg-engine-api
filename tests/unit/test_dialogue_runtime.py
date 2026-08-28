import pytest

from rpg_engine_api.domain.dialogue import DialogueChoice, DialogueDefinition, DialogueNode, DialogueSession, DialogueSessionStatus
from rpg_engine_api.domain.requirements import RequirementExpr
from rpg_engine_api.rules.requirements_runtime import RequirementContext


def _definition() -> DialogueDefinition:
    return DialogueDefinition(
        id="merchant",
        start_node_id="hello",
        nodes=(
            DialogueNode(
                id="hello",
                speaker_ref="npc:merchant",
                text_key="hello",
                choices=(
                    DialogueChoice(id="ask_job", label="Any work?", next_node_id="quest", requirements=RequirementExpr(operator="level_at_least", operands=(2,))),
                    DialogueChoice(id="leave", label="Goodbye"),
                ),
            ),
            DialogueNode(id="quest", speaker_ref="npc:merchant", text_key="quest", terminal=True),
        ),
    )


def test_dialogue_filters_choices_from_requirement_context() -> None:
    session = DialogueSession(session_id="d1", dialogue_id="merchant", campaign_id="c", actor_id="a", npc_id="n", current_node_id="hello")
    definition = _definition()
    assert [choice.id for choice in session.available_choices(definition, RequirementContext(level=1))] == ["leave"]
    assert [choice.id for choice in session.available_choices(definition, RequirementContext(level=2))] == ["ask_job", "leave"]


def test_dialogue_choice_advances_and_completes() -> None:
    session = DialogueSession(session_id="d1", dialogue_id="merchant", campaign_id="c", actor_id="a", npc_id="n", current_node_id="hello")
    session.choose(_definition(), "ask_job", RequirementContext(level=2))
    assert session.status == DialogueSessionStatus.COMPLETED
    assert session.current_node_id == "quest"


def test_unavailable_dialogue_choice_is_rejected() -> None:
    session = DialogueSession(session_id="d1", dialogue_id="merchant", campaign_id="c", actor_id="a", npc_id="n", current_node_id="hello")
    with pytest.raises(ValueError):
        session.choose(_definition(), "ask_job", RequirementContext(level=1))
