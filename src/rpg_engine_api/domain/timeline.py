import heapq
from dataclasses import dataclass, field
from typing import Any

from rpg_engine_api.domain.ids import new_id


@dataclass(order=True, frozen=True, slots=True)
class ScheduledItem:
    simulation_time: int
    priority: int
    sequence: int
    schedule_id: str = field(compare=False)
    kind: str = field(compare=False)
    payload: dict[str, Any] = field(default_factory=dict, compare=False)


class SimulationClock:
    """Deterministic testable simulation clock. It never sleeps."""

    def __init__(self, start: int = 0) -> None:
        self.now = start
        self._sequence = 0
        self._heap: list[ScheduledItem] = []
        self._cancelled: set[str] = set()
        self.paused = False

    def schedule(
        self,
        simulation_time: int,
        kind: str,
        payload: dict[str, Any] | None = None,
        *,
        priority: int = 100,
    ) -> ScheduledItem:
        if simulation_time < self.now:
            raise ValueError("cannot schedule in the simulation past")
        self._sequence += 1
        item = ScheduledItem(
            simulation_time=simulation_time,
            priority=priority,
            sequence=self._sequence,
            schedule_id=new_id("sch"),
            kind=kind,
            payload=payload or {},
        )
        heapq.heappush(self._heap, item)
        return item

    def cancel(self, schedule_id: str) -> None:
        self._cancelled.add(schedule_id)

    def advance_to(self, target: int) -> tuple[ScheduledItem, ...]:
        if target < self.now:
            raise ValueError("simulation time cannot move backward")
        if self.paused:
            return ()
        self.now = target
        due: list[ScheduledItem] = []
        while self._heap and self._heap[0].simulation_time <= target:
            item = heapq.heappop(self._heap)
            if item.schedule_id not in self._cancelled:
                due.append(item)
        return tuple(due)

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False
