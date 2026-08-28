from typing import Any

from rpg_engine_api.application.advanced_service import AdvancedEngineService
from rpg_engine_api.domain.actor import reduce_actor
from rpg_engine_api.domain.branches import CampaignBranch
from rpg_engine_api.domain.campaign import reduce_campaign
from rpg_engine_api.domain.character_creation import reduce_character_creation
from rpg_engine_api.domain.commands import CommandEnvelope, CommandError, CommandReceipt, CommandStatus, ErrorCode, PrincipalContext
from rpg_engine_api.domain.content_evolution import CampaignContentBinding
from rpg_engine_api.domain.controllers import ControllerType
from rpg_engine_api.domain.dialogue import DialogueDefinition, DialogueSession, DialogueSessionStatus
from rpg_engine_api.domain.dice import DeterministicRng
from rpg_engine_api.domain.encounter import EncounterStatus, reduce_encounter
from rpg_engine_api.domain.quest import reduce_quest
from rpg_engine_api.domain.session import SessionStatus, reduce_session
from rpg_engine_api.domain.timeline import TimelineRuntime, TimeoutPolicy, TimingMode
from rpg_engine_api.domain.world import reduce_world
from rpg_engine_api.domain.checkpoints import CampaignCheckpoint


class RecoverableEngineService(AdvancedEngineService):
    """Advanced runtime plus authorization and deterministic restart reconstruction."""

    OWNER_COMMANDS = frozenset({
        "ConfigureCampaignTiming", "AdvanceSimulationTime", "CreateWorld", "PlaceActorInWorld",
        "StartEncounter", "CreateQuest", "CreateCheckpoint", "CreateCampaignBranch",
        "RegisterDialogue", "BindCampaignContent", "ProposeContentRevision", "DryRunContentRevision",
        "ActivateContentRevision", "SetActorController",
    })
    ACTOR_COMMANDS = frozenset({
        "PerformAction", "AdvanceActor", "TravelActor", "SearchLocation", "InteractWorldObject",
        "CraftItem", "StartDialogue", "ChooseDialogue", "ResolveReaction",
    })

    def __init__(self, store: Any | None = None) -> None:
        super().__init__()
        if store is not None:
            self.store = store

    async def execute(self, command: CommandEnvelope, principal: PrincipalContext, *, drive_controllers: bool = True) -> CommandReceipt:
        error = self._authorization_error(command, principal)
        if error is not None:
            return CommandReceipt(command_id=command.command_id, status=CommandStatus.REJECTED, error=error)
        return await super().execute(command, principal, drive_controllers=drive_controllers)

    def _campaign_for_command(self, command: CommandEnvelope) -> str | None:
        if command.campaign_id:
            return command.campaign_id
        payload_campaign = command.payload.get("campaign_id")
        if payload_campaign:
            return str(payload_campaign)
        actor_id = command.actor_id or command.payload.get("actor_id")
        if actor_id and str(actor_id) in self.actors:
            return self.actors[str(actor_id)].campaign_id
        session_id = command.payload.get("session_id")
        if session_id and str(session_id) in self.sessions:
            return self.sessions[str(session_id)].campaign_id
        return None

    def _actor_for_command(self, command: CommandEnvelope) -> str | None:
        actor_id = command.actor_id or command.payload.get("actor_id")
        if actor_id:
            return str(actor_id)
        dialogue_id = command.payload.get("dialogue_session_id")
        if dialogue_id and str(dialogue_id) in self.dialogue_sessions:
            return self.dialogue_sessions[str(dialogue_id)].actor_id
        return None

    @staticmethod
    def _privileged(principal: PrincipalContext) -> bool:
        return bool(principal.roles & {"dm", "owner", "admin", "service"})

    def _authorization_error(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandError | None:
        campaign_id = self._campaign_for_command(command)
        campaign = self.campaigns.get(campaign_id or "")
        if command.command_type in self.OWNER_COMMANDS and campaign is not None:
            if principal.principal_id != campaign.owner_id and not self._privileged(principal):
                return CommandError(code=ErrorCode.FORBIDDEN, message="command requires campaign owner or DM privilege", details={"campaign_id": campaign.campaign_id, "command_type": command.command_type})

        actor_id = self._actor_for_command(command)
        if command.command_type not in self.ACTOR_COMMANDS or actor_id is None:
            return None
        actor = self.actors.get(actor_id)
        if actor is None:
            return None
        if "controller" in principal.roles and principal.principal_id == f"controller:{actor_id}":
            if actor.controller.enabled and actor.controller.controller_type != ControllerType.HUMAN:
                return None
        if campaign is not None and (principal.principal_id == campaign.owner_id or self._privileged(principal)):
            return None
        active_sessions = [session for session in self.sessions.values() if session.campaign_id == actor.campaign_id and session.status in {SessionStatus.OPEN, SessionStatus.PAUSED}]
        if not active_sessions:
            return None
        for session in active_sessions:
            granted = session.actor_controls.get(actor_id)
            if granted == principal.principal_id:
                return None
        return CommandError(code=ErrorCode.FORBIDDEN, message="principal does not control this actor in the active session", details={"actor_id": actor_id, "campaign_id": actor.campaign_id})

    async def _register_dialogue(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        campaign_id = command.campaign_id or str(command.payload.get("campaign_id", ""))
        if campaign_id not in self.campaigns:
            raise KeyError("campaign does not exist")
        definition = DialogueDefinition.model_validate(command.payload.get("definition", {}))
        if definition.id in self.dialogue_definitions:
            raise ValueError("dialogue definition already exists")
        self.dialogue_definitions[definition.id] = definition
        receipt = await self._record_campaign_fact(command, "DialogueDefinitionRegistered", {"dialogue_id": definition.id, "definition": definition.model_dump(mode="json"), "registered_by": principal.principal_id})
        return receipt.model_copy(update={"result": {**receipt.result, "dialogue_id": definition.id}})

    async def rebuild_from_store(self) -> None:
        """Reconstruct event-sourced gameplay state and deterministic RNG position."""
        events = await self.store.read_all()
        self.campaigns.clear()
        self.actors.clear()
        self.encounters.clear()
        self.worlds.clear()
        self.character_creations.clear()
        self.sessions.clear()
        self.quests.clear()
        self.checkpoints.clear()
        self.campaign_content_bindings.clear()
        self.content_revision_proposals.clear()
        self.timelines.clear()
        self.encounter_window_ids.clear()
        self.reaction_windows.clear()
        self.dialogue_definitions.clear()
        self.dialogue_sessions.clear()
        self.branches.clear()
        self._rng.clear()

        for event in events:
            if event.stream_id.startswith("campaign:"):
                self.campaigns[event.campaign_id] = reduce_campaign(self.campaigns.get(event.campaign_id), event)
                self._rebuild_campaign_projection_event(event)
            elif event.stream_id.startswith("actor:"):
                actor_id = event.stream_id.split(":", 1)[1]
                self.actors[actor_id] = reduce_actor(self.actors.get(actor_id), event)
            elif event.stream_id.startswith("character_creation:"):
                creation_id = event.stream_id.split(":", 1)[1]
                self.character_creations[creation_id] = reduce_character_creation(self.character_creations.get(creation_id), event)
            elif event.stream_id.startswith("encounter:"):
                encounter_id = event.stream_id.split(":", 1)[1]
                self.encounters[encounter_id] = reduce_encounter(self.encounters.get(encounter_id), event)
            elif event.stream_id.startswith("world:"):
                world_id = event.stream_id.split(":", 1)[1]
                self.worlds[world_id] = reduce_world(self.worlds.get(world_id), event)
            elif event.stream_id.startswith("session:"):
                session_id = event.stream_id.split(":", 1)[1]
                self.sessions[session_id] = reduce_session(self.sessions.get(session_id), event)
            elif event.stream_id.startswith("quest:"):
                quest_id = event.stream_id.split(":", 1)[1]
                self.quests[quest_id] = reduce_quest(self.quests.get(quest_id), event)

        for campaign_id, campaign in self.campaigns.items():
            self._rng[campaign_id] = DeterministicRng(campaign.seed)
        for event in events:
            self._replay_rng_event(event)

        for session in self.sessions.values():
            if session.status == SessionStatus.PAUSED:
                self._ensure_timeline(session.campaign_id).clock.pause()
        for encounter_id, encounter in sorted(self.encounters.items()):
            if encounter.status == EncounterStatus.ACTIVE:
                self._open_current_window(encounter_id)

    def _rebuild_campaign_projection_event(self, event: Any) -> None:
        if event.event_type == "CheckpointCreated":
            checkpoint_id = str(event.payload["checkpoint_id"])
            self.checkpoints[checkpoint_id] = CampaignCheckpoint(checkpoint_id=checkpoint_id, campaign_id=event.campaign_id, name=str(event.payload["name"]), source_sequence=int(event.payload["source_sequence"]), created_by=str(event.payload["created_by"]), content_lock_hash=event.content_lock_hash)
        elif event.event_type == "CampaignContentBound":
            self.campaign_content_bindings[event.campaign_id] = CampaignContentBinding(campaign_id=event.campaign_id, pack_id=str(event.payload["pack_id"]), version=str(event.payload["version"]), content_hash=str(event.payload["content_hash"]), activated_sequence=event.sequence)
        elif event.event_type == "CampaignContentRevisionActivated":
            self.campaign_content_bindings[event.campaign_id] = CampaignContentBinding(campaign_id=event.campaign_id, pack_id=str(event.payload["pack_id"]), version=str(event.payload["to_version"]), content_hash=str(event.payload["new_content_hash"]), activated_sequence=event.sequence)
        elif event.event_type == "CampaignTimingConfigured":
            previous = self.timelines.get(event.campaign_id)
            current_time = previous.clock.now if previous else 0
            self.timelines[event.campaign_id] = TimelineRuntime(mode=TimingMode(str(event.payload["mode"])), start=current_time, default_decision_duration=None if event.payload.get("decision_duration") is None else int(event.payload["decision_duration"]), timeout_policy=TimeoutPolicy(str(event.payload["timeout_policy"])))
        elif event.event_type == "SimulationTimeAdvanced":
            timeline = self._ensure_timeline(event.campaign_id)
            timeline.clock.now = max(timeline.clock.now, int(event.payload["simulation_time"]))
        elif event.event_type == "DialogueDefinitionRegistered":
            definition = DialogueDefinition.model_validate(event.payload["definition"])
            self.dialogue_definitions[definition.id] = definition
        elif event.event_type == "DialogueStarted":
            dialogue_id = str(event.payload["dialogue_id"])
            definition = self.dialogue_definitions.get(dialogue_id)
            if definition is not None:
                session_id = str(event.payload["dialogue_session_id"])
                self.dialogue_sessions[session_id] = DialogueSession(session_id=session_id, dialogue_id=dialogue_id, campaign_id=event.campaign_id, actor_id=str(event.payload["actor_id"]), npc_id=str(event.payload["npc_id"]), current_node_id=definition.start_node_id)
        elif event.event_type == "DialogueChoiceSelected":
            session = self.dialogue_sessions.get(str(event.payload["dialogue_session_id"]))
            if session is not None:
                session.history.append(str(event.payload["choice_id"]))
                session.current_node_id = str(event.payload["current_node_id"])
                session.status = DialogueSessionStatus(str(event.payload["status"]))
                session.consequence_tags.update(str(item) for item in event.payload.get("consequence_tags", []))
        elif event.event_type == "CampaignBranchCreated":
            branch = CampaignBranch.model_validate(event.payload)
            self.branches[branch.branch_id] = branch

    def _replay_rng_event(self, event: Any) -> None:
        rng = self._rng.get(event.campaign_id)
        if rng is None:
            return
        payload = event.payload
        if event.event_type == "DiceRolled":
            rng.replay_roll(str(payload["expression"]), payload.get("rolls", ()), stream=str(payload.get("rng_stream", "dice")), expected_sequence=int(payload["rng_sequence"]) if payload.get("rng_sequence") is not None else None)
        elif event.event_type in {"AttackResolved", "PowerAttackResolved", "RangedAttackResolved"}:
            rng.replay_roll("1d20", payload.get("attack_roll", ()), stream="dice", expected_sequence=int(payload["attack_rng_sequence"]) if payload.get("attack_rng_sequence") is not None else None)
            if payload.get("hit") and payload.get("damage_roll"):
                expression = "1d6+2" if event.event_type == "PowerAttackResolved" else "1d4+1"
                rng.replay_roll(expression, payload["damage_roll"], stream="dice", expected_sequence=int(payload["damage_rng_sequence"]) if payload.get("damage_rng_sequence") is not None else None)
        elif event.event_type == "HealingApplied" and payload.get("rolls"):
            rng.replay_roll("1d4", payload["rolls"], stream="dice")

    def _advanced_snapshot_from_current(self, campaign_id: str) -> dict[str, Any]:
        timeline = self.timelines.get(campaign_id)
        timing = None
        if timeline is not None:
            timing = {"mode": timeline.mode.value, "simulation_time": timeline.clock.now, "paused": timeline.clock.paused, "default_decision_duration": timeline.default_decision_duration, "timeout_policy": timeline.timeout_policy.value}
        return {
            "timing": timing,
            "dialogues": {key: value.model_dump(mode="json") for key, value in sorted(self.dialogue_sessions.items()) if value.campaign_id == campaign_id},
            "branches": {key: value.model_dump(mode="json") for key, value in sorted(self.branches.items()) if value.parent_campaign_id == campaign_id},
        }

    def live_snapshot(self, campaign_id: str) -> dict[str, Any]:
        snapshot = super().live_snapshot(campaign_id)
        snapshot.update(self._advanced_snapshot_from_current(campaign_id))
        return snapshot

    async def replay_snapshot(self, campaign_id: str) -> dict[str, Any]:
        snapshot = await super().replay_snapshot(campaign_id)
        events = [event for event in await self.store.read_all() if event.campaign_id == campaign_id]
        timing: dict[str, Any] | None = None
        definitions: dict[str, DialogueDefinition] = {}
        dialogues: dict[str, DialogueSession] = {}
        branches: dict[str, CampaignBranch] = {}
        paused = False
        for event in events:
            if event.event_type == "CampaignTimingConfigured":
                timing = {"mode": str(event.payload["mode"]), "simulation_time": timing["simulation_time"] if timing else 0, "paused": paused, "default_decision_duration": event.payload.get("decision_duration"), "timeout_policy": str(event.payload["timeout_policy"])}
            elif event.event_type == "SimulationTimeAdvanced":
                if timing is None:
                    timing = {"mode": TimingMode.TURN_BASED.value, "simulation_time": 0, "paused": paused, "default_decision_duration": None, "timeout_policy": TimeoutPolicy.FORFEIT_TURN.value}
                timing["simulation_time"] = int(event.payload["simulation_time"])
            elif event.event_type == "GameSessionPaused":
                paused = True
                if timing is not None:
                    timing["paused"] = True
            elif event.event_type == "GameSessionResumed":
                paused = False
                if timing is not None:
                    timing["paused"] = False
            elif event.event_type == "DialogueDefinitionRegistered":
                definition = DialogueDefinition.model_validate(event.payload["definition"])
                definitions[definition.id] = definition
            elif event.event_type == "DialogueStarted":
                definition = definitions.get(str(event.payload["dialogue_id"]))
                if definition is not None:
                    session_id = str(event.payload["dialogue_session_id"])
                    dialogues[session_id] = DialogueSession(session_id=session_id, dialogue_id=definition.id, campaign_id=campaign_id, actor_id=str(event.payload["actor_id"]), npc_id=str(event.payload["npc_id"]), current_node_id=definition.start_node_id)
            elif event.event_type == "DialogueChoiceSelected":
                session = dialogues.get(str(event.payload["dialogue_session_id"]))
                if session is not None:
                    session.history.append(str(event.payload["choice_id"]))
                    session.current_node_id = str(event.payload["current_node_id"])
                    session.status = DialogueSessionStatus(str(event.payload["status"]))
                    session.consequence_tags.update(str(item) for item in event.payload.get("consequence_tags", []))
            elif event.event_type == "CampaignBranchCreated":
                branch = CampaignBranch.model_validate(event.payload)
                branches[branch.branch_id] = branch
        snapshot["timing"] = timing
        snapshot["dialogues"] = {key: value.model_dump(mode="json") for key, value in sorted(dialogues.items())}
        snapshot["branches"] = {key: value.model_dump(mode="json") for key, value in sorted(branches.items())}
        return snapshot
