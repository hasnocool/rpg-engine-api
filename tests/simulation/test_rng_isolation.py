import pytest

from rpg_engine_api.domain.dice import DeterministicRng


@pytest.mark.simulation
def test_simulation_seed_streams_are_independent() -> None:
    a = DeterministicRng("sim-seed")
    b = DeterministicRng("sim-seed")
    for _ in range(50):
        a.roll("1d100", stream="encounter")
    assert a.roll("1d20", stream="dice").total == b.roll("1d20", stream="dice").total
