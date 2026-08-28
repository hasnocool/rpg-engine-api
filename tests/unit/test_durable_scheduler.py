from rpg_engine_api.domain.timeline import TimelineRuntime


def test_generic_scheduled_items_survive_timeline_processing_boundary() -> None:
    timeline = TimelineRuntime(start=5)
    item = timeline.clock.schedule(10, "world_event", {"flag": "storm"}, schedule_id="sch_test")
    assert item.schedule_id == "sch_test"
    assert timeline.advance_to(10) == ()
    due = timeline.consume_due_items()
    assert len(due) == 1
    assert due[0].kind == "world_event"
    assert due[0].payload == {"flag": "storm"}
