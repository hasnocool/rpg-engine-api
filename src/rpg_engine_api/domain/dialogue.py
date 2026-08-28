from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rpg_engine_api.domain.requirements import RequirementExpr
from rpg_engine_api.rules.requirements_runtime import RequirementContext, evaluate_requirement


class DialogueSessionStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DialogueChoice(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    label: str
    next_node_id: str | None = None
    requirements: RequirementExpr | None = None
    consequence_tags: tuple[str, ...] = ()


class DialogueNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    speaker_ref: str
    text_key: str
    choices: tuple[DialogueChoice, ...] = ()
    terminal: bool = False


class DialogueDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0"
    id: str
    start_node_id: str
    nodes: tuple[DialogueNode, ...]

    @model_validator(mode="after")
    def validate_graph(self) -> "DialogueDefinition":
        known = {node.id for node in self.nodes}
        if self.start_node_id not in known:
            raise ValueError("dialogue start node does not exist")
        if len(known) != len(self.nodes):
            raise ValueError("dialogue node IDs must be unique")
        for node in self.nodes:
            for choice in node.choices:
                if choice.next_node_id is not None and choice.next_node_id not in known:
                    raise ValueError("dialogue choice references unknown node")
        return self

    def node(self, node_id: str) -> DialogueNode:
        return next(node for node in self.nodes if node.id == node_id)


class DialogueSession(BaseModel):
    schema_version: str = "1.0"
    session_id: str
    dialogue_id: str
    campaign_id: str
    actor_id: str
    npc_id: str
    current_node_id: str
    status: DialogueSessionStatus = DialogueSessionStatus.ACTIVE
    history: list[str] = Field(default_factory=list)
    consequence_tags: set[str] = Field(default_factory=set)

    def available_choices(
        self,
        definition: DialogueDefinition,
        context: RequirementContext,
    ) -> tuple[DialogueChoice, ...]:
        if self.status != DialogueSessionStatus.ACTIVE:
            return ()
        node = definition.node(self.current_node_id)
        return tuple(
            choice
            for choice in node.choices
            if evaluate_requirement(choice.requirements, context)
        )

    def choose(
        self,
        definition: DialogueDefinition,
        choice_id: str,
        context: RequirementContext,
    ) -> DialogueChoice:
        available = {choice.id: choice for choice in self.available_choices(definition, context)}
        choice = available.get(choice_id)
        if choice is None:
            raise ValueError("dialogue choice is not available")
        self.history.append(choice.id)
        self.consequence_tags.update(choice.consequence_tags)
        if choice.next_node_id is None:
            self.status = DialogueSessionStatus.COMPLETED
        else:
            self.current_node_id = choice.next_node_id
            if definition.node(self.current_node_id).terminal:
                self.status = DialogueSessionStatus.COMPLETED
        return choice
