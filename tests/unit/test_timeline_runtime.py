import pytest

from rpg_engine_api.domain.timeline import (
    SimulationClock,
    TimelineRuntime,
    TimeoutPolicy,
    TimingMode,
    WindowKind,
    WindowStatus,
)


def test_clock_orders_by_time_priority_and_sequence() -> None:
    clock = SimulationClock()
    later = clock.schedule(5, "later")
    second = clock.schedule(3, "second", priority=20)
    first = clock.schedule(3, "first", priority=10)

    assert clock.advance_to(2) == ()
    assert clock.advance_to(3) == (first, second)
    assert clock.advance_to(5) == (later,)


def test_clock_cancel_and_reschedule() -> None:
    clock = SimulationClock()
    original = clock.schedule(10, "cooldown")
    replacement = clock.reschedule(original.schedule_id, 4)

    assert replacement.schedule_id != original.schedule_id
    assert clock.advance_to(4) == (replacement,)
    assert clock.advance_to(10) == ()


def test_timed_window_expires_exactly_at_deadline() -> None:
    timeline = TimelineRuntime(
        mode=TimingMode.TIMED_TURN_BASED,
        default_decision_duration=15,
        timeout_policy=TimeoutPolicy.FORFEIT_TURN,
    )
    window = timeline.open_window("hero")

    assert timeline.advance_to(14) == ()
    assert window.status == WindowStatus.OPEN
    expired = timeline.advance_to(15)
    assert expired == (window,)
    assert window.status == WindowStatus.EXPIRED


def test_reaction_window_gets_independent_deadline() -> None:
    timeline = TimelineRuntime(mode=TimingMode.REAL_TIME_WITH_PAUSE)
    reaction = timeline.open_window("hero", kind=WindowKind.REACTION, duration=2)
    action = timeline.open_window("enemy", duration=5)

    assert timeline.advance_to(2) == (reaction,)
    assert action.status == WindowStatus.OPEN


def test_pause_prevents_time_advancement_until_resume() -> None:
    timeline = TimelineRuntime(default_decision_duration=5)
    timeline.open_window("hero")
    timeline.clock.pause()
    assert timeline.advance_to(5) == ()
    assert timeline.clock.now == 0
    timeline.clock.resume()
    assert len(timeline.advance_to(5)) == 1


def test_cooldown_is_deterministic() -> None:
    timeline = TimelineRuntime(start=10)
    assert timeline.set_cooldown("hero", "dash", 5) == 15
    assert timeline.cooldown_remaining("hero", "dash") == 5
    timeline.advance_to(14)
    assert not timeline.is_action_ready("hero", "dash")
    timeline.advance_to(15)
    assert timeline.is_action_ready("hero", "dash")


def test_cannot_move_clock_backwards() -> None:
    clock = SimulationClock(start=5)
    with pytest.raises(ValueError):
        clock.advance_to(4)
