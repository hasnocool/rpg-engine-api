from collections import Counter
from typing import Any

from rpg_engine_api.application.command_bus import EngineService
from rpg_engine_api.domain.actor import reduce_actor
from rpg_engine_api.domain.checkpoints import CampaignCheckpoint
from rpg_engine_api.domain.commands import CommandEnvelope, CommandReceipt, CommandStatus, PrincipalContext
from rpg_engine_api.domain.events import DomainEvent
from rpg_engine_api.domain.ids import new_id
from rpg_engine_api.domain.quest import QuestState, QuestStatus, reduce_quest
from rpg_engine_api.domain.session import GameSessionState, SessionStatus, reduce_session


class PlatformEngineService(EngineService):
    """Composition layer for campaign/session/social/economy operations."""

    def __init__(self) -> None:
        super().__init__()
        self.sessions: dict[str, GameSessionState] = {}
        self.quests: dict[str, QuestState] = {}
        self.checkpoints: dict[str, CampaignCheckpoint] = {}

    async def _dispatch(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        handlers = {
            "CreateGameSession": self._create_game_session,
            "JoinGameSession": self._join_game_session,
            "SetSessionReady": self._set_session_ready,
            "GrantActorControl": self._grant_actor_control,
            "OpenGameSession": self._open_game_session,
            "CloseGameSession": self._close_game_session,
            "TalkToNpc": self._talk_to_npc,
            "CreateQuest": self._create_quest,
            "AcceptQuest": self._accept_quest,
            "CompleteQuest": self._complete_quest,
            "TradeItem": self._trade_item,
            "CreateCheckpoint": self._create_checkpoint,
        }
        handler = handlers.get(command.command_type)
        if handler is not None:
            return await handler(command, principal)
        return await super()._dispatch(command, principal)

    async def _append_session_event(
        self,
        session: GameSessionState,
        command: CommandEnvelope,
        event_type: str,
        payload: dict[str, object],
    ) -> CommandReceipt:
        stream_id = f"session:{session.session_id}"
        expected = await self.store.current_version(stream_id)
        event = DomainEvent(
            event_type=event_type,
            campaign_id=session.campaign_id,
            stream_id=stream_id,
            command_id=command.command_id,
            correlation_id=command.command_id,
            payload=payload,
        )
        stored = await self.store.append(stream_id, expected, (event,))
        self.sessions[session.session_id] = reduce_session(session, stored[0])
        return CommandReceipt(
            command_id=command.command_id,
            status=CommandStatus.ACCEPTED,
            emitted_event_ids=(stored[0].event_id,),
            stream_versions={stream_id: stored[0].stream_version},
            result={"campaign_id": session.campaign_id, "session_id": session.session_id},
        )

    async def _create_game_session(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        campaign_id = command.campaign_id or str(command.payload.get("campaign_id", ""))
        if campaign_id not in self.campaigns:
            raise KeyError("campaign does not exist")
        session_id = str(command.payload.get("session_id") or new_id("session"))
        if session_id in self.sessions:
            raise ValueError("session already exists")
        stream_id = f"session:{session_id}"
        event = DomainEvent(
            event_type="GameSessionCreated",
            campaign_id=campaign_id,
            stream_id=stream_id,
            command_id=command.command_id,
            correlation_id=command.command_id,
            payload={"session_id": session_id, "owner_id": principal.principal_id},
        )
        stored = await self.store.append(stream_id, 0, (event,))
        self.sessions[session_id] = reduce_session(None, stored[0])
        return CommandReceipt(
            command_id=command.command_id,
            status=CommandStatus.ACCEPTED,
            emitted_event_ids=(stored[0].event_id,),
            stream_versions={stream_id: stored[0].stream_version},
            result={"campaign_id": campaign_id, "session_id": session_id},
        )

    async def _join_game_session(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        session = self.sessions.get(str(command.payload.get("session_id", "")))
        if session is None:
            raise KeyError("session does not exist")
        if session.status != SessionStatus.LOBBY:
            raise ValueError("session is not accepting lobby joins")
        if principal.principal_id in session.members:
            raise ValueError("principal is already a session member")
        return await self._append_session_event(
            session,
            command,
            "SessionMemberJoined",
            {"principal_id": principal.principal_id, "role": str(command.payload.get("role", "player"))},
        )

    async def _set_session_ready(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        session = self.sessions.get(str(command.payload.get("session_id", "")))
        if session is None:
            raise KeyError("session does not exist")
        if principal.principal_id not in session.members:
            raise ValueError("principal is not a session member")
        return await self._append_session_event(
            session,
            command,
            "SessionReadyChanged",
            {"principal_id": principal.principal_id, "ready": bool(command.payload.get("ready", True))},
        )

    async def _grant_actor_control(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        session = self.sessions.get(str(command.payload.get("session_id", "")))
        if session is None:
            raise KeyError("session does not exist")
        if principal.principal_id != session.owner_id:
            raise ValueError("only session owner can grant actor control")
        actor_id = str(command.payload.get("actor_id", ""))
        controller_principal = str(command.payload.get("principal_id", ""))
        if actor_id not in self.actors or self.actors[actor_id].campaign_id != session.campaign_id:
            raise ValueError("actor is not in session campaign")
        if controller_principal not in session.members:
            raise ValueError("controller principal is not a session member")
        return await self._append_session_event(
            session,
            command,
            "ActorControlGranted",
            {"actor_id": actor_id, "principal_id": controller_principal},
        )

    async def _open_game_session(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        session = self.sessions.get(str(command.payload.get("session_id", "")))
        if session is None:
            raise KeyError("session does not exist")
        if principal.principal_id != session.owner_id:
            raise ValueError("only session owner can open session")
        if not session.members or not all(member.ready for member in session.members.values()):
            raise ValueError("all session members must be ready")
        return await self._append_session_event(session, command, "GameSessionOpened", {})

    async def _close_game_session(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        session = self.sessions.get(str(command.payload.get("session_id", "")))
        if session is None:
            raise KeyError("session does not exist")
        if principal.principal_id != session.owner_id:
            raise ValueError("only session owner can close session")
        if session.status != SessionStatus.OPEN:
            raise ValueError("session is not open")
        return await self._append_session_event(session, command, "GameSessionClosed", {})

    async def _record_campaign_fact(
        self,
        command: CommandEnvelope,
        event_type: str,
        payload: dict[str, object],
        *,
        actor_id: str | None = None,
    ) -> CommandReceipt:
        campaign_id = command.campaign_id or str(command.payload.get("campaign_id", ""))
        if campaign_id not in self.campaigns:
            raise KeyError("campaign does not exist")
        stream_id = f"campaign:{campaign_id}"
        expected = await self.store.current_version(stream_id)
        event = DomainEvent(
            event_type=event_type,
            campaign_id=campaign_id,
            stream_id=stream_id,
            actor_id=actor_id,
            command_id=command.command_id,
            correlation_id=command.command_id,
            payload=payload,
        )
        stored = await self.store.append(stream_id, expected, (event,))
        from rpg_engine_api.domain.campaign import reduce_campaign

        self.campaigns[campaign_id] = reduce_campaign(self.campaigns[campaign_id], stored[0])
        return CommandReceipt(
            command_id=command.command_id,
            status=CommandStatus.ACCEPTED,
            emitted_event_ids=(stored[0].event_id,),
            stream_versions={stream_id: stored[0].stream_version},
            result={"campaign_id": campaign_id},
        )

    async def _talk_to_npc(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal
        actor_id = command.actor_id or str(command.payload.get("actor_id", ""))
        npc_id = str(command.payload.get("npc_id", ""))
        if actor_id not in self.actors or npc_id not in self.actors:
            raise ValueError("social interaction actors must exist")
        return await self._record_campaign_fact(
            command,
            "SocialInteractionRecorded",
            {"actor_id": actor_id, "npc_id": npc_id, "topic": str(command.payload.get("topic", "general"))},
            actor_id=actor_id,
        )

    async def _create_quest(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal
        campaign_id = command.campaign_id or str(command.payload.get("campaign_id", ""))
        if campaign_id not in self.campaigns:
            raise KeyError("campaign does not exist")
        quest_id = str(command.payload.get("quest_id") or new_id("quest"))
        if quest_id in self.quests:
            raise ValueError("quest already exists")
        stream_id = f"quest:{quest_id}"
        event = DomainEvent(
            event_type="QuestCreated",
            campaign_id=campaign_id,
            stream_id=stream_id,
            command_id=command.command_id,
            correlation_id=command.command_id,
            payload={"quest_id": quest_id, "title": str(command.payload.get("title", "Untitled Quest")), "objective": str(command.payload.get("objective", "Complete the objective"))},
        )
        stored = await self.store.append(stream_id, 0, (event,))
        self.quests[quest_id] = reduce_quest(None, stored[0])
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=(stored[0].event_id,), stream_versions={stream_id: stored[0].stream_version}, result={"campaign_id": campaign_id, "quest_id": quest_id})

    async def _accept_quest(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal
        quest = self.quests.get(str(command.payload.get("quest_id", "")))
        if quest is None:
            raise KeyError("quest does not exist")
        if quest.status != QuestStatus.AVAILABLE:
            raise ValueError("quest is not available")
        actor_id = command.actor_id or str(command.payload.get("actor_id", ""))
        if actor_id not in self.actors or self.actors[actor_id].campaign_id != quest.campaign_id:
            raise ValueError("actor is not eligible for quest")
        stream_id = f"quest:{quest.quest_id}"
        expected = await self.store.current_version(stream_id)
        event = DomainEvent(event_type="QuestAccepted", campaign_id=quest.campaign_id, stream_id=stream_id, actor_id=actor_id, command_id=command.command_id, correlation_id=command.command_id, payload={"actor_id": actor_id})
        stored = await self.store.append(stream_id, expected, (event,))
        self.quests[quest.quest_id] = reduce_quest(quest, stored[0])
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=(stored[0].event_id,), stream_versions={stream_id: stored[0].stream_version}, result={"campaign_id": quest.campaign_id, "quest_id": quest.quest_id, "actor_id": actor_id})

    async def _complete_quest(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal
        quest = self.quests.get(str(command.payload.get("quest_id", "")))
        if quest is None:
            raise KeyError("quest does not exist")
        if quest.status != QuestStatus.ACCEPTED:
            raise ValueError("quest is not accepted")
        required_encounter = command.payload.get("required_encounter_id")
        if required_encounter is not None:
            encounter = self.encounters.get(str(required_encounter))
            if encounter is None or encounter.status.value != "completed":
                raise ValueError("required encounter is not completed")
        stream_id = f"quest:{quest.quest_id}"
        expected = await self.store.current_version(stream_id)
        event = DomainEvent(event_type="QuestCompleted", campaign_id=quest.campaign_id, stream_id=stream_id, actor_id=quest.actor_id, command_id=command.command_id, correlation_id=command.command_id, payload={"quest_id": quest.quest_id, "required_encounter_id": required_encounter})
        stored = await self.store.append(stream_id, expected, (event,))
        self.quests[quest.quest_id] = reduce_quest(quest, stored[0])
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=(stored[0].event_id,), stream_versions={stream_id: stored[0].stream_version}, result={"campaign_id": quest.campaign_id, "quest_id": quest.quest_id})

    async def _trade_item(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal
        actor_id = command.actor_id or str(command.payload.get("actor_id", ""))
        actor = self.actors.get(actor_id)
        if actor is None:
            raise KeyError("actor does not exist")
        item_id = str(command.payload.get("item_id", ""))
        price = int(command.payload.get("price", 0))
        if not item_id or price < 0:
            raise ValueError("trade requires item and non-negative price")
        if actor.currency < price:
            raise ValueError("insufficient currency")
        stream_id = f"actor:{actor_id}"
        expected = await self.store.current_version(stream_id)
        event = DomainEvent(event_type="ItemPurchased", campaign_id=actor.campaign_id, stream_id=stream_id, actor_id=actor_id, command_id=command.command_id, correlation_id=command.command_id, payload={"item_id": item_id, "price": price, "currency_after": actor.currency - price, "vendor_id": str(command.payload.get("vendor_id", "vendor"))})
        stored = await self.store.append(stream_id, expected, (event,))
        self.actors[actor_id] = reduce_actor(actor, stored[0])
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=(stored[0].event_id,), stream_versions={stream_id: stored[0].stream_version}, result={"campaign_id": actor.campaign_id, "actor_id": actor_id, "item_id": item_id, "currency_after": actor.currency - price})

    async def _create_checkpoint(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        campaign_id = command.campaign_id or str(command.payload.get("campaign_id", ""))
        if campaign_id not in self.campaigns:
            raise KeyError("campaign does not exist")
        checkpoint_id = str(command.payload.get("checkpoint_id") or new_id("checkpoint"))
        if checkpoint_id in self.checkpoints:
            raise ValueError("checkpoint already exists")
        events_before = await self.store.read_all()
        source_sequence = events_before[-1].sequence if events_before else 0
        stream_id = f"campaign:{campaign_id}"
        expected = await self.store.current_version(stream_id)
        event = DomainEvent(event_type="CheckpointCreated", campaign_id=campaign_id, stream_id=stream_id, command_id=command.command_id, correlation_id=command.command_id, payload={"checkpoint_id": checkpoint_id, "name": str(command.payload.get("name", "Checkpoint")), "source_sequence": source_sequence, "created_by": principal.principal_id})
        stored = await self.store.append(stream_id, expected, (event,))
        from rpg_engine_api.domain.campaign import reduce_campaign

        self.campaigns[campaign_id] = reduce_campaign(self.campaigns[campaign_id], stored[0])
        self.checkpoints[checkpoint_id] = CampaignCheckpoint(checkpoint_id=checkpoint_id, campaign_id=campaign_id, name=str(command.payload.get("name", "Checkpoint")), source_sequence=source_sequence, created_by=principal.principal_id)
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=(stored[0].event_id,), stream_versions={stream_id: stored[0].stream_version}, result={"campaign_id": campaign_id, "checkpoint_id": checkpoint_id, "source_sequence": source_sequence})

    def session_projection(self, session_id: str) -> dict[str, Any]:
        state = self.sessions[session_id]
        return {"data": state.model_dump(mode="json"), "meta": {"projection_schema_version": "1.0", "projection_sequence": state.stream_version}}

    def quest_projection(self, quest_id: str) -> dict[str, Any]:
        state = self.quests[quest_id]
        return {"data": state.model_dump(mode="json"), "meta": {"projection_schema_version": "1.0", "projection_sequence": state.stream_version}}

    def checkpoint_projection(self, checkpoint_id: str) -> dict[str, Any]:
        return {"data": self.checkpoints[checkpoint_id].model_dump(mode="json"), "meta": {"projection_schema_version": "1.0"}}

    async def session_recap(self, session_id: str) -> dict[str, Any]:
        session = self.sessions[session_id]
        start = session.opened_at_sequence or 0
        end = session.closed_at_sequence or 2**63 - 1
        events = [event for event in await self.store.read_all() if event.campaign_id == session.campaign_id and start <= event.sequence <= end]
        counts = Counter(event.event_type for event in events)
        return {
            "schema_version": "1.0",
            "session_id": session_id,
            "campaign_id": session.campaign_id,
            "event_sequence_start": start,
            "event_sequence_end": session.closed_at_sequence,
            "event_count": len(events),
            "event_type_counts": dict(sorted(counts.items())),
            "actors": sorted({event.actor_id for event in events if event.actor_id}),
        }

    def live_snapshot(self, campaign_id: str) -> dict[str, Any]:
        snapshot = super().live_snapshot(campaign_id)
        snapshot["sessions"] = {key: value.model_dump(mode="json") for key, value in sorted(self.sessions.items()) if value.campaign_id == campaign_id}
        snapshot["quests"] = {key: value.model_dump(mode="json") for key, value in sorted(self.quests.items()) if value.campaign_id == campaign_id}
        snapshot["checkpoints"] = {key: value.model_dump(mode="json") for key, value in sorted(self.checkpoints.items()) if value.campaign_id == campaign_id}
        return snapshot

    async def replay_snapshot(self, campaign_id: str) -> dict[str, Any]:
        snapshot = await super().replay_snapshot(campaign_id)
        sessions: dict[str, GameSessionState] = {}
        quests: dict[str, QuestState] = {}
        checkpoints: dict[str, CampaignCheckpoint] = {}
        for event in await self.store.read_all():
            if event.campaign_id != campaign_id:
                continue
            if event.stream_id.startswith("session:"):
                session_id = event.stream_id.split(":", 1)[1]
                sessions[session_id] = reduce_session(sessions.get(session_id), event)
            elif event.stream_id.startswith("quest:"):
                quest_id = event.stream_id.split(":", 1)[1]
                quests[quest_id] = reduce_quest(quests.get(quest_id), event)
            elif event.event_type == "CheckpointCreated":
                checkpoint_id = str(event.payload["checkpoint_id"])
                checkpoints[checkpoint_id] = CampaignCheckpoint(checkpoint_id=checkpoint_id, campaign_id=campaign_id, name=str(event.payload["name"]), source_sequence=int(event.payload["source_sequence"]), created_by=str(event.payload["created_by"]))
        snapshot["sessions"] = {key: value.model_dump(mode="json") for key, value in sorted(sessions.items())}
        snapshot["quests"] = {key: value.model_dump(mode="json") for key, value in sorted(quests.items())}
        snapshot["checkpoints"] = {key: value.model_dump(mode="json") for key, value in sorted(checkpoints.items())}
        return snapshot
