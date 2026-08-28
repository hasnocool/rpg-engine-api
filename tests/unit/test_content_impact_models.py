from rpg_engine_api.domain.content_evolution import CampaignImpactReport, ContentMigrationOperation, ContentMigrationPlan


def test_migration_plan_exposes_unresolved_and_reversibility() -> None:
    plan = ContentMigrationPlan(proposal_id="p", campaign_id="c", operations=[ContentMigrationOperation(operation="manual_resolution_required", source_ref="pack:item/old")], unresolved_keys=["pack:item/old"], executable_in_place=False, reversible=False)
    assert not plan.executable_in_place
    assert plan.unresolved_keys == ["pack:item/old"]


def test_impact_report_groups_runtime_paths() -> None:
    report = CampaignImpactReport(campaign_id="c", proposal_id="p", affected_keys=["pack:item/x"], matched_paths={"pack:item/x": ["actors.hero.inventory[0]"]}, affected_categories={"actors": ["pack:item/x"]})
    assert report.affected_categories["actors"] == ["pack:item/x"]
