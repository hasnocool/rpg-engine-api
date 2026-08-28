import pytest

from rpg_engine_api.api.contracts import decode_event_cursor, encode_event_cursor


def test_event_cursor_round_trip() -> None:
    cursor = encode_event_cursor(12345)
    assert decode_event_cursor(cursor) == 12345
    assert "12345" not in cursor


def test_event_cursor_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        decode_event_cursor("not-a-valid-cursor")
