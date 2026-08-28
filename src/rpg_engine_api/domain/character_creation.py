from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from rpg_engine_api.domain.character_runtime import ABILITY_NAMES, REFERENCE_CLASSES, REFERENCE_EQUIPMENT_SETS, REFERENCE_SUBCLASSES
from rpg_engine_api.domain.events import DomainEvent


class CharacterCreationStatus(StrEnum): DRAFT="draft"; FINALIZED="finalized"; CANCELLED="cancelled"

REFERENCE_ARCHETYPES: dict[str, dict[str, Any]] = {"guardian":{"label":"Guardian","max_hp":22,"attack_bonus":4,"defense":14},"scout":{"label":"Scout","max_hp":16,"attack_bonus":6,"defense":12},"adept":{"label":"Adept","max_hp":18,"attack_bonus":5,"defense":12}}
REFERENCE_SPECIES: dict[str, dict[str, Any]] = {"human":{"label":"Human","max_hp_delta":1,"attack_bonus_delta":0,"defense_delta":0},"elf":{"label":"Elf","max_hp_delta":0,"attack_bonus_delta":1,"defense_delta":0},"dwarf":{"label":"Dwarf","max_hp_delta":2,"attack_bonus_delta":0,"defense_delta":1},"halfling":{"label":"Halfling","max_hp_delta":0,"attack_bonus_delta":0,"defense_delta":1}}
REFERENCE_BACKGROUNDS: dict[str, dict[str, Any]] = {"wanderer":{"label":"Wanderer","feature":"trailwise","item":"traveler_pack"},"soldier":{"label":"Soldier","feature":"martial_training","item":"field_kit"},"scholar":{"label":"Scholar","feature":"lore_training","item":"reference_notes"},"artisan":{"label":"Artisan","feature":"craft_training","item":"artisan_tools"}}


def character_creation_schema()->dict[str,Any]:
    return {"schema_version":"1.2","steps":[
        {"id":"name","type":"text","required":True},
        {"id":"class","type":"single_choice","required":False,"options":[{"id":k,"label":v["label"]} for k,v in sorted(REFERENCE_CLASSES.items())]},
        {"id":"subclass","type":"dependent_single_choice","required":False,"depends_on":"class","options_by_parent":{k:list(v) for k,v in REFERENCE_SUBCLASSES.items()}},
        {"id":"archetype","type":"single_choice","required":False,"legacy":True,"options":[{"id":k,"label":v["label"]} for k,v in sorted(REFERENCE_ARCHETYPES.items())]},
        {"id":"species","type":"single_choice","required":False,"default":"human","options":[{"id":k,"label":v["label"]} for k,v in sorted(REFERENCE_SPECIES.items())]},
        {"id":"background","type":"single_choice","required":False,"default":"wanderer","options":[{"id":k,"label":v["label"]} for k,v in sorted(REFERENCE_BACKGROUNDS.items())]},
        {"id":"abilities","type":"fixed_array_assignment","required":False,"abilities":list(ABILITY_NAMES),"values":[15,14,13,12,10,8]},
        {"id":"proficiencies","type":"multi_choice","required":False,"options_by_class":{k:list(v["proficiency_choices"]) for k,v in REFERENCE_CLASSES.items()},"count_by_class":{k:int(v["proficiency_count"]) for k,v in REFERENCE_CLASSES.items()}},
        {"id":"equipment_set","type":"dependent_single_choice","required":False,"options_by_class":{k:list(v) for k,v in REFERENCE_EQUIPMENT_SETS.items()}},
        {"id":"prepared_abilities","type":"multi_choice","required":False,"options_by_class":{k:list(v.get("known_abilities",())) for k,v in REFERENCE_CLASSES.items()},"count_by_class":{k:int(v.get("prepare_count",0)) for k,v in REFERENCE_CLASSES.items()}},
        {"id":"finalize","type":"finalize","required":True}]}


class CharacterCreationSession(BaseModel):
    schema_version:str="1.2"; creation_id:str; campaign_id:str; principal_id:str; status:CharacterCreationStatus=CharacterCreationStatus.DRAFT
    name:str|None=None; archetype:str|None=None; class_id:str|None=None; subclass_id:str|None=None; species:str|None=None; background:str|None=None
    ability_scores:dict[str,int]=Field(default_factory=dict); proficiencies:list[str]=Field(default_factory=list); equipment_set:str|None=None; prepared_abilities:list[str]=Field(default_factory=list)
    actor_id:str|None=None; stream_version:int=0; errors:list[str]=Field(default_factory=list)
    @property
    def valid_for_finalize(self)->bool: return bool(self.name and (self.archetype in REFERENCE_ARCHETYPES or self.class_id in REFERENCE_CLASSES))


def reduce_character_creation(state:CharacterCreationSession|None,event:DomainEvent)->CharacterCreationSession:
    if event.event_type=="CharacterCreationStarted": return CharacterCreationSession(creation_id=str(event.payload["creation_id"]),campaign_id=event.campaign_id,principal_id=str(event.payload["principal_id"]),stream_version=event.stream_version)
    if state is None: raise ValueError("character creation stream must start with CharacterCreationStarted")
    next_state=state.model_copy(deep=True); next_state.stream_version=event.stream_version
    if event.event_type=="CharacterNameSelected": next_state.name=str(event.payload["name"])
    elif event.event_type=="CharacterArchetypeSelected": next_state.archetype=str(event.payload["archetype"])
    elif event.event_type=="CharacterClassSelected": next_state.class_id=str(event.payload["class_id"]); next_state.subclass_id=None; next_state.proficiencies=[]; next_state.equipment_set=None; next_state.prepared_abilities=[]
    elif event.event_type=="CharacterSubclassSelected": next_state.subclass_id=str(event.payload["subclass_id"])
    elif event.event_type=="CharacterSpeciesSelected": next_state.species=str(event.payload["species"])
    elif event.event_type=="CharacterBackgroundSelected": next_state.background=str(event.payload["background"])
    elif event.event_type=="CharacterAbilitiesSelected": next_state.ability_scores={str(k):int(v) for k,v in dict(event.payload["ability_scores"]).items()}
    elif event.event_type=="CharacterProficienciesSelected": next_state.proficiencies=sorted(str(item) for item in event.payload["proficiencies"])
    elif event.event_type=="CharacterEquipmentSetSelected": next_state.equipment_set=str(event.payload["equipment_set"])
    elif event.event_type=="CharacterPreparedAbilitiesSelected": next_state.prepared_abilities=sorted(str(item) for item in event.payload["prepared_abilities"])
    elif event.event_type=="CharacterCreationFinalized": next_state.status=CharacterCreationStatus.FINALIZED; next_state.actor_id=str(event.payload["actor_id"]); next_state.species=str(event.payload.get("species") or next_state.species or "human"); next_state.background=str(event.payload.get("background") or next_state.background or "wanderer"); next_state.class_id=str(event.payload.get("class_id") or next_state.class_id or "warrior"); next_state.subclass_id=event.payload.get("subclass_id") or next_state.subclass_id
    return next_state
