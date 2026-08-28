from rpg_engine_api.domain.spatial import GraphSpace, Point2D, SquareGridSpace


def test_grid_path_avoids_blocked_cells() -> None:
    grid = SquareGridSpace(width=4, height=3, blocked={(1, 0)})
    result = grid.path(Point2D(x=0, y=0), Point2D(x=2, y=0))
    assert result is not None
    assert (Point2D(x=1, y=0)) not in result.points
    assert result.points[0] == Point2D(x=0, y=0)
    assert result.points[-1] == Point2D(x=2, y=0)


def test_grid_los_respects_blocker() -> None:
    grid = SquareGridSpace(width=5, height=1, blocked={(2, 0)})
    assert not grid.can_see(Point2D(x=0, y=0), Point2D(x=4, y=0))
    assert grid.can_see(Point2D(x=0, y=0), Point2D(x=1, y=0))


def test_graph_space_returns_deterministic_cheapest_route() -> None:
    graph = GraphSpace({"a": {"b": 1, "c": 5}, "b": {"a": 1, "c": 1}, "c": {"a": 5, "b": 1}})
    assert graph.path("a", "c") == (("a", "b", "c"), 2)
