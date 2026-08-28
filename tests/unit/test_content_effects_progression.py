import pytest

from rpg_engine_api.domain.content import CampaignContentLock, ContentPackManifest
from rpg_engine_api.domain.definitions import DefinitionRef
from rpg_engine_api.domain.effects import EffectDefinition, EffectOperation, EffectOperationType, ResourceDefinition
from rpg_engine_api.domain.progression import ProgressionEdge, ProgressionGraph, ProgressionNode


def test_data_only_effect_definition_round_trip() -> None:
    effect = EffectDefinition(
        id="testing:effect/guard",
        trigger="on_action",
        operations=(EffectOperation(operation=EffectOperationType.MODIFY_VALUE, target="defense", value=2),),
    )
    assert EffectDefinition.model_validate_json(effect.model_dump_json()) == effect


def test_resource_definition_is_explicitly_bounded() -> None:
    resource = ResourceDefinition(id="testing:resource/stamina", name="Stamina", maximum=3)
    assert resource.minimum == 0
    assert resource.maximum == 3


def test_progression_graph_rejects_unknown_edges() -> None:
    with pytest.raises(ValueError):
        ProgressionGraph(
            id="testing:progression/demo",
            nodes=(ProgressionNode(id="a", name="A"),),
            edges=(ProgressionEdge(source="a", target="missing"),),
        )


def test_content_pack_and_lock_are_versioned() -> None:
    ContentPackManifest(
        id="testing",
        version="1.0.0",
        namespace="testing",
        license="CC0-1.0",
        content_hash="deadbeefcafebabe",
    )
    ref = DefinitionRef(
        pack_id="testing",
        pack_version="1.0.0",
        key="testing:item/token",
        content_hash="deadbeefcafebabe",
    )
    lock = CampaignContentLock(
        ruleset_ref="testing-rules@1",
        pack_refs=(ref,),
        combined_hash="0011223344556677",
    )
    assert lock.pack_refs[0].pack_version == "1.0.0"
