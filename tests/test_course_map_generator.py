import json
import re

import pytest

from studybuddy.ingestion.models import CitationAnchor, KnowledgeChunk, SourceType
from studybuddy.tutor.course_map_generator import (
    generate_course_map,
    parse_course_map_draft,
    batch_chunks,
)


def _chunk(chunk_id: str, text: str) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=chunk_id,
        text=text,
        token_count=len(text.split()),
        citation=CitationAnchor(
            source_id="dbms", source_name="DBMS notes", source_type=SourceType.PDF, page=4
        ),
    )


def test_generates_a_valid_source_linked_course_map() -> None:
    chunk = _chunk("normalisation-basics", "Functional dependency is a prerequisite for normalisation.")
    draft = json.dumps(
        {
            "concepts": [
                {
                    "concept_id": "functional-dependency",
                    "name": "Functional dependency",
                    "topic": "Normalisation",
                    "description": "A relationship between attributes.",
                    "evidence_chunk_ids": ["normalisation-basics"],
                    "study_steps": ["Read the cited definition", "Explain the attribute relationship"],
                    "key_points": ["Functional dependencies link attributes."],
                }
            ],
            "prerequisite_edges": [],
        }
    )

    course_map = generate_course_map("DBMS Unit 2", [chunk], generate_json=lambda prompt: draft)

    assert course_map.course_id == "dbms-unit-2"
    assert course_map.concepts[0].evidence_chunk_ids == ["normalisation-basics"]


def test_rejects_concepts_with_unknown_evidence() -> None:
    draft = json.dumps(
        {
            "concepts": [
                {
                    "concept_id": "invented-concept",
                    "name": "Invented concept",
                    "topic": "Test",
                    "description": "Should not be accepted.",
                    "evidence_chunk_ids": ["not-a-real-chunk"],
                }
            ],
            "prerequisite_edges": [],
        }
    )

    with pytest.raises(ValueError, match="unknown source evidence"):
        parse_course_map_draft(draft, title="Test", allowed_chunk_ids={"real-chunk"})


def test_discards_an_edge_to_a_concept_the_model_did_not_return() -> None:
    draft = json.dumps(
        {
            "concepts": [
                {
                    "concept_id": "real-concept",
                    "name": "Real concept",
                    "topic": "Topic",
                    "description": "Supported description.",
                    "evidence_chunk_ids": ["real-chunk"],
                    "study_steps": ["Read the source"],
                    "key_points": ["Supported point"],
                }
            ],
            "prerequisite_edges": [
                {"prerequisite_id": "missing-concept", "dependent_id": "real-concept"}
            ],
        }
    )

    parsed = parse_course_map_draft(draft, title="Test", allowed_chunk_ids={"real-chunk"})

    assert parsed.prerequisite_edges == []


def test_batches_retain_every_chunk_and_full_text_in_source_order() -> None:
    chunks = [_chunk(f"chunk-{index}", "content " * 700) for index in range(25)]
    batches = batch_chunks(chunks)
    assert len(batches) > 1
    assert [chunk for batch in batches for chunk in batch] == chunks


def test_full_generation_reads_the_final_section_and_merges_duplicate_concepts() -> None:
    chunks = [_chunk(f"chunk-{index}", "content " * 700) for index in range(15)]
    seen = []
    def generate(prompt):
        ids = re.findall(r"CHUNK_ID: ([^\n]+)", prompt)
        seen.extend(ids)
        return json.dumps({"concepts": [{"concept_id": "repeated", "name": "Same concept", "topic": "Topic",
            "description": "Summary", "study_steps": ["Read the source"], "key_points": ["Remember this"],
            "evidence_chunk_ids": ids}], "prerequisite_edges": []})
    course = generate_course_map("Full course", chunks, generate_json=generate)
    assert seen == [chunk.chunk_id for chunk in chunks]
    assert len(course.concepts) == 1
    assert course.concepts[0].evidence_chunk_ids == seen


def test_reconciles_prerequisites_between_separate_document_sections() -> None:
    chunks = [_chunk("foundation", "content " * 1100), _chunk("advanced", "content " * 1100)]
    def generate(prompt):
        if "CONCEPTS:" in prompt:
            return json.dumps({"prerequisite_edges": [{"prerequisite_id": "section-1-foundation", "dependent_id": "section-2-advanced"}]})
        identifier = re.findall(r"CHUNK_ID: ([^\n]+)", prompt)[0]
        return json.dumps({"concepts": [{"concept_id": identifier, "name": identifier, "topic": "Topic",
            "description": "Summary", "study_steps": ["Read the source"], "key_points": ["Remember"],
            "evidence_chunk_ids": [identifier]}], "prerequisite_edges": []})
    course = generate_course_map("Full course", chunks, generate_json=generate)
    assert course.prerequisites_of("section-2-advanced") == {"section-1-foundation"}
    assert course.learning_order() == ["section-1-foundation", "section-2-advanced"]


def test_incomplete_generation_keeps_missed_chunks_as_cited_source_summaries() -> None:
    chunks = [_chunk("first", "First topic"), _chunk("last", "Last topic")]
    draft = json.dumps({"concepts": [{"concept_id": "first", "name": "First", "topic": "Topic",
        "description": "Summary", "study_steps": ["Read"], "key_points": ["Remember"],
        "evidence_chunk_ids": ["first"]}], "prerequisite_edges": []})
    course = generate_course_map("Full course", chunks, generate_json=lambda prompt: draft)

    covered = {chunk_id for concept in course.concepts for chunk_id in concept.evidence_chunk_ids}
    assert covered == {"first", "last"}
    fallback = next(concept for concept in course.concepts if concept.evidence_chunk_ids == ["last"])
    assert fallback.topic == "Additional source material"
    assert "DBMS notes, PDF page 4" in fallback.name
    assert fallback.study_steps
