from typing import Any

from rpg_engine_api.application.living_world_service import LivingWorldEngineService
from rpg_engine_api.domain.commands import CommandEnvelope, CommandError, CommandReceipt, CommandStatus, ErrorCode, PrincipalContext
from rpg_engine_api.domain.events import DomainEvent
from rpg_engine_api.domain.extensions import ExtensionInstallation, TrustedExtensionManifest
from rpg_engine_api.extensions import TrustedExtension, TrustedExtensionRegistry


class ExtensionEngineService(LivingWorldEngineService):
    """Trusted extension seam; executable code can only be registered by the deployment."""

    def __init__(self, store: Any | None = None) -> None:
        super().__init__(store=store); self.extensions = TrustedExtensionRegistry()

    def register_trusted_extension(self, implementation: TrustedExtension) -> ExtensionInstallation:
        return self.extensions.register_implementation(implementation)

    async def execute(self, command: CommandEnvelope, principal: PrincipalContext, *, drive_controllers: bool = True) -> CommandReceipt:
        receipt = await super().execute(command, principal, drive_controllers=drive_controllers); self.extensions.observe_receipt(receipt, self); return receipt

    async def _dispatch(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        admin = {"InstallTrustedExtensionDescriptor": self._install_extension_descriptor, "EnableTrustedExtension": self._enable_extension, "DisableTrustedExtension": self._disable_extension}
        if command.command_type in admin:
            return await admin[command.command_type](command, principal)
        error = self.extensions.validate_command(command, principal, self)
        if error is not None:
            return CommandReceipt(command_id=command.command_id, status=CommandStatus.REJECTED, error=CommandError(code=ErrorCode.PREREQUISITE_FAILED, message=error))
        return await super()._dispatch(command, principal)

    def _require_extension_admin(self, principal: PrincipalContext) -> None:
        if not principal.roles.intersection({"admin", "service"}):
            raise ValueError("extension administration requires admin/service role")

    async def _record_extension_event(self, command: CommandEnvelope, event_type: str, payload: dict[str, object]) -> DomainEvent:
        stream = "system:extensions"; event = DomainEvent(event_type=event_type, campaign_id="__system__", stream_id=stream, command_id=command.command_id, correlation_id=command.command_id, payload=payload); stored = await self.store.append(stream, await self.store.current_version(stream), (event,)); return stored[0]

    async def _install_extension_descriptor(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        self._require_extension_admin(principal); manifest = TrustedExtensionManifest.model_validate(command.payload.get("manifest", {})); installation = self.extensions.install_descriptor(manifest, metadata={str(k): str(v) for k, v in dict(command.payload.get("metadata", {})).items()}); event = await self._record_extension_event(command, "TrustedExtensionInstalled", {"manifest": manifest.model_dump(mode="json"), "metadata": installation.metadata}); return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=(event.event_id,), stream_versions={event.stream_id: event.stream_version}, result={"extension": installation.model_dump(mode="json")})

    async def _enable_extension(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        self._require_extension_admin(principal); extension_id = str(command.payload.get("extension_id", "")); installation = self.extensions.enable(extension_id); event = await self._record_extension_event(command, "TrustedExtensionEnabled", {"extension_id": extension_id, "version": installation.manifest.version}); return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=(event.event_id,), stream_versions={event.stream_id: event.stream_version}, result={"extension": installation.model_dump(mode="json")})

    async def _disable_extension(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        self._require_extension_admin(principal); extension_id = str(command.payload.get("extension_id", "")); installation = self.extensions.disable(extension_id); event = await self._record_extension_event(command, "TrustedExtensionDisabled", {"extension_id": extension_id}); return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=(event.event_id,), stream_versions={event.stream_id: event.stream_version}, result={"extension": installation.model_dump(mode="json")})

    def available_actions(self, actor_id: str) -> list[dict[str, Any]]:
        return self.extensions.contribute_actions(actor_id, super().available_actions(actor_id), self)

    async def rebuild_from_store(self) -> None:
        implementations = dict(self.extensions._implementations); await super().rebuild_from_store(); self.extensions = TrustedExtensionRegistry()
        for event in await self.store.read_stream("system:extensions"):
            if event.event_type == "TrustedExtensionInstalled":
                self.extensions.install_descriptor(TrustedExtensionManifest.model_validate(event.payload["manifest"]), metadata={str(k): str(v) for k, v in dict(event.payload.get("metadata", {})).items()})
            elif event.event_type == "TrustedExtensionEnabled":
                installation = self.extensions.installations.get(str(event.payload["extension_id"]));
                if installation is not None: installation.enabled_requested = True
            elif event.event_type == "TrustedExtensionDisabled":
                installation = self.extensions.installations.get(str(event.payload["extension_id"]));
                if installation is not None: installation.enabled_requested = False
        for implementation in implementations.values():
            self.extensions.register_implementation(implementation)

    @classmethod
    def capability_projection(cls) -> dict[str, Any]:
        base = super().capability_projection(); data = dict(base["data"]); data["features"] = list(data.get("features", [])) + ["trusted_extension_registry", "extension_command_validation", "extension_action_provider", "extension_failure_isolation"]; return {"data": data, "meta": {"schema_version": "1.6"}}
