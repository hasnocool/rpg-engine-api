from rpg_engine_api.sdk.models import EventPage, SyncResult


def test_sdk_page_and_sync_models_are_stable() -> None:
    page = EventPage(events=[{"sequence": 1}], next_cursor="abc", has_more=True, current_sequence=4)
    assert page.events[0]["sequence"] == 1
    sync = SyncResult(mode="delta", current_sequence=4, events=[{"sequence": 4}])
    assert sync.snapshot is None
    assert sync.events[0]["sequence"] == 4
