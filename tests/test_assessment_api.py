import json
from pathlib import Path

from studybuddy import api
from studybuddy.database import StudyRepository
from studybuddy.ingestion.models import CitationAnchor, KnowledgeChunk, SourceType


def test_assessment_api_generates_hides_answers_grades_and_exports(monkeypatch, tmp_path: Path) -> None:
    repository = StudyRepository(tmp_path / "test.db")
    course_id = repository.create_course("Machine Learning")
    chunk = KnowledgeChunk(
        chunk_id="optimisation-1",
        text="Gradient descent updates parameters in the negative gradient direction.",
        token_count=9,
        citation=CitationAnchor(
            source_id="source-1", source_name="ML notes.pdf", source_type=SourceType.PDF, page=8,
        ),
    )
    repository.save_material(
        course_id=course_id,
        source_id="source-1",
        name="ML notes.pdf",
        kind="pdf",
        chunks=[chunk],
        stored_path=None,
        source_uri=None,
    )
    monkeypatch.setattr(api, "repository", repository)
    monkeypatch.setattr(api, "workspace", api.workspace_from_record(repository.load_course(course_id)))

    def local_model(prompt: str) -> str:
        if "Independently solve every assessment question" in prompt:
            questions = json.loads(prompt.split("QUESTIONS: ", 1)[1].split("\nEVIDENCE:", 1)[0])
            return json.dumps({"decisions": [
                {"question_id": question["question_id"], "valid": True, "verified_answer": question["correct_answer"], "reason": "Supported"}
                for question in questions
            ]})
        return json.dumps({
            "title": "Gradient descent check",
            "questions": [{
                "question_type": "mcq",
                "prompt": "Which direction does gradient descent use?",
                "topic": "Gradient descent",
                "difficulty": "easy",
                "options": ["Negative gradient", "Positive gradient", "Random direction", "No direction"],
                "correct_answer": "Negative gradient",
                "explanation": "The source states that gradient descent updates parameters in the negative gradient direction. Therefore the supported option is Negative gradient, while the positive, random, and no-direction choices contradict the cited statement.",
                "grading_criteria": [],
                "evidence_chunk_ids": ["optimisation-1"],
            }],
        })

    monkeypatch.setattr(api, "call_ollama_json", local_model)
    created = api.create_assessment(api.AssessmentCreateRequest(
        scope=["Gradient descent"], question_count=1, difficulty="easy", question_types=["mcq"],
    ))

    assert created["status"] == "ready"
    assert "correct_answer" not in created["questions"][0]
    question_id = created["questions"][0]["question_id"]

    submitted = api.submit_assessment(
        created["id"], api.AssessmentSubmitRequest(answers={question_id: "Negative gradient"}),
    )

    assert submitted["report"]["percentage"] == 100
    assert submitted["mastery"][0]["mastery"] > 0.2
    download = api.download_assessment(created["id"])
    assert b"Score: 100.0%" in download.body
    text_download = api.download_assessment(created["id"], format="txt")
    assert text_download.media_type.startswith("text/plain")
    question_paper = api.download_assessment(created["id"], format="json")
    assert question_paper.media_type == "application/json"


def test_additional_objective_assessment_types_are_valid_and_gradeable() -> None:
    true_false = api.AssessmentQuestion(
        question_type="true_false", prompt="Gradient descent follows the negative gradient. True or false?",
        topic="Gradient descent", difficulty="easy", options=["True", "False"], correct_answer="True",
        explanation="The source explicitly states this.", evidence_chunk_ids=["optimisation-1"],
    )
    fill_blank = api.AssessmentQuestion(
        question_type="fill_blank", prompt="Gradient descent follows the ____ gradient.",
        topic="Gradient descent", difficulty="easy", correct_answer="negative",
        explanation="The missing term is negative.", evidence_chunk_ids=["optimisation-1"],
    )

    assert api.grade_objective(true_false, "true").correct is True
    assert api.grade_objective(fill_blank, "Negative").correct is True
