from collections import Counter
from typing import Any

from rpg_engine_api.application.evolution_service import EvolutionEngineService
from rpg_engine_api.controllers.simple_npc import SimpleNpcController
from rpg_engine_api.controllers.utility import UtilityController
from rpg_engine_api.domain.actor import reduce_actor
from rpg_engine_api.domain.branches import CampaignBranch
from rpg_engine_api.domain.character_creation import REFERENCE_ARCHETYPES, REFERENCE_BACKGROUNDS, REFERENCE_SPECIES, CharacterCreationStatus, reduce_character_creation
from rpg_engine_api.domain.commands import CommandEnvelope, CommandReceipt, CommandStatus, PrincipalContext
from rpg_engine_api.domain.controllers import ControllerAssignment, ControllerType
from rpg_engine_api.domain.dialogue import DialogueDefinition, DialogueSession
from rpg_engine_api.domain.encounter import EncounterState, EncounterStatus, reduce_encounter
from rpg_engine_api.domain.events import DomainEvent
from rpg_engine_api.domain.ids import new_id
from rpg_engine_api.domain.reactions import ReactionOption, ReactionWindow, ReactionWindowStatus
from rpg_engine_api.domain.session import SessionStatus
from rpg_engine_api.domain.timeline import TimelineRuntime, TimeoutPolicy, TimingMode, WindowKind, WindowStatus
from rpg_engine_api.rules.requirements_runtime import RequirementContext


