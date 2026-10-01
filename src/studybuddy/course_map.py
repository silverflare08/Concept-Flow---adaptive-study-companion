"""Course concepts and prerequisite graph contracts.

The graph is deliberately separate from retrieval: a source chunk can discuss
several concepts, while the learner model needs a stable concept identity.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class Concept(BaseModel):
    concept_id: str = Field(pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    description: str = Field(min_length=1)


class PrerequisiteEdge(BaseModel):
    prerequisite_id: str
    dependent_id: str

    @model_validator(mode="after")
    def cannot_point_to_itself(self) -> "PrerequisiteEdge":
        if self.prerequisite_id == self.dependent_id:
            raise ValueError("a concept cannot be its own prerequisite")
        return self


class CourseMap(BaseModel):
    course_id: str = Field(pattern=r"^[a-z0-9-]+$")
    title: str = Field(min_length=1)
    concepts: list[Concept] = Field(min_length=1)
    prerequisite_edges: list[PrerequisiteEdge] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_graph(self) -> "CourseMap":
        ids = [concept.concept_id for concept in self.concepts]
        if len(ids) != len(set(ids)):
            raise ValueError("concept ids must be unique")
        known = set(ids)
        for edge in self.prerequisite_edges:
            if edge.prerequisite_id not in known or edge.dependent_id not in known:
                raise ValueError("all prerequisite edges must refer to known concepts")
        self._assert_acyclic()
        return self

    def _assert_acyclic(self) -> None:
        children: dict[str, list[str]] = {item.concept_id: [] for item in self.concepts}
        for edge in self.prerequisite_edges:
            children[edge.prerequisite_id].append(edge.dependent_id)

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise ValueError("prerequisite graph must be acyclic")
            if node not in visited:
                visiting.add(node)
                for child in children[node]:
                    visit(child)
                visiting.remove(node)
                visited.add(node)

        for concept_id in children:
            visit(concept_id)

    def prerequisites_of(self, concept_id: str) -> set[str]:
        """Return direct prerequisite ids; policy can expand this transitively later."""
        return {
            edge.prerequisite_id
            for edge in self.prerequisite_edges
            if edge.dependent_id == concept_id
        }
