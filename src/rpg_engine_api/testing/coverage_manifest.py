import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


def load_feature_coverage(path: Path | None = None) -> dict[str, Any]:
    source = path or ROOT / "feature_coverage.json"
    return json.loads(source.read_text(encoding="utf-8"))


def validate_feature_coverage(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    features = value.get("features", [])
    ids = [str(item.get("feature_id", "")) for item in features]
    if len(ids) != len(set(ids)): errors.append("duplicate feature_id")
    for item in features:
        feature_id = str(item.get("feature_id", ""))
        if not feature_id: errors.append("feature missing feature_id")
        if not item.get("implementation_paths"): errors.append(f"{feature_id}: no implementation paths")
        proof_keys = {"unit_tests", "integration_tests", "playtest_scenarios", "controller_tests", "simulation_checks", "reachability_checks", "migration_fixtures", "negative_cases", "reconnect_cases", "replay_cases"}
        if not any(item.get(key) for key in proof_keys): errors.append(f"{feature_id}: no proof mapping")
        if not item.get("required_local_profiles"): errors.append(f"{feature_id}: no required local profiles")
    return errors
