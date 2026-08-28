from dataclasses import dataclass


@dataclass(slots=True)
class ControllableClock:
    now: int = 0

    def advance(self, amount: int) -> int:
        if amount < 0:
            raise ValueError("test clock cannot move backward")
        self.now += amount
        return self.now
