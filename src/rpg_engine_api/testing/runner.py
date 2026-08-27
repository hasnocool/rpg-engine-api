import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

from .evidence import (
    ArtifactRef,
    EnvironmentEvidence,
    SuiteEvidence,
    SuiteStatus,
    TestEvidenceBundle,
)

ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_ROOT = ROOT / "artifacts" / "test-evidence"

SUITES: dict[str, list[str]] = {
    "unit": ["tests/unit"],
    "playtest": ["tests/playtest"],
    "integration": ["tests/integration"],
    "replay": ["tests/replay"],
    "simulation": ["tests/simulation"],
    "migration": ["tests/migration"],
    "performance": ["tests/performance"],
}

PROFILES: dict[str, list[str]] = {
    "smoke": ["unit", "playtest"],
    "pr": ["unit", "replay", "playtest"],
    "unit": ["unit"],
    "integration": ["integration"],
    "playtest": ["playtest"],
    "simulation": ["simulation"],
    "migration": ["migration"],
    "replay": ["replay"],
    "performance": ["performance"],
    "full": ["unit", "integration", "replay", "playtest", "simulation", "migration"],
    "nightly": ["unit", "integration", "replay", "playtest", "simulation", "migration", "performance"],
    "release": ["unit", "integration", "replay", "playtest", "simulation", "migration", "performance"],
}


def _git(*args: str, default: str = "unknown") -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return default
    return result.stdout.strip() or default


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _dependency_fingerprint() -> str:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return _fingerprint(result.stdout)
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def _postgres_version() -> str | None:
    try:
        result = subprocess.run(
            ["psql", "--version"], capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _parse_junit(path: Path) -> tuple[int, int, int, int]:
    if not path.exists():
        return (0, 0, 0, 0)
    root = ET.parse(path).getroot()
    nodes = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    tests = sum(int(node.attrib.get("tests", 0)) for node in nodes)
    failures = sum(int(node.attrib.get("failures", 0)) for node in nodes)
    errors = sum(int(node.attrib.get("errors", 0)) for node in nodes)
    skipped = sum(int(node.attrib.get("skipped", 0)) for node in nodes)
    passed = max(0, tests - failures - errors - skipped)
    return passed, failures, skipped, errors


def _environment() -> EnvironmentEvidence:
    safe_config = {
        "app_env": os.getenv("RPG_ENGINE_APP_ENV", "development"),
        "persistence_backend": os.getenv("RPG_ENGINE_PERSISTENCE_BACKEND", "memory"),
        "database_configured": bool(os.getenv("RPG_ENGINE_DATABASE_URL")),
    }
    return EnvironmentEvidence(
        os=platform.platform(),
        architecture=platform.machine(),
        python=platform.python_version(),
        dependency_fingerprint=_dependency_fingerprint(),
        postgres_version=_postgres_version(),
        config_fingerprint=_fingerprint(json.dumps(safe_config, sort_keys=True)),
    )


def _run_suite(name: str, evidence_dir: Path) -> SuiteEvidence:
    paths = SUITES[name]
    junit_path = evidence_dir / "junit" / f"{name}.xml"
    log_path = evidence_dir / "logs" / f"{name}.log"
    command = [sys.executable, "-m", "pytest", "-q", *paths, f"--junitxml={junit_path}"]
    started = time.monotonic()
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    duration = time.monotonic() - started
    log_path.write_text(result.stdout + "\n--- STDERR ---\n" + result.stderr, encoding="utf-8")
    passed, failed, skipped, errors = _parse_junit(junit_path)
    if result.returncode != 0:
        status = SuiteStatus.FAILED
    elif passed == 0 and skipped > 0:
        status = SuiteStatus.BLOCKED
    else:
        status = SuiteStatus.PASSED
    return SuiteEvidence(
        name=name,
        command=command,
        status=status,
        exit_code=result.returncode,
        duration_seconds=round(duration, 3),
        passed=passed,
        failed=failed,
        skipped=skipped,
        errors=errors,
        junit_path=str(junit_path.relative_to(ROOT)) if junit_path.exists() else None,
        log_path=str(log_path.relative_to(ROOT)),
    )


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(f"usage: {sys.argv[0]} <profile>; profiles: {', '.join(PROFILES)}")
    profile = sys.argv[1]
    if profile not in PROFILES:
        raise SystemExit(f"unknown profile {profile!r}; profiles: {', '.join(PROFILES)}")

    commit = _git("rev-parse", "HEAD")
    branch = _git("branch", "--show-current", default="") or None
    dirty = bool(_git("status", "--porcelain", default=""))
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    evidence_id = f"{timestamp}-{commit[:12]}-{profile}"
    evidence_dir = ARTIFACT_ROOT / evidence_id
    for child in ("junit", "logs", "coverage", "playtest", "replay", "simulation", "migration", "performance"):
        (evidence_dir / child).mkdir(parents=True, exist_ok=True)

    bundle = TestEvidenceBundle(
        evidence_id=evidence_id,
        repository="hasnocool/rpg-engine-api",
        commit_sha=commit,
        branch=branch,
        dirty_worktree=dirty,
        test_profile=profile,
        environment=_environment(),
    )
    for suite_name in PROFILES[profile]:
        evidence = _run_suite(suite_name, evidence_dir)
        bundle.suites.append(evidence)

    if any(item.status == SuiteStatus.FAILED for item in bundle.suites):
        bundle.overall_status = SuiteStatus.FAILED
    elif any(item.status == SuiteStatus.BLOCKED for item in bundle.suites):
        bundle.overall_status = SuiteStatus.BLOCKED
    else:
        bundle.overall_status = SuiteStatus.PASSED
    bundle.finished_at = datetime.now(UTC)
    bundle.summary = {
        "passed_suites": sum(item.status == SuiteStatus.PASSED for item in bundle.suites),
        "failed_suites": sum(item.status == SuiteStatus.FAILED for item in bundle.suites),
        "blocked_suites": sum(item.status == SuiteStatus.BLOCKED for item in bundle.suites),
    }
    bundle.artifacts.extend(
        [ArtifactRef(kind="junit", path=item.junit_path) for item in bundle.suites if item.junit_path]
    )

    evidence_json = evidence_dir / "evidence.json"
    evidence_json.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    summary = evidence_dir / "summary.md"
    summary.write_text(
        "# Test evidence\n\n"
        f"- commit: `{commit}`\n"
        f"- profile: `{profile}`\n"
        f"- status: **{bundle.overall_status.value}**\n"
        f"- dirty worktree: `{dirty}`\n\n"
        + "\n".join(
            f"- {item.name}: {item.status.value} "
            f"(passed={item.passed}, failed={item.failed}, skipped={item.skipped}, errors={item.errors})"
            for item in bundle.suites
        )
        + "\n",
        encoding="utf-8",
    )
    print(summary.read_text(encoding="utf-8"))
    print(f"evidence: {evidence_json.relative_to(ROOT)}")
    if bundle.overall_status != SuiteStatus.PASSED:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
