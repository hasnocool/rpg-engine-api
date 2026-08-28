import base64
import json
from typing import Any

from fastapi import Request

_CURSOR_PREFIX = "rpg-events-v1"


def encode_event_cursor(sequence: int) -> str:
    payload = json.dumps({"v": _CURSOR_PREFIX, "s": max(0, int(sequence))}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def decode_event_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
        if payload.get("v") != _CURSOR_PREFIX:
            raise ValueError
        sequence = int(payload["s"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("invalid event cursor") from exc
    if sequence < 0:
        raise ValueError("invalid event cursor")
    return sequence


def api_response(request: Request, data: Any, **meta: Any) -> dict[str, Any]:
    return {
        "data": data,
        "meta": {
            "schema_version": "1.0",
            "request_id": getattr(request.state, "request_id", None),
            **meta,
        },
    }
