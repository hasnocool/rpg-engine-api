from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Persona:
    name: str
    principal_id: str
    role: str = "player"
