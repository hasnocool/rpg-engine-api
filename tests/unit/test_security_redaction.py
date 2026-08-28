from rpg_engine_api.security.redaction import redact
from rpg_engine_api.infrastructure.portable import PortableCharacterPackage, executable_paths


def test_redaction_removes_nested_secrets_and_truncates_large_strings() -> None:
    result = redact({"authorization": "Bearer abc", "nested": {"api_key": "secret", "safe": "ok"}, "huge": "x" * 600})
    assert result["authorization"] == "[REDACTED]"
    assert result["nested"]["api_key"] == "[REDACTED]"
    assert result["nested"]["safe"] == "ok"
    assert result["huge"].endswith("...[TRUNCATED]")


def test_portable_character_integrity_and_executable_key_rejection() -> None:
    character = {"name": "Hero", "max_hp": 12, "attack_bonus": 3, "defense": 11}
    package = PortableCharacterPackage(character=character, digest="bad")
    assert package.verify() is False
    assert executable_paths({"content": {"module": "evil.mod"}}) == ("content.module",)
