import hashlib
import json
from typing import Any

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
from rpg_engine_api.domain.controllers import ControllerAssignment
from rpg_engine_api.domain.dice import DeterministicRng
from rpg_engine_api.domain.events import DomainEvent
from rpg_engine_api.domain.ids import new_id
from rpg_engine_api.persistence.event_store import InMemoryEventStore, StreamVersionConflict


class EngineService:
    """Small authoritative command processor used by the initial P0/P1 slice."""

    def __init__(self, store: InMemoryEventStore | None = None) -> None:
        self.store = store or InMemoryEventStore()
        self.campaigns: dict[str, CampaignState] = {}
        self.actors: dict[str, ActorState] = {}
        self._rng: dict[str, DeterministicRng] = {}

    async def execute(
        self,
        command: CommandEnvelope,
        principal: PrincipalContext,
    ) -> CommandReceipt:
        idempotency_key = command.idempotency_key or command.command_id
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
        except (KeyError, ValueError) as exc:
            receipt = CommandReceipt(
                command_id=command.command_id,
                status=CommandStatus.REJECTED,
                error=CommandError(code=ErrorCode.INVALID_CHOICE, message=str(exc)),
            )
        await self.store.save_receipt(idempotency_key, receipt)
        return receipt

    async def _dispatch(
        self,
        command: CommandEnvelope,
        principal: PrincipalContext,
    ) -> CommandReceipt:
        handlers = {
            "CreateCampaign": self._create_campaign,
            "CreateActor": self._create_actor,
            "RollDice": self._roll_dice,
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
            raise ValueError("campaign does not exist")
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
            stream_versions={
                stream_id: stored[0].stream_version,
                campaign_stream: campaign_events[0].stream_version,
            },
            result={"campaign_id": campaign_id, "actor_id": actor_id},
        )

    async def _roll_dice(
        self, command: CommandEnvelope, principal: PrincipalContext
    ) -> CommandReceipt:
        del principal
        campaign_id = command.campaign_id or str(command.payload.get("campaign_id", ""))
        if campaign_id not in self.campaigns:
            raise ValueError("campaign does not exist")
        rng = self._rng[campaign_id]
        result = rng.roll(str(command.payload.get("expression", "1d20")), stream="dice")
        stream_id = f"campaign:{campaign_id}"
        actual = await self.store.current_version(stream_id)
        expected = command.expected_stream_version if command.expected_stream_version is not None else actual
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

    def campaign_projection(self, campaign_id: str) -> dict[str, Any]:
        state = self.campaigns[campaign_id]
        return {
            "data": state.model_dump(mode="json"),
            "meta": {"projection_schema_version": "1.0", "projection_sequence": state.stream_version},
        }

    def actor_projection(self, actor_id: str) -> dict[str, Any]:
        state = self.actors[actor_id]
        return {
            "data": state.model_dump(mode="json"),
            "meta": {"projection_schema_version": "1.0", "projection_sequence": state.stream_version},
        }

    def available_actions(self, actor_id: str) -> list[dict[str, Any]]:
        actor = self.actors[actor_id]
        return [
            {
                "action_id": "roll_check",
                "label": "Roll a check",
                "command_type": "RollDice",
                "campaign_id": actor.campaign_id,
                "actor_id": actor.actor_id,
                "payload_schema": {"expression": "1d20", "purpose": "generic_check"},
            }
        ]

    async def canonical_hash(self, campaign_id: str) -> str:
        snapshot = await self.replay_snapshot(campaign_id)
        encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    async def replay_snapshot(self, campaign_id: str) -> dict[str, Any]:
        campaign: CampaignState | None = None
        actors: dict[str, ActorState] = {}
        for event in await self.store.read_all():
            if event.campaign_id != campaign_id:
                continue
            if event.stream_id.startswith("campaign:"):
                campaign = reduce_campaign(campaign, event)
            elif event.stream_id.startswith("actor:"):
                actor_id = event.stream_id.split(":", 1)[1]
                actors[actor_id] = reduce_actor(actors.get(actor_id), event)
        if campaign is None:
            raise KeyError(campaign_id)
        return {
            "campaign": campaign.model_dump(mode="json"),
            "actors": {key: value.model_dump(mode="json") for key, value in sorted(actors.items())},
        }
