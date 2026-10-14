from studybuddy.ingestion.models import CitationAnchor, KnowledgeChunk, SourceType
from studybuddy.tutor.grounded import build_tutor_prompt, tutor_answer


def _chunk(text: str) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id="normalisation", text=text, token_count=len(text.split()),
        citation=CitationAnchor(source_id="dbms", source_name="DBMS notes", source_type=SourceType.PDF, page=14),
    )


def test_tutor_returns_generated_answer_with_verified_citation() -> None:
    chunks = [_chunk("Second normal form removes partial dependency from a relation.")]
    reply = tutor_answer("Explain second normal form", chunks, generate=lambda prompt: "2NF removes partial dependency.")
    assert reply.answer == "2NF removes partial dependency."
    assert reply.coverage == "course_backed"
    assert reply.citations[0]["label"] == "DBMS notes, PDF page 14"
    assert "partial dependency" in reply.citations[0]["excerpt"]


def test_tutor_refuses_question_without_course_evidence() -> None:
    reply = tutor_answer("Explain quantum entanglement", [_chunk("Second normal form removes partial dependency.")])
    assert reply.coverage == "not_covered"
    assert reply.citations == []


def test_tutor_prompt_contains_the_question_evidence_and_grounding_rule() -> None:
    prompt = build_tutor_prompt("What is 2NF?", [_chunk("Second normal form removes partial dependency.")])
    assert "What is 2NF?" in prompt
    assert "DBMS notes, PDF page 14" in prompt
    assert "closed book" in prompt


def test_tutor_prompt_supports_hindi_and_readable_math() -> None:
    prompt = build_tutor_prompt("द्विघात समीकरण समझाओ", [_chunk("x squared is used here")], language="hindi")
    assert "Devanagari" in prompt
    assert "Never output raw LaTeX" in prompt


def test_tutor_prompt_uses_learner_history_to_personalise_depth() -> None:
    prompt = build_tutor_prompt(
        "Explain 2NF", [_chunk("Second normal form removes partial dependency.")],
        learner_context="Weak topic: Normalisation 35%. Strong topic: Keys 85%.",
    )
    assert "Normalisation 35%" in prompt
    assert "connect to stronger prior topics" in prompt


def test_tutor_retries_when_local_model_ignores_hindi_selection() -> None:
    responses = iter([
        "## Definition\nGradient descent follows the negative gradient.",
        "## परिभाषा\nGradient descent negative gradient की दिशा में चलता है।",
    ])
    prompts = []

    def generator(prompt: str) -> str:
        prompts.append(prompt)
        return next(responses)

    reply = tutor_answer("Explain gradient descent", [_chunk("Gradient descent follows the negative gradient.")], generate=generator, language="hindi")

    assert "परिभाषा" in reply.answer
    assert len(prompts) == 2
    assert "Rewrite" in prompts[1]


def test_hindi_question_is_translated_for_english_source_retrieval() -> None:
    responses = iter([
        "gradient descent negative gradient",
        "## व्याख्या\nGradient descent negative gradient की दिशा में parameters को बदलता है।",
    ])

    reply = tutor_answer(
        "ग्रेडिएंट डिसेंट किस दिशा में चलता है?",
        [_chunk("Gradient descent follows the negative gradient direction.")],
        generate=lambda prompt: next(responses),
        language="hindi",
    )

    assert reply.coverage == "course_backed"
    assert "व्याख्या" in reply.answer