class AdvancedEngineService(EvolutionEngineService):
    """Composed v0.2-v0.8 runtime seams exposed through the normal command gateway."""

    def __init__(self) -> None:
        super().__init__()
        self.timelines: dict[str, TimelineRuntime] = {}
        self.encounter_window_ids: dict[str, str] = {}
        self.reaction_windows: dict[str, ReactionWindow] = {}
        self.dialogue_definitions: dict[str, DialogueDefinition] = {}
        self.dialogue_sessions: dict[str, DialogueSession] = {}
        self.branches: dict[str, CampaignBranch] = {}

    async def _dispatch(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        handlers = {
            "ConfigureCampaignTiming": self._configure_campaign_timing,
            "AdvanceSimulationTime": self._advance_simulation_time,
            "OpenReactionWindow": self._open_reaction_window,
            "ResolveReaction": self._resolve_reaction,
            "SelectCharacterSpecies": self._select_character_species,
            "SelectCharacterBackground": self._select_character_background,
            "PauseGameSession": self._pause_game_session,
            "ResumeGameSession": self._resume_game_session,
            "RegisterDialogue": self._register_dialogue,
            "StartDialogue": self._start_dialogue,
            "ChooseDialogue": self._choose_dialogue,
            "CraftItem": self._craft_item,
            "CreateCampaignBranch": self._create_campaign_branch,
            "SetActorController": self._set_actor_controller,
        }
        handler = handlers.get(command.command_type)
        if handler is not None:
            return await handler(command, principal)
        if command.command_type == "FinalizeCharacterCreation":
            return await self._finalize_character_creation_advanced(command, principal)
        return await super()._dispatch(command, principal)

    def _ensure_timeline(self, campaign_id: str) -> TimelineRuntime:
        return self.timelines.setdefault(campaign_id, TimelineRuntime())

    async def _configure_campaign_timing(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        campaign_id = command.campaign_id or str(command.payload.get("campaign_id", ""))
        if campaign_id not in self.campaigns:
            raise KeyError("campaign does not exist")
        mode = TimingMode(str(command.payload.get("mode", TimingMode.TURN_BASED)))
        timeout_policy = TimeoutPolicy(str(command.payload.get("timeout_policy", TimeoutPolicy.FORFEIT_TURN)))
        raw_duration = command.payload.get("decision_duration")
        duration = None if raw_duration is None else int(raw_duration)
        previous = self.timelines.get(campaign_id)
        start = previous.clock.now if previous else 0
        self.timelines[campaign_id] = TimelineRuntime(mode=mode, start=start, default_decision_duration=duration, timeout_policy=timeout_policy)
        receipt = await self._record_campaign_fact(command, "CampaignTimingConfigured", {"mode": mode.value, "decision_duration": duration, "timeout_policy": timeout_policy.value, "configured_by": principal.principal_id})
        return receipt.model_copy(update={"result": {**receipt.result, "mode": mode.value, "decision_duration": duration, "timeout_policy": timeout_policy.value}})

    async def _start_encounter(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        receipt = await super()._start_encounter(command, principal)
        encounter_id = str(receipt.result["encounter_id"])
        self._ensure_timeline(str(receipt.result["campaign_id"]))
        self._open_current_window(encounter_id)
        return receipt

    def _open_current_window(self, encounter_id: str) -> None:
        encounter = self.encounters.get(encounter_id)
        if encounter is None or encounter.status != EncounterStatus.ACTIVE or encounter.current_actor_id is None:
            return
        timeline = self._ensure_timeline(encounter.campaign_id)
        old_id = self.encounter_window_ids.get(encounter_id)
        if old_id is not None:
            old = timeline.windows.get(old_id)
            if old is not None and old.status == WindowStatus.OPEN:
                old.status = WindowStatus.CANCELLED
        duration = timeline.default_decision_duration if timeline.mode != TimingMode.TURN_BASED else None
        window = timeline.open_window(encounter.current_actor_id, kind=WindowKind.ACTION, duration=duration, context={"encounter_id": encounter_id, "round": encounter.round})
        self.encounter_window_ids[encounter_id] = window.window_id

    async def _perform_action(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        encounter_id = str(command.payload.get("encounter_id", ""))
        encounter = self.encounters.get(encounter_id)
        if encounter is not None:
            timeline = self._ensure_timeline(encounter.campaign_id)
            window_id = self.encounter_window_ids.get(encounter_id)
            if window_id is not None:
                window = timeline.windows[window_id]
                actor_id = command.actor_id or str(command.payload.get("actor_id", ""))
                if window.actor_id != actor_id or window.status != WindowStatus.OPEN:
                    raise ValueError("actor decision window is not open")
                if window.deadline_at is not None and timeline.clock.now > window.deadline_at:
                    raise ValueError("actor decision deadline has expired")
        receipt = await super()._perform_action(command, principal)
        if encounter is not None:
            timeline = self._ensure_timeline(encounter.campaign_id)
            window_id = self.encounter_window_ids.get(encounter_id)
            if window_id is not None and timeline.windows[window_id].status == WindowStatus.OPEN:
                timeline.resolve_window(window_id)
            self._open_current_window(encounter_id)
        return receipt

    async def _advance_simulation_time(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        campaign_id = command.campaign_id or str(command.payload.get("campaign_id", ""))
        timeline = self._ensure_timeline(campaign_id)
        target = int(command.payload.get("target_time", timeline.clock.now + int(command.payload.get("delta", 0))))
        expired = timeline.advance_to(target)
        affected: list[str] = []
        for window in expired:
            encounter_id = str(window.context.get("encounter_id", ""))
            encounter = self.encounters.get(encounter_id)
            if encounter is None or encounter.status != EncounterStatus.ACTIVE or encounter.current_actor_id != window.actor_id:
                continue
            await self._apply_timeout(encounter, window.timeout_policy, command.command_id)
            affected.append(encounter_id)
        receipt = await self._record_campaign_fact(command, "SimulationTimeAdvanced", {"simulation_time": timeline.clock.now, "expired_windows": [window.window_id for window in expired], "advanced_by": principal.principal_id})
        result: dict[str, object] = {**receipt.result, "simulation_time": timeline.clock.now, "expired_windows": len(expired), "affected_encounters": affected}
        if affected:
            result["encounter_id"] = affected[-1]
        return receipt.model_copy(update={"result": result})

    async def _apply_timeout(self, encounter: EncounterState, policy: TimeoutPolicy, command_id: str) -> None:
        actor_id = encounter.current_actor_id
        if actor_id is None:
            return
        if policy == TimeoutPolicy.PAUSE_GAME:
            self._ensure_timeline(encounter.campaign_id).clock.pause()
            return
        if policy == TimeoutPolicy.DM_DECIDES:
            return
        stream_id = f"encounter:{encounter.encounter_id}"
        base = {"campaign_id": encounter.campaign_id, "stream_id": stream_id, "actor_id": actor_id, "command_id": command_id, "correlation_id": command_id}
        events: list[DomainEvent] = [DomainEvent(event_type="TurnTimedOut", payload={"actor_id": actor_id, "policy": policy.value}, **base)]
        preview = encounter
        if policy == TimeoutPolicy.AUTO_DEFEND:
            events.append(DomainEvent(event_type="GuardRaised", payload={"actor_id": actor_id, "guard": 2}, **base))
            preview = reduce_encounter(preview, events[-1])
        elif policy == TimeoutPolicy.AI_CONTROL:
            actions = self.available_actions(actor_id)
            action = SimpleNpcController(profile="balanced").choose_action({"actor_id": actor_id, "available_actions": actions})
            resolved = list(self._resolve_action_events(encounter, actor_id, str(action["action_id"]), action.get("target_id"), CommandEnvelope(command_id=command_id, command_type="PerformAction", campaign_id=encounter.campaign_id, actor_id=actor_id, payload={"encounter_id": encounter.encounter_id, "action_id": action["action_id"]})))
            events.extend(resolved)
            expected = await self.store.current_version(stream_id)
            stored = await self.store.append(stream_id, expected, events)
            state = encounter
            for event in stored:
                state = reduce_encounter(state, event)
            self.encounters[encounter.encounter_id] = state
            self._open_current_window(encounter.encounter_id)
            return
        next_index, next_round = self._next_living_turn(preview)
        events.append(DomainEvent(event_type="TurnAdvanced", payload={"turn_index": next_index, "round": next_round}, **base))
        expected = await self.store.current_version(stream_id)
        stored = await self.store.append(stream_id, expected, events)
        state = encounter
        for event in stored:
            state = reduce_encounter(state, event)
        self.encounters[encounter.encounter_id] = state
        self._open_current_window(encounter.encounter_id)

    def available_actions(self, actor_id: str) -> list[dict[str, Any]]:
        active = next((encounter for encounter in self.encounters.values() if encounter.status == EncounterStatus.ACTIVE and actor_id in encounter.participants), None)
        if active is not None and active.current_actor_id != actor_id:
            return []
        actions = super().available_actions(actor_id)
        if active is None:
            return actions
        participant = active.participants[actor_id]
        enemies = sorted((item for item in active.participants.values() if item.alive and item.side != participant.side), key=lambda item: (abs(item.position - participant.position), item.actor_id))
        allies = sorted((item for item in active.participants.values() if item.alive and item.side == participant.side and item.actor_id != actor_id), key=lambda item: (item.hp_ratio, item.actor_id))
        if not enemies:
            return []
        nearest = enemies[0]
        distance = abs(nearest.position - participant.position)
        metadata = {"attack": ("attack", ("melee",)), "power_attack": ("attack", ("melee", "high_damage")), "move_toward": ("movement", ("approach",)), "guard": ("defense", ("defense",))}
        enriched: list[dict[str, Any]] = []
        for action in actions:
            category, tags = metadata.get(str(action.get("action_id")), (str(action.get("category", "special")), tuple(action.get("tags", ()))))
            enriched.append({**action, "category": category, "tags": list(tags)})
        base = {"command_type": "PerformAction", "campaign_id": active.campaign_id, "actor_id": actor_id, "encounter_id": active.encounter_id}
        if 1 < distance <= 4:
            enriched.append({**base, "action_id": "ranged_attack", "label": f"Ranged attack {nearest.actor_id}", "target_id": nearest.actor_id, "category": "attack", "tags": ["ranged"]})
        enriched.append({**base, "action_id": "retreat", "label": f"Retreat from {nearest.actor_id}", "target_id": nearest.actor_id, "category": "movement", "tags": ["retreat"]})
        if participant.hp < participant.max_hp and participant.stamina > 0:
            enriched.append({**base, "action_id": "second_wind", "label": "Second wind", "target_id": actor_id, "category": "support", "tags": ["healing", "self"]})
        if allies and allies[0].hp < allies[0].max_hp and participant.stamina > 0:
            enriched.append({**base, "action_id": "heal_ally", "label": f"Aid {allies[0].actor_id}", "target_id": allies[0].actor_id, "category": "support", "tags": ["support", "healing"]})
        enriched.append({**base, "action_id": "wait", "label": "Wait", "category": "special", "tags": ["passive"]})
        return sorted(enriched, key=lambda item: (str(item["action_id"]), str(item.get("target_id", ""))))

    def _resolve_action_events(self, encounter: EncounterState, actor_id: str, action_id: str, target_id: object, command: CommandEnvelope) -> tuple[DomainEvent, ...]:
        if action_id not in {"ranged_attack", "retreat", "second_wind", "heal_ally", "wait"}:
            return super()._resolve_action_events(encounter, actor_id, action_id, target_id, command)
        stream_id = f"encounter:{encounter.encounter_id}"
        base = {"campaign_id": encounter.campaign_id, "stream_id": stream_id, "actor_id": actor_id, "command_id": command.command_id, "correlation_id": command.command_id}
        actor = encounter.participants[actor_id]
        events: list[DomainEvent] = []
        if action_id == "ranged_attack":
            target = encounter.participants[str(target_id)]
            distance = abs(target.position - actor.position)
            if distance <= 1 or distance > 4:
                raise ValueError("ranged target is outside supported range")
            attack = self._rng[encounter.campaign_id].roll("1d20", stream="dice")
            attack_total = attack.total + self.actors[actor_id].attack_bonus
            target_defense = self.actors[target.actor_id].defense + target.guard
            hit = attack_total >= target_defense
            damage_result = self._rng[encounter.campaign_id].roll("1d4+1", stream="dice") if hit else None
            damage = damage_result.total if damage_result else 0
            events.append(DomainEvent(event_type="RangedAttackResolved", payload={"actor_id": actor_id, "target_id": target.actor_id, "attack_roll": attack.rolls, "attack_total": attack_total, "target_defense": target_defense, "hit": hit, "damage_roll": damage_result.rolls if damage_result else (), "damage": damage, "target_hp": max(0, target.hp - damage)}, **base))
        elif action_id == "retreat":
            target = encounter.participants[str(target_id)]
            delta = -1 if target.position >= actor.position else 1
            position = actor.position + delta
            fled = abs(target.position - position) >= 5
            events.append(DomainEvent(event_type="ActorRetreated", payload={"actor_id": actor_id, "position": position, "fled": fled}, **base))
        elif action_id in {"second_wind", "heal_ally"}:
            target = encounter.participants[actor_id if action_id == "second_wind" else str(target_id)]
            if actor.stamina <= 0:
                raise ValueError("healing action requires stamina")
            roll = self._rng[encounter.campaign_id].roll("1d4+2" if action_id == "second_wind" else "1d4+1", stream="dice")
            events.append(DomainEvent(event_type="HealingApplied", payload={"source_actor_id": actor_id, "target_id": target.actor_id, "amount": roll.total, "rolls": roll.rolls, "target_hp": min(target.max_hp, target.hp + roll.total), "source_stamina": actor.stamina - 1}, **base))
        else:
            events.append(DomainEvent(event_type="ActorWaited", payload={"actor_id": actor_id}, **base))
        preview = encounter
        for event in events:
            preview = reduce_encounter(preview, event)
        alive_sides = {participant.side for participant in preview.participants.values() if participant.alive}
        if len(alive_sides) == 1:
            events.append(DomainEvent(event_type="EncounterCompleted", payload={"winner_side": next(iter(alive_sides))}, **base))
            return tuple(events)
        next_index, next_round = self._next_living_turn(preview)
        events.append(DomainEvent(event_type="TurnAdvanced", payload={"turn_index": next_index, "round": next_round}, **base))
        return tuple(events)

    async def _drive_simple_npcs(self, encounter_id: str) -> int:
        actions_taken = 0
        while actions_taken < 100:
            encounter = self.encounters.get(encounter_id)
            if encounter is None or encounter.status != EncounterStatus.ACTIVE or encounter.current_actor_id is None:
                return actions_taken
            actor_id = encounter.current_actor_id
            actor = self.actors[actor_id]
            if not actor.controller.enabled or actor.controller.controller_type not in {ControllerType.SIMPLE_NPC, ControllerType.UTILITY_AI}:
                return actions_taken
            participant = encounter.participants[actor_id]
            enemies = [item for item in encounter.participants.values() if item.alive and item.side != participant.side]
            allies = [item for item in encounter.participants.values() if item.alive and item.side == participant.side and item.actor_id != actor_id]
            view: dict[str, object] = {"actor_id": actor_id, "available_actions": self.available_actions(actor_id), "self_hp_ratio": participant.hp_ratio, "nearest_enemy_distance": min((abs(item.position - participant.position) for item in enemies), default=0), "lowest_ally_hp_ratio": min((item.hp_ratio for item in allies), default=1.0)}
            if actor.controller.controller_type == ControllerType.UTILITY_AI:
                action = UtilityController().choose_action(view)
            else:
                action = SimpleNpcController(profile=actor.controller.behavior_profile_ref or "aggressive_melee").choose_action(view)
            payload: dict[str, object] = {"encounter_id": encounter_id, "action_id": action["action_id"]}
            if action.get("target_id") is not None:
                payload["target_id"] = action["target_id"]
            receipt = await self.execute(CommandEnvelope(command_type="PerformAction", campaign_id=encounter.campaign_id, actor_id=actor_id, idempotency_key=f"npc:{encounter_id}:{encounter.stream_version}:{actor_id}", payload=payload), PrincipalContext(principal_id=f"controller:{actor_id}", roles=frozenset({"controller"})), drive_controllers=False)
            if receipt.status != CommandStatus.ACCEPTED:
                raise RuntimeError(f"autonomous controller action rejected: {receipt.error}")
            actions_taken += 1
        raise RuntimeError("automatic controller safety limit exceeded")

    async def _open_reaction_window(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal
        encounter_id = str(command.payload.get("encounter_id", ""))
        encounter = self.encounters.get(encounter_id)
        if encounter is None:
            raise KeyError("encounter does not exist")
        eligible_actor_id = str(command.payload.get("eligible_actor_id", ""))
        participant = encounter.participants.get(eligible_actor_id)
        if participant is None or not participant.alive or participant.reaction_points <= 0:
            raise ValueError("actor is not eligible to react")
        options = tuple(ReactionOption(action_id=str(option.get("action_id", "guard_reaction")), actor_id=eligible_actor_id, target_ids=tuple(str(item) for item in option.get("target_ids", [])), label=str(option.get("label", "React"))) for option in command.payload.get("options", [{"action_id": "guard_reaction", "label": "Guard reaction"}]) if isinstance(option, dict))
        timeline = self._ensure_timeline(encounter.campaign_id)
        window = ReactionWindow(triggering_action_instance_id=str(command.payload.get("triggering_action_instance_id", new_id("action"))), eligible_actor_ids=(eligible_actor_id,), opened_at=timeline.clock.now, deadline_at=timeline.clock.now + int(command.payload.get("duration", 3)), options=options)
        self.reaction_windows[window.reaction_window_id] = window
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, result={"encounter_id": encounter_id, "reaction_window_id": window.reaction_window_id})

    async def _resolve_reaction(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal
        window = self.reaction_windows.get(str(command.payload.get("reaction_window_id", "")))
        if window is None:
            raise KeyError("reaction window does not exist")
        actor_id = command.actor_id or str(command.payload.get("actor_id", ""))
        accept = bool(command.payload.get("accept", True))
        if not accept:
            window.decline(actor_id)
            return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, result={"reaction_window_id": window.reaction_window_id, "status": window.status.value})
        action_id = str(command.payload.get("action_id", "guard_reaction"))
        window.accept(actor_id, action_id)
        encounter = next((item for item in self.encounters.values() if actor_id in item.participants and item.status == EncounterStatus.ACTIVE), None)
        if encounter is None:
            raise ValueError("reacting actor is not in an active encounter")
        stream_id = f"encounter:{encounter.encounter_id}"
        expected = await self.store.current_version(stream_id)
        events = [DomainEvent(event_type="ReactionSpent", campaign_id=encounter.campaign_id, stream_id=stream_id, actor_id=actor_id, command_id=command.command_id, correlation_id=command.command_id, payload={"actor_id": actor_id, "amount": 1, "reaction_window_id": window.reaction_window_id})]
        if action_id == "guard_reaction":
            events.append(DomainEvent(event_type="GuardRaised", campaign_id=encounter.campaign_id, stream_id=stream_id, actor_id=actor_id, command_id=command.command_id, correlation_id=command.command_id, payload={"actor_id": actor_id, "guard": 2}))
        stored = await self.store.append(stream_id, expected, events)
        state = encounter
        for event in stored:
            state = reduce_encounter(state, event)
        self.encounters[encounter.encounter_id] = state
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=tuple(event.event_id for event in stored), stream_versions={stream_id: stored[-1].stream_version}, result={"encounter_id": encounter.encounter_id, "reaction_window_id": window.reaction_window_id, "status": window.status.value})

    async def _select_character_species(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        creation_id = str(command.payload.get("creation_id", ""))
        session = self._owned_creation(creation_id, principal)
        species = str(command.payload.get("species", ""))
        if species not in REFERENCE_SPECIES:
            raise ValueError("unknown species")
        return await self._append_creation_event(command, session, "CharacterSpeciesSelected", {"species": species})

    async def _select_character_background(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        creation_id = str(command.payload.get("creation_id", ""))
        session = self._owned_creation(creation_id, principal)
        background = str(command.payload.get("background", ""))
        if background not in REFERENCE_BACKGROUNDS:
            raise ValueError("unknown background")
        return await self._append_creation_event(command, session, "CharacterBackgroundSelected", {"background": background})

    async def _finalize_character_creation_advanced(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        creation_id = str(command.payload.get("creation_id", ""))
        session = self._owned_creation(creation_id, principal)
        if not session.valid_for_finalize or session.status != CharacterCreationStatus.DRAFT:
            raise ValueError("character creation requires name and archetype")
        assert session.archetype is not None and session.name is not None
        species = session.species or "human"
        background = session.background or "wanderer"
        archetype = REFERENCE_ARCHETYPES[session.archetype]
        species_data = REFERENCE_SPECIES[species]
        background_data = REFERENCE_BACKGROUNDS[background]
        actor_id = str(command.payload.get("actor_id") or new_id("act"))
        actor_receipt = await self._create_actor(CommandEnvelope(command_id=new_id("cmd"), command_type="CreateActor", campaign_id=session.campaign_id, payload={"actor_id": actor_id, "name": session.name, "max_hp": int(archetype["max_hp"]) + int(species_data["max_hp_delta"]), "attack_bonus": int(archetype["attack_bonus"]) + int(species_data["attack_bonus_delta"]), "defense": int(archetype["defense"]) + int(species_data["defense_delta"]), "controller": {"controller_type": "human", "controller_version": "1"}}), principal)
        actor = self.actors[actor_id]
        actor_stream = f"actor:{actor_id}"
        actor_expected = await self.store.current_version(actor_stream)
        origin = DomainEvent(event_type="CharacterOriginApplied", campaign_id=session.campaign_id, stream_id=actor_stream, actor_id=actor_id, command_id=command.command_id, correlation_id=command.command_id, payload={"species": species, "background": background, "features": [background_data["feature"]], "items": [background_data["item"]]})
        origin_stored = await self.store.append(actor_stream, actor_expected, (origin,))
        self.actors[actor_id] = reduce_actor(actor, origin_stored[0])
        creation_stream = f"character_creation:{creation_id}"
        expected = await self.store.current_version(creation_stream)
        finalized = DomainEvent(event_type="CharacterCreationFinalized", campaign_id=session.campaign_id, stream_id=creation_stream, actor_id=actor_id, command_id=command.command_id, correlation_id=command.command_id, payload={"actor_id": actor_id, "archetype": session.archetype, "species": species, "background": background})
        stored = await self.store.append(creation_stream, expected, (finalized,))
        self.character_creations[creation_id] = reduce_character_creation(session, stored[0])
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=actor_receipt.emitted_event_ids + (origin_stored[0].event_id, stored[0].event_id), stream_versions={**actor_receipt.stream_versions, actor_stream: origin_stored[0].stream_version, creation_stream: stored[0].stream_version}, result={"campaign_id": session.campaign_id, "creation_id": creation_id, "actor_id": actor_id, "archetype": session.archetype, "species": species, "background": background})

    async def _pause_game_session(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        session = self.sessions.get(str(command.payload.get("session_id", "")))
        if session is None:
            raise KeyError("session does not exist")
        if principal.principal_id != session.owner_id or session.status != SessionStatus.OPEN:
            raise ValueError("only the owner can pause an open session")
        self._ensure_timeline(session.campaign_id).clock.pause()
        return await self._append_session_event(session, command, "GameSessionPaused", {})

    async def _resume_game_session(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        session = self.sessions.get(str(command.payload.get("session_id", "")))
        if session is None:
            raise KeyError("session does not exist")
        if principal.principal_id != session.owner_id or session.status != SessionStatus.PAUSED:
            raise ValueError("only the owner can resume a paused session")
        self._ensure_timeline(session.campaign_id).clock.resume()
        return await self._append_session_event(session, command, "GameSessionResumed", {})

    async def _register_dialogue(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal
        definition = DialogueDefinition.model_validate(command.payload.get("definition", {}))
        if definition.id in self.dialogue_definitions:
            raise ValueError("dialogue definition already exists")
        self.dialogue_definitions[definition.id] = definition
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, result={"dialogue_id": definition.id})

    async def _start_dialogue(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal
        dialogue_id = str(command.payload.get("dialogue_id", ""))
        definition = self.dialogue_definitions.get(dialogue_id)
        if definition is None:
            raise KeyError("dialogue definition does not exist")
        actor_id = command.actor_id or str(command.payload.get("actor_id", ""))
        npc_id = str(command.payload.get("npc_id", ""))
        if actor_id not in self.actors or npc_id not in self.actors:
            raise ValueError("dialogue actors must exist")
        campaign_id = self.actors[actor_id].campaign_id
        session_id = str(command.payload.get("dialogue_session_id") or new_id("dialogue"))
        session = DialogueSession(session_id=session_id, dialogue_id=dialogue_id, campaign_id=campaign_id, actor_id=actor_id, npc_id=npc_id, current_node_id=definition.start_node_id)
        self.dialogue_sessions[session_id] = session
        receipt = await self._record_campaign_fact(CommandEnvelope(command_id=command.command_id, command_type="DialogueStarted", campaign_id=campaign_id, actor_id=actor_id, payload={}), "DialogueStarted", {"dialogue_session_id": session_id, "dialogue_id": dialogue_id, "actor_id": actor_id, "npc_id": npc_id}, actor_id=actor_id)
        return receipt.model_copy(update={"result": {**receipt.result, "dialogue_session_id": session_id, "dialogue_id": dialogue_id}})

    def _dialogue_context(self, actor_id: str) -> RequirementContext:
        actor = self.actors[actor_id]
        return RequirementContext(level=actor.level, features=set(actor.features), items=set(actor.inventory), conditions=set(actor.conditions), resources=dict(actor.resources))

    async def _choose_dialogue(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal
        session = self.dialogue_sessions.get(str(command.payload.get("dialogue_session_id", "")))
        if session is None:
            raise KeyError("dialogue session does not exist")
        definition = self.dialogue_definitions[session.dialogue_id]
        choice = session.choose(definition, str(command.payload.get("choice_id", "")), self._dialogue_context(session.actor_id))
        receipt = await self._record_campaign_fact(CommandEnvelope(command_id=command.command_id, command_type="DialogueChoiceSelected", campaign_id=session.campaign_id, actor_id=session.actor_id, payload={}), "DialogueChoiceSelected", {"dialogue_session_id": session.session_id, "dialogue_id": session.dialogue_id, "choice_id": choice.id, "current_node_id": session.current_node_id, "status": session.status.value, "consequence_tags": sorted(choice.consequence_tags)}, actor_id=session.actor_id)
        return receipt.model_copy(update={"result": {**receipt.result, "dialogue_session_id": session.session_id, "choice_id": choice.id, "status": session.status.value}})

    async def _craft_item(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal
        actor_id = command.actor_id or str(command.payload.get("actor_id", ""))
        actor = self.actors.get(actor_id)
        if actor is None:
            raise KeyError("actor does not exist")
        ingredients = [str(item) for item in command.payload.get("ingredients", [])]
        required = Counter(ingredients)
        owned = Counter(actor.inventory)
        if any(owned[item] < count for item, count in required.items()):
            raise ValueError("actor does not have required crafting ingredients")
        result_item_id = str(command.payload.get("result_item_id", ""))
        if not result_item_id:
            raise ValueError("crafting requires result_item_id")
        stream_id = f"actor:{actor_id}"
        expected = await self.store.current_version(stream_id)
        event = DomainEvent(event_type="ItemCrafted", campaign_id=actor.campaign_id, stream_id=stream_id, actor_id=actor_id, command_id=command.command_id, correlation_id=command.command_id, payload={"ingredients": ingredients, "result_item_id": result_item_id, "recipe_id": str(command.payload.get("recipe_id", "custom"))})
        stored = await self.store.append(stream_id, expected, (event,))
        self.actors[actor_id] = reduce_actor(actor, stored[0])
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=(stored[0].event_id,), stream_versions={stream_id: stored[0].stream_version}, result={"campaign_id": actor.campaign_id, "actor_id": actor_id, "result_item_id": result_item_id})

    async def _create_campaign_branch(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        checkpoint_id = str(command.payload.get("checkpoint_id", ""))
        checkpoint = self.checkpoints.get(checkpoint_id)
        if checkpoint is None:
            raise KeyError("checkpoint does not exist")
        branch_id = str(command.payload.get("branch_id") or new_id("branch"))
        if branch_id in self.branches:
            raise ValueError("branch already exists")
        branch = CampaignBranch(branch_id=branch_id, campaign_id=str(command.payload.get("new_campaign_id") or new_id("cmpbranch")), parent_campaign_id=checkpoint.campaign_id, source_checkpoint_id=checkpoint_id, fork_sequence=checkpoint.source_sequence, created_by=principal.principal_id, reason=str(command.payload.get("reason", "manual_restore")))
        self.branches[branch_id] = branch
        receipt = await self._record_campaign_fact(CommandEnvelope(command_id=command.command_id, command_type="CampaignBranchCreated", campaign_id=checkpoint.campaign_id, payload={}), "CampaignBranchCreated", branch.model_dump(mode="json"))
        return receipt.model_copy(update={"result": {**receipt.result, "branch": branch.model_dump(mode="json")}})

    async def _set_actor_controller(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal
        actor_id = command.actor_id or str(command.payload.get("actor_id", ""))
        actor = self.actors.get(actor_id)
        if actor is None:
            raise KeyError("actor does not exist")
        controller = ControllerAssignment.model_validate(command.payload.get("controller", {}))
        stream_id = f"actor:{actor_id}"
        expected = await self.store.current_version(stream_id)
        event = DomainEvent(event_type="ControllerAssignmentChanged", campaign_id=actor.campaign_id, stream_id=stream_id, actor_id=actor_id, command_id=command.command_id, correlation_id=command.command_id, payload={"controller": controller.model_dump(mode="json")})
        stored = await self.store.append(stream_id, expected, (event,))
        self.actors[actor_id] = reduce_actor(actor, stored[0])
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=(stored[0].event_id,), stream_versions={stream_id: stored[0].stream_version}, result={"campaign_id": actor.campaign_id, "actor_id": actor_id, "controller": controller.model_dump(mode="json")})

    def timeline_projection(self, campaign_id: str) -> dict[str, Any]:
        timeline = self._ensure_timeline(campaign_id)
        windows = [window.model_dump(mode="json") for window in sorted(timeline.windows.values(), key=lambda item: item.window_id)]
        return {"data": {"campaign_id": campaign_id, "mode": timeline.mode.value, "simulation_time": timeline.clock.now, "paused": timeline.clock.paused, "default_decision_duration": timeline.default_decision_duration, "timeout_policy": timeline.timeout_policy.value, "windows": windows, "pending": [{"schedule_id": item.schedule_id, "simulation_time": item.simulation_time, "priority": item.priority, "kind": item.kind, "payload": item.payload} for item in timeline.clock.pending()]}, "meta": {"schema_version": "1.0"}}

    def reaction_projection(self, reaction_window_id: str) -> dict[str, Any]:
        return {"data": self.reaction_windows[reaction_window_id].model_dump(mode="json"), "meta": {"schema_version": "1.0"}}

    def dialogue_projection(self, dialogue_session_id: str) -> dict[str, Any]:
        session = self.dialogue_sessions[dialogue_session_id]
        definition = self.dialogue_definitions[session.dialogue_id]
        data = session.model_dump(mode="json")
        data["available_choices"] = [choice.model_dump(mode="json") for choice in session.available_choices(definition, self._dialogue_context(session.actor_id))]
        return {"data": data, "meta": {"schema_version": "1.0"}}

    def branch_projection(self, branch_id: str) -> dict[str, Any]:
        return {"data": self.branches[branch_id].model_dump(mode="json"), "meta": {"schema_version": "1.0"}}

    @staticmethod
    def capability_projection() -> dict[str, Any]:
        return {"data": {"timing_modes": [mode.value for mode in TimingMode], "timeout_policies": [policy.value for policy in TimeoutPolicy], "controller_types": [controller.value for controller in ControllerType], "character_creation": {"species": sorted(REFERENCE_SPECIES), "backgrounds": sorted(REFERENCE_BACKGROUNDS)}, "features": ["timelines", "decision_windows", "reaction_windows", "ranged_combat", "healing_actions", "species_background_creation", "session_pause_resume", "dialogue_graphs", "crafting", "campaign_branch_metadata", "utility_ai"]}, "meta": {"schema_version": "1.0"}}
