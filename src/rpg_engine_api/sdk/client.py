from collections.abc import Mapping
from typing import Any

import httpx

from rpg_engine_api.domain.commands import CommandEnvelope, CommandReceipt
from rpg_engine_api.sdk.models import EventPage, SyncResult


class AsyncRpgClient:
    """Thin public-API client; it intentionally contains no game legality rules."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        *,
        principal_id: str = "local-player",
        roles: tuple[str, ...] = ("player",),
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.principal_id = principal_id
        self.roles = roles
        self._client = httpx.AsyncClient(
            base_url=base_url,
            transport=transport,
            timeout=timeout,
            headers={"X-Principal-Id": principal_id, "X-Principal-Roles": ",".join(roles)},
        )

    async def __aenter__(self) -> "AsyncRpgClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def command(self, command: CommandEnvelope | Mapping[str, Any]) -> CommandReceipt:
        payload = command.model_dump(mode="json") if isinstance(command, CommandEnvelope) else dict(command)
        response = await self._client.post("/api/v1/commands", json=payload)
        response.raise_for_status()
        return CommandReceipt.model_validate(response.json())

    async def capabilities(self) -> dict[str, Any]:
        return await self._get_data("/api/v1/capabilities")

    async def campaign(self, campaign_id: str) -> dict[str, Any]:
        return await self._get_data(f"/api/v1/campaigns/{campaign_id}")

    async def actor(self, actor_id: str) -> dict[str, Any]:
        return await self._get_data(f"/api/v1/actors/{actor_id}")

    async def available_actions(self, actor_id: str) -> list[dict[str, Any]]:
        return list(await self._get_data(f"/api/v1/actors/{actor_id}/available-actions"))

    async def timeline(self, campaign_id: str) -> dict[str, Any]:
        return await self._get_data(f"/api/v1/campaigns/{campaign_id}/timeline")

    async def dialogue(self, dialogue_session_id: str) -> dict[str, Any]:
        return await self._get_data(f"/api/v1/dialogues/sessions/{dialogue_session_id}")

    async def events_page(self, campaign_id: str, *, cursor: str | None = None, limit: int = 100) -> EventPage:
        response = await self._client.get(
            f"/api/v1/campaigns/{campaign_id}/events",
            params={"limit": limit, **({"cursor": cursor} if cursor else {})},
        )
        response.raise_for_status()
        body = response.json()
        meta = body.get("meta", {})
        return EventPage(
            events=list(body.get("data", [])),
            next_cursor=meta.get("next_cursor"),
            has_more=bool(meta.get("has_more", False)),
            current_sequence=int(meta.get("current_sequence", 0)),
        )

    async def events(self, campaign_id: str, *, page_size: int = 200) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            page = await self.events_page(campaign_id, cursor=cursor, limit=page_size)
            result.extend(page.events)
            if not page.has_more or page.next_cursor is None:
                return result
            cursor = page.next_cursor

    async def sync(self, campaign_id: str, *, after_sequence: int | None = None) -> SyncResult:
        response = await self._client.get(
            f"/api/v1/campaigns/{campaign_id}/sync",
            params={} if after_sequence is None else {"after_sequence": after_sequence},
        )
        response.raise_for_status()
        body = response.json()
        data = body["data"]
        return SyncResult(
            mode=str(data["mode"]),
            current_sequence=int(body.get("meta", {}).get("current_sequence", 0)),
            snapshot=data.get("snapshot"),
            events=list(data.get("events", [])),
        )

    async def _get_data(self, path: str) -> Any:
        response = await self._client.get(path)
        response.raise_for_status()
        body = response.json()
        return body.get("data", body)
