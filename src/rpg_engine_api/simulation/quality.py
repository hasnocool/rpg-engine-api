from collections import defaultdict, deque
from typing import Any

from pydantic import BaseModel, Field

from rpg_engine_api.domain.dialogue import DialogueDefinition
from rpg_engine_api.domain.progression import ProgressionGraph


class QualityFinding(BaseModel):
    severity: str
    code: str
    message: str
    refs: tuple[str, ...] = ()


class GraphQualityReport(BaseModel):
    schema_version: str = "1.0"
    graph_id: str
    node_count: int
    reachable_count: int
    unreachable_nodes: tuple[str, ...] = ()
    dead_end_nodes: tuple[str, ...] = ()
    cyclic_components: tuple[tuple[str, ...], ...] = ()
    findings: tuple[QualityFinding, ...] = ()

    @property
    def valid(self) -> bool:
        return not any(item.severity == "error" for item in self.findings)


class PackQualityReport(BaseModel):
    schema_version: str = "1.0"
    pack_id: str
    version: str
    definition_count: int
    findings: list[QualityFinding] = Field(default_factory=list)
    referenced_keys: set[str] = Field(default_factory=set)
    declared_keys: set[str] = Field(default_factory=set)

    @property
    def valid(self) -> bool:
        return not any(item.severity == "error" for item in self.findings)


def analyze_graph(graph_id: str, nodes: set[str], edges: dict[str, set[str]], *, starts: set[str], terminals: set[str] | None = None) -> GraphQualityReport:
    unknown_starts = starts - nodes
    if unknown_starts:
        raise ValueError(f"graph starts reference unknown nodes: {sorted(unknown_starts)}")
    reachable: set[str] = set()
    queue = deque(sorted(starts))
    while queue:
        node = queue.popleft()
        if node in reachable:
            continue
        reachable.add(node)
        for target in sorted(edges.get(node, set())):
            if target in nodes and target not in reachable:
                queue.append(target)
    unreachable = tuple(sorted(nodes - reachable))
    terminal_nodes = terminals or set()
    dead_ends = tuple(sorted(node for node in reachable if not edges.get(node) and node not in terminal_nodes))
    cycles = _cyclic_components(nodes, edges)
    findings: list[QualityFinding] = []
    for node in unreachable:
        findings.append(QualityFinding(severity="error", code="unreachable_node", message=f"node {node} is unreachable", refs=(node,)))
    for node in dead_ends:
        findings.append(QualityFinding(severity="warning", code="dead_end", message=f"node {node} is a reachable non-terminal dead end", refs=(node,)))
    return GraphQualityReport(graph_id=graph_id, node_count=len(nodes), reachable_count=len(reachable), unreachable_nodes=unreachable, dead_end_nodes=dead_ends, cyclic_components=cycles, findings=tuple(findings))


def _cyclic_components(nodes: set[str], edges: dict[str, set[str]]) -> tuple[tuple[str, ...], ...]:
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    result: list[tuple[str, ...]] = []

    def strongconnect(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlink[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for neighbor in sorted(edges.get(node, set())):
            if neighbor not in nodes:
                continue
            if neighbor not in indices:
                strongconnect(neighbor)
                lowlink[node] = min(lowlink[node], lowlink[neighbor])
            elif neighbor in on_stack:
                lowlink[node] = min(lowlink[node], indices[neighbor])
        if lowlink[node] == indices[node]:
            component: list[str] = []
            while True:
                value = stack.pop()
                on_stack.remove(value)
                component.append(value)
                if value == node:
                    break
            component.sort()
            if len(component) > 1 or (len(component) == 1 and component[0] in edges.get(component[0], set())):
                result.append(tuple(component))

    for node in sorted(nodes):
        if node not in indices:
            strongconnect(node)
    return tuple(sorted(result))


def analyze_dialogue(definition: DialogueDefinition) -> GraphQualityReport:
    nodes = {node.id for node in definition.nodes}
    edges = {node.id: {choice.next_node_id for choice in node.choices if choice.next_node_id is not None} for node in definition.nodes}
    terminals = {node.id for node in definition.nodes if node.terminal or any(choice.next_node_id is None for choice in node.choices)}
    return analyze_graph(definition.id, nodes, edges, starts={definition.start_node_id}, terminals=terminals)


def analyze_progression(graph: ProgressionGraph) -> GraphQualityReport:
    nodes = {node.id for node in graph.nodes}
    edges: dict[str, set[str]] = defaultdict(set)
    incoming: dict[str, int] = {node: 0 for node in nodes}
    for edge in graph.edges:
        edges[edge.source].add(edge.target)
        incoming[edge.target] += 1
    starts = {node for node, count in incoming.items() if count == 0}
    if not starts and nodes:
        starts = {sorted(nodes)[0]}
    return analyze_graph(graph.id, nodes, dict(edges), starts=starts, terminals={node for node in nodes if not edges.get(node)})


def analyze_pack(pack: Any) -> PackQualityReport:
    definitions = tuple(pack.definitions)
    declared = {str(item.key) for item in definitions}
    report = PackQualityReport(pack_id=str(pack.pack_id), version=str(pack.version), definition_count=len(definitions), declared_keys=declared)
    seen: set[str] = set()
    for definition in definitions:
        key = str(definition.key)
        if key in seen:
            report.findings.append(QualityFinding(severity="error", code="duplicate_key", message=f"duplicate definition key {key}", refs=(key,)))
        seen.add(key)
        data = definition.data
        refs = _find_content_refs(data)
        report.referenced_keys.update(refs)
        for ref in sorted(refs - declared):
            report.findings.append(QualityFinding(severity="error", code="dangling_reference", message=f"definition {key} references missing key {ref}", refs=(key, ref)))
        if definition.definition_type == "encounter_template" and not data.get("enemy_ref"):
            report.findings.append(QualityFinding(severity="error", code="missing_enemy_ref", message=f"encounter {key} has no enemy_ref", refs=(key,)))
    return report


def _find_content_refs(value: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key.endswith("_ref") and isinstance(child, str) and ":" in child:
                refs.add(child)
            elif key.endswith("_refs") and isinstance(child, (list, tuple)):
                refs.update(str(item) for item in child if isinstance(item, str) and ":" in item)
            refs.update(_find_content_refs(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            refs.update(_find_content_refs(child))
    return refs
