from rpg_engine_api.domain.commands import CommandReceipt, CommandStatus
from rpg_engine_api.infrastructure.metrics import RuntimeMetrics


def test_runtime_metrics_record_command_status_and_duration() -> None:
    metrics = RuntimeMetrics()
    metrics.record_command("CreateCampaign", CommandReceipt(command_id="c", status=CommandStatus.ACCEPTED), 0.25)
    snapshot = metrics.snapshot()
    assert snapshot["commands_total"] == 1
    assert snapshot["command_types"]["CreateCampaign"] == 1
    assert snapshot["command_statuses"]["accepted"] == 1
    assert snapshot["command_duration_seconds_max"] == 0.25
