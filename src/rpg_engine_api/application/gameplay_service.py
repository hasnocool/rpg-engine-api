from typing import Any

from rpg_engine_api.application.complete_service import CompleteEngineService
from rpg_engine_api.domain.actor import ActorState, reduce_actor
from rpg_engine_api.domain.campaign import reduce_campaign
from rpg_engine_api.domain.commands import CommandEnvelope, CommandReceipt, CommandStatus, PrincipalContext
from rpg_engine_api.domain.controllers import ControllerAssignment
from rpg_engine_api.domain.encounter import EncounterState, EncounterStatus, reduce_encounter
from rpg_engine_api.domain.events import DomainEvent
from rpg_engine_api.domain.ids import new_id


class GameplayEngineService(CompleteEngineService):
    """Persistent actor/combat bridge so encounter outcomes survive outside combat."""

    async def _create_actor(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        campaign_id = command.campaign_id or str(command.payload.get("campaign_id", ""))
        if campaign_id not in self.campaigns:
            raise KeyError("campaign does not exist")
        actor_id = str(command.payload.get("actor_id") or command.actor_id or new_id("act"))
        if actor_id in self.actors:
            raise ValueError("actor already exists")
        controller = ControllerAssignment.model_validate(command.payload.get("controller", {}))
        maximum = int(command.payload.get("max_hp", 10))
        current = max(0, min(maximum, int(command.payload.get("current_hp", maximum))))
        stream_id = f"actor:{actor_id}"
        expected = command.expected_stream_version if command.expected_stream_version is not None else 0
        event = DomainEvent(
            event_type="ActorCreated", campaign_id=campaign_id, stream_id=stream_id,
            actor_id=actor_id, command_id=command.command_id, correlation_id=command.command_id,
            payload={
                "actor_id": actor_id, "name": str(command.payload.get("name", "Unnamed Actor")),
                "controller": controller.model_dump(mode="json"), "max_hp": maximum, "current_hp": current,
                "attack_bonus": int(command.payload.get("attack_bonus", 2)), "defense": int(command.payload.get("defense", 10)),
                "currency": int(command.payload.get("currency", 10)),
            },
        )
        stored = await self.store.append(stream_id, expected, (event,))
        actor = reduce_actor(None, stored[0]); self.actors[actor_id] = actor
        campaign_stream = f"campaign:{campaign_id}"; campaign_version = await self.store.current_version(campaign_stream)
        registration = DomainEvent(event_type="ActorRegistered", campaign_id=campaign_id, stream_id=campaign_stream, actor_id=actor_id, command_id=command.command_id, causation_id=stored[0].event_id, correlation_id=command.command_id, payload={"actor_id": actor_id, "created_by": principal.principal_id})
        campaign_events = await self.store.append(campaign_stream, campaign_version, (registration,)); self.campaigns[campaign_id] = reduce_campaign(self.campaigns[campaign_id], campaign_events[0])
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=(stored[0].event_id, campaign_events[0].event_id), stream_versions={stream_id: stored[0].stream_version, campaign_stream: campaign_events[0].stream_version}, result={"campaign_id": campaign_id, "actor_id": actor_id})

    async def _start_encounter(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal
        campaign_id = command.campaign_id or str(command.payload.get("campaign_id", ""))
        if campaign_id not in self.campaigns: raise KeyError("campaign does not exist")
        encounter_id = str(command.payload.get("encounter_id") or new_id("enc"))
        if encounter_id in self.encounters: raise ValueError("encounter already exists")
        raw_participants = command.payload.get("participants")
        if not isinstance(raw_participants, list) or len(raw_participants) < 2: raise ValueError("encounter requires at least two participants")
        participants: list[dict[str, object]] = []; sides: set[str] = set()
        for index, raw in enumerate(raw_participants):
            if not isinstance(raw, dict): raise ValueError("participant entries must be objects")
            actor_id = str(raw["actor_id"]); actor = self.actors.get(actor_id)
            if actor is None or actor.campaign_id != campaign_id: raise ValueError(f"actor {actor_id} is not in campaign")
            if actor.current_hp <= 0: raise ValueError(f"actor {actor_id} is not conscious enough to enter encounter")
            side = str(raw.get("side", "side_a" if index == 0 else "side_b")); sides.add(side)
            stamina = int(raw.get("stamina", actor.resources.get("stamina", 1)))
            max_stamina = int(raw.get("max_stamina", actor.resource_maxima.get("stamina", max(1, stamina))))
            participants.append({"actor_id": actor_id, "side": side, "hp": actor.current_hp, "max_hp": actor.max_hp, "position": int(raw.get("position", index * 2)), "stamina": stamina, "max_stamina": max(1, max_stamina), "guard": 0, "conditions": list(actor.conditions)})
        if len(sides) < 2: raise ValueError("encounter requires at least two opposing sides")
        stream_id = f"encounter:{encounter_id}"
        event = DomainEvent(event_type="EncounterStarted", campaign_id=campaign_id, stream_id=stream_id, command_id=command.command_id, correlation_id=command.command_id, payload={"encounter_id": encounter_id, "participants": participants, "turn_order": [item["actor_id"] for item in participants]})
        stored = await self.store.append(stream_id, 0, (event,)); self.encounters[encounter_id] = reduce_encounter(None, stored[0]); self._ensure_timeline(campaign_id); self._open_current_window(encounter_id)
        receipt = CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=(stored[0].event_id,), stream_versions={stream_id: stored[0].stream_version}, result={"campaign_id": campaign_id, "encounter_id": encounter_id})
        return self._merge_receipts(receipt, await self._persist_decision_window(command, encounter_id))

    async def _grant_encounter_rewards(self, encounter: EncounterState, command_id: str) -> tuple[tuple[str, ...], dict[str, int]]:
        requests: list[tuple[str, int, tuple[DomainEvent, ...]]] = []
        for participant in sorted(encounter.participants.values(), key=lambda item: item.actor_id):
            actor = self.actors[participant.actor_id]; stream = f"actor:{actor.actor_id}"; events: list[DomainEvent] = []
            events.append(DomainEvent(event_type="ActorEncounterStateSynchronized", campaign_id=actor.campaign_id, stream_id=stream, actor_id=actor.actor_id, command_id=command_id, correlation_id=command_id, payload={"current_hp": max(0, participant.hp), "source": f"encounter:{encounter.encounter_id}"}))
            if "stamina" in actor.resource_maxima:
                events.append(DomainEvent(event_type="ActorResourceChanged", campaign_id=actor.campaign_id, stream_id=stream, actor_id=actor.actor_id, command_id=command_id, correlation_id=command_id, payload={"resource_id": "stamina", "current": max(0, participant.stamina), "source": f"encounter:{encounter.encounter_id}"}))
            if participant.alive and participant.side == encounter.winner_side:
                events.append(DomainEvent(event_type="ExperienceGranted", campaign_id=actor.campaign_id, stream_id=stream, actor_id=actor.actor_id, command_id=command_id, correlation_id=command_id, payload={"experience": 100, "progression_points": 1, "new_level": max(actor.level, 2), "source": f"encounter:{encounter.encounter_id}"}))
            requests.append((stream, await self.store.current_version(stream), tuple(events)))
        if not requests: return (), {}
        stored = await self.store.append_many(tuple(requests)); event_ids: list[str] = []; versions: dict[str, int] = {}
        for stream, _, _ in requests:
            actor_id = stream.split(":", 1)[1]; state: ActorState = self.actors[actor_id]
            for event in stored[stream]: state = reduce_actor(state, event); event_ids.append(event.event_id)
            self.actors[actor_id] = state; versions[stream] = stored[stream][-1].stream_version
        return tuple(event_ids), versions

    @classmethod
    def capability_projection(cls) -> dict[str, Any]:
        base = super().capability_projection(); data = dict(base["data"]); data["features"] = list(data.get("features", [])) + ["persistent_encounter_health", "encounter_resource_sync", "atomic_encounter_rewards"]
        return {"data": data, "meta": {"schema_version": "1.3"}}
