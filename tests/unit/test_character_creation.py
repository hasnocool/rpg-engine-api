from rpg_engine_api.domain.character_creation import REFERENCE_ARCHETYPES, character_creation_schema


def test_reference_character_creation_schema_is_discoverable() -> None:
    schema = character_creation_schema()
    assert schema["schema_version"] == "1.0"
    assert {option["id"] for step in schema["steps"] if step["id"] == "archetype" for option in step["options"]} == set(REFERENCE_ARCHETYPES)
