from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from rpg_engine_api.domain.events import DomainEvent


class OutboxDrainResult(BaseModel):
    attempted: int = 0
    published: int = 0
    deduplicated: int = 0
    failed_event_id: str | None = None


@runtime_checkable
class IdempotentOutboxPublisher(Protocol):
    async def has_published(self, event_id: str) -> bool: ...
    async def publish(self, event: DomainEvent) -> None: ...


class InMemoryIdempotentPublisher:
    """Reference publisher proving event-id dedupe semantics for local recovery tests."""

    def __init__(self) -> None:
        self.published_ids: set[str] = set()
        self.events: list[DomainEvent] = []

    async def has_published(self, event_id: str) -> bool:
        return event_id in self.published_ids

    async def publish(self, event: DomainEvent) -> None:
        if event.event_id in self.published_ids:
            return
        self.published_ids.add(event.event_id)
        self.events.append(event)


async def drain_outbox(
    store: object,
    publisher: Callable[[DomainEvent], Awaitable[None]] | IdempotentOutboxPublisher,
    *,
    limit: int = 100,
) -> OutboxDrainResult:
    """Drain pending events.

    Exactly-once *logical* publication across crash/retry boundaries requires an idempotent
    downstream publisher keyed by immutable event_id. Plain callables remain supported but
    provide only at-least-once delivery semantics.
    """
    pending = await store.pending_outbox(limit=limit)  # type: ignore[attr-defined]
    published = 0
    deduplicated = 0
    for index, event in enumerate(pending, start=1):
        try:
            if isinstance(publisher, IdempotentOutboxPublisher):
                if await publisher.has_published(event.event_id):
                    await store.mark_outbox_published(event.event_id)  # type: ignore[attr-defined]
                    deduplicated += 1
                    continue
                await publisher.publish(event)
            else:
                await publisher(event)
        except Exception:
            return OutboxDrainResult(attempted=index, published=published, deduplicated=deduplicated, failed_event_id=event.event_id)
        await store.mark_outbox_published(event.event_id)  # type: ignore[attr-defined]
        published += 1
    return OutboxDrainResult(attempted=len(pending), published=published, deduplicated=deduplicated)
