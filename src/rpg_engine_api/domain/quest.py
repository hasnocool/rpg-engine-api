from enum import StrEnum

from pydantic import BaseModel

from rpg_engine_api.domain.events import DomainEvent


class QuestStatus(StrEnum):
    AVAILABLE = "available"
    ACCEPTED = "accepted"
    COMPLETED = "completed"


class QuestState(BaseModel):
    schema_version: str = "1.0"
    quest_id: str
    campaign_id: str
    title: str
    objective: str
    status: QuestStatus = QuestStatus.AVAILABLE
    actor_id: str | None = None
    stream_version: int = 0


def reduce_quest(state: QuestState | None, event: DomainEvent) -> QuestState:
    if event.event_type == "QuestCreated":
        return QuestState(
            quest_id=str(event.payload["quest_id"]),
            campaign_id=event.campaign_id,
            title=str(event.payload["title"]),
            objective=str(event.payload["objective"]),
            stream_version=event.stream_version,
        )
    if state is None:
        raise ValueError("quest stream must start with QuestCreated")
    next_state = state.model_copy(deep=True)
    next_state.stream_version = event.stream_version
    if event.event_type == "QuestAccepted":
        next_state.status = QuestStatus.ACCEPTED
        next_state.actor_id = str(event.actor_id)
    elif event.event_type == "QuestCompleted":
        next_state.status = QuestStatus.COMPLETED
    return next_state
