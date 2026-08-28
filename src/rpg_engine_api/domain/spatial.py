from __future__ import annotations

import heapq
from collections.abc import Iterable
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field


class Point2D(BaseModel):
    model_config = ConfigDict(frozen=True)

    x: int
    y: int


class SenseDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    range: int = Field(default=6, ge=0)
    ignores_line_of_sight: bool = False
    tags: tuple[str, ...] = ()


class KnowledgeProjection(BaseModel):
    actor_id: str
    known_locations: set[str] = Field(default_factory=set)
    known_entities: set[str] = Field(default_factory=set)
    known_facts: set[str] = Field(default_factory=set)
    last_known_positions: dict[str, Point2D] = Field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PathResult:
    points: tuple[Point2D, ...]
    cost: int


class SquareGridSpace:
    """Deterministic square-grid authority with A* pathing and Bresenham LOS."""

    def __init__(
        self,
        *,
        width: int,
        height: int,
        blocked: Iterable[tuple[int, int]] = (),
        terrain_costs: dict[tuple[int, int], int] | None = None,
    ) -> None:
        if width <= 0 or height <= 0:
            raise ValueError("grid dimensions must be positive")
        self.width = width
        self.height = height
        self.blocked = frozenset(blocked)
        self.terrain_costs = dict(terrain_costs or {})

    def contains(self, point: Point2D) -> bool:
        return 0 <= point.x < self.width and 0 <= point.y < self.height

    def can_occupy(self, point: Point2D) -> bool:
        return self.contains(point) and (point.x, point.y) not in self.blocked

    @staticmethod
    def distance(a: Point2D, b: Point2D) -> int:
        return abs(a.x - b.x) + abs(a.y - b.y)

    def neighbors(self, point: Point2D) -> tuple[Point2D, ...]:
        candidates = (
            Point2D(x=point.x - 1, y=point.y),
            Point2D(x=point.x + 1, y=point.y),
            Point2D(x=point.x, y=point.y - 1),
            Point2D(x=point.x, y=point.y + 1),
        )
        return tuple(sorted((item for item in candidates if self.can_occupy(item)), key=lambda p: (p.y, p.x)))

    def terrain_cost(self, point: Point2D) -> int:
        return max(1, int(self.terrain_costs.get((point.x, point.y), 1)))

    def path(self, start: Point2D, goal: Point2D) -> PathResult | None:
        if not self.can_occupy(start) or not self.can_occupy(goal):
            return None
        frontier: list[tuple[int, int, int, Point2D]] = []
        sequence = 0
        heapq.heappush(frontier, (0, 0, sequence, start))
        came_from: dict[Point2D, Point2D | None] = {start: None}
        cost_so_far: dict[Point2D, int] = {start: 0}
        while frontier:
            _, current_cost, _, current = heapq.heappop(frontier)
            if current == goal:
                break
            if current_cost != cost_so_far[current]:
                continue
            for neighbor in self.neighbors(current):
                new_cost = current_cost + self.terrain_cost(neighbor)
                if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                    cost_so_far[neighbor] = new_cost
                    sequence += 1
                    priority = new_cost + self.distance(neighbor, goal)
                    heapq.heappush(frontier, (priority, new_cost, sequence, neighbor))
                    came_from[neighbor] = current
        if goal not in came_from:
            return None
        route: list[Point2D] = []
        cursor: Point2D | None = goal
        while cursor is not None:
            route.append(cursor)
            cursor = came_from[cursor]
        route.reverse()
        return PathResult(points=tuple(route), cost=cost_so_far[goal])

    def can_see(self, start: Point2D, goal: Point2D, *, maximum_range: int | None = None) -> bool:
        if maximum_range is not None and self.distance(start, goal) > maximum_range:
            return False
        for point in self._line(start, goal)[1:-1]:
            if (point.x, point.y) in self.blocked:
                return False
        return True

    @staticmethod
    def _line(start: Point2D, goal: Point2D) -> tuple[Point2D, ...]:
        x0, y0 = start.x, start.y
        x1, y1 = goal.x, goal.y
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        error = dx + dy
        points: list[Point2D] = []
        while True:
            points.append(Point2D(x=x0, y=y0))
            if x0 == x1 and y0 == y1:
                break
            twice = 2 * error
            if twice >= dy:
                error += dy
                x0 += sx
            if twice <= dx:
                error += dx
                y0 += sy
        return tuple(points)


class GraphSpace:
    """Deterministic weighted location-graph adapter."""

    def __init__(self, adjacency: dict[str, dict[str, int]]) -> None:
        self.adjacency = {
            node: {neighbor: max(1, int(cost)) for neighbor, cost in neighbors.items()}
            for node, neighbors in adjacency.items()
        }

    def distance(self, start: str, goal: str) -> int | None:
        route = self.path(start, goal)
        return route[1] if route is not None else None

    def path(self, start: str, goal: str) -> tuple[tuple[str, ...], int] | None:
        if start not in self.adjacency or goal not in self.adjacency:
            return None
        frontier: list[tuple[int, str]] = [(0, start)]
        costs = {start: 0}
        previous: dict[str, str | None] = {start: None}
        while frontier:
            cost, node = heapq.heappop(frontier)
            if cost != costs[node]:
                continue
            if node == goal:
                break
            for neighbor, edge_cost in sorted(self.adjacency[node].items()):
                candidate = cost + edge_cost
                if neighbor not in costs or candidate < costs[neighbor]:
                    costs[neighbor] = candidate
                    previous[neighbor] = node
                    heapq.heappush(frontier, (candidate, neighbor))
        if goal not in previous:
            return None
        route: list[str] = []
        cursor: str | None = goal
        while cursor is not None:
            route.append(cursor)
            cursor = previous[cursor]
        route.reverse()
        return tuple(route), costs[goal]
