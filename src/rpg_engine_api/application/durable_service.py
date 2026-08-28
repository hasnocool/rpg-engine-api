import logging
import time
from typing import Any

from rpg_engine_api.application.production_service import ProductionEngineService
from rpg_engine_api.domain.authoring import AuthoringWorkspace, PublishedContentPack
from rpg_engine_api.domain.commands import CommandEnvelope, CommandReceipt, CommandStatus, PrincipalContext
from rpg_engine_api.domain.encounter import EncounterStatus
from rpg_engine_api.domain.timeline import DecisionWindow, TimelineRuntime, WindowStatus
from rpg_engine_api.infrastructure.metrics import RuntimeMetrics

logger = logging.getLogger("rpg_engine_api.commands")


class DurableEngineService(ProductionEngineService):
    """Production service with durable creator, scheduler and operational state."""

    AUTHORING_COMMANDS = frozenset({"CreateAuthoringWorkspace", "UpsertDraftDefinition", "ValidateAuthoringWorkspace", "PublishAuthoringWorkspace"})
    OWNER_COMMANDS = ProductionEngineService.OWNER_COMMANDS | {"ScheduleCampaignEvent", "CancelScheduledCampaignEvent"}

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
        handlers = {"ScheduleCampaignEvent": self._schedule_campaign_event, "CancelScheduledCampaignEvent": self._cancel_scheduled_campaign_event}
        handler = handlers.get(command.command_type)
        receipt = await handler(command, principal) if handler is not None else await super()._dispatch(command, principal)
        if receipt.status == CommandStatus.ACCEPTED and command.command_type in self.AUTHORING_COMMANDS:
            await self._persist_authoring_result(command, receipt)
        return receipt

    async def _start_encounter(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        receipt = await super()._start_encounter(command, principal)
        return self._merge_receipts(receipt, await self._persist_decision_window(command, str(receipt.result["encounter_id"])))

    async def _perform_action(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        receipt = await super()._perform_action(command, principal)
        encounter_id = str(receipt.result.get("encounter_id", command.payload.get("encounter_id", "")))
        return self._merge_receipts(receipt, await self._persist_decision_window(command, encounter_id))

    async def _create_checkpoint(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        receipt = await super()._create_checkpoint(command, principal)
        campaign_id = str(receipt.result["campaign_id"])
        checkpoint_id = str(receipt.result["checkpoint_id"])
        save_snapshot = getattr(self.store, "save_snapshot", None)
        if save_snapshot is not None:
            last_sequence = await self.store.last_sequence(campaign_id=campaign_id)
            await save_snapshot(f"checkpoint:{checkpoint_id}", stream_version=last_sequence, schema_version="1.0", value=self.live_snapshot(campaign_id))
        return receipt

    async def _advance_simulation_time(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        receipt = await super()._advance_simulation_time(command, principal)
        campaign_id = command.campaign_id or str(command.payload.get("campaign_id", ""))
        timeline = self._ensure_timeline(campaign_id)
        extra_ids: list[str] = []
        extra_versions: dict[str, int] = {}
        triggered: list[dict[str, object]] = []
        for item in timeline.consume_due_items():
            fact = await self._record_campaign_fact(command, "ScheduledEventTriggered", {"schedule_id": item.schedule_id, "kind": item.kind, "payload": item.payload, "simulation_time": item.simulation_time, "priority": item.priority})
            extra_ids.extend(fact.emitted_event_ids)
            extra_versions.update(fact.stream_versions)
            triggered.append({"schedule_id": item.schedule_id, "kind": item.kind, "payload": item.payload})
        for encounter_id, encounter in sorted(self.encounters.items()):
            if encounter.campaign_id == campaign_id:
                fact = await self._persist_decision_window(command, encounter_id)
                extra_ids.extend(fact.emitted_event_ids)
                extra_versions.update(fact.stream_versions)
        return receipt.model_copy(update={"emitted_event_ids": receipt.emitted_event_ids + tuple(extra_ids), "stream_versions": {**receipt.stream_versions, **extra_versions}, "result": {**receipt.result, "triggered_scheduled_events": triggered}})

    async def _schedule_campaign_event(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal
        campaign_id = command.campaign_id or str(command.payload.get("campaign_id", ""))
        if campaign_id not in self.campaigns:
            raise KeyError("campaign does not exist")
        timeline = self._ensure_timeline(campaign_id)
        simulation_time = int(command.payload["simulation_time"]) if command.payload.get("simulation_time") is not None else timeline.clock.now + int(command.payload.get("delay", 0))
        item = timeline.clock.schedule(simulation_time, str(command.payload.get("kind", "world_event")), dict(command.payload.get("event_payload", {})), priority=int(command.payload.get("priority", 100)))
        receipt = await self._record_campaign_fact(command, "CampaignEventScheduled", {"schedule_id": item.schedule_id, "simulation_time": item.simulation_time, "kind": item.kind, "payload": item.payload, "priority": item.priority})
        return receipt.model_copy(update={"result": {**receipt.result, "schedule_id": item.schedule_id, "simulation_time": item.simulation_time, "kind": item.kind}})

    async def _cancel_scheduled_campaign_event(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal
        campaign_id = command.campaign_id or str(command.payload.get("campaign_id", ""))
        timeline = self._ensure_timeline(campaign_id)
        schedule_id = str(command.payload.get("schedule_id", ""))
        if not schedule_id or not timeline.clock.cancel(schedule_id):
            raise KeyError("scheduled event does not exist or is no longer pending")
        receipt = await self._record_campaign_fact(command, "CampaignEventCancelled", {"schedule_id": schedule_id})
        return receipt.model_copy(update={"result": {**receipt.result, "schedule_id": schedule_id}})

    async def _persist_decision_window(self, command: CommandEnvelope, encounter_id: str) -> CommandReceipt:
        encounter = self.encounters.get(encounter_id)
        if encounter is None:
            return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED)
        active = encounter.status == EncounterStatus.ACTIVE
        window = None
        if active:
            timeline = self._ensure_timeline(encounter.campaign_id)
            window_id = self.encounter_window_ids.get(encounter_id)
            if window_id is not None:
                window = timeline.windows.get(window_id)
        return await self._record_campaign_fact(command, "DecisionWindowStateRecorded", {"encounter_id": encounter_id, "active": bool(active and window is not None), "window": window.model_dump(mode="json") if window is not None else None})

    @staticmethod
    def _merge_receipts(primary: CommandReceipt, extra: CommandReceipt) -> CommandReceipt:
        return primary.model_copy(update={"emitted_event_ids": primary.emitted_event_ids + extra.emitted_event_ids, "stream_versions": {**primary.stream_versions, **extra.stream_versions}, "result": {**primary.result, **extra.result}})

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
        events = await self.store.read_all()
        self._restore_timeline_runtime(events)
        save_checkpoint = getattr(self.store, "save_projection_checkpoint", None)
        if save_checkpoint is not None:
            await save_checkpoint("runtime", schema_version="1.0", last_sequence=events[-1].sequence if events else 0)

    def _restore_timeline_runtime(self, events: tuple[Any, ...]) -> None:
        latest_windows: dict[str, dict[str, object]] = {}
        scheduled: dict[str, dict[str, object]] = {}
        for event in events:
            if event.event_type == "DecisionWindowStateRecorded":
                latest_windows[str(event.payload["encounter_id"])] = dict(event.payload)
            elif event.event_type == "CampaignEventScheduled":
                scheduled[str(event.payload["schedule_id"])] = {"campaign_id": event.campaign_id, **dict(event.payload)}
            elif event.event_type in {"CampaignEventCancelled", "ScheduledEventTriggered"}:
                scheduled.pop(str(event.payload["schedule_id"]), None)
        for campaign_id, current in list(self.timelines.items()):
            replacement = TimelineRuntime(mode=current.mode, start=current.clock.now, default_decision_duration=current.default_decision_duration, timeout_policy=current.timeout_policy)
            if current.clock.paused:
                replacement.clock.pause()
            self.timelines[campaign_id] = replacement
        self.encounter_window_ids.clear()
        for item in sorted(scheduled.values(), key=lambda value: (int(value["simulation_time"]), str(value["schedule_id"]))):
            campaign_id = str(item["campaign_id"])
            timeline = self._ensure_timeline(campaign_id)
            simulation_time = int(item["simulation_time"])
            if simulation_time >= timeline.clock.now:
                timeline.clock.schedule(simulation_time, str(item["kind"]), dict(item.get("payload", {})), priority=int(item.get("priority", 100)), schedule_id=str(item["schedule_id"]))
        for encounter_id, encounter in sorted(self.encounters.items()):
            if encounter.status != EncounterStatus.ACTIVE:
                continue
            record = latest_windows.get(encounter_id)
            if record and record.get("active") and record.get("window"):
                window = DecisionWindow.model_validate(record["window"])
                timeline = self._ensure_timeline(encounter.campaign_id)
                if window.deadline_at is not None and window.deadline_at < timeline.clock.now and window.status == WindowStatus.OPEN:
                    window.status = WindowStatus.EXPIRED
                timeline.restore_window(window)
                self.encounter_window_ids[encounter_id] = window.window_id
            else:
                self._open_current_window(encounter_id)
