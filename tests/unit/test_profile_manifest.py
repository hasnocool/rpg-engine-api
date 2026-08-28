import json
from pathlib import Path

from rpg_engine_api.testing.runner import PROFILES, ROOT, SUITES


def test_test_profile_manifest_is_authoritative_and_local_only() -> None:
    value = json.loads((Path(ROOT) / "test-profiles.json").read_text(encoding="utf-8"))
    assert value["local_only"] is True
    assert SUITES == value["suites"]
    assert PROFILES == value["profiles"]
    assert "release" in PROFILES and "performance" in PROFILES["release"]
