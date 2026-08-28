import asyncio
import time
from collections import defaultdict, deque


class SlidingWindowRateLimiter:
    """Process-local abuse-control seam suitable for local/single-process deployments."""

    def __init__(self, limit: int, *, window_seconds: float = 60.0) -> None:
        if limit < 0:
            raise ValueError("limit cannot be negative")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self._entries: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, key: str, *, now: float | None = None) -> bool:
        if self.limit == 0:
            return True
        moment = time.monotonic() if now is None else now
        cutoff = moment - self.window_seconds
        async with self._lock:
            values = self._entries[key]
            while values and values[0] <= cutoff:
                values.popleft()
            if len(values) >= self.limit:
                return False
            values.append(moment)
            return True
