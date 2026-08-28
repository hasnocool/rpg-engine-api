from rpg_engine_api.domain.character_creation import REFERENCE_BACKGROUNDS, REFERENCE_SPECIES, CharacterCreationSession, character_creation_schema


def test_character_schema_advertises_species_and_backgrounds() -> None:
    schema = character_creation_schema()
    steps = {step["id"]: step for step in schema["steps"]}
    assert {option["id"] for option in steps["species"]["options"]} == set(REFERENCE_SPECIES)
    assert {option["id"] for option in steps["background"]["options"]} == set(REFERENCE_BACKGROUNDS)


def test_legacy_minimal_draft_remains_finalizable() -> None:
    session = CharacterCreationSession(creation_id="c", campaign_id="cmp", principal_id="p", name="Hero", archetype="guardian")
    assert session.valid_for_finalize
