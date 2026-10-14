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
                {"question_id": question["question_id"], "valid": True, "verified_answer": "Negative gradient", "reason": "Supported",
                 "support_quote": "Gradient descent updates parameters in the negative gradient direction.", "cognitive_level": "easy"}
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


def test_recall_fallback_can_be_completed_and_updates_saved_progress(monkeypatch, tmp_path):
    repository = StudyRepository(tmp_path / "practice.db")
    course_id = repository.create_course("Mechanics")
    text = " ".join(f"Experiment {index} measures temperature changes in heated metal samples after {index + 10} minutes." for index in range(1, 9))
    chunk = KnowledgeChunk(chunk_id="mechanics-1", text=text, token_count=len(text.split()),
        citation=CitationAnchor(source_id="source-1", source_name="Notes.txt", source_type=SourceType.DOCUMENT, section="Experiments"))
    repository.save_material(course_id=course_id, source_id="source-1", name="Notes.txt", kind="document",
        chunks=[chunk], stored_path=None, source_uri=None)
    monkeypatch.setattr(api, "repository", repository)
    monkeypatch.setattr(api, "workspace", api.workspace_from_record(repository.load_course(course_id)))
    def offline(prompt):
        raise RuntimeError("Model unavailable")
    monkeypatch.setattr(api, "call_ollama_json", offline)
    created = api.create_assessment(api.AssessmentCreateRequest(question_count=12,
        difficulty="easy", allow_source_recall=True,
        question_types=["mcq", "short_answer", "numerical", "true_false", "fill_blank"]))
    record = repository.get_assessment(created["id"])
    answers = {question.question_id: question.correct_answer for question in record["questions"]}
    submitted = api.submit_assessment(created["id"], api.AssessmentSubmitRequest(answers=answers))
    assert len(created["questions"]) == 12
    assert submitted["report"]["percentage"] == 100
    assert len(submitted["report"]["feedback"]) == 12
    progress = repository.progress_summary(course_id)
    assert progress["completed_assessments"] == 1
    assert progress["total_questions"] == 12
    assert progress["score_history"][0]["score"] == 100
