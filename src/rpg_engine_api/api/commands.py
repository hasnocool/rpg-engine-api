from fastapi import APIRouter, Request

from rpg_engine_api.domain.commands import CommandEnvelope, CommandError, CommandReceipt, CommandStatus, ErrorCode

router = APIRouter(prefix="/api/v1", tags=["commands"])


@router.post("/commands", response_model=CommandReceipt)
async def submit_command(command: CommandEnvelope, request: Request) -> CommandReceipt:
    principal = await request.app.state.auth_provider.authenticate_headers(request.headers)
    if not await request.app.state.rate_limiter.allow(principal.principal_id):
        return CommandReceipt(
            command_id=command.command_id,
            status=CommandStatus.REJECTED,
            error=CommandError(code=ErrorCode.RATE_LIMITED, message="command rate limit exceeded"),
        )
    return await request.app.state.engine.execute(command, principal)
