from pydantic import BaseModel, Field
from .controllers import ControllerAssignment
from .events import DomainEvent

class ActorState(BaseModel):
    schema_version:str="1.3"; actor_id:str; campaign_id:str; name:str; controller:ControllerAssignment
    max_hp:int=10; current_hp:int=10; attack_bonus:int=2; defense:int=10; level:int=1; experience:int=0; progression_points:int=0
    features:list[str]=Field(default_factory=list); currency:int=10; inventory:list[str]=Field(default_factory=list); equipment:dict[str,str]=Field(default_factory=dict)
    species:str|None=None; background:str|None=None; class_id:str|None=None; subclass_id:str|None=None; ability_scores:dict[str,int]=Field(default_factory=dict); proficiencies:list[str]=Field(default_factory=list); known_abilities:list[str]=Field(default_factory=list); prepared_abilities:list[str]=Field(default_factory=list)
    resources:dict[str,int]=Field(default_factory=dict); resource_maxima:dict[str,int]=Field(default_factory=dict); conditions:list[str]=Field(default_factory=list); tags:list[str]=Field(default_factory=list); stream_version:int=0

def reduce_actor(state:ActorState|None,event:DomainEvent)->ActorState:
    if event.event_type=="ActorCreated":
        maximum=int(event.payload.get("max_hp",10)); return ActorState(actor_id=str(event.payload["actor_id"]),campaign_id=event.campaign_id,name=str(event.payload["name"]),controller=ControllerAssignment.model_validate(event.payload["controller"]),max_hp=maximum,current_hp=int(event.payload.get("current_hp",maximum)),attack_bonus=int(event.payload.get("attack_bonus",2)),defense=int(event.payload.get("defense",10)),currency=int(event.payload.get("currency",10)),stream_version=event.stream_version)
    if state is None: raise ValueError("actor stream must start with ActorCreated")
    s=state.model_copy(deep=True); s.stream_version=event.stream_version
    if event.event_type=="ExperienceGranted": s.experience+=int(event.payload["experience"]); s.progression_points+=int(event.payload.get("progression_points",0)); s.level=max(s.level,int(event.payload.get("new_level",s.level)))
    elif event.event_type=="ProgressionChoiceApplied":
        feature=str(event.payload["feature"])
        if feature not in s.features:s.features.append(feature);s.features.sort()
        s.progression_points=int(event.payload["progression_points"]); s.max_hp+=int(event.payload.get("max_hp_delta",0)); s.current_hp=min(s.max_hp,s.current_hp+int(event.payload.get("max_hp_delta",0))); s.attack_bonus+=int(event.payload.get("attack_bonus_delta",0)); s.defense+=int(event.payload.get("defense_delta",0))
    elif event.event_type=="ItemPurchased": s.currency=int(event.payload["currency_after"]);s.inventory.append(str(event.payload["item_id"]));s.inventory.sort()
    elif event.event_type=="ItemSold":
        s.currency=int(event.payload["currency_after"]); item=str(event.payload["item_id"])
        if item in s.inventory:s.inventory.remove(item)
        for slot,value in list(s.equipment.items()):
            if value==item:s.equipment.pop(slot,None)
    elif event.event_type=="ItemGranted": s.inventory.append(str(event.payload["item_id"]));s.inventory.sort()
    elif event.event_type=="CharacterOriginApplied":
        s.species=str(event.payload["species"]);s.background=str(event.payload["background"])
        for feature in event.payload.get("features",[]):
            value=str(feature)
            if value not in s.features:s.features.append(value)
        s.inventory.extend(str(item) for item in event.payload.get("items",[]));s.features.sort();s.inventory.sort()
    elif event.event_type=="CharacterBuildApplied":
        s.class_id=str(event.payload["class_id"]);s.subclass_id=event.payload.get("subclass_id");s.ability_scores={str(k):int(v) for k,v in dict(event.payload.get("ability_scores",{})).items()};s.proficiencies=sorted(str(x) for x in event.payload.get("proficiencies",[]));s.known_abilities=sorted(str(x) for x in event.payload.get("known_abilities",[]));s.prepared_abilities=sorted(str(x) for x in event.payload.get("prepared_abilities",[]));s.inventory.extend(str(x) for x in event.payload.get("items",[]));s.inventory.sort();s.equipment={str(k):str(v) for k,v in dict(event.payload.get("equipment",{})).items()};s.resources={str(k):int(v) for k,v in dict(event.payload.get("resources",{})).items()};s.resource_maxima=dict(s.resources);s.attack_bonus+=int(event.payload.get("attack_bonus_delta",0));s.defense+=int(event.payload.get("defense_delta",0))
    elif event.event_type=="ItemCrafted":
        for ingredient in event.payload.get("ingredients",[]):
            value=str(ingredient)
            if value in s.inventory:s.inventory.remove(value)
        s.inventory.append(str(event.payload["result_item_id"]));s.inventory.sort()
    elif event.event_type=="ItemEquipped": s.equipment[str(event.payload["slot"])]=str(event.payload["item_id"]);s.attack_bonus+=int(event.payload.get("attack_bonus_delta",0));s.defense+=int(event.payload.get("defense_delta",0))
    elif event.event_type=="ItemUnequipped": s.equipment.pop(str(event.payload["slot"]),None);s.attack_bonus+=int(event.payload.get("attack_bonus_delta",0));s.defense+=int(event.payload.get("defense_delta",0))
    elif event.event_type=="AbilitiesPrepared": s.prepared_abilities=sorted(str(x) for x in event.payload.get("prepared_abilities",[]))
    elif event.event_type=="ActorRested": s.current_hp=int(event.payload.get("current_hp",s.current_hp));s.resources={str(k):int(v) for k,v in dict(event.payload.get("resources",s.resources)).items()};s.conditions=[str(x) for x in event.payload.get("conditions",s.conditions)]
    elif event.event_type=="ActorEncounterStateSynchronized": s.current_hp=int(event.payload.get("current_hp",s.current_hp))
    elif event.event_type=="ControllerAssignmentChanged": s.controller=ControllerAssignment.model_validate(event.payload["controller"])
    elif event.event_type=="ActorResourceChanged": s.resources[str(event.payload["resource_id"])]=int(event.payload["current"])
    elif event.event_type=="ActorConditionApplied":
        condition=str(event.payload["condition_id"])
        if condition not in s.conditions:s.conditions.append(condition);s.conditions.sort()
    elif event.event_type=="ActorConditionRemoved": s.conditions=[x for x in s.conditions if x!=str(event.payload["condition_id"])]
    return s
