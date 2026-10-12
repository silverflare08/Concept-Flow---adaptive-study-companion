"""A small terminal demo for the currently implemented ConceptFlow foundation.

Run with:
    python -m studybuddy.demo
    python -m studybuddy.demo --question "Which traversal uses a queue?"
"""

from __future__ import annotations

import argparse

from studybuddy.course_map import Concept, CourseMap, PrerequisiteEdge
from studybuddy.ingestion.models import CitationAnchor, KnowledgeChunk, SourceType
from studybuddy.retrieval.bm25 import BM25Index
from studybuddy.tutor.bkt import BKTParameters, update_mastery


def _chunk(chunk_id: str, text: str, page: int, concepts: list[str]) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=chunk_id,
        text=text,
        token_count=len(text.split()),
        concepts=concepts,
        citation=CitationAnchor(
            source_id="graph-notes",
            source_name="Graph Algorithms notes",
            source_type=SourceType.PDF,
            source_uri="https://example.edu/graph-algorithms-notes.pdf",
            page=page,
        ),
    )


def _course_map() -> CourseMap:
    return CourseMap(
        course_id="graph-demo",
        title="Graph Algorithms",
        concepts=[
            Concept(
                concept_id="graph-representations",
                name="Graph representations",
                topic="Foundations",
                description="Vertices, edges, and adjacency representations.",
            ),
            Concept(
                concept_id="bfs",
                name="Breadth-first search",
                topic="Traversal",
                description="Layered graph traversal with a queue.",
            ),
            Concept(
                concept_id="dfs",
                name="Depth-first search",
                topic="Traversal",
                description="Traversal using recursion or a stack.",
            ),
            Concept(
                concept_id="topological-sort",
                name="Topological sort",
                topic="Directed graphs",
                description="An ordering consistent with directed dependencies.",
            ),
        ],
        prerequisite_edges=[
            PrerequisiteEdge(prerequisite_id="graph-representations", dependent_id="bfs"),
            PrerequisiteEdge(prerequisite_id="graph-representations", dependent_id="dfs"),
            PrerequisiteEdge(prerequisite_id="dfs", dependent_id="topological-sort"),
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ConceptFlow foundation demo.")
    parser.add_argument(
        "--question",
        default="Which traversal uses a queue?",
        help="Question to search in the small graph-algorithms demo corpus.",
    )
    arguments = parser.parse_args()

    course = _course_map()
    index = BM25Index(
        [
            _chunk(
                "bfs-notes",
                "Breadth-first search uses a queue and discovers vertices in graph layers.",
                4,
                ["bfs"],
            ),
            _chunk(
                "dfs-notes",
                "Depth-first search uses recursion or an explicit stack before backtracking.",
                8,
                ["dfs"],
            ),
            _chunk(
                "topological-notes",
                "Topological sorting uses DFS finishing order on a directed acyclic graph.",
                12,
                ["topological-sort"],
            ),
        ]
    )

    print("\n=== ConceptFlow foundation demo ===\n")
    print(f"Course: {course.title}")
    print("Prerequisite for topological sort:", ", ".join(course.prerequisites_of("topological-sort")))

    print(f"\nQuestion: {arguments.question}")
    results = index.search(arguments.question)
    if not results:
        print("Course-backed answer: Not covered by the available material.")
    else:
        best = results[0]
        print("Retrieved evidence:", best.chunk.text)
        print("Citation:", best.chunk.citation.label())
        print("Open target:", best.chunk.citation.target_uri())

    before = 0.35
    after = update_mastery(before, correct=True, parameters=BKTParameters(learn=0.1))
    print(f"\nLearner model: BFS mastery after a correct answer: {before:.0%} -> {after:.0%}")
    print("\nNext build: real course uploads, dense retrieval, and the chat interface.")


if __name__ == "__main__":
    main()
