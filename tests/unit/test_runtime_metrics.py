from rpg_engine_api.domain.commands import CommandReceipt, CommandStatus
from rpg_engine_api.infrastructure.metrics import RuntimeMetrics


def test_runtime_metrics_cover_release_subsystems() -> None:
    metrics = RuntimeMetrics()
    metrics.record_command("CreateCampaign", CommandReceipt(command_id="cmd", status=CommandStatus.ACCEPTED), 0.01)
    metrics.record_scheduler_events(2)
    metrics.record_controller_decision()
    metrics.record_simulation_runs(4)
    metrics.record_migration_dry_run(success=False)
    metrics.websocket_connected()
    metrics.websocket_resync()
    metrics.websocket_disconnected()
    metrics.record_operational_failure("audit")
    value = metrics.snapshot()
    assert value["commands_total"] == 1
    assert value["scheduler_events_total"] == 2
    assert value["controller_decisions_total"] == 1
    assert value["simulation_runs_total"] == 4
    assert value["migration_dry_run_failures"] == 1
    assert value["websocket_connections_current"] == 0
    assert value["websocket_resync_total"] == 1
    assert value["operational_failures"]["audit"] == 1
