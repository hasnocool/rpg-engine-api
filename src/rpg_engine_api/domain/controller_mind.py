from __future__ import annotations

from pydantic import BaseModel, Field

from rpg_engine_api.domain.events import DomainEvent


class ControllerGoal(BaseModel):
    goal_id: str
    description: str
    priority: int = Field(default=50, ge=0, le=100)
    desired_tags: tuple[str, ...] = ()
    active: bool = True


class ControllerMemory(BaseModel):
    memory_id: str
    summary: str
    tags: tuple[str, ...] = ()
    observed_sequence: int = Field(default=0, ge=0)
    importance: int = Field(default=50, ge=0, le=100)


class ControllerMindState(BaseModel):
    schema_version: str = "1.0"
    actor_id: str
    campaign_id: str
    goals: dict[str, ControllerGoal] = Field(default_factory=dict)
    memories: list[ControllerMemory] = Field(default_factory=list)
    max_memories: int = Field(default=32, ge=1, le=256)
    stream_version: int = 0

    def active_goal_tags(self) -> tuple[str, ...]:
        tags: set[str] = set()
        for goal in self.goals.values():
            if goal.active:
                tags.update(goal.desired_tags)
        return tuple(sorted(tags))

    def memory_tags(self) -> tuple[str, ...]:
        tags: set[str] = set()
        for memory in self.memories:
            tags.update(memory.tags)
        return tuple(sorted(tags))


def reduce_controller_mind(state: ControllerMindState | None, event: DomainEvent) -> ControllerMindState:
    if event.event_type == "ControllerMindCreated":
        return ControllerMindState(
            actor_id=str(event.payload["actor_id"]),
            campaign_id=event.campaign_id,
            max_memories=int(event.payload.get("max_memories", 32)),
            stream_version=event.stream_version,
        )
    if state is None:
        raise ValueError("controller mind stream must start with ControllerMindCreated")
    next_state = state.model_copy(deep=True)
    next_state.stream_version = event.stream_version
    if event.event_type == "ControllerGoalConfigured":
        goal = ControllerGoal.model_validate(event.payload["goal"])
        next_state.goals[goal.goal_id] = goal
    elif event.event_type == "ControllerGoalRemoved":
        next_state.goals.pop(str(event.payload["goal_id"]), None)
    elif event.event_type == "ControllerFactRemembered":
        memory = ControllerMemory.model_validate(event.payload["memory"])
        next_state.memories = [item for item in next_state.memories if item.memory_id != memory.memory_id]
        next_state.memories.append(memory)
        next_state.memories.sort(key=lambda item: (-item.importance, -item.observed_sequence, item.memory_id))
        del next_state.memories[next_state.max_memories :]
    elif event.event_type == "ControllerFactForgotten":
        memory_id = str(event.payload["memory_id"])
        next_state.memories = [item for item in next_state.memories if item.memory_id != memory_id]
    return next_state
