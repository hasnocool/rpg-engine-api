from rpg_engine_api.application.full_service import FullEngineService
from rpg_engine_api.domain.authoring import AuthoringWorkspace, DraftDefinition


def test_authoring_validator_catches_missing_license_and_reference() -> None:
    service = FullEngineService()
    workspace = AuthoringWorkspace(workspace_id="w", namespace="demo", owner_id="owner")
    workspace.drafts["e"] = DraftDefinition(draft_id="e", definition_type="encounter_template", key="demo:encounter/test", data={"enemy_ref": "demo:npc/missing"})
    report = service._quality_report(workspace)
    codes = {issue.code for issue in report.issues}
    assert "missing_license" in codes
    assert "unknown_reference" in codes
    assert report.valid is False
