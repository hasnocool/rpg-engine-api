from rpg_engine_api.domain.progression import ProgressionGraph, ProgressionNode
from rpg_engine_api.rules.requirements_runtime import RequirementContext, evaluate_requirement


def available_progression_nodes(
    graph: ProgressionGraph,
    *,
    unlocked: set[str],
    currency: int,
    context: RequirementContext,
) -> tuple[ProgressionNode, ...]:
    incoming: dict[str, set[str]] = {node.id: set() for node in graph.nodes}
    for edge in graph.edges:
        incoming[edge.target].add(edge.source)
    available: list[ProgressionNode] = []
    for node in graph.nodes:
        if node.id in unlocked or node.cost > currency:
            continue
        if incoming[node.id] and not incoming[node.id].issubset(unlocked):
            continue
        if not evaluate_requirement(node.prerequisites, context):
            continue
        exclusive_groups = {
            edge.exclusive_group
            for edge in graph.edges
            if edge.target == node.id and edge.exclusive_group is not None
        }
        if exclusive_groups:
            conflicting = {
                edge.target
                for edge in graph.edges
                if edge.exclusive_group in exclusive_groups and edge.target != node.id
            }
            if unlocked & conflicting:
                continue
        available.append(node)
    return tuple(sorted(available, key=lambda item: (item.rank, item.id)))
