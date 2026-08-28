from fastapi import APIRouter, Header, Request

from rpg_engine_api.domain.commands import CommandEnvelope, CommandReceipt, PrincipalContext

router = APIRouter(prefix="/api/v1", tags=["commands"])


@router.post("/commands", response_model=CommandReceipt)
async def submit_command(command: CommandEnvelope, request: Request, x_principal_id: str | None = Header(default=None), x_principal_roles: str | None = Header(default=None)) -> CommandReceipt:
    settings = request.app.state.settings
    roles = frozenset(role.strip().lower() for role in (x_principal_roles or "player").split(",") if role.strip()) or frozenset({"player"})
    principal = PrincipalContext(principal_id=x_principal_id or settings.default_principal_id, roles=roles)
    return await request.app.state.engine.execute(command, principal)
