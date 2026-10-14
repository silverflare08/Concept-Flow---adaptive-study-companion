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
    assert result["fallback_reasons"][0]["section"] == 1
    assert "not currently available" in result["fallback_reasons"][0]["message"]


def test_overview_prompt_can_request_hinglish() -> None:
    prompt = build_overview_prompt("Biology", [material_chunk()], 1, 1, language="hinglish")
    assert "conversational Hinglish" in prompt
    assert "raw LaTeX" in prompt


def test_overview_retries_when_model_returns_english_for_hindi() -> None:
    responses = iter([
        "## Photosynthesis\nPlants convert light energy.",
        "## प्रकाश संश्लेषण\nपौधे light energy को chemical energy में बदलते हैं।",
    ])

    result = generate_material_overview(
        "Biology", [material_chunk()], generate=lambda prompt: next(responses), language="hindi",
    )

    assert "प्रकाश संश्लेषण" in result["answer"]
    assert result["generation_mode"] == "local_ai"


def test_overview_rejects_repetitive_or_unsupported_lessons() -> None:
    repeated = generate_material_overview(
        "Biology", [material_chunk()], generate=lambda prompt: "A repeated sentence about cells. " * 100,
    )
    assert repeated["fallback_sections"] == 1
    rejected = generate_material_overview(
        "Biology", [material_chunk()], generate=lambda prompt: "An invented explanation.",
        verify=lambda prompt: '{"supported": false, "issues": ["Not in the source"]}',
    )
    assert rejected["fallback_sections"] == 1
    assert "invented explanation" not in rejected["answer"]
    assert "not a verified explanation" in rejected["answer"]
    assert "source-comparison check" in rejected["fallback_reasons"][0]["message"]


def test_overview_keeps_source_locations_for_every_section() -> None:
    chunk = material_chunk()
    result = generate_material_overview("Biology", [chunk], generate=lambda prompt: "## Plants\nA lesson.")
    assert "Sources for this section" in result["answer"]
    assert "Biology.pdf, PDF page 7" in result["answer"]


def test_overview_does_not_teach_from_repetitive_stored_ocr() -> None:
    chunk = material_chunk().model_copy(update={"text": "The label For NB is written below the diagram. " * 100})
    def never_called(prompt):
        raise AssertionError("Unreliable extraction must not be used as teaching evidence")
    result = generate_material_overview("Notes", [chunk], generate=never_called)
    assert result["fallback_sections"] == 1
    assert "saved extraction for this location is repetitive" in result["answer"]
    assert "re-upload" in result["answer"]
    assert "extracted source" in result["fallback_reasons"][0]["message"]


def test_one_damaged_passage_does_not_block_a_readable_passage():
    good = material_chunk()
    bad = good.model_copy(update={"chunk_id": "bad", "text": "The label For NB is written below the diagram. " * 100})
    prompts = []
    result = generate_material_overview("Notes", [good, bad], generate=lambda prompt: prompts.append(prompt) or "## Photosynthesis\nPlants convert light energy.")
    assert len(prompts) == 1
    assert "For NB" not in prompts[0]
    assert "Plants convert light energy" in result["answer"]
    assert result["fallback_sections"] == 1
