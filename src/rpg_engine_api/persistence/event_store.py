import asyncio
import copy
from collections.abc import Iterable
from typing import Any

from rpg_engine_api.domain.commands import CommandReceipt
from rpg_engine_api.domain.events import DomainEvent


class StreamVersionConflict(Exception):
    def __init__(self, stream_id: str, expected: int, actual: int) -> None:
        super().__init__(f"stream {stream_id} expected version {expected}, actual {actual}")
        self.stream_id = stream_id
        self.expected = expected
        self.actual = actual


class InMemoryEventStore:
    """Async append-only runtime store plus durable-style local content repositories."""

    def __init__(self) -> None:
        self._events: list[DomainEvent] = []
        self._streams: dict[str, list[DomainEvent]] = {}
        self._receipts: dict[str, CommandReceipt] = {}
        self._receipt_fingerprints: dict[str, str] = {}
        self._content_packs: dict[tuple[str, str], dict[str, Any]] = {}
        self._authoring_workspaces: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._subscribers: set[asyncio.Queue[DomainEvent]] = set()
        self._overflowed_subscribers: set[asyncio.Queue[DomainEvent]] = set()

    async def current_version(self, stream_id: str) -> int:
        return len(self._streams.get(stream_id, ()))

    async def append(self, stream_id: str, expected_version: int, events: Iterable[DomainEvent]) -> tuple[DomainEvent, ...]:
        async with self._lock:
            stream = self._streams.setdefault(stream_id, [])
            actual = len(stream)
            if actual != expected_version:
                raise StreamVersionConflict(stream_id, expected_version, actual)
            stored: list[DomainEvent] = []
            for raw in events:
                version = len(stream) + 1
                sequence = len(self._events) + 1
                event = raw.model_copy(update={"stream_id": stream_id, "stream_version": version, "sequence": sequence})
                stream.append(event)
                self._events.append(event)
                stored.append(event)
            subscribers = tuple(self._subscribers)
        for event in stored:
            for queue in subscribers:
                if queue in self._overflowed_subscribers:
                    continue
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    self._overflowed_subscribers.add(queue)
        return tuple(stored)

    async def read_stream(self, stream_id: str) -> tuple[DomainEvent, ...]:
        return tuple(self._streams.get(stream_id, ()))

    async def read_all(self) -> tuple[DomainEvent, ...]:
        return tuple(self._events)

    async def read_after(self, sequence: int, *, campaign_id: str | None = None, limit: int = 1000) -> tuple[DomainEvent, ...]:
        if sequence < 0 or limit <= 0:
            raise ValueError("sequence must be non-negative and limit positive")
        result: list[DomainEvent] = []
        for event in self._events:
            if event.sequence > sequence and (campaign_id is None or event.campaign_id == campaign_id):
                result.append(event)
                if len(result) >= limit:
                    break
        return tuple(result)

    async def last_sequence(self, *, campaign_id: str | None = None) -> int:
        if campaign_id is None:
            return self._events[-1].sequence if self._events else 0
        for event in reversed(self._events):
            if event.campaign_id == campaign_id:
                return event.sequence
        return 0

    async def get_receipt(self, key: str) -> CommandReceipt | None:
        return self._receipts.get(key)

    async def get_receipt_fingerprint(self, key: str) -> str | None:
        return self._receipt_fingerprints.get(key)

    async def save_receipt(self, key: str, receipt: CommandReceipt, *, fingerprint: str | None = None) -> None:
        self._receipts[key] = receipt
        if fingerprint is not None:
            self._receipt_fingerprints[key] = fingerprint

    async def save_content_pack(self, value: dict[str, Any]) -> None:
        self._content_packs[(str(value["pack_id"]), str(value["version"]))] = copy.deepcopy(value)

    async def load_content_packs(self) -> tuple[dict[str, Any], ...]:
        return tuple(copy.deepcopy(self._content_packs[key]) for key in sorted(self._content_packs))

    async def save_authoring_workspace(self, value: dict[str, Any]) -> None:
        self._authoring_workspaces[str(value["workspace_id"])] = copy.deepcopy(value)

    async def load_authoring_workspaces(self) -> tuple[dict[str, Any], ...]:
        return tuple(copy.deepcopy(self._authoring_workspaces[key]) for key in sorted(self._authoring_workspaces))

    def subscribe(self, *, maxsize: int = 256) -> asyncio.Queue[DomainEvent]:
        queue: asyncio.Queue[DomainEvent] = asyncio.Queue(maxsize=maxsize)
        self._subscribers.add(queue)
        return queue

    def subscription_overflowed(self, queue: asyncio.Queue[DomainEvent]) -> bool:
        return queue in self._overflowed_subscribers

    def unsubscribe(self, queue: asyncio.Queue[DomainEvent]) -> None:
        self._subscribers.discard(queue)
        self._overflowed_subscribers.discard(queue)
