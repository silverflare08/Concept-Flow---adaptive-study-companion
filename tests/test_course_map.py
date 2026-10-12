import json
from pathlib import Path

import pytest

from studybuddy.course_map import Concept, CourseMap, PrerequisiteEdge


def test_graph_fixture_is_a_valid_prerequisite_dag() -> None:
    fixture = Path(__file__).parents[1] / "configs" / "mit_6006_graphs.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    course = CourseMap(
        course_id=payload["course_id"],
        title=payload["title"],
        concepts=payload["concepts"],
        prerequisite_edges=payload["prerequisite_edges"],
    )

    assert course.prerequisites_of("dijkstra") == {"weighted-graphs"}
    assert course.prerequisites_of("topological-sort") == {"dfs"}


def test_course_map_rejects_cycles() -> None:
    concepts = [
        Concept(concept_id="a", name="A", topic="T", description="first"),
        Concept(concept_id="b", name="B", topic="T", description="second"),
    ]

    with pytest.raises(ValueError, match="acyclic"):
        CourseMap(
            course_id="cycle-test",
            title="Cycle test",
            concepts=concepts,
            prerequisite_edges=[
                PrerequisiteEdge(prerequisite_id="a", dependent_id="b"),
                PrerequisiteEdge(prerequisite_id="b", dependent_id="a"),
            ],
        )
def test_course_map_finds_a_concept_by_id() -> None:
    course = CourseMap(
        course_id="dbms-basics",
        title="DBMS basics",
        concepts=[
            Concept(
                concept_id="functional-dependency",
                name="Functional dependency",
                topic="Normalisation",
                description="A relationship between attributes.",
            )
        ],
    )

    concept = course.concept_by_id("functional-dependency")

    assert concept.name == "Functional dependency"


def test_course_map_finds_a_later_concept_by_id() -> None:
    course = CourseMap(
        course_id="dbms-basics",
        title="DBMS basics",
        concepts=[
            Concept(
                concept_id="functional-dependency",
                name="Functional dependency",
                topic="Normalisation",
                description="A relationship between attributes.",
            ),
            Concept(
                concept_id="second-normal-form",
                name="Second normal form",
                topic="Normalisation",
                description="Removes partial dependencies.",
            ),
        ],
    )

    concept = course.concept_by_id("second-normal-form")

    assert concept.name == "Second normal form"


def test_course_map_returns_prerequisite_first_learning_order() -> None:
    course = CourseMap(
        course_id="dbms-basics",
        title="DBMS basics",
        concepts=[
            Concept(concept_id="dependency", name="Dependency", topic="Normalisation", description="Foundation."),
            Concept(concept_id="second-normal-form", name="Second normal form", topic="Normalisation", description="Advanced."),
        ],
        prerequisite_edges=[PrerequisiteEdge(prerequisite_id="dependency", dependent_id="second-normal-form")],
    )

    assert course.learning_order() == ["dependency", "second-normal-form"]
