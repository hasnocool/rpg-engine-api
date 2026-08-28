from __future__ import annotations

import logging
from typing import Any

from rpg_engine_api.application.extension_service import ExtensionEngineService
from rpg_engine_api.domain.actor import reduce_actor
from rpg_engine_api.domain.commands import CommandEnvelope, CommandReceipt, CommandStatus, PrincipalContext
from rpg_engine_api.domain.events import DomainEvent
from rpg_engine_api.domain.ids import new_id
from rpg_engine_api.infrastructure.backup import export_event_history
from rpg_engine_api.infrastructure.migration_sandbox import run_content_migration_sandbox
from rpg_engine_api.infrastructure.portable import PortableCampaignPackage, PortableCharacterPackage
from rpg_engine_api.security.redaction import redact

logger = logging.getLogger("rpg_engine_api.audit")


class ReleaseEngineService(ExtensionEngineService):
    """Release/operations layer: audit, portable packages and shipping-time invariants."""

    OWNER_COMMANDS = ExtensionEngineService.OWNER_COMMANDS | {"ImportCharacterPackage"}

    async def execute(self, command: CommandEnvelope, principal: PrincipalContext, *, drive_controllers: bool = True) -> CommandReceipt:
        receipt = await super().execute(command, principal, drive_controllers=drive_controllers)
        metrics = getattr(self, "metrics", None)
        if metrics is not None:
            if "controller" in principal.roles and command.command_type == "PerformAction":
                metrics.record_controller_decision()
            triggered = receipt.result.get("triggered_scheduled_events")
            if isinstance(triggered, list):
                metrics.record_scheduler_events(len(triggered))
            if command.command_type.startswith("Simulate"):
                metrics.record_simulation_runs(int(receipt.result.get("runs", 1)))
        try:
            await self._append_audit(command, principal, receipt)
        except Exception:
            logger.exception("audit_record_failed command_id=%s", command.command_id)
            if metrics is not None:
                metrics.record_operational_failure("audit")
        return receipt

    async def _dispatch(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        if command.command_type == "ImportCharacterPackage":
            return await self._import_character_package(command, principal)
        return await super()._dispatch(command, principal)

    async def _dry_run_content_revision(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        receipt = await super()._dry_run_content_revision(command, principal)
        proposal_id = str(command.payload.get("proposal_id", ""))
        success = False
        try:
            sandbox_report = await run_content_migration_sandbox(self, proposal_id, type(self))
            success = bool(sandbox_report["pre_replay_matches_live"] and sandbox_report["target_quality"]["valid"] and sandbox_report["post_replay_matches_live"])
            return receipt.model_copy(update={"result": {**receipt.result, "sandbox_report": sandbox_report}})
        finally:
            metrics = getattr(self, "metrics", None)
            if metrics is not None:
                metrics.record_migration_dry_run(success=success)

    async def _append_audit(self, command: CommandEnvelope, principal: PrincipalContext, receipt: CommandReceipt) -> None:
        stream = "system:audit"
        payload = {
            "principal_id": principal.principal_id,
            "roles": sorted(principal.roles),
            "command_type": command.command_type,
            "campaign_id": command.campaign_id,
            "actor_id": command.actor_id,
            "status": receipt.status.value,
            "error_code": receipt.error.code.value if receipt.error else None,
            "request": redact(command.model_dump(mode="json")),
            "result": redact(receipt.result),
        }
        event = DomainEvent(event_type="AdminAuditRecorded", campaign_id="__system__", stream_id=stream, command_id=command.command_id, correlation_id=command.command_id, payload=payload)
        await self.store.append(stream, await self.store.current_version(stream), (event,))

    async def audit_records(self, *, limit: int = 200, principal_id: str | None = None, campaign_id: str | None = None) -> list[dict[str, Any]]:
        events = await self.store.read_stream("system:audit")
        records: list[dict[str, Any]] = []
        for event in reversed(events):
            payload = dict(event.payload)
            if principal_id is not None and payload.get("principal_id") != principal_id:
                continue
            if campaign_id is not None and payload.get("campaign_id") != campaign_id:
                continue
            records.append({"audit_id": event.event_id, "sequence": event.sequence, "timestamp": event.server_timestamp.isoformat(), **payload})
            if len(records) >= max(1, min(limit, 1000)):
                break
        return records

    async def export_campaign_package(self, campaign_id: str) -> PortableCampaignPackage:
        if campaign_id not in self.campaigns:
            raise KeyError("campaign does not exist")
        binding = self.campaign_content_bindings.get(campaign_id)
        packs = ()
        if binding is not None:
            packs = tuple(pack for (pack_id, _), pack in self.published_packs.items() if pack_id == binding.pack_id)
        backup = await export_event_history(self.store, campaign_id=campaign_id, content_packs=packs)
        return PortableCampaignPackage.from_backup(backup)

    def export_character_package(self, actor_id: str) -> PortableCharacterPackage:
        actor = self.actors.get(actor_id)
        if actor is None:
            raise KeyError("actor does not exist")
        return PortableCharacterPackage.from_actor(actor)

    async def _import_character_package(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        campaign_id = command.campaign_id or str(command.payload.get("campaign_id", ""))
        if campaign_id not in self.campaigns:
            raise KeyError("campaign does not exist")
        package = PortableCharacterPackage.model_validate(command.payload.get("package", {}))
        if not package.verify():
            raise ValueError("character package failed integrity/security validation")
        data = package.character
        actor_id = str(command.payload.get("actor_id") or new_id("act"))
        actor_receipt = await self._create_actor(CommandEnvelope(command_id=new_id("cmd"), command_type="CreateActor", campaign_id=campaign_id, payload={"actor_id": actor_id, "name": str(data.get("name") or "Imported Character"), "max_hp": int(data.get("max_hp", 10)), "attack_bonus": int(data.get("attack_bonus", 2)), "defense": int(data.get("defense", 10)), "controller": {"controller_type": "human", "controller_version": "1"}}), principal)
        actor = self.actors[actor_id]
        stream = f"actor:{actor_id}"
        expected = await self.store.current_version(stream)
        events: list[DomainEvent] = []
        species = data.get("species")
        background = data.get("background")
        if species or background:
            events.append(DomainEvent(event_type="CharacterOriginApplied", campaign_id=campaign_id, stream_id=stream, actor_id=actor_id, command_id=command.command_id, correlation_id=command.command_id, payload={"species": species or "human", "background": background or "wanderer", "features": [], "items": []}))
        if data.get("class_id"):
            events.append(DomainEvent(event_type="CharacterBuildApplied", campaign_id=campaign_id, stream_id=stream, actor_id=actor_id, command_id=command.command_id, correlation_id=command.command_id, payload={"class_id": str(data["class_id"]), "subclass_id": data.get("subclass_id"), "ability_scores": dict(data.get("ability_scores", {})), "proficiencies": list(data.get("proficiencies", [])), "known_abilities": list(data.get("known_abilities", [])), "prepared_abilities": list(data.get("prepared_abilities", [])), "items": [], "equipment": {}, "resources": {}, "attack_bonus_delta": 0, "defense_delta": 0}))
        if events:
            stored = await self.store.append(stream, expected, events)
            state = actor
            for event in stored:
                state = reduce_actor(state, event)
            self.actors[actor_id] = state
        else:
            stored = ()
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=actor_receipt.emitted_event_ids + tuple(event.event_id for event in stored), stream_versions={**actor_receipt.stream_versions, **({stream: stored[-1].stream_version} if stored else {})}, result={"campaign_id": campaign_id, "actor_id": actor_id, "imported": True, "source_digest": package.digest})

    @classmethod
    def capability_projection(cls) -> dict[str, Any]:
        base = super().capability_projection()
        data = dict(base["data"])
        data["features"] = list(data.get("features", [])) + ["admin_audit_log", "portable_campaign_package", "portable_character_package", "data_only_import_validation", "isolated_migration_sandbox"]
        return {"data": data, "meta": {"schema_version": "1.8"}}
