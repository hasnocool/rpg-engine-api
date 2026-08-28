from pydantic import BaseModel, ConfigDict, Field, model_validator

from .grants import Grant
from .requirements import RequirementExpr


class ProgressionNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    rank: int = Field(default=1, ge=1)
    prerequisites: RequirementExpr | None = None
    grants: tuple[Grant, ...] = ()
    cost: int = Field(default=1, ge=0)
    hidden: bool = False


class ProgressionEdge(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    target: str
    exclusive_group: str | None = None


class ProgressionGraph(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0"
    id: str
    currency_key: str = "progression_points"
    nodes: tuple[ProgressionNode, ...] = ()
    edges: tuple[ProgressionEdge, ...] = ()

    @model_validator(mode="after")
    def references_known_nodes(self) -> "ProgressionGraph":
        known = {node.id for node in self.nodes}
        if len(known) != len(self.nodes):
            raise ValueError("progression node IDs must be unique")
        for edge in self.edges:
            if edge.source not in known or edge.target not in known:
                raise ValueError("progression edge references unknown node")
        return self
