import heapq
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from rpg_engine_api.domain.ids import new_id


class TimingMode(StrEnum):
    TURN_BASED = "turn_based"
    TIMED_TURN_BASED = "timed_turn_based"
    ACTIVE_TIME = "active_time"
    REAL_TIME_WITH_PAUSE = "real_time_with_pause"
    REAL_TIME = "real_time"
    HYBRID = "hybrid"


class TimeoutPolicy(StrEnum):
    FORFEIT_TURN = "forfeit_turn"
    AUTO_DEFEND = "auto_defend"
    AI_CONTROL = "ai_control"
    PAUSE_GAME = "pause_game"
    DM_DECIDES = "dm_decides"


class WindowKind(StrEnum):
    ACTION = "action"
    REACTION = "reaction"


class WindowStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class DecisionWindow(BaseModel):
    schema_version: str = "1.0"
    window_id: str
    actor_id: str
    kind: WindowKind
    opened_at: int
    deadline_at: int | None = None
    status: WindowStatus = WindowStatus.OPEN
    timeout_policy: TimeoutPolicy = TimeoutPolicy.FORFEIT_TURN
    context: dict[str, Any] = Field(default_factory=dict)


@dataclass(order=True, frozen=True, slots=True)
class ScheduledItem:
    simulation_time: int
    priority: int
    sequence: int
    schedule_id: str = field(compare=False)
    kind: str = field(compare=False)
    payload: dict[str, Any] = field(default_factory=dict, compare=False)


class SimulationClock:
    """Deterministic simulation clock and priority scheduler. It never sleeps."""

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
        schedule_id: str | None = None,
    ) -> ScheduledItem:
        if simulation_time < self.now:
            raise ValueError("cannot schedule in the simulation past")
        self._sequence += 1
        item = ScheduledItem(
            simulation_time=simulation_time,
            priority=priority,
            sequence=self._sequence,
            schedule_id=schedule_id or new_id("sch"),
            kind=kind,
            payload=dict(payload or {}),
        )
        heapq.heappush(self._heap, item)
        return item

    def schedule_after(self, delay: int, kind: str, payload: dict[str, Any] | None = None, *, priority: int = 100) -> ScheduledItem:
        if delay < 0:
            raise ValueError("delay must be non-negative")
        return self.schedule(self.now + delay, kind, payload, priority=priority)

    def cancel(self, schedule_id: str) -> bool:
        if not any(item.schedule_id == schedule_id for item in self._heap):
            return False
        self._cancelled.add(schedule_id)
        return True

    def reschedule(self, schedule_id: str, simulation_time: int) -> ScheduledItem:
        source = next((item for item in self._heap if item.schedule_id == schedule_id), None)
        if source is None or schedule_id in self._cancelled:
            raise KeyError(schedule_id)
        self._cancelled.add(schedule_id)
        return self.schedule(simulation_time, source.kind, source.payload, priority=source.priority)

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

    def advance_by(self, delta: int) -> tuple[ScheduledItem, ...]:
        if delta < 0:
            raise ValueError("delta must be non-negative")
        return self.advance_to(self.now + delta)

    def pending(self) -> tuple[ScheduledItem, ...]:
        return tuple(sorted(item for item in self._heap if item.schedule_id not in self._cancelled))

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False


class TimelineRuntime:
    """Mode-independent decision windows layered on a deterministic simulation clock."""

    def __init__(self, *, mode: TimingMode = TimingMode.TURN_BASED, start: int = 0, default_decision_duration: int | None = None, timeout_policy: TimeoutPolicy = TimeoutPolicy.FORFEIT_TURN) -> None:
        self.mode = mode
        self.clock = SimulationClock(start)
        self.default_decision_duration = default_decision_duration
        self.timeout_policy = timeout_policy
        self.windows: dict[str, DecisionWindow] = {}
        self.cooldowns: dict[tuple[str, str], int] = {}
        self._due_items: list[ScheduledItem] = []

    def open_window(self, actor_id: str, *, kind: WindowKind = WindowKind.ACTION, duration: int | None = None, timeout_policy: TimeoutPolicy | None = None, context: dict[str, Any] | None = None) -> DecisionWindow:
        resolved_duration = self.default_decision_duration if duration is None else duration
        if resolved_duration is not None and resolved_duration < 0:
            raise ValueError("decision duration must be non-negative")
        deadline = None if resolved_duration is None else self.clock.now + resolved_duration
        window = DecisionWindow(window_id=new_id("window"), actor_id=actor_id, kind=kind, opened_at=self.clock.now, deadline_at=deadline, timeout_policy=timeout_policy or self.timeout_policy, context=dict(context or {}))
        self.windows[window.window_id] = window
        self._schedule_window_deadline(window)
        return window

    def restore_window(self, window: DecisionWindow) -> DecisionWindow:
        self.windows[window.window_id] = window.model_copy(deep=True)
        self._schedule_window_deadline(self.windows[window.window_id])
        return self.windows[window.window_id]

    def _schedule_window_deadline(self, window: DecisionWindow) -> None:
        if window.status != WindowStatus.OPEN or window.deadline_at is None or window.deadline_at < self.clock.now:
            return
        self.clock.schedule(window.deadline_at, "decision_window_deadline", {"window_id": window.window_id}, priority=10 if window.kind == WindowKind.REACTION else 20)

    def resolve_window(self, window_id: str) -> DecisionWindow:
        window = self.windows[window_id]
        if window.status != WindowStatus.OPEN:
            raise ValueError("decision window is not open")
        window.status = WindowStatus.RESOLVED
        return window

    def cancel_window(self, window_id: str) -> DecisionWindow:
        window = self.windows[window_id]
        if window.status != WindowStatus.OPEN:
            raise ValueError("decision window is not open")
        window.status = WindowStatus.CANCELLED
        return window

    def advance_to(self, target: int) -> tuple[DecisionWindow, ...]:
        due = self.clock.advance_to(target)
        expired: list[DecisionWindow] = []
        for item in due:
            if item.kind == "decision_window_deadline":
                window = self.windows.get(str(item.payload["window_id"]))
                if window is not None and window.status == WindowStatus.OPEN:
                    window.status = WindowStatus.EXPIRED
                    expired.append(window)
            else:
                self._due_items.append(item)
        return tuple(expired)

    def consume_due_items(self) -> tuple[ScheduledItem, ...]:
        result = tuple(self._due_items)
        self._due_items.clear()
        return result

    def set_cooldown(self, actor_id: str, action_id: str, duration: int) -> int:
        if duration < 0:
            raise ValueError("cooldown duration must be non-negative")
        ready_at = self.clock.now + duration
        self.cooldowns[(actor_id, action_id)] = ready_at
        self.clock.schedule(ready_at, "cooldown_expired", {"actor_id": actor_id, "action_id": action_id}, priority=50)
        return ready_at

    def cooldown_remaining(self, actor_id: str, action_id: str) -> int:
        ready_at = self.cooldowns.get((actor_id, action_id), self.clock.now)
        return max(0, ready_at - self.clock.now)

    def is_action_ready(self, actor_id: str, action_id: str) -> bool:
        return self.cooldown_remaining(actor_id, action_id) == 0
