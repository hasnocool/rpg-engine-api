from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from rpg_engine_api.domain.actor import ActorState
from rpg_engine_api.infrastructure.backup import EventHistoryBackup

EXECUTABLE_KEYS = {
    "callable",
    "code",
    "entrypoint",
    "eval",
    "exec",
    "module",
    "python",
    "script",
}


def _digest(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def executable_paths(value: Any, *, path: str = "") -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            normalized = str(key).lower().replace("-", "_")
            if normalized in EXECUTABLE_KEYS:
                found.append(child_path)
            found.extend(executable_paths(child, path=child_path))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            found.extend(executable_paths(child, path=f"{path}[{index}]"))
    return tuple(sorted(set(found)))


class PortableCharacterPackage(BaseModel):
    schema_version: str = "1.0"
    package_type: str = "rpg-engine-character"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    character: dict[str, Any]
    digest: str

    @classmethod
    def from_actor(cls, actor: ActorState) -> "PortableCharacterPackage":
        character = {
            "name": actor.name,
            "species": actor.species,
            "background": actor.background,
            "class_id": actor.class_id,
            "subclass_id": actor.subclass_id,
            "ability_scores": actor.ability_scores,
            "proficiencies": actor.proficiencies,
            "known_abilities": actor.known_abilities,
            "prepared_abilities": actor.prepared_abilities,
            "max_hp": actor.max_hp,
            "attack_bonus": actor.attack_bonus,
            "defense": actor.defense,
        }
        return cls(character=character, digest=_digest(character))

    def verify(self) -> bool:
        if self.package_type != "rpg-engine-character" or self.digest != _digest(self.character):
            return False
        if executable_paths(self.character):
            return False
        maximum = int(self.character.get("max_hp", 10))
        attack = int(self.character.get("attack_bonus", 2))
        defense = int(self.character.get("defense", 10))
        return 1 <= maximum <= 500 and -20 <= attack <= 100 and 0 <= defense <= 100


class PortableCampaignPackage(BaseModel):
    schema_version: str = "1.0"
    package_type: str = "rpg-engine-campaign"
    engine_api: str = "v1"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    backup: EventHistoryBackup
    digest: str

    @classmethod
    def from_backup(cls, backup: EventHistoryBackup) -> "PortableCampaignPackage":
        body = {"engine_api": "v1", "backup_digest": backup.digest, "campaign_id": backup.campaign_id}
        return cls(backup=backup, digest=_digest(body))

    def validation_report(self, *, max_events: int = 1_000_000) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        if self.package_type != "rpg-engine-campaign":
            issues.append({"code": "unsupported_package_type", "message": self.package_type})
        if self.engine_api != "v1":
            issues.append({"code": "unsupported_engine_api", "message": self.engine_api})
        if not self.backup.verify():
            issues.append({"code": "digest_mismatch", "message": "backup digest does not match contents"})
        body = {"engine_api": self.engine_api, "backup_digest": self.backup.digest, "campaign_id": self.backup.campaign_id}
        if self.digest != _digest(body):
            issues.append({"code": "package_digest_mismatch", "message": "package envelope digest mismatch"})
        if len(self.backup.events) > max_events:
            issues.append({"code": "event_limit_exceeded", "message": f"package contains {len(self.backup.events)} events"})
        executable = executable_paths(self.backup.content_packs)
        if executable:
            issues.append({"code": "executable_content_rejected", "message": "content packs must be data-only", "paths": list(executable)})
        for raw in self.backup.content_packs:
            for definition in raw.get("definitions", []):
                if str(definition.get("definition_type", "")).lower() in {"trusted_extension", "python_extension", "script"}:
                    issues.append({"code": "executable_definition_rejected", "message": str(definition.get("key", "unknown"))})
        return {"valid": not issues, "issues": issues, "event_count": len(self.backup.events), "content_pack_count": len(self.backup.content_packs)}

    def verify(self) -> bool:
        return bool(self.validation_report()["valid"])
