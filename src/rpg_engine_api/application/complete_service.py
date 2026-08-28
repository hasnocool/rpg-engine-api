from typing import Any

from rpg_engine_api.application.release_service import ReleaseCandidateEngineService
from rpg_engine_api.domain.actor import reduce_actor
from rpg_engine_api.domain.character_creation import CharacterCreationStatus, REFERENCE_BACKGROUNDS, REFERENCE_SPECIES, reduce_character_creation
from rpg_engine_api.domain.character_runtime import ITEM_MODIFIERS, LEGACY_ARCHETYPE_CLASS, REFERENCE_CLASSES, REFERENCE_EQUIPMENT_SETS, REFERENCE_SUBCLASSES, default_ability_scores, validate_ability_scores
from rpg_engine_api.domain.commands import CommandEnvelope, CommandReceipt, CommandStatus, PrincipalContext
from rpg_engine_api.domain.events import DomainEvent
from rpg_engine_api.domain.ids import new_id


class CompleteEngineService(ReleaseCandidateEngineService):
    """Richer character/equipment/rest runtime while preserving legacy creation presets."""
    ACTOR_COMMANDS=ReleaseCandidateEngineService.ACTOR_COMMANDS|{"EquipItem","UnequipItem","PrepareAbilities","TakeRest"}

    async def _dispatch(self,command:CommandEnvelope,principal:PrincipalContext)->CommandReceipt:
        handlers={"SelectCharacterClass":self._select_class,"SelectCharacterSubclass":self._select_subclass,"SelectCharacterAbilities":self._select_abilities,"SelectCharacterProficiencies":self._select_proficiencies,"SelectCharacterEquipmentSet":self._select_equipment,"SelectCharacterPreparedAbilities":self._select_prepared,"EquipItem":self._equip_item,"UnequipItem":self._unequip_item,"PrepareAbilities":self._prepare_abilities,"TakeRest":self._take_rest}
        if command.command_type=="FinalizeCharacterCreation":return await self._finalize_complete(command,principal)
        handler=handlers.get(command.command_type)
        return await handler(command,principal) if handler else await super()._dispatch(command,principal)

    async def _select_class(self,command:CommandEnvelope,principal:PrincipalContext)->CommandReceipt:
        session=self._owned_creation(str(command.payload.get("creation_id","")),principal); class_id=str(command.payload.get("class_id",""))
        if class_id not in REFERENCE_CLASSES:raise ValueError("unknown class")
        return await self._append_creation_event(command,session,"CharacterClassSelected",{"class_id":class_id})
    async def _select_subclass(self,command:CommandEnvelope,principal:PrincipalContext)->CommandReceipt:
        session=self._owned_creation(str(command.payload.get("creation_id","")),principal); subclass=str(command.payload.get("subclass_id","")); class_id=session.class_id or LEGACY_ARCHETYPE_CLASS.get(session.archetype or "")
        if class_id is None or subclass not in REFERENCE_SUBCLASSES[class_id]:raise ValueError("subclass is not available for selected class")
        return await self._append_creation_event(command,session,"CharacterSubclassSelected",{"subclass_id":subclass})
    async def _select_abilities(self,command:CommandEnvelope,principal:PrincipalContext)->CommandReceipt:
        session=self._owned_creation(str(command.payload.get("creation_id","")),principal); values={str(k):int(v) for k,v in dict(command.payload.get("ability_scores",{})).items()};validate_ability_scores(values);return await self._append_creation_event(command,session,"CharacterAbilitiesSelected",{"ability_scores":values})
    async def _select_proficiencies(self,command:CommandEnvelope,principal:PrincipalContext)->CommandReceipt:
        session=self._owned_creation(str(command.payload.get("creation_id","")),principal);class_id=session.class_id or LEGACY_ARCHETYPE_CLASS.get(session.archetype or "")
        if class_id is None:raise ValueError("select class before proficiencies")
        values=sorted({str(x) for x in command.payload.get("proficiencies",[])});definition=REFERENCE_CLASSES[class_id]
        if len(values)!=int(definition["proficiency_count"]) or any(x not in definition["proficiency_choices"] for x in values):raise ValueError("invalid proficiency choices")
        return await self._append_creation_event(command,session,"CharacterProficienciesSelected",{"proficiencies":values})
    async def _select_equipment(self,command:CommandEnvelope,principal:PrincipalContext)->CommandReceipt:
        session=self._owned_creation(str(command.payload.get("creation_id","")),principal);class_id=session.class_id or LEGACY_ARCHETYPE_CLASS.get(session.archetype or "");selection=str(command.payload.get("equipment_set",""))
        if class_id is None or selection not in REFERENCE_EQUIPMENT_SETS[class_id]:raise ValueError("invalid equipment set")
        return await self._append_creation_event(command,session,"CharacterEquipmentSetSelected",{"equipment_set":selection})
    async def _select_prepared(self,command:CommandEnvelope,principal:PrincipalContext)->CommandReceipt:
        session=self._owned_creation(str(command.payload.get("creation_id","")),principal);class_id=session.class_id or LEGACY_ARCHETYPE_CLASS.get(session.archetype or "")
        if class_id is None:raise ValueError("select class before abilities")
        definition=REFERENCE_CLASSES[class_id];values=sorted({str(x) for x in command.payload.get("prepared_abilities",[])})
        if len(values)>int(definition.get("prepare_count",0)) or any(x not in definition.get("known_abilities",()) for x in values):raise ValueError("invalid prepared abilities")
        return await self._append_creation_event(command,session,"CharacterPreparedAbilitiesSelected",{"prepared_abilities":values})

    async def _finalize_complete(self,command:CommandEnvelope,principal:PrincipalContext)->CommandReceipt:
        creation_id=str(command.payload.get("creation_id",""));session=self._owned_creation(creation_id,principal)
        if not session.valid_for_finalize or session.status!=CharacterCreationStatus.DRAFT:raise ValueError("character creation requires name and class/archetype")
        assert session.name is not None
        class_id=session.class_id or LEGACY_ARCHETYPE_CLASS.get(session.archetype or "") or "warrior"; class_data=REFERENCE_CLASSES[class_id]; species=session.species or "human";background=session.background or "wanderer";species_data=REFERENCE_SPECIES[species];background_data=REFERENCE_BACKGROUNDS[background]
        abilities=session.ability_scores or default_ability_scores(class_id); proficiencies=session.proficiencies or list(class_data["proficiency_choices"][:int(class_data["proficiency_count"])]); equipment_set=session.equipment_set or next(iter(REFERENCE_EQUIPMENT_SETS[class_id]));equipment_data=REFERENCE_EQUIPMENT_SETS[class_id][equipment_set];known=list(class_data.get("known_abilities",()));prepared=session.prepared_abilities or known[:int(class_data.get("prepare_count",0))]
        attack_delta=sum(ITEM_MODIFIERS.get(item,{}).get("attack_bonus",0) for item in equipment_data["equipment"].values()); defense_delta=sum(ITEM_MODIFIERS.get(item,{}).get("defense",0) for item in equipment_data["equipment"].values())
        actor_id=str(command.payload.get("actor_id") or new_id("act"));base_hp=int(class_data["max_hp"])+int(species_data["max_hp_delta"])
        actor_receipt=await self._create_actor(CommandEnvelope(command_id=new_id("cmd"),command_type="CreateActor",campaign_id=session.campaign_id,payload={"actor_id":actor_id,"name":session.name,"max_hp":base_hp,"current_hp":base_hp,"attack_bonus":int(class_data["attack_bonus"])+int(species_data["attack_bonus_delta"]),"defense":int(class_data["defense"])+int(species_data["defense_delta"]),"controller":{"controller_type":"human","controller_version":"1"}}),principal)
        actor=self.actors[actor_id];astream=f"actor:{actor_id}";aexpected=await self.store.current_version(astream)
        origin=DomainEvent(event_type="CharacterOriginApplied",campaign_id=session.campaign_id,stream_id=astream,actor_id=actor_id,command_id=command.command_id,correlation_id=command.command_id,payload={"species":species,"background":background,"features":[background_data["feature"]],"items":[background_data["item"]]})
        build=DomainEvent(event_type="CharacterBuildApplied",campaign_id=session.campaign_id,stream_id=astream,actor_id=actor_id,command_id=command.command_id,correlation_id=command.command_id,payload={"class_id":class_id,"subclass_id":session.subclass_id,"ability_scores":abilities,"proficiencies":proficiencies,"known_abilities":known,"prepared_abilities":prepared,"items":list(equipment_data["items"]),"equipment":dict(equipment_data["equipment"]),"resources":dict(class_data.get("resources",{})),"attack_bonus_delta":attack_delta,"defense_delta":defense_delta})
        astored=await self.store.append(astream,aexpected,(origin,build));state=actor
        for event in astored:state=reduce_actor(state,event)
        self.actors[actor_id]=state
        cstream=f"character_creation:{creation_id}";cexpected=await self.store.current_version(cstream);finalized=DomainEvent(event_type="CharacterCreationFinalized",campaign_id=session.campaign_id,stream_id=cstream,actor_id=actor_id,command_id=command.command_id,correlation_id=command.command_id,payload={"actor_id":actor_id,"class_id":class_id,"subclass_id":session.subclass_id,"species":species,"background":background});cstored=await self.store.append(cstream,cexpected,(finalized,));self.character_creations[creation_id]=reduce_character_creation(session,cstored[0]);events=actor_receipt.emitted_event_ids+tuple(e.event_id for e in astored)+(cstored[0].event_id,)
        return CommandReceipt(command_id=command.command_id,status=CommandStatus.ACCEPTED,emitted_event_ids=events,stream_versions={**actor_receipt.stream_versions,astream:astored[-1].stream_version,cstream:cstored[-1].stream_version},result={"campaign_id":session.campaign_id,"creation_id":creation_id,"actor_id":actor_id,"class_id":class_id,"subclass_id":session.subclass_id,"species":species,"background":background})

    async def _actor_event(self,command:CommandEnvelope,event_type:str,payload:dict[str,object])->CommandReceipt:
        actor_id=command.actor_id or str(command.payload.get("actor_id",""));actor=self.actors.get(actor_id)
        if actor is None:raise KeyError("actor does not exist")
        stream=f"actor:{actor_id}";event=DomainEvent(event_type=event_type,campaign_id=actor.campaign_id,stream_id=stream,actor_id=actor_id,command_id=command.command_id,correlation_id=command.command_id,payload=payload);stored=await self.store.append(stream,await self.store.current_version(stream),(event,));self.actors[actor_id]=reduce_actor(actor,stored[0]);return CommandReceipt(command_id=command.command_id,status=CommandStatus.ACCEPTED,emitted_event_ids=(stored[0].event_id,),stream_versions={stream:stored[0].stream_version},result={"actor_id":actor_id,"campaign_id":actor.campaign_id})
    async def _equip_item(self,command:CommandEnvelope,principal:PrincipalContext)->CommandReceipt:
        del principal;actor_id=command.actor_id or str(command.payload.get("actor_id",""));actor=self.actors[actor_id];item=str(command.payload.get("item_id",""));slot=str(command.payload.get("slot",""))
        if item not in actor.inventory:raise ValueError("actor does not own item")
        old=actor.equipment.get(slot);old_mod=ITEM_MODIFIERS.get(old or "",{});new_mod=ITEM_MODIFIERS.get(item,{})
        return await self._actor_event(command,"ItemEquipped",{"slot":slot,"item_id":item,"attack_bonus_delta":new_mod.get("attack_bonus",0)-old_mod.get("attack_bonus",0),"defense_delta":new_mod.get("defense",0)-old_mod.get("defense",0)})
    async def _unequip_item(self,command:CommandEnvelope,principal:PrincipalContext)->CommandReceipt:
        del principal;actor_id=command.actor_id or str(command.payload.get("actor_id",""));actor=self.actors[actor_id];slot=str(command.payload.get("slot",""));item=actor.equipment.get(slot)
        if item is None:raise ValueError("equipment slot is empty")
        mod=ITEM_MODIFIERS.get(item,{})
        return await self._actor_event(command,"ItemUnequipped",{"slot":slot,"item_id":item,"attack_bonus_delta":-mod.get("attack_bonus",0),"defense_delta":-mod.get("defense",0)})
    async def _prepare_abilities(self,command:CommandEnvelope,principal:PrincipalContext)->CommandReceipt:
        del principal;actor_id=command.actor_id or str(command.payload.get("actor_id",""));actor=self.actors[actor_id];class_data=REFERENCE_CLASSES.get(actor.class_id or "",{});values=sorted({str(x) for x in command.payload.get("prepared_abilities",[])})
        if len(values)>int(class_data.get("prepare_count",0)) or any(x not in actor.known_abilities for x in values):raise ValueError("invalid prepared abilities")
        return await self._actor_event(command,"AbilitiesPrepared",{"prepared_abilities":values})
    async def _take_rest(self,command:CommandEnvelope,principal:PrincipalContext)->CommandReceipt:
        del principal;actor_id=command.actor_id or str(command.payload.get("actor_id",""));actor=self.actors[actor_id]
        if any(e.status.value=="active" and actor_id in e.participants for e in self.encounters.values()):raise ValueError("cannot rest during active encounter")
        kind=str(command.payload.get("rest_type","short"));resources=dict(actor.resources);conditions=list(actor.conditions);hp=actor.current_hp
        if kind=="short": hp=min(actor.max_hp,hp+max(1,actor.max_hp//4)); resources["stamina"]=actor.resource_maxima.get("stamina",resources.get("stamina",0))
        elif kind=="long": hp=actor.max_hp;resources=dict(actor.resource_maxima);conditions=[]
        else:raise ValueError("rest_type must be short or long")
        receipt=await self._actor_event(command,"ActorRested",{"rest_type":kind,"current_hp":hp,"resources":resources,"conditions":conditions});return receipt.model_copy(update={"result":{**receipt.result,"rest_type":kind,"current_hp":hp,"resources":resources}})

    def available_actions(self,actor_id:str)->list[dict[str,Any]]:
        actions=super().available_actions(actor_id);actor=self.actors[actor_id]
        if not any(e.status.value=="active" and actor_id in e.participants for e in self.encounters.values()):
            if actor.current_hp<actor.max_hp or any(actor.resources.get(k,0)<v for k,v in actor.resource_maxima.items()):actions.append({"action_id":"rest_short","label":"Take a short rest","command_type":"TakeRest","campaign_id":actor.campaign_id,"actor_id":actor_id,"rest_type":"short"});actions.append({"action_id":"rest_long","label":"Take a long rest","command_type":"TakeRest","campaign_id":actor.campaign_id,"actor_id":actor_id,"rest_type":"long"})
        return actions

    @classmethod
    def capability_projection(cls)->dict[str,Any]:
        base=super().capability_projection();data=dict(base["data"]);data["features"]=list(data.get("features",[]))+["classes_subclasses","ability_scores","proficiencies","equipment_slots","known_prepared_abilities","persistent_actor_health","short_long_rest"];data["classes"]={key:{"label":value["label"],"subclasses":list(REFERENCE_SUBCLASSES[key])} for key,value in REFERENCE_CLASSES.items()};return {"data":data,"meta":{"schema_version":"1.2"}}
