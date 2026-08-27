from rpg_engine_api.application.evolution_service import EvolutionEngineService
from rpg_engine_api.domain.authoring import PublishedContentPack, PublishedDefinition


def pack(version: str, value: int) -> PublishedContentPack:
    definition = PublishedDefinition(definition_type="item", key="demo:item/x", data={"value": value}, source={"license_id": "CC0-1.0"})
    return PublishedContentPack(pack_id="demo", namespace="demo", version=version, content_hash=f"hash{version}00000000", definitions=(definition,))


def test_semantic_diff_detects_changed_definition() -> None:
    service = EvolutionEngineService()
    service.published_packs[("demo", "1.0.0")] = pack("1.0.0", 1)
    service.published_packs[("demo", "1.1.0")] = pack("1.1.0", 2)
    diff = service._diff("demo", "1.0.0", "1.1.0")
    assert diff.changed_keys == ["demo:item/x"]
    assert diff.removed_keys == []
