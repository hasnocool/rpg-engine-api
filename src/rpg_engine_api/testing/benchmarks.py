from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rpg_engine_api.application.release_service import ReleaseEngineService
from rpg_engine_api.controllers.simple_npc import SimpleNpcController
from rpg_engine_api.domain.commands import CommandEnvelope, PrincipalContext
from rpg_engine_api.domain.events import DomainEvent
from rpg_engine_api.domain.timeline import SimulationClock
from rpg_engine_api.persistence.event_store import InMemoryEventStore

ROOT = Path(__file__).resolve().parents[3]

DEFAULT_BUDGETS = {
    "event_append_per_second_min": 200.0,
    "command_per_second_min": 20.0,
    "scheduler_items_per_second_min": 1000.0,
    "fanout_deliveries_per_second_min": 1000.0,
    "controller_decisions_per_second_min": 1000.0,
    "rebuild_seconds_max": 10.0,
}


def _rate(count: int, duration: float) -> float:
    return count / max(duration, 1e-9)


async def run_release_benchmarks(*, event_count: int = 1000, command_count: int = 100, scheduler_count: int = 5000, fanout_subscribers: int = 20, fanout_events: int = 100) -> dict[str, Any]:
    store = InMemoryEventStore()
    events = tuple(
        DomainEvent(event_type="BenchmarkEvent", campaign_id="bench", stream_id="bench:events", command_id=f"cmd-{index}", payload={"index": index})
        for index in range(event_count)
    )
    started = time.perf_counter()
    await store.append("bench:events", 0, events)
    event_duration = time.perf_counter() - started

    service = ReleaseEngineService(store=store)
    principal = PrincipalContext(principal_id="bench-owner", roles=frozenset({"owner"}))
    await service.execute(CommandEnvelope(command_type="CreateCampaign", payload={"campaign_id": "bench_campaign", "name": "Benchmark", "seed": 1}), principal, drive_controllers=False)
    started = time.perf_counter()
    for index in range(command_count):
        await service.execute(CommandEnvelope(command_type="CreateActor", campaign_id="bench_campaign", payload={"actor_id": f"bench_actor_{index}", "name": f"Actor {index}"}), principal, drive_controllers=False)
    command_duration = time.perf_counter() - started

    clock = SimulationClock()
    started = time.perf_counter()
    for index in range(scheduler_count):
        clock.schedule(index + 1, "bench", {"index": index})
    clock.advance_to(scheduler_count + 1)
    scheduler_duration = time.perf_counter() - started

    controller = SimpleNpcController(profile="aggressive_melee")
    view = {"available_actions": [{"action_id": "attack", "target_id": "target", "category": "attack"}, {"action_id": "guard"}], "self_hp_ratio": 1.0, "nearest_enemy_distance": 1, "lowest_ally_hp_ratio": 1.0}
    started = time.perf_counter()
    controller_iterations = 10_000
    for _ in range(controller_iterations):
        controller.choose_action(view)
    controller_duration = time.perf_counter() - started

    fanout_store = InMemoryEventStore()
    queues = [fanout_store.subscribe(maxsize=fanout_events + 1) for _ in range(fanout_subscribers)]
    fanout_batch = tuple(DomainEvent(event_type="Fanout", campaign_id="fanout", stream_id="fanout:events", command_id=f"fan-{index}") for index in range(fanout_events))
    started = time.perf_counter()
    await fanout_store.append("fanout:events", 0, fanout_batch)
    delivered = 0
    for queue in queues:
        while not queue.empty():
            queue.get_nowait()
            delivered += 1
    fanout_duration = time.perf_counter() - started

    rebuilt = ReleaseEngineService(store=store)
    started = time.perf_counter()
    await rebuilt.rebuild_from_store()
    rebuild_duration = time.perf_counter() - started

    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "workload": {"event_count": event_count, "command_count": command_count, "scheduler_count": scheduler_count, "fanout_subscribers": fanout_subscribers, "fanout_events": fanout_events},
        "metrics": {
            "event_append_per_second": _rate(event_count, event_duration),
            "command_per_second": _rate(command_count, command_duration),
            "scheduler_items_per_second": _rate(scheduler_count, scheduler_duration),
            "fanout_deliveries_per_second": _rate(delivered, fanout_duration),
            "controller_decisions_per_second": _rate(controller_iterations, controller_duration),
            "rebuild_seconds": rebuild_duration,
        },
        "budgets": DEFAULT_BUDGETS,
    }


def budget_failures(report: dict[str, Any]) -> list[str]:
    metrics = report["metrics"]
    budgets = report["budgets"]
    failures: list[str] = []
    for key, limit in budgets.items():
        metric = key.removesuffix("_min").removesuffix("_max")
        value = float(metrics[metric])
        if key.endswith("_min") and value < float(limit):
            failures.append(f"{metric}={value:.3f} below minimum {limit}")
        elif key.endswith("_max") and value > float(limit):
            failures.append(f"{metric}={value:.3f} above maximum {limit}")
    return failures


async def _main() -> int:
    report = await run_release_benchmarks()
    report["failures"] = budget_failures(report)
    output_dir = ROOT / "artifacts" / "performance"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"benchmark-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    print(f"artifact: {path.relative_to(ROOT)}")
    return 1 if report["failures"] else 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
