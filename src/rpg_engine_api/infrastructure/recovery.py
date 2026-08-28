from __future__ import annotations

from typing import Any, Callable

from rpg_engine_api.infrastructure.backup import restore_event_history
from rpg_engine_api.persistence.event_store import InMemoryEventStore


async def run_recovery_probe(engine: Any, campaign_id: str, engine_factory: Callable[..., Any]) -> dict[str, Any]:
    """Restore one campaign into an isolated engine and compare authoritative/replay state."""
    package = await engine.export_campaign_package(campaign_id)
    report = package.validation_report()
    if not report["valid"]:
        return {"schema_version": "1.0", "campaign_id": campaign_id, "success": False, "stage": "package_validation", "validation": report}

    source_live = engine.live_hash(campaign_id)
    source_replay = await engine.canonical_hash(campaign_id)
    store = InMemoryEventStore()
    restored = await restore_event_history(package.backup, store, require_empty=True)
    for raw in package.backup.content_packs:
        await store.save_content_pack(raw)
    restored_engine = engine_factory(store=store)
    await restored_engine.rebuild_from_store()
    restored_live = restored_engine.live_hash(campaign_id)
    restored_replay = await restored_engine.canonical_hash(campaign_id)
    pending_outbox = await store.pending_outbox_count()
    success = source_live == source_replay == restored_live == restored_replay
    return {
        "schema_version": "1.0",
        "campaign_id": campaign_id,
        "success": success,
        "restored_events": restored,
        "source_live_hash": source_live,
        "source_replay_hash": source_replay,
        "restored_live_hash": restored_live,
        "restored_replay_hash": restored_replay,
        "source_replay_matches_live": source_live == source_replay,
        "restored_replay_matches_live": restored_live == restored_replay,
        "restored_matches_source": restored_live == source_live,
        "pending_outbox_after_restore": pending_outbox,
        "isolated": True,
    }
