from rpg_engine_api.domain.dialogue import DialogueChoice, DialogueDefinition, DialogueNode
from rpg_engine_api.domain.progression import ProgressionEdge, ProgressionGraph, ProgressionNode
from rpg_engine_api.simulation.quality import analyze_dialogue, analyze_progression


def test_dialogue_quality_finds_unreachable_node() -> None:
    definition = DialogueDefinition(id="dialogue", start_node_id="start", nodes=(DialogueNode(id="start", speaker_ref="npc", text_key="start", choices=(DialogueChoice(id="end", label="End"),)), DialogueNode(id="orphan", speaker_ref="npc", text_key="orphan", terminal=True)))
    report = analyze_dialogue(definition)
    assert report.unreachable_nodes == ("orphan",)
    assert not report.valid


def test_progression_quality_finds_cycle_without_root_reachability() -> None:
    graph = ProgressionGraph(id="tree", nodes=(ProgressionNode(id="a", name="A"), ProgressionNode(id="b", name="B"), ProgressionNode(id="root", name="Root")), edges=(ProgressionEdge(source="a", target="b"), ProgressionEdge(source="b", target="a"), ProgressionEdge(source="root", target="root")))
    report = analyze_progression(graph)
    assert any(set(component) == {"a", "b"} for component in report.cyclic_components)
