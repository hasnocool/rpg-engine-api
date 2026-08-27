from typing import Protocol


class ActorController(Protocol):
    controller_type: str
    controller_version: str

    def choose_action(self, decision_view: dict[str, object]) -> dict[str, object]: ...
