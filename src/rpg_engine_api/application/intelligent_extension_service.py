from __future__ import annotations

from typing import Any

from rpg_engine_api.application.extension_service import ExtensionEngineService
from rpg_engine_api.controllers.goal_utility import GoalAwareUtilityController
from rpg_engine_api.controllers.simple_npc import SimpleNpcController
from rpg_engine_api.domain.commands import CommandEnvelope, CommandReceipt, CommandStatus, PrincipalContext
from rpg_engine_api.domain.controller_mind import ControllerGoal, ControllerMemory, ControllerMindState, reduce_controller_mind
from rpg_engine_api.domain.controllers import ControllerType
from rpg_engine_api.domain.encounter import EncounterStatus
from rpg_engine_api.domain.events import DomainEvent
from rpg_engine_api.domain.ids import new_id


class IntelligentExtensionEngineService(ExtensionEngineService):
    """Persistent bounded goals/memories layered over deployment-controlled extensions."""

    OWNER_COMMANDS = ExtensionEngineService.OWNER_COMMANDS | {
        "ConfigureControllerGoal", "RemoveControllerGoal", "RememberControllerFact", "ForgetControllerFact"
    }

    def __init__(self, store: Any | None = None) -> None:
        super().__init__(store=store)
        self.controller_minds: dict[str, ControllerMindState] = {}

    async def _dispatch(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        handlers = {
            "ConfigureControllerGoal": self._configure_goal,
            "RemoveControllerGoal": self._remove_goal,
            "RememberControllerFact": self._remember_fact,
            "ForgetControllerFact": self._forget_fact,
        }
        handler = handlers.get(command.command_type)
        return await handler(command, principal) if handler else await super()._dispatch(command, principal)

    async def _mind(self, actor_id: str, command: CommandEnvelope) -> ControllerMindState:
        state = self.controller_minds.get(actor_id)
        if state is not None:
            return state
        actor = self.actors.get(actor_id)
        if actor is None:
            raise KeyError("actor does not exist")
        stream = f"controller_mind:{actor_id}"
        event = DomainEvent(
            event_type="ControllerMindCreated", campaign_id=actor.campaign_id, stream_id=stream,
            actor_id=actor_id, command_id=command.command_id, correlation_id=command.command_id,
            payload={"actor_id": actor_id, "max_memories": int(command.payload.get("max_memories", 32))},
        )
        stored = await self.store.append(stream, 0, (event,))
        state = reduce_controller_mind(None, stored[0]); self.controller_minds[actor_id] = state
        return state

    async def _mind_event(self, command: CommandEnvelope, actor_id: str, event_type: str, payload: dict[str, object]) -> CommandReceipt:
        state = await self._mind(actor_id, command); stream = f"controller_mind:{actor_id}"
        event = DomainEvent(event_type=event_type, campaign_id=state.campaign_id, stream_id=stream, actor_id=actor_id, command_id=command.command_id, correlation_id=command.command_id, payload=payload)
        stored = await self.store.append(stream, await self.store.current_version(stream), (event,))
        self.controller_minds[actor_id] = reduce_controller_mind(state, stored[0])
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=(stored[0].event_id,), stream_versions={stream: stored[0].stream_version}, result={"actor_id": actor_id})

    async def _configure_goal(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal; actor_id = command.actor_id or str(command.payload.get("actor_id", "")); goal = ControllerGoal.model_validate(command.payload.get("goal", {}))
        receipt = await self._mind_event(command, actor_id, "ControllerGoalConfigured", {"goal": goal.model_dump(mode="json")})
        return receipt.model_copy(update={"result": {**receipt.result, "goal": goal.model_dump(mode="json")}})

    async def _remove_goal(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal; actor_id = command.actor_id or str(command.payload.get("actor_id", "")); return await self._mind_event(command, actor_id, "ControllerGoalRemoved", {"goal_id": str(command.payload.get("goal_id", ""))})

    async def _remember_fact(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal; actor_id = command.actor_id or str(command.payload.get("actor_id", "")); sequence = int(command.payload.get("observed_sequence") or await self.store.last_sequence(campaign_id=self.actors[actor_id].campaign_id))
        memory = ControllerMemory(memory_id=str(command.payload.get("memory_id") or new_id("memory")), summary=str(command.payload.get("summary", "")), tags=tuple(sorted({str(item) for item in command.payload.get("tags", [])})), observed_sequence=sequence, importance=int(command.payload.get("importance", 50)))
        receipt = await self._mind_event(command, actor_id, "ControllerFactRemembered", {"memory": memory.model_dump(mode="json")})
        return receipt.model_copy(update={"result": {**receipt.result, "memory": memory.model_dump(mode="json")}})

    async def _forget_fact(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal; actor_id = command.actor_id or str(command.payload.get("actor_id", "")); return await self._mind_event(command, actor_id, "ControllerFactForgotten", {"memory_id": str(command.payload.get("memory_id", ""))})

    async def _drive_simple_npcs(self, encounter_id: str) -> int:
        actions_taken = 0
        while actions_taken < 100:
            encounter = self.encounters.get(encounter_id)
            if encounter is None or encounter.status != EncounterStatus.ACTIVE or encounter.current_actor_id is None:
                return actions_taken
            actor_id = encounter.current_actor_id; actor = self.actors[actor_id]
            if not actor.controller.enabled or actor.controller.controller_type not in {ControllerType.SIMPLE_NPC, ControllerType.UTILITY_AI}:
                return actions_taken
            participant = encounter.participants[actor_id]
            enemies = [item for item in encounter.participants.values() if item.alive and item.side != participant.side]
            allies = [item for item in encounter.participants.values() if item.alive and item.side == participant.side and item.actor_id != actor_id]
            mind = self.controller_minds.get(actor_id)
            npc_runtime = getattr(self, "npc_runtimes", {}).get(actor_id)
            current_activity = ""
            if npc_runtime is not None and npc_runtime.completed_steps:
                current_activity = str(npc_runtime.completed_steps[-1].get("activity", ""))
            view: dict[str, object] = {
                "actor_id": actor_id, "available_actions": self.available_actions(actor_id), "self_hp_ratio": participant.hp_ratio,
                "nearest_enemy_distance": min((abs(item.position - participant.position) for item in enemies), default=0),
                "lowest_ally_hp_ratio": min((item.hp_ratio for item in allies), default=1.0),
                "goal_tags": mind.active_goal_tags() if mind else (), "memory_tags": mind.memory_tags() if mind else (), "current_activity": current_activity,
            }
            action = GoalAwareUtilityController().choose_action(view) if actor.controller.controller_type == ControllerType.UTILITY_AI else SimpleNpcController(profile=actor.controller.behavior_profile_ref or "aggressive_melee").choose_action(view)
            payload: dict[str, object] = {"encounter_id": encounter_id, "action_id": action["action_id"]}
            if action.get("target_id") is not None: payload["target_id"] = action["target_id"]
            receipt = await self.execute(CommandEnvelope(command_type="PerformAction", campaign_id=encounter.campaign_id, actor_id=actor_id, idempotency_key=f"npc:{encounter_id}:{encounter.stream_version}:{actor_id}", payload=payload), PrincipalContext(principal_id=f"controller:{actor_id}", roles=frozenset({"controller"})), drive_controllers=False)
            if receipt.status != CommandStatus.ACCEPTED: raise RuntimeError(f"autonomous controller action rejected: {receipt.error}")
            actions_taken += 1
        raise RuntimeError("automatic controller safety limit exceeded")

    async def rebuild_from_store(self) -> None:
        await super().rebuild_from_store(); self.controller_minds.clear()
        for event in await self.store.read_all():
            if event.stream_id.startswith("controller_mind:"):
                actor_id = event.stream_id.split(":", 1)[1]; self.controller_minds[actor_id] = reduce_controller_mind(self.controller_minds.get(actor_id), event)

    def controller_mind_projection(self, actor_id: str) -> dict[str, Any]:
        return {"data": self.controller_minds[actor_id].model_dump(mode="json"), "meta": {"schema_version": "1.0"}}

    def live_snapshot(self, campaign_id: str) -> dict[str, Any]:
        snapshot = super().live_snapshot(campaign_id); snapshot["controller_minds"] = {key: value.model_dump(mode="json") for key, value in sorted(self.controller_minds.items()) if value.campaign_id == campaign_id}; return snapshot

    async def replay_snapshot(self, campaign_id: str) -> dict[str, Any]:
        snapshot = await super().replay_snapshot(campaign_id); minds: dict[str, ControllerMindState] = {}
        for event in await self.store.read_all():
            if event.campaign_id == campaign_id and event.stream_id.startswith("controller_mind:"):
                actor_id = event.stream_id.split(":", 1)[1]; minds[actor_id] = reduce_controller_mind(minds.get(actor_id), event)
        snapshot["controller_minds"] = {key: value.model_dump(mode="json") for key, value in sorted(minds.items())}; return snapshot

    @classmethod
    def capability_projection(cls) -> dict[str, Any]:
        base = super().capability_projection(); data = dict(base["data"]); data["features"] = list(data.get("features", [])) + ["bounded_controller_memory", "controller_goals", "goal_aware_utility_ai", "deterministic_controller_budget"]
        return {"data": data, "meta": {"schema_version": "1.7"}}
