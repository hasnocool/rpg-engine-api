from dataclasses import dataclass
from typing import Any

from rpg_engine_api.domain.commands import CommandEnvelope, CommandReceipt, PrincipalContext
from rpg_engine_api.domain.extensions import ExtensionCapability, TrustedExtensionManifest
from rpg_engine_api.extensions import TrustedExtensionRegistry


@dataclass
class FakeExtension:
    manifest: TrustedExtensionManifest = TrustedExtensionManifest(extension_id="testing.safe",version="1.0.0",capabilities=(ExtensionCapability.COMMAND_VALIDATOR,ExtensionCapability.ACTION_PROVIDER,ExtensionCapability.RECEIPT_OBSERVER))
    observed: int = 0
    def validate_command(self,command:CommandEnvelope,principal:PrincipalContext,engine:Any)->str|None:return "blocked for test" if command.command_type=="Blocked" else None
    def contribute_actions(self,actor_id:str,actions:list[dict[str,Any]],engine:Any)->list[dict[str,Any]]:return [{"action_id":"extension_check","command_type":"RollDice","actor_id":actor_id,"payload_schema":{"expression":"1d20"}}]
    def observe_receipt(self,receipt:CommandReceipt,engine:Any)->None:self.observed+=1


def test_trusted_extension_requires_loaded_code_before_enable() -> None:
    registry=TrustedExtensionRegistry();extension=FakeExtension();registry.install_descriptor(extension.manifest)
    try:registry.enable(extension.manifest.extension_id)
    except ValueError:pass
    else:raise AssertionError("descriptor without deployment code must not enable")
    registry.register_implementation(extension);registry.enable(extension.manifest.extension_id);assert registry.installations[extension.manifest.extension_id].active
    error=registry.validate_command(CommandEnvelope(command_type="Blocked"),PrincipalContext(principal_id="p"),object());assert error and "blocked" in error
    actions=registry.contribute_actions("actor",[],object());assert actions[0]["extension_id"]=="testing.safe"
