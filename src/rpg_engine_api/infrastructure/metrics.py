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

    def record_command(self, command_type: str, receipt: CommandReceipt, duration_seconds: float) -> None:
        self.command_total += 1
        self.command_types[command_type] += 1
        self.command_statuses[receipt.status.value] += 1
        if receipt.error is not None:
            self.error_codes[receipt.error.code.value] += 1
        self.command_duration_seconds_total += duration_seconds
        self.command_duration_seconds_max = max(self.command_duration_seconds_max, duration_seconds)

    def snapshot(self) -> dict[str, Any]:
        average = self.command_duration_seconds_total / self.command_total if self.command_total else 0.0
        return {
            "schema_version": "1.0",
            "uptime_seconds": max(0.0, time.monotonic() - self.started_at_monotonic),
            "commands_total": self.command_total,
            "command_statuses": dict(sorted(self.command_statuses.items())),
            "command_types": dict(sorted(self.command_types.items())),
            "error_codes": dict(sorted(self.error_codes.items())),
            "command_duration_seconds_total": self.command_duration_seconds_total,
            "command_duration_seconds_average": average,
            "command_duration_seconds_max": self.command_duration_seconds_max,
        }
