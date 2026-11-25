"""Bounded user-authored workflow graph; legal support is never client assigned."""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)
]
Item = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
Items = Annotated[list[Item], Field(max_length=30)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class Position(StrictModel):
    x: float = Field(ge=-100000, le=100000, allow_inf_nan=False)
    y: float = Field(ge=-100000, le=100000, allow_inf_nan=False)


class EditorStage(StrictModel):
    id: UUID
    title: Title
    explanation: Description
    responsible_party: Item | None = None
    required_documents: Items = Field(default_factory=list)
    limitations: Items = Field(default_factory=list)
    position: Position
    actions: Items = Field(default_factory=list)
    preconditions: Items = Field(default_factory=list)
    outcomes: Items = Field(default_factory=list)
    status: Literal["pending", "in_progress", "completed"] = "pending"


class Edge(StrictModel):
    source: UUID
    target: UUID


class WorkflowWrite(StrictModel):
    version: int = Field(ge=0)
    stages: list[EditorStage] = Field(max_length=50)
    edges: list[Edge] = Field(max_length=200)

    @model_validator(mode="after")
    def valid_graph(self) -> Self:
        ids = {stage.id for stage in self.stages}
        if len(ids) != len(self.stages):
            raise ValueError("Stage IDs must be unique")
        titles = {stage.title.casefold() for stage in self.stages}
        if len(titles) != len(self.stages):
            raise ValueError("Stage titles must be unique")
        pairs = {(edge.source, edge.target) for edge in self.edges}
        if len(pairs) != len(self.edges):
            raise ValueError("Connections must be unique")
        children: dict[UUID, list[UUID]] = {key: [] for key in ids}
        for source, target in pairs:
            if source not in ids or target not in ids or source == target:
                raise ValueError("Connections must reference distinct existing stages")
            children[source].append(target)
        visiting, visited = set(), set()

        def visit(key):
            if key in visiting:
                raise ValueError("Workflow connections cannot form a cycle")
            if key in visited:
                return
            visiting.add(key)
            for child in children[key]:
                visit(child)
            visiting.remove(key)
            visited.add(key)

        for key in ids:
            visit(key)
        return self


class WorkflowRead(WorkflowWrite):
    review_status: str
