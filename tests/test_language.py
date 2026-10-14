from studybuddy.language import HINGLISH_INSTRUCTION, matches_requested_language, rewrite_prompt
from studybuddy.tutor.grounded import build_tutor_prompt


def test_hinglish_means_romanised_hindi_not_devanagari_or_english():
    assert matches_requested_language("Standardisation se features ka scale comparable ho jata hai.", "hinglish")
    assert not matches_requested_language("Standardisation makes the feature scales comparable.", "hinglish")
    assert not matches_requested_language("Standardisation से features का scale comparable हो जाता है।", "hinglish")
    assert matches_requested_language("यह एक महत्वपूर्ण परिभाषा है।", "hindi")


def test_shared_hinglish_instruction_is_used_for_tutor_and_rewrite():
    assert HINGLISH_INSTRUCTION in build_tutor_prompt("Explain this", [], language="hinglish")
    assert HINGLISH_INSTRUCTION in rewrite_prompt("A definition", "hinglish")


def test_romanised_query_is_translated_when_retrieval_has_no_match():
    from studybuddy.tutor.grounded import tutor_answer
    from studybuddy.ingestion.models import KnowledgeChunk, CitationAnchor, SourceType
    chunk = KnowledgeChunk(chunk_id="q", text="Standardisation makes feature scales comparable.", token_count=6,
        citation=CitationAnchor(source_id="notes", source_name="ML", source_type=SourceType.PDF, page=1))
    replies = iter(["standardisation feature scales", "Standardisation se features ka scale comparable ho jata hai."])
    answer = tutor_answer("Isko kaise samjhu?", [chunk], language="hinglish", generate=lambda prompt: next(replies))
    assert answer.coverage == "course_backed"
    assert "se features ka" in answer.answer
