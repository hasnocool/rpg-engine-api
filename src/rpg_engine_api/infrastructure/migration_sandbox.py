from __future__ import annotations

from typing import Any, Callable

from rpg_engine_api.domain.commands import CommandEnvelope, PrincipalContext
from rpg_engine_api.infrastructure.backup import export_event_history, restore_event_history
from rpg_engine_api.persistence.event_store import InMemoryEventStore
from rpg_engine_api.simulation.quality import analyze_pack


async def run_content_migration_sandbox(engine: Any, proposal_id: str, engine_factory: Callable[..., Any]) -> dict[str, Any]:
    """Clone one campaign into an isolated in-memory runtime and validate a revision there."""
    proposal = engine.content_revision_proposals.get(proposal_id)
    if proposal is None:
        raise KeyError("content revision proposal does not exist")
    campaign_id = proposal.campaign_id
    packs = tuple(
        pack
        for (pack_id, _), pack in sorted(engine.published_packs.items())
        if pack_id == proposal.pack_id
    )
    backup = await export_event_history(engine.store, campaign_id=campaign_id, content_packs=packs)
    sandbox_store = InMemoryEventStore()
    await restore_event_history(backup, sandbox_store, require_empty=True)
    for pack in packs:
        await sandbox_store.save_content_pack(pack.model_dump(mode="json"))

    sandbox = engine_factory(store=sandbox_store)
    await sandbox.rebuild_from_store()
    before_live = sandbox.live_hash(campaign_id)
    before_replay = await sandbox.canonical_hash(campaign_id)
    target_pack = sandbox._pack(proposal.pack_id, proposal.to_version)
    quality = analyze_pack(target_pack)

    activation_status = "not_attempted"
    activation_error: str | None = None
    post_live = before_live
    post_replay = before_replay
    binding_version = sandbox.campaign_content_bindings.get(campaign_id).version if campaign_id in sandbox.campaign_content_bindings else None
    sandbox_proposal = sandbox.content_revision_proposals.get(proposal_id)
    compatible = bool(sandbox_proposal and sandbox_proposal.report and sandbox_proposal.report.compatible)
    if compatible and quality.valid:
        campaign = sandbox.campaigns[campaign_id]
        receipt = await sandbox.execute(
            CommandEnvelope(command_type="ActivateContentRevision", campaign_id=campaign_id, payload={"proposal_id": proposal_id}),
            PrincipalContext(principal_id=campaign.owner_id, roles=frozenset({"owner"})),
            drive_controllers=False,
        )
        activation_status = receipt.status.value
        activation_error = receipt.error.message if receipt.error else None
        post_live = sandbox.live_hash(campaign_id)
        post_replay = await sandbox.canonical_hash(campaign_id)
        binding = sandbox.campaign_content_bindings.get(campaign_id)
        binding_version = binding.version if binding else None

    return {
        "schema_version": "1.0",
        "campaign_id": campaign_id,
        "proposal_id": proposal_id,
        "restored_events": len(backup.events),
        "pre_replay_matches_live": before_live == before_replay,
        "target_quality": {
            "valid": quality.valid,
            "findings": [finding.model_dump(mode="json") for finding in quality.findings],
        },
        "compatible": compatible,
        "activation_status": activation_status,
        "activation_error": activation_error,
        "post_replay_matches_live": post_live == post_replay,
        "target_binding_version": binding_version,
        "isolated": True,
    }
