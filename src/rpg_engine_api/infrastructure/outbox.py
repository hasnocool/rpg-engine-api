from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from rpg_engine_api.domain.events import DomainEvent


class OutboxDrainResult(BaseModel):
    attempted: int = 0
    published: int = 0
    failed_event_id: str | None = None


async def drain_outbox(
    store: object,
    publisher: Callable[[DomainEvent], Awaitable[None]],
    *,
    limit: int = 100,
) -> OutboxDrainResult:
    pending = await store.pending_outbox(limit=limit)  # type: ignore[attr-defined]
    published = 0
    for event in pending:
        try:
            await publisher(event)
        except Exception:
            return OutboxDrainResult(attempted=published + 1, published=published, failed_event_id=event.event_id)
        await store.mark_outbox_published(event.event_id)  # type: ignore[attr-defined]
        published += 1
    return OutboxDrainResult(attempted=len(pending), published=published)
