from typing import Any

from httpx import ASGITransport, AsyncClient

from rpg_engine_api.app import create_app
from rpg_engine_api.config import Settings

from .persona import Persona


class PlaytestClient:
    """Thin black-box client: it knows transport contracts, never hidden RPG rules."""

    def __init__(self, persona: Persona, *, app: Any | None = None) -> None:
        self.persona = persona
        self.app = app or create_app(Settings())
        self.http = AsyncClient(transport=ASGITransport(app=self.app), base_url="http://playtest")

    async def close(self) -> None:
        await self.http.aclose()

    async def command(self, command_type: str, **kwargs: Any) -> dict[str, Any]:
        body = {"command_type": command_type, **kwargs}
        response = await self.http.post(
            "/api/v1/commands",
            json=body,
            headers={"x-principal-id": self.persona.principal_id},
        )
        response.raise_for_status()
        return response.json()

    async def get(self, path: str) -> dict[str, Any]:
        response = await self.http.get(path, headers={"x-principal-id": self.persona.principal_id})
        response.raise_for_status()
        return response.json()
