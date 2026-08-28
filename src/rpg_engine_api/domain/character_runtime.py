from typing import Any

ABILITY_NAMES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
FIXED_ARRAY = (15, 14, 13, 12, 10, 8)

REFERENCE_CLASSES: dict[str, dict[str, Any]] = {
    "warrior": {"label": "Warrior", "max_hp": 24, "attack_bonus": 4, "defense": 13, "proficiency_choices": ("athletics", "intimidation", "survival"), "proficiency_count": 2, "known_abilities": ("second_wind",), "resources": {"stamina": 2}},
    "rogue": {"label": "Rogue", "max_hp": 17, "attack_bonus": 6, "defense": 12, "proficiency_choices": ("stealth", "acrobatics", "perception", "deception"), "proficiency_count": 2, "known_abilities": ("quick_step",), "resources": {"stamina": 2}},
    "mage": {"label": "Mage", "max_hp": 14, "attack_bonus": 5, "defense": 10, "proficiency_choices": ("arcana", "history", "investigation", "insight"), "proficiency_count": 2, "known_abilities": ("arcane_bolt", "ward", "light"), "prepare_count": 2, "resources": {"spell_slots": 2}},
    "healer": {"label": "Healer", "max_hp": 19, "attack_bonus": 4, "defense": 12, "proficiency_choices": ("medicine", "insight", "religion", "persuasion"), "proficiency_count": 2, "known_abilities": ("healing_prayer", "radiant_bolt", "blessing"), "prepare_count": 2, "resources": {"spell_slots": 2}},
}

REFERENCE_SUBCLASSES: dict[str, tuple[str, ...]] = {
    "warrior": ("vanguard", "guardian"),
    "rogue": ("scout", "shadow"),
    "mage": ("elementalist", "sage"),
    "healer": ("life_keeper", "warden"),
}

REFERENCE_EQUIPMENT_SETS: dict[str, dict[str, Any]] = {
    "warrior": {"martial": {"items": ("starter:sword", "starter:shield", "starter:field_pack"), "equipment": {"weapon": "starter:sword", "off_hand": "starter:shield"}}, "heavy": {"items": ("starter:axe", "starter:mail", "starter:field_pack"), "equipment": {"weapon": "starter:axe", "armor": "starter:mail"}}},
    "rogue": {"skirmisher": {"items": ("starter:shortbow", "starter:dagger", "starter:tools"), "equipment": {"weapon": "starter:shortbow", "off_hand": "starter:dagger"}}},
    "mage": {"scholar": {"items": ("starter:staff", "starter:focus", "starter:spellbook"), "equipment": {"weapon": "starter:staff", "focus": "starter:focus"}}},
    "healer": {"pilgrim": {"items": ("starter:mace", "starter:symbol", "starter:healer_kit"), "equipment": {"weapon": "starter:mace", "focus": "starter:symbol"}}},
}

ITEM_MODIFIERS: dict[str, dict[str, int]] = {
    "starter:sword": {"attack_bonus": 1}, "starter:axe": {"attack_bonus": 1}, "starter:shortbow": {"attack_bonus": 1},
    "starter:shield": {"defense": 1}, "starter:mail": {"defense": 2}, "starter:staff": {"attack_bonus": 1}, "starter:mace": {"attack_bonus": 1},
}

LEGACY_ARCHETYPE_CLASS = {"guardian": "warrior", "scout": "rogue", "adept": "mage"}


def default_ability_scores(class_id: str) -> dict[str, int]:
    orders = {
        "warrior": ("strength", "constitution", "dexterity", "wisdom", "charisma", "intelligence"),
        "rogue": ("dexterity", "intelligence", "charisma", "wisdom", "constitution", "strength"),
        "mage": ("intelligence", "dexterity", "wisdom", "constitution", "charisma", "strength"),
        "healer": ("wisdom", "constitution", "charisma", "strength", "dexterity", "intelligence"),
    }
    order = orders[class_id]
    return {ability: value for ability, value in zip(order, FIXED_ARRAY, strict=True)}


def validate_ability_scores(values: dict[str, int]) -> None:
    if set(values) != set(ABILITY_NAMES):
        raise ValueError("ability scores must include all six abilities")
    if sorted(values.values(), reverse=True) != list(FIXED_ARRAY):
        raise ValueError("baseline character creation uses the fixed 15,14,13,12,10,8 array")
