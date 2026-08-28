from fastapi import APIRouter, Header, Request

from rpg_engine_api.domain.commands import CommandEnvelope, CommandError, CommandReceipt, CommandStatus, ErrorCode, PrincipalContext

router = APIRouter(prefix="/api/v1", tags=["commands"])


@router.post("/commands", response_model=CommandReceipt)
async def submit_command(command: CommandEnvelope, request: Request, x_principal_id: str | None = Header(default=None), x_principal_roles: str | None = Header(default=None)) -> CommandReceipt:
    settings = request.app.state.settings
    principal_id = x_principal_id or settings.default_principal_id
    roles = frozenset(role.strip().lower() for role in (x_principal_roles or "player").split(",") if role.strip()) or frozenset({"player"})
    if not await request.app.state.rate_limiter.allow(principal_id):
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.REJECTED, error=CommandError(code=ErrorCode.RATE_LIMITED, message="command rate limit exceeded"))
    return await request.app.state.engine.execute(command, PrincipalContext(principal_id=principal_id, roles=roles))
