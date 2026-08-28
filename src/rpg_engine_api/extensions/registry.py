from typing import Any, Protocol

from rpg_engine_api.domain.commands import CommandEnvelope, CommandReceipt, PrincipalContext
from rpg_engine_api.domain.extensions import ExtensionCapability, ExtensionInstallation, TrustedExtensionManifest


class TrustedExtension(Protocol):
    manifest: TrustedExtensionManifest

    def validate_command(self, command: CommandEnvelope, principal: PrincipalContext, engine: Any) -> str | None: ...
    def contribute_actions(self, actor_id: str, actions: list[dict[str, Any]], engine: Any) -> list[dict[str, Any]]: ...
    def observe_receipt(self, receipt: CommandReceipt, engine: Any) -> None: ...


class TrustedExtensionRegistry:
    """Deployment-controlled extension registry. Content payloads never instantiate code."""

    def __init__(self) -> None:
        self.installations: dict[str, ExtensionInstallation] = {}
        self._implementations: dict[str, TrustedExtension] = {}

    def install_descriptor(self, manifest: TrustedExtensionManifest, *, metadata: dict[str, str] | None = None) -> ExtensionInstallation:
        if not manifest.trusted:
            raise ValueError("rules extensions must be explicitly trusted")
        if not manifest.deterministic:
            raise ValueError("authoritative rules extensions must declare deterministic behavior")
        existing = self.installations.get(manifest.extension_id)
        if existing is not None and existing.manifest.version != manifest.version:
            raise ValueError("extension ID already installed with another version")
        installation = existing or ExtensionInstallation(manifest=manifest, metadata=dict(metadata or {}))
        self.installations[manifest.extension_id] = installation
        if manifest.extension_id in self._implementations:
            installation.implementation_loaded = True
        return installation

    def register_implementation(self, implementation: TrustedExtension) -> ExtensionInstallation:
        manifest = implementation.manifest
        installation = self.installations.get(manifest.extension_id)
        if installation is None:
            installation = self.install_descriptor(manifest)
        if installation.manifest.version != manifest.version:
            raise ValueError("extension implementation version does not match descriptor")
        self._implementations[manifest.extension_id] = implementation
        installation.implementation_loaded = True
        installation.fault = None
        return installation

    def enable(self, extension_id: str) -> ExtensionInstallation:
        installation = self.installations[extension_id]
        if extension_id not in self._implementations:
            raise ValueError("extension code is not loaded by the deployment")
        installation.enabled_requested = True; installation.fault = None
        return installation

    def disable(self, extension_id: str) -> ExtensionInstallation:
        installation = self.installations[extension_id]; installation.enabled_requested = False
        return installation

    def active(self) -> tuple[tuple[ExtensionInstallation, TrustedExtension], ...]:
        return tuple((self.installations[key], self._implementations[key]) for key in sorted(self.installations) if self.installations[key].active and key in self._implementations)

    def validate_command(self, command: CommandEnvelope, principal: PrincipalContext, engine: Any) -> str | None:
        for installation, implementation in self.active():
            if ExtensionCapability.COMMAND_VALIDATOR not in installation.manifest.capabilities:
                continue
            try:
                error = implementation.validate_command(command, principal, engine)
            except Exception as exc:
                installation.fault = f"validator failure: {type(exc).__name__}"
                return f"trusted extension {installation.manifest.extension_id} faulted"
            if error:
                return f"{installation.manifest.extension_id}: {error}"
        return None

    def contribute_actions(self, actor_id: str, actions: list[dict[str, Any]], engine: Any) -> list[dict[str, Any]]:
        result = [dict(item) for item in actions]
        for installation, implementation in self.active():
            if ExtensionCapability.ACTION_PROVIDER not in installation.manifest.capabilities:
                continue
            try:
                additions = implementation.contribute_actions(actor_id, [dict(item) for item in result], engine)
                for action in additions:
                    if not isinstance(action, dict) or not action.get("action_id") or not action.get("command_type"):
                        raise ValueError("extension action must declare action_id and command_type")
                    normalized = dict(action); normalized["extension_id"] = installation.manifest.extension_id; result.append(normalized)
            except Exception as exc:
                installation.fault = f"action provider failure: {type(exc).__name__}"
        return sorted(result, key=lambda item: (str(item.get("action_id", "")), str(item.get("target_id", "")), str(item.get("extension_id", ""))))

    def observe_receipt(self, receipt: CommandReceipt, engine: Any) -> None:
        for installation, implementation in self.active():
            if ExtensionCapability.RECEIPT_OBSERVER not in installation.manifest.capabilities:
                continue
            try:
                implementation.observe_receipt(receipt, engine)
            except Exception as exc:
                installation.fault = f"observer failure: {type(exc).__name__}"
