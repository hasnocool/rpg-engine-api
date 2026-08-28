from collections import deque
from typing import Any

from rpg_engine_api.application.power_service import PowerEngineService
from rpg_engine_api.domain.actor import reduce_actor
from rpg_engine_api.domain.commands import CommandEnvelope, CommandReceipt, CommandStatus, PrincipalContext
from rpg_engine_api.domain.events import DomainEvent
from rpg_engine_api.domain.ids import new_id
from rpg_engine_api.domain.living_world import ContainerState, NpcPersonalityProfile, NpcRuntimeState, NpcScheduleStep, reduce_container, reduce_npc_runtime
from rpg_engine_api.domain.world import reduce_world


class LivingWorldEngineService(PowerEngineService):
    """NPC routines and reusable container inventories driven by simulation time."""

    OWNER_COMMANDS = PowerEngineService.OWNER_COMMANDS | {"ConfigureNpcPersonality", "ConfigureNpcSchedule", "CreateContainer", "SetContainerLocked"}
    ACTOR_COMMANDS = PowerEngineService.ACTOR_COMMANDS | {"StoreItemInContainer", "TakeItemFromContainer"}

    def __init__(self, store: Any | None = None) -> None:
        super().__init__(store=store); self.npc_runtimes: dict[str, NpcRuntimeState] = {}; self.containers: dict[str, ContainerState] = {}

    async def _dispatch(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        handlers = {"ConfigureNpcPersonality": self._configure_npc_personality, "ConfigureNpcSchedule": self._configure_npc_schedule, "CreateContainer": self._create_container, "SetContainerLocked": self._set_container_locked, "StoreItemInContainer": self._store_item, "TakeItemFromContainer": self._take_item}
        handler = handlers.get(command.command_type)
        return await handler(command, principal) if handler else await super()._dispatch(command, principal)

    async def _ensure_npc_runtime(self, actor_id: str, command: CommandEnvelope) -> NpcRuntimeState:
        runtime = self.npc_runtimes.get(actor_id)
        if runtime is not None: return runtime
        actor = self.actors.get(actor_id)
        if actor is None: raise KeyError("actor does not exist")
        stream = f"npc_runtime:{actor_id}"; event = DomainEvent(event_type="NpcRuntimeCreated", campaign_id=actor.campaign_id, stream_id=stream, actor_id=actor_id, command_id=command.command_id, correlation_id=command.command_id, payload={"actor_id": actor_id}); stored = await self.store.append(stream, 0, (event,)); runtime = reduce_npc_runtime(None, stored[0]); self.npc_runtimes[actor_id] = runtime; return runtime

    async def _npc_event(self, command: CommandEnvelope, runtime: NpcRuntimeState, event_type: str, payload: dict[str, object]) -> DomainEvent:
        stream = f"npc_runtime:{runtime.actor_id}"; event = DomainEvent(event_type=event_type, campaign_id=runtime.campaign_id, stream_id=stream, actor_id=runtime.actor_id, command_id=command.command_id, correlation_id=command.command_id, payload=payload); stored = await self.store.append(stream, await self.store.current_version(stream), (event,)); self.npc_runtimes[runtime.actor_id] = reduce_npc_runtime(runtime, stored[0]); return stored[0]

    async def _configure_npc_personality(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal; actor_id = command.actor_id or str(command.payload.get("actor_id", "")); runtime = await self._ensure_npc_runtime(actor_id, command); personality = NpcPersonalityProfile.model_validate(command.payload.get("personality", {})); event = await self._npc_event(command, runtime, "NpcPersonalityConfigured", {"personality": personality.model_dump(mode="json")}); return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=(event.event_id,), stream_versions={event.stream_id: event.stream_version}, result={"actor_id": actor_id, "personality": personality.model_dump(mode="json")})

    def _day_length(self, campaign_id: str) -> int:
        environment = next((item for item in self.world_environments.values() if item.campaign_id == campaign_id), None); return environment.day_length if environment else 1440

    async def _configure_npc_schedule(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        actor_id = command.actor_id or str(command.payload.get("actor_id", "")); runtime = await self._ensure_npc_runtime(actor_id, command); raw = command.payload.get("schedule", []); steps = [NpcScheduleStep.model_validate(item) for item in raw]; day_length = self._day_length(runtime.campaign_id)
        if any(step.minute_of_day >= day_length for step in steps): raise ValueError("schedule minute must be inside campaign day length")
        event = await self._npc_event(command, runtime, "NpcScheduleConfigured", {"schedule": [step.model_dump(mode="json") for step in steps]}); emitted = [event.event_id]; versions = {event.stream_id: event.stream_version}; timeline = self._ensure_timeline(runtime.campaign_id)
        for step in steps:
            day_start = (timeline.clock.now // day_length) * day_length; target = day_start + step.minute_of_day
            if target <= timeline.clock.now: target += day_length
            receipt = await self._schedule_campaign_event(CommandEnvelope(command_id=new_id("cmd"), command_type="ScheduleCampaignEvent", campaign_id=runtime.campaign_id, payload={"simulation_time": target, "kind": "npc_schedule", "event_payload": {"actor_id": actor_id, "step_id": step.step_id, "world_id": step.world_id, "location_id": step.location_id, "activity": step.activity}}), principal); emitted.extend(receipt.emitted_event_ids); versions.update(receipt.stream_versions)
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=tuple(emitted), stream_versions=versions, result={"actor_id": actor_id, "schedule_steps": len(steps)})

    @staticmethod
    def _world_path(world: Any, origin: str, destination: str) -> list[str]:
        if origin == destination: return [origin]
        queue = deque([(origin, [origin])]); seen = {origin}
        while queue:
            node, path = queue.popleft()
            for nxt in sorted(world.locations[node].connections):
                if nxt in seen: continue
                if nxt == destination: return path + [nxt]
                seen.add(nxt); queue.append((nxt, path + [nxt]))
        raise ValueError("NPC schedule destination is unreachable")

    async def _execute_schedule_step(self, command: CommandEnvelope, payload: dict[str, object], principal: PrincipalContext) -> CommandReceipt:
        actor_id = str(payload["actor_id"]); runtime = self.npc_runtimes.get(actor_id)
        if runtime is None: raise KeyError("NPC runtime does not exist")
        world_id = str(payload["world_id"]); world = self.worlds.get(world_id)
        if world is None: raise KeyError("scheduled NPC world does not exist")
        current = world.actor_locations.get(actor_id)
        if current is None: raise ValueError("scheduled NPC is not placed in world")
        destination = str(payload["location_id"]); path = self._world_path(world, current, destination); wstream = f"world:{world_id}"; nstream = f"npc_runtime:{actor_id}"; world_events: list[DomainEvent] = []
        for origin, target in zip(path, path[1:]): world_events.append(DomainEvent(event_type="ActorTravelled", campaign_id=runtime.campaign_id, stream_id=wstream, actor_id=actor_id, command_id=command.command_id, correlation_id=command.command_id, payload={"origin_id": origin, "destination_id": target, "schedule_step_id": str(payload["step_id"])}))
        npc_event = DomainEvent(event_type="NpcScheduleStepCompleted", campaign_id=runtime.campaign_id, stream_id=nstream, actor_id=actor_id, command_id=command.command_id, correlation_id=command.command_id, payload={"step_id": str(payload["step_id"]), "simulation_time": self._ensure_timeline(runtime.campaign_id).clock.now, "location_id": destination, "activity": str(payload.get("activity", "idle"))})
        requests: list[tuple[str, int, tuple[DomainEvent, ...]]] = [(nstream, await self.store.current_version(nstream), (npc_event,))]
        if world_events: requests.insert(0, (wstream, await self.store.current_version(wstream), tuple(world_events)))
        stored = await self.store.append_many(tuple(requests)); state = world
        for event in stored.get(wstream, ()): state = reduce_world(state, event)
        self.worlds[world_id] = state; self.npc_runtimes[actor_id] = reduce_npc_runtime(runtime, stored[nstream][0]); emitted = tuple(event.event_id for stream in requests for event in stored[stream[0]]); versions = {stream_id: events[-1].stream_version for stream_id, events in stored.items()}
        day_length = self._day_length(runtime.campaign_id); next_time = self._ensure_timeline(runtime.campaign_id).clock.now + day_length; scheduled = await self._schedule_campaign_event(CommandEnvelope(command_id=new_id("cmd"), command_type="ScheduleCampaignEvent", campaign_id=runtime.campaign_id, payload={"simulation_time": next_time, "kind": "npc_schedule", "event_payload": dict(payload)}), principal)
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=emitted + scheduled.emitted_event_ids, stream_versions={**versions, **scheduled.stream_versions}, result={"actor_id": actor_id, "location_id": destination, "activity": payload.get("activity", "idle")})

    async def _advance_simulation_time(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        receipt = await super()._advance_simulation_time(command, principal); emitted = list(receipt.emitted_event_ids); versions = dict(receipt.stream_versions); completed = []
        for item in receipt.result.get("triggered_scheduled_events", []):
            if isinstance(item, dict) and item.get("kind") == "npc_schedule":
                child = await self._execute_schedule_step(CommandEnvelope(command_id=new_id("cmd"), command_type="ExecuteNpcScheduleStep", campaign_id=command.campaign_id, payload={}), dict(item.get("payload", {})), principal); emitted.extend(child.emitted_event_ids); versions.update(child.stream_versions); completed.append(child.result)
        return receipt.model_copy(update={"emitted_event_ids": tuple(emitted), "stream_versions": versions, "result": {**receipt.result, "npc_schedule_steps": completed}})

    async def _create_container(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal; campaign_id = command.campaign_id or str(command.payload.get("campaign_id", "")); container_id = str(command.payload.get("container_id") or new_id("container")); stream = f"container:{container_id}"
        event = DomainEvent(event_type="ContainerCreated", campaign_id=campaign_id, stream_id=stream, command_id=command.command_id, correlation_id=command.command_id, payload={"container_id": container_id, "name": str(command.payload.get("name", "Container")), "owner_actor_id": command.payload.get("owner_actor_id"), "world_id": command.payload.get("world_id"), "location_id": command.payload.get("location_id"), "items": list(command.payload.get("items", [])), "locked": bool(command.payload.get("locked", False))}); stored = await self.store.append(stream, 0, (event,)); self.containers[container_id] = reduce_container(None, stored[0]); return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=(stored[0].event_id,), stream_versions={stream: 1}, result={"container_id": container_id, "campaign_id": campaign_id})

    async def _set_container_locked(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal; container = self.containers.get(str(command.payload.get("container_id", "")))
        if container is None: raise KeyError("container does not exist")
        stream = f"container:{container.container_id}"; event = DomainEvent(event_type="ContainerLockChanged", campaign_id=container.campaign_id, stream_id=stream, command_id=command.command_id, correlation_id=command.command_id, payload={"locked": bool(command.payload.get("locked", True))}); stored = await self.store.append(stream, await self.store.current_version(stream), (event,)); self.containers[container.container_id] = reduce_container(container, stored[0]); return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=(stored[0].event_id,), stream_versions={stream: stored[0].stream_version}, result={"container_id": container.container_id, "locked": self.containers[container.container_id].locked})

    async def _transfer_container_item(self, command: CommandEnvelope, *, take: bool) -> CommandReceipt:
        actor_id = command.actor_id or str(command.payload.get("actor_id", "")); actor = self.actors.get(actor_id); container = self.containers.get(str(command.payload.get("container_id", ""))); item_id = str(command.payload.get("item_id", ""))
        if actor is None or container is None: raise KeyError("actor or container does not exist")
        if actor.campaign_id != container.campaign_id: raise ValueError("actor and container are in different campaigns")
        if container.locked: raise ValueError("container is locked")
        if take and item_id not in container.items: raise ValueError("item is not in container")
        if not take and item_id not in actor.inventory: raise ValueError("actor does not own item")
        astream = f"actor:{actor_id}"; cstream = f"container:{container.container_id}"
        actor_event = DomainEvent(event_type="ItemGranted" if take else "ItemStored", campaign_id=actor.campaign_id, stream_id=astream, actor_id=actor_id, command_id=command.command_id, correlation_id=command.command_id, payload={"item_id": item_id, "container_id": container.container_id})
        container_event = DomainEvent(event_type="ItemTakenFromContainer" if take else "ItemStoredInContainer", campaign_id=actor.campaign_id, stream_id=cstream, actor_id=actor_id, command_id=command.command_id, correlation_id=command.command_id, payload={"item_id": item_id, "actor_id": actor_id})
        stored = await self.store.append_many(((astream, await self.store.current_version(astream), (actor_event,)), (cstream, await self.store.current_version(cstream), (container_event,)))); self.actors[actor_id] = reduce_actor(actor, stored[astream][0]); self.containers[container.container_id] = reduce_container(container, stored[cstream][0]); events = stored[astream] + stored[cstream]
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=tuple(event.event_id for event in events), stream_versions={astream: stored[astream][-1].stream_version, cstream: stored[cstream][-1].stream_version}, result={"actor_id": actor_id, "container_id": container.container_id, "item_id": item_id, "direction": "take" if take else "store"})

    async def _store_item(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt: del principal; return await self._transfer_container_item(command, take=False)
    async def _take_item(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt: del principal; return await self._transfer_container_item(command, take=True)

    async def rebuild_from_store(self) -> None:
        await super().rebuild_from_store(); self.npc_runtimes.clear(); self.containers.clear()
        for event in await self.store.read_all():
            if event.stream_id.startswith("npc_runtime:"):
                actor_id = event.stream_id.split(":", 1)[1]; self.npc_runtimes[actor_id] = reduce_npc_runtime(self.npc_runtimes.get(actor_id), event)
            elif event.stream_id.startswith("container:"):
                container_id = event.stream_id.split(":", 1)[1]; self.containers[container_id] = reduce_container(self.containers.get(container_id), event)

    def live_snapshot(self, campaign_id: str) -> dict[str, Any]:
        snapshot = super().live_snapshot(campaign_id); snapshot["npc_runtimes"] = {key: value.model_dump(mode="json") for key, value in sorted(self.npc_runtimes.items()) if value.campaign_id == campaign_id}; snapshot["containers"] = {key: value.model_dump(mode="json") for key, value in sorted(self.containers.items()) if value.campaign_id == campaign_id}; return snapshot

    async def replay_snapshot(self, campaign_id: str) -> dict[str, Any]:
        snapshot = await super().replay_snapshot(campaign_id); npcs: dict[str, NpcRuntimeState] = {}; containers: dict[str, ContainerState] = {}
        for event in await self.store.read_all():
            if event.campaign_id != campaign_id: continue
            if event.stream_id.startswith("npc_runtime:"):
                key = event.stream_id.split(":", 1)[1]; npcs[key] = reduce_npc_runtime(npcs.get(key), event)
            elif event.stream_id.startswith("container:"):
                key = event.stream_id.split(":", 1)[1]; containers[key] = reduce_container(containers.get(key), event)
        snapshot["npc_runtimes"] = {key: value.model_dump(mode="json") for key, value in sorted(npcs.items())}; snapshot["containers"] = {key: value.model_dump(mode="json") for key, value in sorted(containers.items())}; return snapshot

    @classmethod
    def capability_projection(cls) -> dict[str, Any]:
        base = super().capability_projection(); data = dict(base["data"]); data["features"] = list(data.get("features", [])) + ["npc_personality", "recurring_npc_schedules", "scheduled_world_movement", "inventory_containers", "atomic_container_transfer"]; return {"data": data, "meta": {"schema_version": "1.5"}}
