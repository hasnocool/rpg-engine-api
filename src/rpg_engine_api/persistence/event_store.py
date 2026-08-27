import asyncio
from collections.abc import Iterable

from rpg_engine_api.domain.commands import CommandReceipt
from rpg_engine_api.domain.events import DomainEvent


class StreamVersionConflict(Exception):
    def __init__(self, stream_id: str, expected: int, actual: int) -> None:
        super().__init__(f"stream {stream_id} expected version {expected}, actual {actual}")
        self.stream_id = stream_id
        self.expected = expected
        self.actual = actual


class InMemoryEventStore:
    """Async append-only test/runtime store with optimistic concurrency and subscriptions."""

    def __init__(self) -> None:
        self._events: list[DomainEvent] = []
        self._streams: dict[str, list[DomainEvent]] = {}
        self._receipts: dict[str, CommandReceipt] = {}
        self._lock = asyncio.Lock()
        self._subscribers: set[asyncio.Queue[DomainEvent]] = set()

    async def current_version(self, stream_id: str) -> int:
        return len(self._streams.get(stream_id, ()))

    async def append(
        self,
        stream_id: str,
        expected_version: int,
        events: Iterable[DomainEvent],
    ) -> tuple[DomainEvent, ...]:
        async with self._lock:
            stream = self._streams.setdefault(stream_id, [])
            actual = len(stream)
            if actual != expected_version:
                raise StreamVersionConflict(stream_id, expected_version, actual)
            stored: list[DomainEvent] = []
            for raw in events:
                version = len(stream) + 1
                sequence = len(self._events) + 1
                event = raw.model_copy(
                    update={"stream_id": stream_id, "stream_version": version, "sequence": sequence}
                )
                stream.append(event)
                self._events.append(event)
                stored.append(event)
            subscribers = tuple(self._subscribers)
        for event in stored:
            for queue in subscribers:
                queue.put_nowait(event)
        return tuple(stored)

    async def read_stream(self, stream_id: str) -> tuple[DomainEvent, ...]:
        return tuple(self._streams.get(stream_id, ()))

    async def read_all(self) -> tuple[DomainEvent, ...]:
        return tuple(self._events)

    async def get_receipt(self, key: str) -> CommandReceipt | None:
        return self._receipts.get(key)

    async def save_receipt(self, key: str, receipt: CommandReceipt) -> None:
        self._receipts[key] = receipt

    def subscribe(self, *, maxsize: int = 256) -> asyncio.Queue[DomainEvent]:
        queue: asyncio.Queue[DomainEvent] = asyncio.Queue(maxsize=maxsize)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[DomainEvent]) -> None:
        self._subscribers.discard(queue)
