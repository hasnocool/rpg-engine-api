from rpg_engine_api.domain.events import DomainEvent
from rpg_engine_api.domain.world import reduce_world


def test_world_reducer_discovers_and_moves_actor() -> None:
    created = DomainEvent(event_type="WorldCreated", campaign_id="cmp", stream_id="world:w", command_id="cmd1", payload={"world_id": "w", "locations": [{"id": "a", "name": "A", "connections": ["b"]}, {"id": "b", "name": "B", "connections": ["a"], "hidden": True}]})
    state = reduce_world(None, created)
    placed = DomainEvent(event_type="ActorPlacedInWorld", campaign_id="cmp", stream_id="world:w", actor_id="hero", command_id="cmd2", payload={"actor_id": "hero", "location_id": "a"})
    state = reduce_world(state, placed)
    discovered = DomainEvent(event_type="LocationDiscovered", campaign_id="cmp", stream_id="world:w", actor_id="hero", command_id="cmd3", payload={"location_id": "b"})
    state = reduce_world(state, discovered)
    assert state.actor_locations["hero"] == "a"
    assert state.discovered_locations["hero"] == ["a", "b"]
