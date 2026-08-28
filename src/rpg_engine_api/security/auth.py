from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from rpg_engine_api.domain.commands import PrincipalContext


class AuthenticationProvider(Protocol):
    async def authenticate_headers(self, headers: Mapping[str, str]) -> PrincipalContext: ...


@dataclass(frozen=True, slots=True)
class LocalHeaderAuthenticationProvider:
    """Local-development auth adapter.

    This keeps authentication behind a replaceable boundary. It intentionally trusts
    local headers and therefore must not be treated as an Internet-facing identity
    provider.
    """

    default_principal_id: str = "local-player"

    async def authenticate_headers(self, headers: Mapping[str, str]) -> PrincipalContext:
        principal_id = (headers.get("x-principal-id") or self.default_principal_id).strip()
        if not principal_id:
            principal_id = self.default_principal_id
        raw_roles = headers.get("x-principal-roles") or "player"
        roles = frozenset(
            role.strip().lower() for role in raw_roles.split(",") if role.strip()
        ) or frozenset({"player"})
        return PrincipalContext(principal_id=principal_id, roles=roles)
