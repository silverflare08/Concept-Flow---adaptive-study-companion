from studybuddy.ingestion.models import CitationAnchor, KnowledgeChunk, SourceType
from studybuddy.tutor.material_overview import build_overview_prompt, generate_material_overview


def material_chunk() -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id="notes-1", text="Photosynthesis converts light energy into chemical energy.", token_count=8,
        citation=CitationAnchor(
            source_id="notes", source_name="Biology.pdf", source_type=SourceType.PDF,
            source_uri="/api/sources/notes", page=7,
        ),
    )


def test_overview_prompt_requests_a_teachable_exam_lesson() -> None:
    prompt = build_overview_prompt("Biology", [material_chunk()], 1, 1)
    assert "definitions, formulas, processes" in prompt
    assert "Exam focus" in prompt
    assert "ONLY" in prompt


def test_overview_returns_model_lesson_with_application_owned_citations() -> None:
    result = generate_material_overview(
        "Biology", [material_chunk()], generate=lambda prompt: "## Photosynthesis\nA detailed lesson.",
    )
    assert result["answer"].startswith("## Photosynthesis")
    assert result["citations"][0]["label"] == "Biology.pdf, PDF page 7"
    assert result["citations"][0]["target_uri"] == "/api/sources/notes#page=7"
    assert result["generation_mode"] == "local_ai"


def test_overview_falls_back_to_a_cited_source_lesson_when_model_is_offline() -> None:
    result = generate_material_overview(
        "Biology", [material_chunk()], generate=lambda prompt: "unused", model_available=False,
    )

    assert result["generation_mode"] == "extractive_fallback"
    assert "Photosynthesis converts light energy" in result["answer"]
    assert "Biology.pdf, PDF page 7" in result["answer"]


def test_overview_prompt_can_request_hinglish() -> None:
    prompt = build_overview_prompt("Biology", [material_chunk()], 1, 1, language="hinglish")
    assert "conversational Hinglish" in prompt
    assert "raw LaTeX" in prompt
