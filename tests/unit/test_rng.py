from rpg_engine_api.domain.dice import DeterministicRng


def test_same_seed_same_stream_same_results() -> None:
    first = DeterministicRng(1234)
    second = DeterministicRng(1234)
    assert [first.roll("1d20").total for _ in range(10)] == [
        second.roll("1d20").total for _ in range(10)
    ]


def test_unrelated_stream_does_not_perturb_dice() -> None:
    first = DeterministicRng(99)
    second = DeterministicRng(99)
    first.roll("1d100", stream="world")
    assert first.roll("1d20", stream="dice").total == second.roll("1d20", stream="dice").total
