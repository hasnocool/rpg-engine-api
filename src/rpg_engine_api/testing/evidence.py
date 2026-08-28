from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SuiteStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"


class EnvironmentEvidence(BaseModel):
    os: str
    architecture: str
    python: str
    dependency_fingerprint: str
    postgres_version: str | None = None
    config_fingerprint: str


class SuiteEvidence(BaseModel):
    name: str
    command: list[str]
    status: SuiteStatus
    exit_code: int
    duration_seconds: float
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    junit_path: str | None = None
    log_path: str | None = None


class ArtifactRef(BaseModel):
    kind: str
    path: str


class TestEvidenceBundle(BaseModel):
    schema_version: str = "1.0"
    evidence_id: str
    repository: str
    commit_sha: str
    branch: str | None = None
    dirty_worktree: bool
    test_profile: str
    executor_kind: str = "local_agent"
    executor_version: str = "1"
    environment: EnvironmentEvidence
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    overall_status: SuiteStatus = SuiteStatus.PASSED
    suites: list[SuiteEvidence] = Field(default_factory=list)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
