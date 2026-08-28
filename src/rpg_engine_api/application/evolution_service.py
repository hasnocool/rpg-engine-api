from typing import Any

from rpg_engine_api.application.full_service import FullEngineService
from rpg_engine_api.domain.commands import CommandEnvelope, CommandReceipt, CommandStatus, PrincipalContext
from rpg_engine_api.domain.content_evolution import (
    CampaignContentBinding,
    CompatibilityReport,
    ContentRevisionDiff,
    ContentRevisionProposal,
)
from rpg_engine_api.domain.events import DomainEvent
from rpg_engine_api.domain.ids import new_id


class EvolutionEngineService(FullEngineService):
    """Minimal explicit campaign content-binding/evolution workflow.

    This establishes the P7 transport/domain seam. It deliberately rejects removals of
    definitions in the baseline automatic path rather than pretending arbitrary state
    migration is safe.
    """

    def __init__(self) -> None:
        super().__init__()
        self.campaign_content_bindings: dict[str, CampaignContentBinding] = {}
        self.content_revision_proposals: dict[str, ContentRevisionProposal] = {}

    async def _dispatch(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        handlers = {
            "BindCampaignContent": self._bind_campaign_content,
            "ProposeContentRevision": self._propose_content_revision,
            "DryRunContentRevision": self._dry_run_content_revision,
            "ActivateContentRevision": self._activate_content_revision,
        }
        handler = handlers.get(command.command_type)
        if handler is not None:
            return await handler(command, principal)
        return await super()._dispatch(command, principal)

    def _diff(self, pack_id: str, from_version: str, to_version: str) -> ContentRevisionDiff:
        old = self._pack(pack_id, from_version)
        new = self._pack(pack_id, to_version)
        old_map = {item.key: item for item in old.definitions}
        new_map = {item.key: item for item in new.definitions}
        old_keys = set(old_map)
        new_keys = set(new_map)
        changed = sorted(
            key
            for key in old_keys & new_keys
            if old_map[key].model_dump(mode="json") != new_map[key].model_dump(mode="json")
        )
        return ContentRevisionDiff(
            pack_id=pack_id,
            from_version=from_version,
            to_version=to_version,
            added_keys=sorted(new_keys - old_keys),
            removed_keys=sorted(old_keys - new_keys),
            changed_keys=changed,
        )

    async def _append_campaign_content_event(
        self,
        command: CommandEnvelope,
        campaign_id: str,
        event_type: str,
        payload: dict[str, object],
    ) -> DomainEvent:
        stream_id = f"campaign:{campaign_id}"
        expected = await self.store.current_version(stream_id)
        event = DomainEvent(
            event_type=event_type,
            campaign_id=campaign_id,
            stream_id=stream_id,
            command_id=command.command_id,
            correlation_id=command.command_id,
            payload=payload,
        )
        stored = await self.store.append(stream_id, expected, (event,))
        from rpg_engine_api.domain.campaign import reduce_campaign
        self.campaigns[campaign_id] = reduce_campaign(self.campaigns[campaign_id], stored[0])
        return stored[0]

    async def _bind_campaign_content(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal
        campaign_id = command.campaign_id or str(command.payload.get("campaign_id", ""))
        if campaign_id not in self.campaigns:
            raise KeyError("campaign does not exist")
        if campaign_id in self.campaign_content_bindings:
            raise ValueError("campaign already has a content binding; use revision workflow")
        pack = self._pack(str(command.payload.get("pack_id", "")), str(command.payload.get("version", "")))
        event = await self._append_campaign_content_event(
            command,
            campaign_id,
            "CampaignContentBound",
            {"pack_id": pack.pack_id, "version": pack.version, "content_hash": pack.content_hash},
        )
        self.campaign_content_bindings[campaign_id] = CampaignContentBinding(
            campaign_id=campaign_id,
            pack_id=pack.pack_id,
            version=pack.version,
            content_hash=pack.content_hash,
            activated_sequence=event.sequence,
        )
        return CommandReceipt(
            command_id=command.command_id,
            status=CommandStatus.ACCEPTED,
            emitted_event_ids=(event.event_id,),
            stream_versions={event.stream_id: event.stream_version},
            result={"campaign_id": campaign_id, "pack_id": pack.pack_id, "version": pack.version},
        )

    async def _propose_content_revision(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal
        campaign_id = command.campaign_id or str(command.payload.get("campaign_id", ""))
        binding = self.campaign_content_bindings.get(campaign_id)
        if binding is None:
            raise ValueError("campaign has no bound content pack")
        to_version = str(command.payload.get("to_version", ""))
        self._pack(binding.pack_id, to_version)
        proposal_id = str(command.payload.get("proposal_id") or new_id("contentrev"))
        proposal = ContentRevisionProposal(
            proposal_id=proposal_id,
            campaign_id=campaign_id,
            pack_id=binding.pack_id,
            from_version=binding.version,
            to_version=to_version,
        )
        self.content_revision_proposals[proposal_id] = proposal
        return CommandReceipt(
            command_id=command.command_id,
            status=CommandStatus.ACCEPTED,
            result={"proposal_id": proposal_id, "campaign_id": campaign_id, "from_version": binding.version, "to_version": to_version},
        )

    async def _dry_run_content_revision(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal
        proposal_id = str(command.payload.get("proposal_id", ""))
        proposal = self.content_revision_proposals.get(proposal_id)
        if proposal is None:
            raise KeyError("content revision proposal does not exist")
        diff = self._diff(proposal.pack_id, proposal.from_version, proposal.to_version)
        reasons: list[str] = []
        if diff.removed_keys:
            reasons.append("baseline automatic migration refuses removed definitions")
        report = CompatibilityReport(
            campaign_id=proposal.campaign_id,
            pack_id=proposal.pack_id,
            from_version=proposal.from_version,
            to_version=proposal.to_version,
            compatible=not reasons,
            requires_branch=bool(reasons),
            reasons=reasons,
            diff=diff,
        )
        proposal.report = report
        proposal.status = "validated" if report.compatible else "requires_branch"
        return CommandReceipt(
            command_id=command.command_id,
            status=CommandStatus.ACCEPTED,
            result={"proposal_id": proposal_id, "compatibility_report": report.model_dump(mode="json")},
        )

    async def _activate_content_revision(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        proposal_id = str(command.payload.get("proposal_id", ""))
        proposal = self.content_revision_proposals.get(proposal_id)
        if proposal is None:
            raise KeyError("content revision proposal does not exist")
        if proposal.report is None:
            raise ValueError("content revision must be dry-run before activation")
        if not proposal.report.compatible:
            raise ValueError("content revision is not safe for direct activation; branch/migration required")
        checkpoint_id = str(command.payload.get("checkpoint_id") or new_id("checkpoint"))
        checkpoint_receipt = await self._create_checkpoint(
            CommandEnvelope(
                command_id=new_id("cmd"),
                command_type="CreateCheckpoint",
                campaign_id=proposal.campaign_id,
                payload={"checkpoint_id": checkpoint_id, "name": f"Before content {proposal.to_version}"},
            ),
            principal,
        )
        target = self._pack(proposal.pack_id, proposal.to_version)
        event = await self._append_campaign_content_event(
            command,
            proposal.campaign_id,
            "CampaignContentRevisionActivated",
            {
                "proposal_id": proposal_id,
                "pack_id": proposal.pack_id,
                "from_version": proposal.from_version,
                "to_version": proposal.to_version,
                "old_content_hash": self.campaign_content_bindings[proposal.campaign_id].content_hash,
                "new_content_hash": target.content_hash,
                "pre_activation_checkpoint_id": checkpoint_id,
            },
        )
        self.campaign_content_bindings[proposal.campaign_id] = CampaignContentBinding(
            campaign_id=proposal.campaign_id,
            pack_id=proposal.pack_id,
            version=proposal.to_version,
            content_hash=target.content_hash,
            activated_sequence=event.sequence,
        )
        proposal.status = "activated"
        proposal.pre_activation_checkpoint_id = checkpoint_id
        return CommandReceipt(
            command_id=command.command_id,
            status=CommandStatus.ACCEPTED,
            emitted_event_ids=checkpoint_receipt.emitted_event_ids + (event.event_id,),
            stream_versions={**checkpoint_receipt.stream_versions, event.stream_id: event.stream_version},
            result={
                "proposal_id": proposal_id,
                "campaign_id": proposal.campaign_id,
                "version": proposal.to_version,
                "checkpoint_id": checkpoint_id,
            },
        )

    def content_binding_projection(self, campaign_id: str) -> dict[str, Any]:
        return {"data": self.campaign_content_bindings[campaign_id].model_dump(mode="json"), "meta": {"schema_version": "1.0"}}

    def content_revision_projection(self, proposal_id: str) -> dict[str, Any]:
        return {"data": self.content_revision_proposals[proposal_id].model_dump(mode="json"), "meta": {"schema_version": "1.0"}}

    def live_snapshot(self, campaign_id: str) -> dict[str, Any]:
        snapshot = super().live_snapshot(campaign_id)
        binding = self.campaign_content_bindings.get(campaign_id)
        snapshot["content_binding"] = binding.model_dump(mode="json") if binding else None
        return snapshot

    async def replay_snapshot(self, campaign_id: str) -> dict[str, Any]:
        snapshot = await super().replay_snapshot(campaign_id)
        binding: CampaignContentBinding | None = None
        for event in await self.store.read_all():
            if event.campaign_id != campaign_id:
                continue
            if event.event_type == "CampaignContentBound":
                binding = CampaignContentBinding(
                    campaign_id=campaign_id,
                    pack_id=str(event.payload["pack_id"]),
                    version=str(event.payload["version"]),
                    content_hash=str(event.payload["content_hash"]),
                    activated_sequence=event.sequence,
                )
            elif event.event_type == "CampaignContentRevisionActivated":
                binding = CampaignContentBinding(
                    campaign_id=campaign_id,
                    pack_id=str(event.payload["pack_id"]),
                    version=str(event.payload["to_version"]),
                    content_hash=str(event.payload["new_content_hash"]),
                    activated_sequence=event.sequence,
                )
        snapshot["content_binding"] = binding.model_dump(mode="json") if binding else None
        return snapshot
