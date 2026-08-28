from rpg_engine_api.domain.events import DomainEvent
from rpg_engine_api.domain.quest import reduce_quest
from rpg_engine_api.domain.session import reduce_session


def test_session_reducer_tracks_ready_and_open() -> None:
    created = DomainEvent(event_type="GameSessionCreated", campaign_id="cmp", stream_id="session:s", command_id="c1", payload={"session_id": "s", "owner_id": "owner"})
    state = reduce_session(None, created)
    ready = DomainEvent(event_type="SessionReadyChanged", campaign_id="cmp", stream_id="session:s", command_id="c2", payload={"principal_id": "owner", "ready": True})
    state = reduce_session(state, ready)
    assert state.members["owner"].ready is True


def test_quest_reducer_accepts_and_completes() -> None:
    created = DomainEvent(event_type="QuestCreated", campaign_id="cmp", stream_id="quest:q", command_id="c1", payload={"quest_id": "q", "title": "Q", "objective": "Do it"})
    state = reduce_quest(None, created)
    accepted = DomainEvent(event_type="QuestAccepted", campaign_id="cmp", stream_id="quest:q", actor_id="hero", command_id="c2", payload={"actor_id": "hero"})
    state = reduce_quest(state, accepted)
    completed = DomainEvent(event_type="QuestCompleted", campaign_id="cmp", stream_id="quest:q", actor_id="hero", command_id="c3", payload={"quest_id": "q"})
    state = reduce_quest(state, completed)
    assert state.status.value == "completed"
