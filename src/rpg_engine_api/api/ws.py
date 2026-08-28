import asyncio
from contextlib import suppress

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from rpg_engine_api.application.visibility import can_read_campaign, event_visible_to

router = APIRouter()


@router.websocket("/api/v1/ws/campaigns/{campaign_id}")
async def campaign_ws(websocket: WebSocket, campaign_id: str) -> None:
    engine = websocket.app.state.engine
    principal = await websocket.app.state.auth_provider.authenticate_headers(websocket.headers)
    if campaign_id not in engine.campaigns:
        await websocket.close(code=4404, reason="campaign not found")
        return
    if not can_read_campaign(engine, campaign_id, principal):
        await websocket.close(code=4403, reason="forbidden")
        return
    await websocket.accept()
    queue = engine.store.subscribe(maxsize=256)
    send_lock = asyncio.Lock()
    last_sent = 0

    async def send_json(payload: dict[str, object]) -> None:
        async with send_lock:
            await websocket.send_json(payload)

    async def send_backlog(after_sequence: int) -> int:
        current = await engine.store.last_sequence(campaign_id=campaign_id)
        if current - after_sequence > 1000:
            await send_json({"type": "server.resync_required", "campaign_id": campaign_id, "last_sequence": current, "reason": "resume_window_exceeded"})
            return current
        events = await engine.store.read_after(after_sequence, campaign_id=campaign_id, limit=1000)
        last_scanned = after_sequence
        for event in events:
            last_scanned = event.sequence
            if event_visible_to(engine, event, principal):
                await send_json({"type": "server.event", "event": event.model_dump(mode="json")})
        return last_scanned

    query_after = websocket.query_params.get("after_sequence")
    if query_after is not None:
        try:
            last_sent = await send_backlog(max(0, int(query_after)))
        except ValueError:
            await send_json({"type": "server.error", "code": "invalid_schema", "message": "after_sequence must be an integer"})

    async def send_events() -> None:
        nonlocal last_sent
        while True:
            if engine.store.subscription_overflowed(queue):
                current = await engine.store.last_sequence(campaign_id=campaign_id)
                await send_json({"type": "server.resync_required", "campaign_id": campaign_id, "last_sequence": current, "reason": "subscriber_backpressure"})
                await websocket.close(code=1013, reason="subscriber fell behind")
                return
            event = await queue.get()
            if event.campaign_id == campaign_id and event.sequence > last_sent:
                last_sent = event.sequence
                if event_visible_to(engine, event, principal):
                    await send_json({"type": "server.event", "event": event.model_dump(mode="json")})

    sender = asyncio.create_task(send_events())
    try:
        current = await engine.store.last_sequence(campaign_id=campaign_id)
        await send_json({"type": "server.ready", "campaign_id": campaign_id, "heartbeat_interval": 30, "schema_version": "1.2", "current_sequence": current, "resume_from": last_sent, "principal_id": principal.principal_id})
        while True:
            message = await websocket.receive_json()
            message_type = message.get("type")
            if message_type == "client.ping":
                await send_json({"type": "server.pong", "current_sequence": await engine.store.last_sequence(campaign_id=campaign_id)})
            elif message_type == "client.hello":
                raw_sequence = message.get("last_sequence")
                if raw_sequence is not None:
                    try:
                        last_sent = await send_backlog(max(0, int(raw_sequence)))
                    except (TypeError, ValueError):
                        await send_json({"type": "server.error", "code": "invalid_schema", "message": "last_sequence must be an integer"})
                        continue
                await send_json({"type": "server.ready", "campaign_id": campaign_id, "resume_from": last_sent, "current_sequence": await engine.store.last_sequence(campaign_id=campaign_id), "schema_version": "1.2"})
            elif message_type in {"client.subscribe", "client.unsubscribe", "client.ack"}:
                await send_json({"type": "server.ack", "request_type": message_type, "current_sequence": await engine.store.last_sequence(campaign_id=campaign_id)})
            else:
                await send_json({"type": "server.error", "code": "invalid_schema", "message": "unknown message type"})
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        with suppress(asyncio.CancelledError):
            await sender
        engine.store.unsubscribe(queue)
