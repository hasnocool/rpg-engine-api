from typing import Any

from rpg_engine_api.application.recoverable_service import RecoverableEngineService
from rpg_engine_api.domain.authoring import PublishedContentPack
from rpg_engine_api.domain.commands import CommandEnvelope, CommandReceipt, CommandStatus, PrincipalContext
from rpg_engine_api.domain.content_evolution import CampaignContentBinding, CampaignImpactReport, CompatibilityReport, ContentMigrationOperation, ContentMigrationPlan, ContentRevisionDiff, ContentRevisionProposal
from rpg_engine_api.domain.ids import new_id
from rpg_engine_api.infrastructure.backup import EventHistoryBackup, export_event_history


class ProductionEngineService(RecoverableEngineService):
    """Production-facing migration/impact/backup workflows on top of recoverable gameplay."""

    OWNER_COMMANDS = RecoverableEngineService.OWNER_COMMANDS | {"AnalyzeContentRevisionImpact", "BuildContentMigrationPlan", "RollbackContentRevision", "ExportCampaignBackup"}

    async def _dispatch(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        handlers = {
            "AnalyzeContentRevisionImpact": self._analyze_content_revision_impact,
            "BuildContentMigrationPlan": self._build_content_migration_plan_command,
            "RollbackContentRevision": self._rollback_content_revision,
            "ExportCampaignBackup": self._export_campaign_backup,
        }
        handler = handlers.get(command.command_type)
        if handler is not None:
            return await handler(command, principal)
        return await super()._dispatch(command, principal)

    def _diff(self, pack_id: str, from_version: str, to_version: str) -> ContentRevisionDiff:
        base = super()._diff(pack_id, from_version, to_version)
        old = self._pack(pack_id, from_version)
        new = self._pack(pack_id, to_version)
        old_map = {item.key: item for item in old.definitions}
        new_map = {item.key: item for item in new.definitions}
        mechanics: list[str] = []
        presentation: list[str] = []
        provenance: list[str] = []
        presentation_keys = {"label", "name", "description", "text", "text_key", "icon", "ui_group"}
        for key in base.changed_keys:
            before = old_map[key]
            after = new_map[key]
            source_changed = before.source != after.source
            before_data = dict(before.data)
            after_data = dict(after.data)
            before_mechanics = {item: value for item, value in before_data.items() if item not in presentation_keys}
            after_mechanics = {item: value for item, value in after_data.items() if item not in presentation_keys}
            if before.definition_type != after.definition_type or before_mechanics != after_mechanics:
                mechanics.append(key)
            elif before_data != after_data:
                presentation.append(key)
            if source_changed:
                provenance.append(key)
        return base.model_copy(update={"mechanic_changed_keys": mechanics, "presentation_changed_keys": presentation, "provenance_changed_keys": provenance})

    async def _propose_content_revision(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        receipt = await super()._propose_content_revision(command, principal)
        proposal = self.content_revision_proposals[str(receipt.result["proposal_id"])]
        event_receipt = await self._record_campaign_fact(command, "ContentRevisionProposed", proposal.model_dump(mode="json"))
        return receipt.model_copy(update={"emitted_event_ids": event_receipt.emitted_event_ids, "stream_versions": event_receipt.stream_versions})

    async def _dry_run_content_revision(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        receipt = await super()._dry_run_content_revision(command, principal)
        proposal_id = str(command.payload.get("proposal_id", ""))
        proposal = self.content_revision_proposals[proposal_id]
        impact = self._impact_report(proposal)
        plan = self._migration_plan(proposal, remaps={})
        proposal.impact_report = impact
        proposal.migration_plan = plan
        event_receipt = await self._record_campaign_fact(CommandEnvelope(command_id=command.command_id, command_type="ContentRevisionDryRunCompleted", campaign_id=proposal.campaign_id, payload={}), "ContentRevisionDryRunCompleted", {"proposal_id": proposal_id, "compatibility_report": proposal.report.model_dump(mode="json") if proposal.report else None, "impact_report": impact.model_dump(mode="json"), "migration_plan": plan.model_dump(mode="json"), "status": proposal.status})
        result = {**receipt.result, "impact_report": impact.model_dump(mode="json"), "migration_plan": plan.model_dump(mode="json")}
        return receipt.model_copy(update={"emitted_event_ids": receipt.emitted_event_ids + event_receipt.emitted_event_ids, "stream_versions": {**receipt.stream_versions, **event_receipt.stream_versions}, "result": result})

    def _impact_report(self, proposal: ContentRevisionProposal) -> CampaignImpactReport:
        if proposal.report is not None:
            diff = proposal.report.diff
        else:
            diff = self._diff(proposal.pack_id, proposal.from_version, proposal.to_version)
        affected = sorted(set(diff.removed_keys) | set(diff.changed_keys))
        snapshot = self.live_snapshot(proposal.campaign_id)
        matched: dict[str, list[str]] = {key: [] for key in affected}

        def walk(value: Any, path: str) -> None:
            if isinstance(value, str) and value in matched:
                matched[value].append(path)
            elif isinstance(value, dict):
                for key, child in value.items():
                    walk(child, f"{path}.{key}" if path else str(key))
            elif isinstance(value, (list, tuple, set)):
                for index, child in enumerate(value):
                    walk(child, f"{path}[{index}]")

        walk(snapshot, "")
        categories: dict[str, list[str]] = {}
        for key, paths in matched.items():
            for path in paths:
                category = path.split(".", 1)[0].split("[", 1)[0] or "unknown"
                categories.setdefault(category, []).append(key)
        for values in categories.values():
            values[:] = sorted(set(values))
        future = sorted(set(diff.mechanic_changed_keys) | set(diff.added_keys))
        warnings = [f"removed definition {key} requires explicit migration/branch handling" for key in diff.removed_keys]
        return CampaignImpactReport(campaign_id=proposal.campaign_id, proposal_id=proposal.proposal_id, affected_keys=affected, matched_paths={key: sorted(paths) for key, paths in matched.items() if paths}, affected_categories=dict(sorted(categories.items())), future_mechanics_affected=future, warnings=warnings)

    def _migration_plan(self, proposal: ContentRevisionProposal, *, remaps: dict[str, str]) -> ContentMigrationPlan:
        diff = proposal.report.diff if proposal.report is not None else self._diff(proposal.pack_id, proposal.from_version, proposal.to_version)
        target = self._pack(proposal.pack_id, proposal.to_version)
        target_keys = {definition.key for definition in target.definitions}
        operations: list[ContentMigrationOperation] = []
        unresolved: list[str] = []
        for key in diff.removed_keys:
            replacement = remaps.get(key)
            if replacement is not None and replacement in target_keys:
                operations.append(ContentMigrationOperation(operation="remap_reference", source_ref=key, target_ref=replacement, reversible=True, notes="descriptor only; state transformer must apply this before in-place activation"))
            else:
                unresolved.append(key)
                operations.append(ContentMigrationOperation(operation="manual_resolution_required", source_ref=key, reversible=False))
        for key in diff.mechanic_changed_keys:
            operations.append(ContentMigrationOperation(operation="reinterpret_future_under_new_lock", source_ref=key, target_ref=key, reversible=True))
        for key in diff.presentation_changed_keys:
            operations.append(ContentMigrationOperation(operation="projection_refresh", source_ref=key, target_ref=key, reversible=True))
        executable = not unresolved and not diff.removed_keys
        return ContentMigrationPlan(proposal_id=proposal.proposal_id, campaign_id=proposal.campaign_id, operations=operations, unresolved_keys=sorted(unresolved), executable_in_place=executable, reversible=all(operation.reversible for operation in operations))

    async def _analyze_content_revision_impact(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal
        proposal = self.content_revision_proposals.get(str(command.payload.get("proposal_id", "")))
        if proposal is None:
            raise KeyError("content revision proposal does not exist")
        impact = self._impact_report(proposal)
        proposal.impact_report = impact
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, result={"proposal_id": proposal.proposal_id, "impact_report": impact.model_dump(mode="json")})

    async def _build_content_migration_plan_command(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal
        proposal = self.content_revision_proposals.get(str(command.payload.get("proposal_id", "")))
        if proposal is None:
            raise KeyError("content revision proposal does not exist")
        remaps = {str(key): str(value) for key, value in dict(command.payload.get("remaps", {})).items()}
        plan = self._migration_plan(proposal, remaps=remaps)
        proposal.migration_plan = plan
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, result={"proposal_id": proposal.proposal_id, "migration_plan": plan.model_dump(mode="json")})

    async def _rollback_content_revision(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        proposal = self.content_revision_proposals.get(str(command.payload.get("proposal_id", "")))
        if proposal is None:
            raise KeyError("content revision proposal does not exist")
        if proposal.status != "activated" or not proposal.pre_activation_checkpoint_id:
            raise ValueError("only a directly activated revision with a recovery checkpoint can be rolled back")
        current = self.campaign_content_bindings.get(proposal.campaign_id)
        if current is None or current.version != proposal.to_version:
            raise ValueError("campaign is no longer on the proposal target version")
        old_pack = self._pack(proposal.pack_id, proposal.from_version)
        checkpoint_id = str(command.payload.get("checkpoint_id") or new_id("checkpoint"))
        checkpoint_receipt = await self._create_checkpoint(CommandEnvelope(command_id=new_id("cmd"), command_type="CreateCheckpoint", campaign_id=proposal.campaign_id, payload={"checkpoint_id": checkpoint_id, "name": f"Before rollback to {proposal.from_version}"}), principal)
        event = await self._append_campaign_content_event(command, proposal.campaign_id, "CampaignContentRevisionRolledBack", {"proposal_id": proposal.proposal_id, "pack_id": proposal.pack_id, "from_version": proposal.to_version, "to_version": proposal.from_version, "new_content_hash": old_pack.content_hash, "rollback_checkpoint_id": checkpoint_id, "original_pre_activation_checkpoint_id": proposal.pre_activation_checkpoint_id})
        self.campaign_content_bindings[proposal.campaign_id] = CampaignContentBinding(campaign_id=proposal.campaign_id, pack_id=proposal.pack_id, version=proposal.from_version, content_hash=old_pack.content_hash, activated_sequence=event.sequence)
        proposal.status = "rolled_back"
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=checkpoint_receipt.emitted_event_ids + (event.event_id,), stream_versions={**checkpoint_receipt.stream_versions, event.stream_id: event.stream_version}, result={"proposal_id": proposal.proposal_id, "campaign_id": proposal.campaign_id, "version": proposal.from_version, "checkpoint_id": checkpoint_id})

    async def _export_campaign_backup(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal
        campaign_id = command.campaign_id or str(command.payload.get("campaign_id", ""))
        if campaign_id not in self.campaigns:
            raise KeyError("campaign does not exist")
        pack_ids = {binding.pack_id for cid, binding in self.campaign_content_bindings.items() if cid == campaign_id}
        packs = tuple(pack for (pack_id, _), pack in self.published_packs.items() if pack_id in pack_ids)
        backup = await export_event_history(self.store, campaign_id=campaign_id, content_packs=packs)
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, result={"campaign_id": campaign_id, "backup": backup.model_dump(mode="json")})

    def _rebuild_campaign_projection_event(self, event: Any) -> None:
        super()._rebuild_campaign_projection_event(event)
        if event.event_type == "ContentRevisionProposed":
            proposal = ContentRevisionProposal.model_validate(event.payload)
            self.content_revision_proposals[proposal.proposal_id] = proposal
        elif event.event_type == "ContentRevisionDryRunCompleted":
            proposal = self.content_revision_proposals.get(str(event.payload["proposal_id"]))
            if proposal is not None:
                proposal.report = CompatibilityReport.model_validate(event.payload["compatibility_report"]) if event.payload.get("compatibility_report") else None
                proposal.impact_report = CampaignImpactReport.model_validate(event.payload["impact_report"])
                proposal.migration_plan = ContentMigrationPlan.model_validate(event.payload["migration_plan"])
                proposal.status = str(event.payload["status"])
        elif event.event_type == "CampaignContentRevisionActivated":
            proposal = self.content_revision_proposals.get(str(event.payload.get("proposal_id", "")))
            if proposal is not None:
                proposal.status = "activated"
                proposal.pre_activation_checkpoint_id = str(event.payload["pre_activation_checkpoint_id"])
        elif event.event_type == "CampaignContentRevisionRolledBack":
            self.campaign_content_bindings[event.campaign_id] = CampaignContentBinding(campaign_id=event.campaign_id, pack_id=str(event.payload["pack_id"]), version=str(event.payload["to_version"]), content_hash=str(event.payload["new_content_hash"]), activated_sequence=event.sequence)
            proposal = self.content_revision_proposals.get(str(event.payload.get("proposal_id", "")))
            if proposal is not None:
                proposal.status = "rolled_back"

    async def replay_snapshot(self, campaign_id: str) -> dict[str, Any]:
        snapshot = await super().replay_snapshot(campaign_id)
        binding = snapshot.get("content_binding")
        for event in await self.store.read_all():
            if event.campaign_id == campaign_id and event.event_type == "CampaignContentRevisionRolledBack":
                binding = CampaignContentBinding(campaign_id=campaign_id, pack_id=str(event.payload["pack_id"]), version=str(event.payload["to_version"]), content_hash=str(event.payload["new_content_hash"]), activated_sequence=event.sequence).model_dump(mode="json")
        snapshot["content_binding"] = binding
        return snapshot
