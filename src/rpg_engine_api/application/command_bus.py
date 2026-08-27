import asyncio
import hashlib
import json
from typing import Any

from rpg_engine_api.controllers.simple_npc import SimpleNpcController
from rpg_engine_api.domain.actor import ActorState, reduce_actor
from rpg_engine_api.domain.campaign import CampaignState, reduce_campaign
from rpg_engine_api.domain.commands import (
    CommandEnvelope,
    CommandError,
    CommandReceipt,
    CommandStatus,
    ErrorCode,
    PrincipalContext,
)
from rpg_engine_api.domain.controllers import ControllerAssignment, ControllerType
from rpg_engine_api.domain.dice import DeterministicRng
from rpg_engine_api.domain.encounter import EncounterState, EncounterStatus, reduce_encounter
from rpg_engine_api.domain.events import DomainEvent
from rpg_engine_api.domain.ids import new_id
from rpg_engine_api.persistence.event_store import InMemoryEventStore, StreamVersionConflict


class EngineService:
    """Authoritative deterministic command processor for the initial playable slices."""

    def __init__(self, store: InMemoryEventStore | None = None) -> None:
        self.store = store or InMemoryEventStore()
        self.campaigns: dict[str, CampaignState] = {}
        self.actors: dict[str, ActorState] = {}
        self.encounters: dict[str, EncounterState] = {}
        self._rng: dict[str, DeterministicRng] = {}
        self._command_lock = asyncio.Lock()

    async def execute(
        self,
        command: CommandEnvelope,
        principal: PrincipalContext,
        *,
        drive_controllers: bool = True,
    ) -> CommandReceipt:
        idempotency_key = command.idempotency_key or command.command_id
        async with self._command_lock:
            previous = await self.store.get_receipt(idempotency_key)
            if previous is not None:
                return previous.model_copy(update={"status": CommandStatus.ALREADY_PROCESSED})
            try:
                receipt = await self._dispatch(command, principal)
            except StreamVersionConflict as exc:
                receipt = CommandReceipt(
                    command_id=command.command_id,
                    status=CommandStatus.CONFLICT,
                    error=CommandError(
                        code=ErrorCode.STATE_CONFLICT,
                        message=str(exc),
                        details={"stream_id": exc.stream_id, "expected": exc.expected, "actual": exc.actual},
                    ),
                )
            except KeyError as exc:
                receipt = CommandReceipt(
                    command_id=command.command_id,
                    status=CommandStatus.REJECTED,
                    error=CommandError(code=ErrorCode.NOT_FOUND, message=str(exc)),
                )
            except ValueError as exc:
                receipt = CommandReceipt(
                    command_id=command.command_id,
                    status=CommandStatus.REJECTED,
                    error=CommandError(code=ErrorCode.INVALID_CHOICE, message=str(exc)),
                )
            await self.store.save_receipt(idempotency_key, receipt)

        if drive_controllers and receipt.status == CommandStatus.ACCEPTED:
            encounter_id = receipt.result.get("encounter_id")
            if isinstance(encounter_id, str):
                automatic = await self._drive_simple_npcs(encounter_id)
                if automatic:
                    receipt = receipt.model_copy(
                        update={"result": {**receipt.result, "automatic_controller_actions": automatic}}
                    )
        return receipt

    async def _dispatch(
        self, command: CommandEnvelope, principal: PrincipalContext
    ) -> CommandReceipt:
        handlers = {
            "CreateCampaign": self._create_campaign,
            "CreateActor": self._create_actor,
            "RollDice": self._roll_dice,
            "StartEncounter": self._start_encounter,
            "PerformAction": self._perform_action,
        }
        handler = handlers.get(command.command_type)
        if handler is None:
            return CommandReceipt(
                command_id=command.command_id,
                status=CommandStatus.REJECTED,
                error=CommandError(
                    code=ErrorCode.ACTION_NOT_AVAILABLE,
                    message=f"unsupported command type: {command.command_type}",
                ),
            )
        return await handler(command, principal)

    async def _create_campaign(
        self, command: CommandEnvelope, principal: PrincipalContext
    ) -> CommandReceipt:
        campaign_id = str(command.payload.get("campaign_id") or command.campaign_id or new_id("cmp"))
        if campaign_id in self.campaigns:
            raise ValueError("campaign already exists")
        stream_id = f"campaign:{campaign_id}"
        expected = command.expected_stream_version if command.expected_stream_version is not None else 0
        event = DomainEvent(
            event_type="CampaignCreated",
            campaign_id=campaign_id,
            stream_id=stream_id,
            command_id=command.command_id,
            correlation_id=command.command_id,
            payload={
                "name": str(command.payload.get("name", "Untitled Campaign")),
                "seed": command.payload.get("seed", 1),
                "owner_id": principal.principal_id,
            },
        )
        stored = await self.store.append(stream_id, expected, (event,))
        state = reduce_campaign(None, stored[0])
        self.campaigns[campaign_id] = state
        self._rng[campaign_id] = DeterministicRng(state.seed)
        return CommandReceipt(
            command_id=command.command_id,
            status=CommandStatus.ACCEPTED,
            emitted_event_ids=(stored[0].event_id,),
            stream_versions={stream_id: stored[0].stream_version},
            result={"campaign_id": campaign_id},
        )

    async def _create_actor(
        self, command: CommandEnvelope, principal: PrincipalContext
    ) -> CommandReceipt:
        del principal
        campaign_id = command.campaign_id or str(command.payload.get("campaign_id", ""))
        if campaign_id not in self.campaigns:
            raise KeyError("campaign does not exist")
        actor_id = str(command.payload.get("actor_id") or command.actor_id or new_id("act"))
        if actor_id in self.actors:
            raise ValueError("actor already exists")
        controller = ControllerAssignment.model_validate(command.payload.get("controller", {}))
        stream_id = f"actor:{actor_id}"
        expected = command.expected_stream_version if command.expected_stream_version is not None else 0
        event = DomainEvent(
            event_type="ActorCreated",
            campaign_id=campaign_id,
            stream_id=stream_id,
            actor_id=actor_id,
            command_id=command.command_id,
            correlation_id=command.command_id,
            payload={
                "actor_id": actor_id,
                "name": str(command.payload.get("name", "Unnamed Actor")),
                "controller": controller.model_dump(mode="json"),
                "max_hp": int(command.payload.get("max_hp", 10)),
                "attack_bonus": int(command.payload.get("attack_bonus", 2)),
                "defense": int(command.payload.get("defense", 10)),
            },
        )
        stored = await self.store.append(stream_id, expected, (event,))
        actor = reduce_actor(None, stored[0])
        self.actors[actor_id] = actor
        campaign_stream = f"campaign:{campaign_id}"
        campaign_version = await self.store.current_version(campaign_stream)
        registration = DomainEvent(
            event_type="ActorRegistered",
            campaign_id=campaign_id,
            stream_id=campaign_stream,
            actor_id=actor_id,
            command_id=command.command_id,
            causation_id=stored[0].event_id,
            correlation_id=command.command_id,
            payload={"actor_id": actor_id},
        )
        campaign_events = await self.store.append(campaign_stream, campaign_version, (registration,))
        self.campaigns[campaign_id] = reduce_campaign(self.campaigns[campaign_id], campaign_events[0])
        return CommandReceipt(
            command_id=command.command_id,
            status=CommandStatus.ACCEPTED,
            emitted_event_ids=(stored[0].event_id, campaign_events[0].event_id),
            stream_versions={stream_id: stored[0].stream_version, campaign_stream: campaign_events[0].stream_version},
            result={"campaign_id": campaign_id, "actor_id": actor_id},
        )

    async def _roll_dice(
        self, command: CommandEnvelope, principal: PrincipalContext
    ) -> CommandReceipt:
        del principal
        campaign_id = command.campaign_id or str(command.payload.get("campaign_id", ""))
        if campaign_id not in self.campaigns:
            raise KeyError("campaign does not exist")
        stream_id = f"campaign:{campaign_id}"
        actual = await self.store.current_version(stream_id)
        expected = command.expected_stream_version if command.expected_stream_version is not None else actual
        if expected != actual:
            raise StreamVersionConflict(stream_id, expected, actual)
        result = self._rng[campaign_id].roll(str(command.payload.get("expression", "1d20")), stream="dice")
        event = DomainEvent(
            event_type="DiceRolled",
            campaign_id=campaign_id,
            stream_id=stream_id,
            actor_id=command.actor_id,
            command_id=command.command_id,
            correlation_id=command.command_id,
            payload={
                "expression": result.expression,
                "rolls": result.rolls,
                "modifier": result.modifier,
                "total": result.total,
                "purpose": str(command.payload.get("purpose", "generic_check")),
                "rng_stream": result.rng_stream,
                "rng_sequence": result.rng_sequence,
            },
        )
        stored = await self.store.append(stream_id, expected, (event,))
        self.campaigns[campaign_id] = reduce_campaign(self.campaigns[campaign_id], stored[0])
        return CommandReceipt(
            command_id=command.command_id,
            status=CommandStatus.ACCEPTED,
            emitted_event_ids=(stored[0].event_id,),
            stream_versions={stream_id: stored[0].stream_version},
            result={"dice": stored[0].payload},
        )

    async def _start_encounter(
        self, command: CommandEnvelope, principal: PrincipalContext
    ) -> CommandReceipt:
        del principal
        campaign_id = command.campaign_id or str(command.payload.get("campaign_id", ""))
        if campaign_id not in self.campaigns:
            raise KeyError("campaign does not exist")
        encounter_id = str(command.payload.get("encounter_id") or new_id("enc"))
        if encounter_id in self.encounters:
            raise ValueError("encounter already exists")
        raw_participants = command.payload.get("participants")
        if not isinstance(raw_participants, list) or len(raw_participants) < 2:
            raise ValueError("encounter requires at least two participants")
        participants: list[dict[str, object]] = []
        sides: set[str] = set()
        for index, raw in enumerate(raw_participants):
            if not isinstance(raw, dict):
                raise ValueError("participant entries must be objects")
            actor_id = str(raw["actor_id"])
            actor = self.actors.get(actor_id)
            if actor is None or actor.campaign_id != campaign_id:
                raise ValueError(f"actor {actor_id} is not in campaign")
            side = str(raw.get("side", "side_a" if index == 0 else "side_b"))
            sides.add(side)
            participants.append(
                {
                    "actor_id": actor_id,
                    "side": side,
                    "hp": actor.max_hp,
                    "max_hp": actor.max_hp,
                    "position": int(raw.get("position", index * 2)),
                    "stamina": int(raw.get("stamina", 1)),
                    "guard": 0,
                }
            )
        if len(sides) < 2:
            raise ValueError("encounter requires at least two opposing sides")
        stream_id = f"encounter:{encounter_id}"
        event = DomainEvent(
            event_type="EncounterStarted",
            campaign_id=campaign_id,
            stream_id=stream_id,
            command_id=command.command_id,
            correlation_id=command.command_id,
            payload={
                "encounter_id": encounter_id,
                "participants": participants,
                "turn_order": [item["actor_id"] for item in participants],
            },
        )
        stored = await self.store.append(stream_id, 0, (event,))
        self.encounters[encounter_id] = reduce_encounter(None, stored[0])
        return CommandReceipt(
            command_id=command.command_id,
            status=CommandStatus.ACCEPTED,
            emitted_event_ids=(stored[0].event_id,),
            stream_versions={stream_id: stored[0].stream_version},
            result={"campaign_id": campaign_id, "encounter_id": encounter_id},
        )

    async def _perform_action(
        self, command: CommandEnvelope, principal: PrincipalContext
    ) -> CommandReceipt:
        del principal
        encounter_id = str(command.payload.get("encounter_id", ""))
        encounter = self.encounters.get(encounter_id)
        if encounter is None:
            raise KeyError("encounter does not exist")
        actor_id = command.actor_id or str(command.payload.get("actor_id", ""))
        if encounter.current_actor_id != actor_id:
            raise ValueError("actor is not ready")
        legal = self.available_actions(actor_id)
        action_id = str(command.payload.get("action_id", ""))
        target_id = command.payload.get("target_id")
        candidates = [
            action for action in legal
            if action["action_id"] == action_id
            and (target_id is None or action.get("target_id") == target_id)
        ]
        if not candidates:
            raise ValueError("action/target is not currently available")

        stream_id = f"encounter:{encounter_id}"
        actual = await self.store.current_version(stream_id)
        expected = command.expected_stream_version if command.expected_stream_version is not None else actual
        if expected != actual:
            raise StreamVersionConflict(stream_id, expected, actual)

        events = self._resolve_action_events(encounter, actor_id, action_id, target_id, command)
        stored = await self.store.append(stream_id, expected, events)
        state = encounter
        for event in stored:
            state = reduce_encounter(state, event)
        self.encounters[encounter_id] = state
        return CommandReceipt(
            command_id=command.command_id,
            status=CommandStatus.ACCEPTED,
            emitted_event_ids=tuple(event.event_id for event in stored),
            stream_versions={stream_id: stored[-1].stream_version},
            result={"campaign_id": encounter.campaign_id, "encounter_id": encounter_id, "action_id": action_id},
        )

    def _resolve_action_events(
        self,
        encounter: EncounterState,
        actor_id: str,
        action_id: str,
        target_id: object,
        command: CommandEnvelope,
    ) -> tuple[DomainEvent, ...]:
        stream_id = f"encounter:{encounter.encounter_id}"
        base = {
            "campaign_id": encounter.campaign_id,
            "stream_id": stream_id,
            "actor_id": actor_id,
            "command_id": command.command_id,
            "correlation_id": command.command_id,
        }
        actor = encounter.participants[actor_id]
        events: list[DomainEvent] = []
        if action_id == "move_toward":
            target = encounter.participants[str(target_id)]
            delta = 1 if target.position > actor.position else -1
            events.append(
                DomainEvent(event_type="ActorMoved", payload={"actor_id": actor_id, "position": actor.position + delta}, **base)
            )
        elif action_id == "guard":
            events.append(DomainEvent(event_type="GuardRaised", payload={"actor_id": actor_id, "guard": 2}, **base))
        elif action_id in {"attack", "power_attack"}:
            target = encounter.participants[str(target_id)]
            attack = self._rng[encounter.campaign_id].roll("1d20", stream="dice")
            attack_total = attack.total + self.actors[actor_id].attack_bonus
            target_defense = self.actors[target.actor_id].defense + target.guard
            hit = attack_total >= target_defense
            damage_expression = "1d6+2" if action_id == "power_attack" else "1d4+1"
            damage_result = self._rng[encounter.campaign_id].roll(damage_expression, stream="dice") if hit else None
            damage = damage_result.total if damage_result else 0
            stamina = actor.stamina - (1 if action_id == "power_attack" else 0)
            events.append(
                DomainEvent(
                    event_type="PowerAttackResolved" if action_id == "power_attack" else "AttackResolved",
                    payload={
                        "actor_id": actor_id,
                        "target_id": target.actor_id,
                        "attack_roll": attack.rolls,
                        "attack_total": attack_total,
                        "target_defense": target_defense,
                        "hit": hit,
                        "damage_roll": damage_result.rolls if damage_result else (),
                        "damage": damage,
                        "target_hp": max(0, target.hp - damage),
                        "attacker_stamina": stamina,
                    },
                    **base,
                )
            )
        else:
            raise ValueError("unknown action")

        preview = encounter
        for event in events:
            preview = reduce_encounter(preview, event)
        alive_sides = {participant.side for participant in preview.participants.values() if participant.alive}
        if len(alive_sides) == 1:
            winner = next(iter(alive_sides))
            events.append(DomainEvent(event_type="EncounterCompleted", payload={"winner_side": winner}, **base))
            return tuple(events)

        next_index, next_round = self._next_living_turn(preview)
        events.append(
            DomainEvent(
                event_type="TurnAdvanced",
                payload={"turn_index": next_index, "round": next_round},
                **base,
            )
        )
        return tuple(events)

    @staticmethod
    def _next_living_turn(encounter: EncounterState) -> tuple[int, int]:
        count = len(encounter.turn_order)
        for step in range(1, count + 1):
            index = (encounter.turn_index + step) % count
            actor_id = encounter.turn_order[index]
            if encounter.participants[actor_id].alive:
                round_number = encounter.round + (1 if index <= encounter.turn_index else 0)
                return index, round_number
        raise ValueError("no living encounter participants")

    async def _drive_simple_npcs(self, encounter_id: str) -> int:
        actions_taken = 0
        while actions_taken < 100:
            encounter = self.encounters.get(encounter_id)
            if encounter is None or encounter.status != EncounterStatus.ACTIVE:
                return actions_taken
            actor_id = encounter.current_actor_id
            if actor_id is None:
                return actions_taken
            actor = self.actors[actor_id]
            if actor.controller.controller_type != ControllerType.SIMPLE_NPC or not actor.controller.enabled:
                return actions_taken
            profile = actor.controller.behavior_profile_ref or "aggressive_melee"
            controller = SimpleNpcController(profile=profile)
            action = controller.choose_action(
                {"actor_id": actor_id, "available_actions": self.available_actions(actor_id)}
            )
            payload = {
                "encounter_id": encounter_id,
                "action_id": action["action_id"],
            }
            if action.get("target_id") is not None:
                payload["target_id"] = action["target_id"]
            receipt = await self.execute(
                CommandEnvelope(
                    command_type="PerformAction",
                    campaign_id=encounter.campaign_id,
                    actor_id=actor_id,
                    idempotency_key=f"npc:{encounter_id}:{encounter.stream_version}:{actor_id}",
                    payload=payload,
                ),
                PrincipalContext(principal_id=f"controller:{actor_id}", roles=frozenset({"controller"})),
                drive_controllers=False,
            )
            if receipt.status != CommandStatus.ACCEPTED:
                raise RuntimeError(f"SimpleNpcController action rejected: {receipt.error}")
            actions_taken += 1
        raise RuntimeError("automatic controller safety limit exceeded")

    def campaign_projection(self, campaign_id: str) -> dict[str, Any]:
        state = self.campaigns[campaign_id]
        return {"data": state.model_dump(mode="json"), "meta": {"projection_schema_version": "1.0", "projection_sequence": state.stream_version}}

    def actor_projection(self, actor_id: str) -> dict[str, Any]:
        state = self.actors[actor_id]
        return {"data": state.model_dump(mode="json"), "meta": {"projection_schema_version": "1.0", "projection_sequence": state.stream_version}}

    def encounter_projection(self, encounter_id: str) -> dict[str, Any]:
        state = self.encounters[encounter_id]
        return {"data": state.model_dump(mode="json"), "meta": {"projection_schema_version": "1.0", "projection_sequence": state.stream_version}}

    def available_actions(self, actor_id: str) -> list[dict[str, Any]]:
        actor = self.actors[actor_id]
        encounter = next(
            (
                value
                for value in self.encounters.values()
                if value.status == EncounterStatus.ACTIVE
                and actor_id in value.participants
                and value.current_actor_id == actor_id
            ),
            None,
        )
        if encounter is None:
            return [{"action_id": "roll_check", "label": "Roll a check", "command_type": "RollDice", "campaign_id": actor.campaign_id, "actor_id": actor.actor_id, "payload_schema": {"expression": "1d20", "purpose": "generic_check"}}]
        participant = encounter.participants[actor_id]
        enemies = sorted(
            (
                item for item in encounter.participants.values()
                if item.alive and item.side != participant.side
            ),
            key=lambda item: (abs(item.position - participant.position), item.actor_id),
        )
        if not enemies:
            return []
        nearest = enemies[0]
        distance = abs(nearest.position - participant.position)
        base = {"command_type": "PerformAction", "campaign_id": actor.campaign_id, "actor_id": actor_id, "encounter_id": encounter.encounter_id}
        actions: list[dict[str, Any]] = []
        if distance > 1:
            actions.append({**base, "action_id": "move_toward", "label": f"Move toward {nearest.actor_id}", "target_id": nearest.actor_id})
        else:
            for enemy in enemies:
                if abs(enemy.position - participant.position) <= 1:
                    actions.append({**base, "action_id": "attack", "label": f"Attack {enemy.actor_id}", "target_id": enemy.actor_id})
                    if participant.stamina > 0:
                        actions.append({**base, "action_id": "power_attack", "label": f"Power attack {enemy.actor_id}", "target_id": enemy.actor_id})
        actions.append({**base, "action_id": "guard", "label": "Guard"})
        return actions

    def live_snapshot(self, campaign_id: str) -> dict[str, Any]:
        campaign = self.campaigns[campaign_id]
        actors = {actor_id: self.actors[actor_id].model_dump(mode="json") for actor_id in sorted(campaign.actor_ids) if actor_id in self.actors}
        encounters = {
            encounter_id: encounter.model_dump(mode="json")
            for encounter_id, encounter in sorted(self.encounters.items())
            if encounter.campaign_id == campaign_id
        }
        return {"campaign": campaign.model_dump(mode="json"), "actors": actors, "encounters": encounters}

    async def canonical_hash(self, campaign_id: str) -> str:
        snapshot = await self.replay_snapshot(campaign_id)
        return hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def live_hash(self, campaign_id: str) -> str:
        return hashlib.sha256(json.dumps(self.live_snapshot(campaign_id), sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    async def replay_snapshot(self, campaign_id: str) -> dict[str, Any]:
        campaign: CampaignState | None = None
        actors: dict[str, ActorState] = {}
        encounters: dict[str, EncounterState] = {}
        for event in await self.store.read_all():
            if event.campaign_id != campaign_id:
                continue
            if event.stream_id.startswith("campaign:"):
                campaign = reduce_campaign(campaign, event)
            elif event.stream_id.startswith("actor:"):
                actor_id = event.stream_id.split(":", 1)[1]
                actors[actor_id] = reduce_actor(actors.get(actor_id), event)
            elif event.stream_id.startswith("encounter:"):
                encounter_id = event.stream_id.split(":", 1)[1]
                encounters[encounter_id] = reduce_encounter(encounters.get(encounter_id), event)
        if campaign is None:
            raise KeyError(campaign_id)
        return {
            "campaign": campaign.model_dump(mode="json"),
            "actors": {key: value.model_dump(mode="json") for key, value in sorted(actors.items())},
            "encounters": {key: value.model_dump(mode="json") for key, value in sorted(encounters.items())},
        }
