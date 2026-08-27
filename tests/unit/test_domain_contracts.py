import pytest

from rpg_engine_api.domain.choices import ChoiceGroup, ChoiceOption
from rpg_engine_api.domain.controllers import ControllerAssignment, ControllerType
from rpg_engine_api.domain.definitions import DefinitionRef
from rpg_engine_api.domain.ids import validate_content_key


def test_namespaced_content_key_and_definition_round_trip() -> None:
    assert validate_content_key("srd_5_2_1:class/fighter") == "srd_5_2_1:class/fighter"
    ref = DefinitionRef(
        pack_id="srd_5_2_1",
        pack_version="1.0.0",
        key="srd_5_2_1:class/fighter",
        content_hash="12345678abcdef",
    )
    assert DefinitionRef.model_validate_json(ref.model_dump_json()) == ref


def test_invalid_content_key_is_rejected() -> None:
    with pytest.raises(ValueError):
        validate_content_key("Not Namespaced")


def test_choice_bounds_are_validated() -> None:
    with pytest.raises(ValueError):
        ChoiceGroup(id="bad", min_choices=2, max_choices=1)
    good = ChoiceGroup(id="one", options=(ChoiceOption(id="a", value="a"),))
    assert good.max_choices == 1


def test_controller_assignment_is_versioned() -> None:
    assignment = ControllerAssignment(controller_type=ControllerType.SIMPLE_NPC)
    assert assignment.controller_version == "1"
    assert assignment.schema_version == "1.0"
