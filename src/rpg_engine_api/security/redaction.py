from __future__ import annotations

from typing import Any

SENSITIVE_FRAGMENTS = (
    "authorization",
    "cookie",
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
)


def is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(fragment in normalized for fragment in SENSITIVE_FRAGMENTS)


def redact(value: Any, *, max_string: int = 512) -> Any:
    """Return a JSON-safe redacted copy suitable for audit/evidence/log payloads."""
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if is_sensitive_key(str(key)) else redact(child, max_string=max_string)
            for key, child in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [redact(child, max_string=max_string) for child in value]
    if isinstance(value, str):
        return value if len(value) <= max_string else value[:max_string] + "...[TRUNCATED]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact(str(value), max_string=max_string)
