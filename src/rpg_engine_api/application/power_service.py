from typing import Any

from rpg_engine_api.application.gameplay_service import GameplayEngineService
from rpg_engine_api.domain.actor import reduce_actor
from rpg_engine_api.domain.commands import CommandEnvelope, CommandReceipt, CommandStatus, PrincipalContext
from rpg_engine_api.domain.encounter import EncounterStatus, reduce_encounter
from rpg_engine_api.domain.events import DomainEvent
from rpg_engine_api.domain.timeline import WindowStatus
from rpg_engine_api.persistence.event_store import StreamVersionConflict


class PowerEngineService(GameplayEngineService):
    """Prepared abilities execute through the same authoritative PerformAction command."""

    POWER_ACTIONS = {
        "ability:arcane_bolt": "arcane_bolt",
        "ability:radiant_bolt": "radiant_bolt",
        "ability:healing_prayer": "healing_prayer",
        "ability:ward": "ward",
    }

    def available_actions(self, actor_id: str) -> list[dict[str, Any]]:
        actions = super().available_actions(actor_id)
        encounter = next((value for value in self.encounters.values() if value.status == EncounterStatus.ACTIVE and actor_id in value.participants), None)
        if encounter is None or encounter.current_actor_id != actor_id:
            return actions
        actor = self.actors[actor_id]
        if actor.resources.get("spell_slots", 0) <= 0:
            return actions
        participant = encounter.participants[actor_id]
        enemies = sorted((item for item in encounter.participants.values() if item.alive and item.side != participant.side), key=lambda item: (abs(item.position - participant.position), item.actor_id))
        allies = sorted((item for item in encounter.participants.values() if item.alive and item.side == participant.side), key=lambda item: (item.hp_ratio, item.actor_id))
        base = {"command_type": "PerformAction", "campaign_id": actor.campaign_id, "actor_id": actor_id, "encounter_id": encounter.encounter_id}
        if "arcane_bolt" in actor.prepared_abilities:
            for enemy in enemies:
                if abs(enemy.position - participant.position) <= 4:
                    actions.append({**base, "action_id": "ability:arcane_bolt", "label": f"Arcane bolt {enemy.actor_id}", "target_id": enemy.actor_id, "category": "attack", "tags": ("magic", "ranged")})
        if "radiant_bolt" in actor.prepared_abilities:
            for enemy in enemies:
                if abs(enemy.position - participant.position) <= 4:
                    actions.append({**base, "action_id": "ability:radiant_bolt", "label": f"Radiant bolt {enemy.actor_id}", "target_id": enemy.actor_id, "category": "attack", "tags": ("magic", "ranged")})
        if "healing_prayer" in actor.prepared_abilities:
            for ally in allies:
                if ally.hp < ally.max_hp and abs(ally.position - participant.position) <= 4:
                    actions.append({**base, "action_id": "ability:healing_prayer", "label": f"Heal {ally.actor_id}", "target_id": ally.actor_id, "category": "support", "tags": ("magic", "support")})
        if "ward" in actor.prepared_abilities:
            actions.append({**base, "action_id": "ability:ward", "label": "Raise arcane ward", "target_id": actor_id, "category": "defense", "tags": ("magic", "defense")})
        return actions

    async def _perform_action(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        action_id = str(command.payload.get("action_id", ""))
        if action_id not in self.POWER_ACTIONS:
            return await super()._perform_action(command, principal)
        encounter_id = str(command.payload.get("encounter_id", "")); encounter = self.encounters.get(encounter_id)
        if encounter is None: raise KeyError("encounter does not exist")
        actor_id = command.actor_id or str(command.payload.get("actor_id", "")); actor = self.actors.get(actor_id)
        if actor is None: raise KeyError("actor does not exist")
        if encounter.current_actor_id != actor_id: raise ValueError("actor is not ready")
        target_id = str(command.payload.get("target_id", actor_id))
        if not any(item["action_id"] == action_id and str(item.get("target_id", actor_id)) == target_id for item in self.available_actions(actor_id)):
            raise ValueError("ability/target is not currently available")
        if actor.resources.get("spell_slots", 0) <= 0: raise ValueError("ability requires an available spell slot")
        timeline = self._ensure_timeline(encounter.campaign_id); window_id = self.encounter_window_ids.get(encounter_id)
        if window_id is not None:
            window = timeline.windows[window_id]
            if window.actor_id != actor_id or window.status != WindowStatus.OPEN: raise ValueError("actor decision window is not open")
            if window.deadline_at is not None and timeline.clock.now > window.deadline_at: raise ValueError("actor decision deadline has expired")
        encounter_stream=f"encounter:{encounter_id}"; actor_stream=f"actor:{actor_id}"; actual=await self.store.current_version(encounter_stream);expected=command.expected_stream_version if command.expected_stream_version is not None else actual
        if expected!=actual: raise StreamVersionConflict(encounter_stream,expected,actual)
        base={"campaign_id":encounter.campaign_id,"stream_id":encounter_stream,"actor_id":actor_id,"command_id":command.command_id,"correlation_id":command.command_id}; events:list[DomainEvent]=[]; power=self.POWER_ACTIONS[action_id]; source=encounter.participants[actor_id]
        if power in {"arcane_bolt","radiant_bolt"}:
            target=encounter.participants[target_id]; attack=self._rng[encounter.campaign_id].roll("1d20",stream="dice");attack_total=attack.total+actor.attack_bonus;target_defense=self.actors[target_id].defense+target.guard;hit=attack_total>=target_defense;damage_roll=self._rng[encounter.campaign_id].roll("1d6+2" if power=="arcane_bolt" else "1d6+1",stream="dice") if hit else None;damage=damage_roll.total if damage_roll else 0
            events.append(DomainEvent(event_type="RangedAttackResolved",payload={"actor_id":actor_id,"target_id":target_id,"ability_id":power,"attack_roll":attack.rolls,"attack_total":attack_total,"target_defense":target_defense,"hit":hit,"damage_roll":damage_roll.rolls if damage_roll else (),"damage":damage,"target_hp":max(0,target.hp-damage)},**base))
        elif power=="healing_prayer":
            target=encounter.participants[target_id];heal=self._rng[encounter.campaign_id].roll("1d6+2",stream="dice");events.append(DomainEvent(event_type="HealingApplied",payload={"source_actor_id":actor_id,"target_id":target_id,"ability_id":power,"amount":heal.total,"rolls":heal.rolls,"target_hp":min(target.max_hp,target.hp+heal.total)},**base))
        else:
            events.append(DomainEvent(event_type="GuardRaised",payload={"actor_id":actor_id,"guard":3,"ability_id":power},**base))
        preview=encounter
        for event in events: preview=reduce_encounter(preview,event)
        alive_sides={item.side for item in preview.participants.values() if item.alive}
        if len(alive_sides)==1: events.append(DomainEvent(event_type="EncounterCompleted",payload={"winner_side":next(iter(alive_sides))},**base))
        else:
            next_index,next_round=self._next_living_turn(preview);events.append(DomainEvent(event_type="TurnAdvanced",payload={"turn_index":next_index,"round":next_round},**base))
        resource=DomainEvent(event_type="ActorResourceChanged",campaign_id=actor.campaign_id,stream_id=actor_stream,actor_id=actor_id,command_id=command.command_id,correlation_id=command.command_id,payload={"resource_id":"spell_slots","current":actor.resources["spell_slots"]-1,"source":power})
        stored=await self.store.append_many(((encounter_stream,expected,tuple(events)),(actor_stream,await self.store.current_version(actor_stream),(resource,))))
        state=encounter
        for event in stored[encounter_stream]: state=reduce_encounter(state,event)
        self.encounters[encounter_id]=state;self.actors[actor_id]=reduce_actor(actor,stored[actor_stream][0]);reward_ids:tuple[str,...]=();reward_versions:dict[str,int]={}
        if encounter.status==EncounterStatus.ACTIVE and state.status==EncounterStatus.COMPLETED: reward_ids,reward_versions=await self._grant_encounter_rewards(state,command.command_id)
        if window_id is not None and timeline.windows[window_id].status==WindowStatus.OPEN: timeline.resolve_window(window_id)
        self._open_current_window(encounter_id)
        all_events=stored[encounter_stream]+stored[actor_stream];receipt=CommandReceipt(command_id=command.command_id,status=CommandStatus.ACCEPTED,emitted_event_ids=tuple(event.event_id for event in all_events)+reward_ids,stream_versions={encounter_stream:stored[encounter_stream][-1].stream_version,actor_stream:stored[actor_stream][-1].stream_version,**reward_versions},result={"campaign_id":encounter.campaign_id,"encounter_id":encounter_id,"action_id":action_id,"ability_id":power,"spell_slots":self.actors[actor_id].resources.get("spell_slots",0)})
        return self._merge_receipts(receipt,await self._persist_decision_window(command,encounter_id))

    @classmethod
    def capability_projection(cls)->dict[str,Any]:
        base=super().capability_projection();data=dict(base["data"]);data["features"]=list(data.get("features",[]))+["prepared_power_actions","spell_slot_costs","magic_attack_heal_ward"] ;return {"data":data,"meta":{"schema_version":"1.4"}}
