import json

import pytest

from studybuddy.assessment import (
    AssessmentQuestion,
    generate_assessment,
    grade_objective,
    grade_short_answer,
    humanize_math_text,
    parse_assessment_draft,
    question_fingerprint,
    question_similarity,
)
from studybuddy.ingestion.models import CitationAnchor, KnowledgeChunk, SourceType


def chunk() -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id="optimisation-1",
        text="Gradient descent updates parameters in the negative gradient direction. A learning rate of 0.1 controls the step size.",
        token_count=18,
        citation=CitationAnchor(
            source_id="notes", source_name="ML notes.pdf", source_type=SourceType.PDF, page=8,
        ),
    )


def test_raw_latex_is_converted_to_readable_math() -> None:
    assert humanize_math_text(r"\(\frac{a}{b} \times \pi\)") == "(a) ÷ (b) × π"


def mcq_payload(prompt: str = "Which direction does gradient descent use?") -> dict:
    return {
        "title": "Optimisation check",
        "questions": [{
            "question_type": "mcq",
            "prompt": prompt,
            "topic": "Gradient descent",
            "difficulty": "easy",
            "options": ["Negative gradient", "Positive gradient", "Random direction", "No direction"],
            "correct_answer": "Negative gradient",
            "explanation": "The notes state that gradient descent moves parameters in the negative gradient direction. This direction reduces the objective locally, so the negative gradient is the supported answer rather than a positive or random direction.",
            "grading_criteria": [],
            "evidence_chunk_ids": ["optimisation-1"],
        }],
    }


def verifier(prompt: str) -> str:
    questions = json.loads(prompt.split("QUESTIONS: ", 1)[1].split("\nEVIDENCE:", 1)[0])
    return json.dumps({"decisions": [
        {"question_id": question["question_id"], "valid": True, "verified_answer": question["correct_answer"], "reason": "Supported by the passage."}
        for question in questions
    ]})


def test_question_schema_rejects_invalid_mcq() -> None:
    payload = mcq_payload()
    payload["questions"][0]["options"] = ["A", "B"]
    with pytest.raises(ValueError, match="four distinct options"):
        parse_assessment_draft(json.dumps(payload), allowed_chunk_ids={"optimisation-1"})


def test_question_schema_rejects_unknown_source_chunk() -> None:
    payload = mcq_payload()
    payload["questions"][0]["evidence_chunk_ids"] = ["invented-source"]
    with pytest.raises(ValueError, match="unknown source chunks"):
        parse_assessment_draft(json.dumps(payload), allowed_chunk_ids={"optimisation-1"})


def test_generation_repairs_a_repeated_question() -> None:
    calls = 0

    def generator(prompt: str) -> str:
        nonlocal calls
        calls += 1
        repeated = "Which direction does gradient descent use?"
        replacement = "According to the notes, how are parameters updated by gradient descent?"
        return json.dumps(mcq_payload(repeated if calls == 1 else replacement))

    draft = generate_assessment(
        course_name="Machine Learning",
        chunks=[chunk()],
        count=1,
        difficulty="easy",
        question_types=["mcq"],
        scope=["Gradient descent"],
        previous_prompts=["Which direction does gradient descent use?"],
        generate_json=generator,
        verify_json=verifier,
    )

    assert calls == 2
    assert draft.questions[0].prompt.startswith("According to")


def test_generation_repairs_an_mcq_answer_without_direct_source_support() -> None:
    calls = 0

    def generator(prompt: str) -> str:
        nonlocal calls
        calls += 1
        payload = mcq_payload()
        if calls == 1:
            payload["questions"][0]["options"] = [
                "Increase parameters", "Decrease parameters", "Multiply parameters", "Keep parameters fixed",
            ]
            payload["questions"][0]["correct_answer"] = "Decrease parameters"
        return json.dumps(payload)

    draft = generate_assessment(
        course_name="Machine Learning",
        chunks=[chunk()],
        count=1,
        difficulty="easy",
        question_types=["mcq"],
        scope=["Gradient descent"],
        previous_prompts=[],
        generate_json=generator,
        verify_json=verifier,
    )

    assert calls == 2
    assert draft.questions[0].correct_answer == "Negative gradient"


def test_objective_grading_handles_mcq_and_numeric_tolerance() -> None:
    mcq = AssessmentQuestion.model_validate(mcq_payload()["questions"][0])
    assert grade_objective(mcq, "negative gradient").correct is True
    numerical = AssessmentQuestion(
        question_type="numerical",
        prompt="What learning rate is stated in the notes?",
        topic="Gradient descent",
        difficulty="easy",
        correct_answer="0.1",
        explanation="The passage states 0.1.",
        evidence_chunk_ids=["optimisation-1"],
        numerical_tolerance=0.01,
    )
    assert grade_objective(numerical, "0.105").correct is True
    assert grade_objective(numerical, "0.3").correct is False


def test_short_answer_grading_is_bounded_and_grounded() -> None:
    question = AssessmentQuestion(
        question_type="short_answer",
        prompt="How does gradient descent update parameters?",
        topic="Gradient descent",
        difficulty="medium",
        correct_answer="It updates them in the negative gradient direction.",
        explanation="This is stated in the notes.",
        grading_criteria=["Mentions the negative gradient direction"],
        evidence_chunk_ids=["optimisation-1"],
    )
    result = grade_short_answer(
        question,
        "It moves opposite to the gradient.",
        {"optimisation-1": chunk()},
        grade_json=lambda prompt: json.dumps({
            "score": 0.9, "correct": True, "feedback": "Correct idea.", "misconception": None,
        }),
    )
    assert result.correct is True
    assert result.score == 0.9


def test_novelty_uses_exact_hash_and_lexical_similarity() -> None:
    assert question_fingerprint("What is gradient descent?") == question_fingerprint("What is gradient-descent")
    assert question_similarity(
        "What direction does gradient descent use to update parameters?",
        "Which direction does gradient descent use to update parameters?",
    ) >= 0.82
