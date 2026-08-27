from rpg_engine_api.testing.evidence import EnvironmentEvidence, TestEvidenceBundle


def test_evidence_bundle_round_trip() -> None:
    bundle = TestEvidenceBundle(
        evidence_id="example",
        repository="hasnocool/rpg-engine-api",
        commit_sha="abc123",
        dirty_worktree=False,
        test_profile="smoke",
        environment=EnvironmentEvidence(
            os="test",
            architecture="x86_64",
            python="3.12",
            dependency_fingerprint="deadbeef",
            config_fingerprint="cafebabe",
        ),
    )
    assert TestEvidenceBundle.model_validate_json(bundle.model_dump_json()) == bundle
