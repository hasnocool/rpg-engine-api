import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .ids import new_id


class CommandStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ALREADY_PROCESSED = "already_processed"
    CONFLICT = "conflict"
    PENDING_EXTERNAL_RESOLUTION = "pending_external_resolution"


class ErrorCode(StrEnum):
    INVALID_SCHEMA = "invalid_schema"
    UNAUTHENTICATED = "unauthenticated"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    STATE_CONFLICT = "state_conflict"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    INVALID_CHOICE = "invalid_choice"
    PREREQUISITE_FAILED = "prerequisite_failed"
    RESOURCE_INSUFFICIENT = "resource_insufficient"
    TARGET_INVALID = "target_invalid"
    OUT_OF_RANGE = "out_of_range"
    NOT_ACTOR_READY = "not_actor_ready"
    DEADLINE_EXPIRED = "deadline_expired"
    ACTION_NOT_AVAILABLE = "action_not_available"
    RULESET_INCOMPATIBLE = "ruleset_incompatible"
    CONTENT_DEPENDENCY_ERROR = "content_dependency_error"
    CAMPAIGN_LOCKED = "campaign_locked"
    RATE_LIMITED = "rate_limited"
    INTERNAL_ERROR = "internal_error"
    SERVICE_UNAVAILABLE = "service_unavailable"


class CommandError(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: ErrorCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class CommandEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    command_id: str = Field(default_factory=lambda: new_id("cmd"))
    command_type: str
    campaign_id: str | None = None
    actor_id: str | None = None
    expected_stream_version: int | None = Field(default=None, ge=0)
    idempotency_key: str | None = None
    client_sequence: int | None = Field(default=None, ge=0)
    payload: dict[str, Any] = Field(default_factory=dict)

    def idempotency_fingerprint(self) -> str:
        """Hash semantic request fields while allowing a retry to use a new command_id."""
        value = {
            "schema_version": self.schema_version,
            "command_type": self.command_type,
            "campaign_id": self.campaign_id,
            "actor_id": self.actor_id,
            "expected_stream_version": self.expected_stream_version,
            "client_sequence": self.client_sequence,
            "payload": self.payload,
        }
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class PrincipalContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    principal_id: str
    roles: frozenset[str] = frozenset({"player"})


class CommandReceipt(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0"
    command_id: str
    status: CommandStatus
    emitted_event_ids: tuple[str, ...] = ()
    stream_versions: dict[str, int] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    error: CommandError | None = None
