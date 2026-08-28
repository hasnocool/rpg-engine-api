from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree

from rpg_engine_api.testing.evidence import ArtifactRef, EnvironmentEvidence, SuiteEvidence, SuiteStatus, TestEvidenceBundle

ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_ROOT = ROOT / "artifacts" / "test-evidence"
PROFILE_MANIFEST = ROOT / "test-profiles.json"


def _load_profiles() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    value = json.loads(PROFILE_MANIFEST.read_text(encoding="utf-8"))
    if value.get("local_only") is not True:
        raise RuntimeError("test-profiles.json must declare local_only=true")
    suites = {str(name): [str(item) for item in paths] for name, paths in dict(value["suites"]).items()}
    profiles = {str(name): [str(item) for item in names] for name, names in dict(value["profiles"]).items()}
    for profile, names in profiles.items():
        unknown = [name for name in names if name not in suites]
        if unknown:
            raise RuntimeError(f"profile {profile} references unknown suites: {unknown}")
    return suites, profiles


SUITES, PROFILES = _load_profiles()


def _run_capture(command: list[str]) -> tuple[int, str]:
    process = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    return process.returncode, process.stdout.strip()


def _git_metadata() -> tuple[str, str | None, bool]:
    sha_code, sha = _run_capture(["git", "rev-parse", "HEAD"])
    branch_code, branch = _run_capture(["git", "branch", "--show-current"])
    dirty_code, status = _run_capture(["git", "status", "--porcelain"])
    return (sha if sha_code == 0 else "unknown", branch if branch_code == 0 and branch else None, dirty_code != 0 or bool(status))


def _fingerprint(command: list[str]) -> str:
    code, output = _run_capture(command)
    raw = output if code == 0 else f"unavailable:{code}:{output}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _postgres_version() -> str | None:
    url = os.environ.get("RPG_ENGINE_DATABASE_URL")
    if not url:
        return None
    code, output = _run_capture(["psql", "--version"])
    return output if code == 0 else "configured-version-unavailable"


def _environment() -> EnvironmentEvidence:
    config = {key: value for key, value in sorted(os.environ.items()) if key.startswith("RPG_ENGINE_") and not any(secret in key.lower() for secret in ("password", "secret", "token", "key"))}
    return EnvironmentEvidence(os=platform.platform(), architecture=platform.machine(), python=sys.version.split()[0], dependency_fingerprint=_fingerprint([sys.executable, "-m", "pip", "freeze"]), postgres_version=_postgres_version(), config_fingerprint=hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest())


def _parse_junit(path: Path) -> dict[str, int]:
    if not path.exists(): return {"passed":0,"failed":0,"skipped":0,"errors":0}
    root = ElementTree.parse(path).getroot(); tests=failures=skipped=errors=0
    nodes=[root] if root.tag=="testsuite" else list(root.findall("testsuite"))
    for node in nodes:
        tests+=int(node.attrib.get("tests",0));failures+=int(node.attrib.get("failures",0));skipped+=int(node.attrib.get("skipped",0));errors+=int(node.attrib.get("errors",0))
    return {"passed":max(0,tests-failures-skipped-errors),"failed":failures,"skipped":skipped,"errors":errors}


def _policy_suite(profile: str, dirty: bool) -> tuple[SuiteEvidence, list[str]]:
    errors: list[str] = []
    workflows = ROOT / ".github" / "workflows"
    if workflows.exists() and any(path.is_file() for path in workflows.rglob("*")):
        errors.append("GitHub Actions workflows are prohibited; .github/workflows must remain absent/empty")
    if profile == "release" and dirty:
        errors.append("release profile requires a clean exact-commit worktree")
    status = SuiteStatus.BLOCKED if errors else SuiteStatus.PASSED
    return SuiteEvidence(name="repository_policy", command=["internal:repository_policy"], status=status, exit_code=2 if errors else 0, duration_seconds=0.0, passed=0 if errors else 1, failed=0, skipped=0, errors=len(errors)), errors


def _run_suite(name: str, paths: list[str], run_dir: Path) -> SuiteEvidence:
    junit = run_dir / f"{name}.xml"; log = run_dir / f"{name}.log"; command=[sys.executable,"-m","pytest","-q",*paths,"--junitxml",str(junit)]
    started=time.perf_counter(); process=subprocess.run(command,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=False); duration=time.perf_counter()-started; log.write_text(process.stdout,encoding="utf-8"); counts=_parse_junit(junit)
    return SuiteEvidence(name=name,command=command,status=SuiteStatus.PASSED if process.returncode==0 else SuiteStatus.FAILED,exit_code=process.returncode,duration_seconds=duration,junit_path=str(junit.relative_to(ROOT)),log_path=str(log.relative_to(ROOT)),**counts)


def _write_bundle(bundle: TestEvidenceBundle, run_dir: Path) -> Path:
    path=run_dir/"evidence.json";path.write_text(bundle.model_dump_json(indent=2),encoding="utf-8");return path


def run_profile(profile: str) -> int:
    if profile not in PROFILES: print(f"unknown profile {profile!r}; choose one of: {', '.join(sorted(PROFILES))}",file=sys.stderr);return 2
    evidence_id=f"evidence-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}";run_dir=ARTIFACT_ROOT/evidence_id;run_dir.mkdir(parents=True,exist_ok=False);sha,branch,dirty=_git_metadata();started=datetime.now(UTC)
    bundle=TestEvidenceBundle(evidence_id=evidence_id,repository="hasnocool/rpg-engine-api",commit_sha=sha,branch=branch,dirty_worktree=dirty,test_profile=profile,environment=_environment(),started_at=started)
    policy, policy_errors = _policy_suite(profile, dirty); bundle.suites.append(policy)
    if policy_errors:
        bundle.overall_status=SuiteStatus.BLOCKED;bundle.finished_at=datetime.now(UTC);bundle.summary={"policy_errors":policy_errors,"passed":0,"failed":0,"blocked":1,"skipped":0,"errors":len(policy_errors)};path=_write_bundle(bundle,run_dir);print(f"{profile}: blocked -> {path.relative_to(ROOT)}");return 2
    for suite_name in PROFILES[profile]:
        suite=_run_suite(suite_name,SUITES[suite_name],run_dir);bundle.suites.append(suite)
        if suite.junit_path: bundle.artifacts.append(ArtifactRef(kind="junit",path=suite.junit_path))
        if suite.log_path: bundle.artifacts.append(ArtifactRef(kind="log",path=suite.log_path))
    failed=any(suite.status==SuiteStatus.FAILED for suite in bundle.suites);bundle.overall_status=SuiteStatus.FAILED if failed else SuiteStatus.PASSED;bundle.finished_at=datetime.now(UTC);bundle.summary={"passed":sum(suite.passed for suite in bundle.suites),"failed":sum(suite.failed for suite in bundle.suites),"blocked":sum(suite.status==SuiteStatus.BLOCKED for suite in bundle.suites),"skipped":sum(suite.skipped for suite in bundle.suites),"errors":sum(suite.errors for suite in bundle.suites)};path=_write_bundle(bundle,run_dir);print(f"{profile}: {bundle.overall_status.value} -> {path.relative_to(ROOT)}");return 0 if bundle.overall_status==SuiteStatus.PASSED else 1


def main(argv: list[str] | None = None) -> int:
    args=list(argv if argv is not None else sys.argv[1:]);
    if len(args)!=1: print("usage: python -m rpg_engine_api.testing.runner <profile>",file=sys.stderr);return 2
    return run_profile(args[0])


if __name__ == "__main__": raise SystemExit(main())
