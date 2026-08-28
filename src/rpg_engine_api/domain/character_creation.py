from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from rpg_engine_api.domain.events import DomainEvent


class CharacterCreationStatus(StrEnum):
    DRAFT = "draft"
    FINALIZED = "finalized"
    CANCELLED = "cancelled"


REFERENCE_ARCHETYPES: dict[str, dict[str, Any]] = {
    "guardian": {"label": "Guardian", "max_hp": 22, "attack_bonus": 4, "defense": 14},
    "scout": {"label": "Scout", "max_hp": 16, "attack_bonus": 6, "defense": 12},
    "adept": {"label": "Adept", "max_hp": 18, "attack_bonus": 5, "defense": 12},
}

REFERENCE_SPECIES: dict[str, dict[str, Any]] = {
    "human": {"label": "Human", "max_hp_delta": 1, "attack_bonus_delta": 0, "defense_delta": 0},
    "elf": {"label": "Elf", "max_hp_delta": 0, "attack_bonus_delta": 1, "defense_delta": 0},
    "dwarf": {"label": "Dwarf", "max_hp_delta": 2, "attack_bonus_delta": 0, "defense_delta": 1},
    "halfling": {"label": "Halfling", "max_hp_delta": 0, "attack_bonus_delta": 0, "defense_delta": 1},
}

REFERENCE_BACKGROUNDS: dict[str, dict[str, Any]] = {
    "wanderer": {"label": "Wanderer", "feature": "trailwise", "item": "traveler_pack"},
    "soldier": {"label": "Soldier", "feature": "martial_training", "item": "field_kit"},
    "scholar": {"label": "Scholar", "feature": "lore_training", "item": "reference_notes"},
    "artisan": {"label": "Artisan", "feature": "craft_training", "item": "artisan_tools"},
}


def character_creation_schema() -> dict[str, Any]:
    return {
        "schema_version": "1.1",
        "steps": [
            {"id": "name", "type": "text", "required": True},
            {
                "id": "archetype",
                "type": "single_choice",
                "required": True,
                "options": [{"id": key, "label": value["label"]} for key, value in sorted(REFERENCE_ARCHETYPES.items())],
            },
            {
                "id": "species",
                "type": "single_choice",
                "required": False,
                "default": "human",
                "options": [{"id": key, "label": value["label"]} for key, value in sorted(REFERENCE_SPECIES.items())],
            },
            {
                "id": "background",
                "type": "single_choice",
                "required": False,
                "default": "wanderer",
                "options": [{"id": key, "label": value["label"]} for key, value in sorted(REFERENCE_BACKGROUNDS.items())],
            },
            {"id": "finalize", "type": "finalize", "required": True},
        ],
    }


class CharacterCreationSession(BaseModel):
    schema_version: str = "1.1"
    creation_id: str
    campaign_id: str
    principal_id: str
    status: CharacterCreationStatus = CharacterCreationStatus.DRAFT
    name: str | None = None
    archetype: str | None = None
    species: str | None = None
    background: str | None = None
    actor_id: str | None = None
    stream_version: int = 0
    errors: list[str] = Field(default_factory=list)

    @property
    def valid_for_finalize(self) -> bool:
        return bool(self.name and self.archetype in REFERENCE_ARCHETYPES)


def reduce_character_creation(state: CharacterCreationSession | None, event: DomainEvent) -> CharacterCreationSession:
    if event.event_type == "CharacterCreationStarted":
        return CharacterCreationSession(
            creation_id=str(event.payload["creation_id"]),
            campaign_id=event.campaign_id,
            principal_id=str(event.payload["principal_id"]),
            stream_version=event.stream_version,
        )
    if state is None:
        raise ValueError("character creation stream must start with CharacterCreationStarted")
    next_state = state.model_copy(deep=True)
    next_state.stream_version = event.stream_version
    if event.event_type == "CharacterNameSelected":
        next_state.name = str(event.payload["name"])
    elif event.event_type == "CharacterArchetypeSelected":
        next_state.archetype = str(event.payload["archetype"])
    elif event.event_type == "CharacterSpeciesSelected":
        next_state.species = str(event.payload["species"])
    elif event.event_type == "CharacterBackgroundSelected":
        next_state.background = str(event.payload["background"])
    elif event.event_type == "CharacterCreationFinalized":
        next_state.status = CharacterCreationStatus.FINALIZED
        next_state.actor_id = str(event.payload["actor_id"])
        next_state.species = str(event.payload.get("species") or next_state.species or "human")
        next_state.background = str(event.payload.get("background") or next_state.background or "wanderer")
    return next_state
