import logging
import time
from typing import Any

from rpg_engine_api.application.production_service import ProductionEngineService
from rpg_engine_api.domain.authoring import AuthoringWorkspace, PublishedContentPack
from rpg_engine_api.domain.commands import CommandEnvelope, CommandReceipt, CommandStatus, PrincipalContext
from rpg_engine_api.infrastructure.metrics import RuntimeMetrics

logger = logging.getLogger("rpg_engine_api.commands")


class DurableEngineService(ProductionEngineService):
    """Production service with durable creator state and operational instrumentation."""

    AUTHORING_COMMANDS = frozenset({"CreateAuthoringWorkspace", "UpsertDraftDefinition", "ValidateAuthoringWorkspace", "PublishAuthoringWorkspace"})

    def __init__(self, store: Any | None = None) -> None:
        super().__init__(store=store)
        self.metrics = RuntimeMetrics()

    async def execute(self, command: CommandEnvelope, principal: PrincipalContext, *, drive_controllers: bool = True) -> CommandReceipt:
        started = time.perf_counter()
        receipt = await super().execute(command, principal, drive_controllers=drive_controllers)
        duration = time.perf_counter() - started
        self.metrics.record_command(command.command_type, receipt, duration)
        logger.info("command_processed type=%s command_id=%s campaign_id=%s actor_id=%s status=%s duration_seconds=%.6f", command.command_type, command.command_id, command.campaign_id, command.actor_id, receipt.status.value, duration)
        return receipt

    async def _dispatch(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        receipt = await super()._dispatch(command, principal)
        if receipt.status == CommandStatus.ACCEPTED and command.command_type in self.AUTHORING_COMMANDS:
            await self._persist_authoring_result(command, receipt)
        return receipt

    async def _persist_authoring_result(self, command: CommandEnvelope, receipt: CommandReceipt) -> None:
        workspace_id = str(receipt.result.get("workspace_id") or command.payload.get("workspace_id", ""))
        workspace = self.authoring_workspaces.get(workspace_id)
        save_workspace = getattr(self.store, "save_authoring_workspace", None)
        if workspace is not None and save_workspace is not None:
            await save_workspace(workspace.model_dump(mode="json"))
        if command.command_type == "PublishAuthoringWorkspace":
            pack_id = str(receipt.result["pack_id"])
            version = str(receipt.result["version"])
            pack = self.published_packs[(pack_id, version)]
            save_pack = getattr(self.store, "save_content_pack", None)
            if save_pack is not None:
                await save_pack(pack.model_dump(mode="json"))

    async def rebuild_from_store(self) -> None:
        await super().rebuild_from_store()
        self.authoring_workspaces.clear()
        self.published_packs.clear()
        load_workspaces = getattr(self.store, "load_authoring_workspaces", None)
        if load_workspaces is not None:
            for raw in await load_workspaces():
                workspace = AuthoringWorkspace.model_validate(raw)
                self.authoring_workspaces[workspace.workspace_id] = workspace
        load_packs = getattr(self.store, "load_content_packs", None)
        if load_packs is not None:
            for raw in await load_packs():
                pack = PublishedContentPack.model_validate(raw)
                self.published_packs[(pack.pack_id, pack.version)] = pack
