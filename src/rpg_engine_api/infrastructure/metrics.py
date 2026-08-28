import time
from collections import Counter
from typing import Any

from rpg_engine_api.domain.commands import CommandReceipt


class RuntimeMetrics:
    """Low-overhead process-local operational counters; never authoritative game state."""

    def __init__(self) -> None:
        self.started_at_monotonic = time.monotonic()
        self.command_total = 0
        self.command_statuses: Counter[str] = Counter()
        self.command_types: Counter[str] = Counter()
        self.error_codes: Counter[str] = Counter()
        self.command_duration_seconds_total = 0.0
        self.command_duration_seconds_max = 0.0
        self.scheduler_events_total = 0
        self.controller_decisions_total = 0
        self.simulation_runs_total = 0
        self.migration_dry_runs_total = 0
        self.migration_dry_run_failures = 0
        self.websocket_connections_total = 0
        self.websocket_connections_current = 0
        self.websocket_resync_total = 0
        self.operational_failures: Counter[str] = Counter()

    def record_command(self, command_type: str, receipt: CommandReceipt, duration_seconds: float) -> None:
        self.command_total += 1
        self.command_types[command_type] += 1
        self.command_statuses[receipt.status.value] += 1
        if receipt.error is not None:
            self.error_codes[receipt.error.code.value] += 1
        self.command_duration_seconds_total += duration_seconds
        self.command_duration_seconds_max = max(self.command_duration_seconds_max, duration_seconds)

    def record_scheduler_events(self, count: int) -> None:
        self.scheduler_events_total += max(0, int(count))

    def record_controller_decision(self) -> None:
        self.controller_decisions_total += 1

    def record_simulation_runs(self, count: int = 1) -> None:
        self.simulation_runs_total += max(0, int(count))

    def record_migration_dry_run(self, *, success: bool) -> None:
        self.migration_dry_runs_total += 1
        if not success:
            self.migration_dry_run_failures += 1

    def websocket_connected(self) -> None:
        self.websocket_connections_total += 1
        self.websocket_connections_current += 1

    def websocket_disconnected(self) -> None:
        self.websocket_connections_current = max(0, self.websocket_connections_current - 1)

    def websocket_resync(self) -> None:
        self.websocket_resync_total += 1

    def record_operational_failure(self, subsystem: str) -> None:
        self.operational_failures[subsystem] += 1

    def snapshot(self) -> dict[str, Any]:
        average = self.command_duration_seconds_total / self.command_total if self.command_total else 0.0
        return {
            "schema_version": "1.1",
            "uptime_seconds": max(0.0, time.monotonic() - self.started_at_monotonic),
            "commands_total": self.command_total,
            "command_statuses": dict(sorted(self.command_statuses.items())),
            "command_types": dict(sorted(self.command_types.items())),
            "error_codes": dict(sorted(self.error_codes.items())),
            "command_duration_seconds_total": self.command_duration_seconds_total,
            "command_duration_seconds_average": average,
            "command_duration_seconds_max": self.command_duration_seconds_max,
            "scheduler_events_total": self.scheduler_events_total,
            "controller_decisions_total": self.controller_decisions_total,
            "simulation_runs_total": self.simulation_runs_total,
            "migration_dry_runs_total": self.migration_dry_runs_total,
            "migration_dry_run_failures": self.migration_dry_run_failures,
            "websocket_connections_total": self.websocket_connections_total,
            "websocket_connections_current": self.websocket_connections_current,
            "websocket_resync_total": self.websocket_resync_total,
            "operational_failures": dict(sorted(self.operational_failures.items())),
        }
