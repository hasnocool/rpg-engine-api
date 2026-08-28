from rpg_engine_api.testing.coverage_manifest import load_feature_coverage, validate_feature_coverage


def test_feature_coverage_manifest_is_machine_validatable() -> None:
    value = load_feature_coverage()
    assert value["schema_version"] == "1.0"
    assert validate_feature_coverage(value) == []
