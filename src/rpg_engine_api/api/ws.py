import asyncio
from contextlib import suppress

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/api/v1/ws/campaigns/{campaign_id}")
async def campaign_ws(websocket: WebSocket, campaign_id: str) -> None:
    await websocket.accept()
    engine = websocket.app.state.engine
    queue = engine.store.subscribe()

    async def send_events() -> None:
        while True:
            event = await queue.get()
            if event.campaign_id == campaign_id:
                await websocket.send_json(
                    {"type": "server.event", "event": event.model_dump(mode="json")}
                )

    sender = asyncio.create_task(send_events())
    try:
        await websocket.send_json(
            {
                "type": "server.ready",
                "campaign_id": campaign_id,
                "heartbeat_interval": 30,
                "schema_version": "1.0",
            }
        )
        while True:
            message = await websocket.receive_json()
            message_type = message.get("type")
            if message_type == "client.ping":
                await websocket.send_json({"type": "server.pong"})
            elif message_type == "client.hello":
                await websocket.send_json(
                    {
                        "type": "server.ready",
                        "campaign_id": campaign_id,
                        "resume_from": message.get("last_sequence"),
                        "schema_version": "1.0",
                    }
                )
            elif message_type in {"client.subscribe", "client.unsubscribe", "client.ack"}:
                await websocket.send_json({"type": "server.ack", "request_type": message_type})
            else:
                await websocket.send_json(
                    {"type": "server.error", "code": "invalid_schema", "message": "unknown message type"}
                )
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        with suppress(asyncio.CancelledError):
            await sender
        engine.store.unsubscribe(queue)
