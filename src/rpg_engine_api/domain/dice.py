import hashlib
import random
import re
from dataclasses import dataclass

_DICE = re.compile(r"^(?P<count>[1-9][0-9]*)d(?P<sides>[1-9][0-9]*)(?P<mod>[+-][0-9]+)?$")


@dataclass(frozen=True, slots=True)
class DiceResult:
    expression: str
    rolls: tuple[int, ...]
    modifier: int
    total: int
    rng_stream: str
    rng_sequence: int


class DeterministicRng:
    """Independent named deterministic streams derived from one campaign seed."""

    def __init__(self, seed: int | str) -> None:
        self._seed = str(seed)
        self._streams: dict[str, random.Random] = {}
        self._sequence: dict[str, int] = {}

    def _stream(self, name: str) -> random.Random:
        if name not in self._streams:
            digest = hashlib.sha256(f"{self._seed}:{name}".encode()).digest()
            self._streams[name] = random.Random(int.from_bytes(digest, "big"))
            self._sequence[name] = 0
        return self._streams[name]

    def roll(self, expression: str, *, stream: str = "dice") -> DiceResult:
        match = _DICE.fullmatch(expression.strip().lower())
        if match is None:
            raise ValueError("dice expression must look like NdM, NdM+K, or NdM-K")
        count = int(match.group("count"))
        sides = int(match.group("sides"))
        if count > 100 or sides > 100000:
            raise ValueError("dice expression exceeds safety bounds")
        modifier = int(match.group("mod") or 0)
        rng = self._stream(stream)
        rolls = tuple(rng.randint(1, sides) for _ in range(count))
        self._sequence[stream] += 1
        return DiceResult(expression=expression, rolls=rolls, modifier=modifier, total=sum(rolls) + modifier, rng_stream=stream, rng_sequence=self._sequence[stream])

    def replay_roll(self, expression: str, expected_rolls: tuple[int, ...] | list[int], *, stream: str = "dice", expected_sequence: int | None = None) -> DiceResult:
        """Advance a stream while proving stored random evidence still matches the seed."""
        result = self.roll(expression, stream=stream)
        expected = tuple(int(value) for value in expected_rolls)
        if result.rolls != expected:
            raise ValueError(f"deterministic RNG replay mismatch on stream {stream}: expected {expected}, got {result.rolls}")
        if expected_sequence is not None and result.rng_sequence != expected_sequence:
            raise ValueError(f"deterministic RNG sequence mismatch on stream {stream}: expected {expected_sequence}, got {result.rng_sequence}")
        return result

    def sequence(self, stream: str = "dice") -> int:
        self._stream(stream)
        return self._sequence[stream]
