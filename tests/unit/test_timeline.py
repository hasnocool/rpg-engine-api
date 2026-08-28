from rpg_engine_api.domain.timeline import SimulationClock


def test_clock_orders_by_time_priority_then_sequence_without_sleeping() -> None:
    clock = SimulationClock()
    late = clock.schedule(10, "late")
    second = clock.schedule(5, "second", priority=20)
    first = clock.schedule(5, "first", priority=10)
    assert clock.advance_to(4) == ()
    assert clock.advance_to(5) == (first, second)
    assert clock.advance_to(10) == (late,)


def test_clock_pause_and_cancel() -> None:
    clock = SimulationClock()
    cancelled = clock.schedule(1, "cancelled")
    clock.cancel(cancelled.schedule_id)
    clock.pause()
    assert clock.advance_to(2) == ()
    clock.resume()
    assert clock.advance_to(2) == ()
