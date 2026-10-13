from pathlib import Path

from studybuddy.course_map import Concept, CourseMap
from studybuddy.database import StudyRepository
from studybuddy.assessment import AssessmentDraft, AssessmentQuestion, QuestionFeedback
from studybuddy.ingestion.models import CitationAnchor, KnowledgeChunk, SourceType


def sample_chunk() -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id="source-1-chunk-1",
        text="Gradient descent repeatedly updates model parameters.",
        token_count=7,
        citation=CitationAnchor(
            source_id="source-1",
            source_name="optimisation.txt",
            source_type=SourceType.DOCUMENT,
            source_uri="/api/sources/source-1",
            section="paragraph 1",
        ),
    )


def test_course_sources_and_chunks_survive_repository_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "conceptflow.db"
    repository = StudyRepository(database_path)
    course_id = repository.create_course("Machine Learning")
    source_file = tmp_path / "optimisation.txt"
    source_file.write_text("Gradient descent repeatedly updates model parameters.", encoding="utf-8")
    repository.save_material(
        course_id=course_id,
        source_id="source-1",
        name=source_file.name,
        kind="document",
        chunks=[sample_chunk()],
        stored_path=source_file,
        source_uri="/api/sources/source-1",
    )

    restarted_repository = StudyRepository(database_path)
    restored = restarted_repository.load_course(course_id)

    assert restored is not None
    assert restored["name"] == "Machine Learning"
    assert restored["sources"][0]["downloadable"] is True
    assert restored["chunks"][0].text.startswith("Gradient descent")
    assert restored["source_files"]["source-1"] == source_file

    archived_path = restarted_repository.archive_material(course_id, "source-1")
    active_view = restarted_repository.load_course(course_id)
    historical_view = restarted_repository.load_course(course_id, include_archived_materials=True)
    assert archived_path == source_file
    assert active_view["sources"] == []
    assert active_view["chunks"] == []
    assert historical_view["sources"][0]["id"] == "source-1"
    assert historical_view["chunks"][0].text.startswith("Gradient descent")
    assert source_file.exists()


def test_chat_and_generated_artifact_are_persistent_and_downloadable(tmp_path: Path) -> None:
    repository = StudyRepository(tmp_path / "conceptflow.db")
    course_id = repository.create_course("Linear Algebra")
    conversation_id = repository.save_chat_exchange(
        course_id=course_id,
        question="What is an eigenvector?",
        answer="It is explained in your uploaded notes.",
        response_metadata={"citations": [{"label": "notes.pdf, PDF page 4"}]},
    )
    course_map = CourseMap(
        course_id=course_id,
        title="Linear Algebra",
        concepts=[Concept(
            concept_id="eigenvectors",
            name="Eigenvectors",
            topic="Linear algebra",
            description="Direction-preserving vectors.",
            evidence_chunk_ids=[],
            study_steps=["Read the definition."],
            key_points=["Direction is preserved."],
        )],
    )
    artifact_id = repository.save_course_map(course_id, course_map)

    conversation = repository.get_conversation(conversation_id)
    artifact = repository.get_artifact(artifact_id)

    assert conversation is not None
    assert [message["role"] for message in conversation["messages"]] == ["user", "assistant"]
    assert conversation["messages"][1]["metadata"]["citations"][0]["label"].endswith("page 4")
    assert artifact is not None
    assert artifact["content"]["title"] == "Linear Algebra"


def test_archiving_course_preserves_its_records_but_hides_it_from_active_courses(tmp_path: Path) -> None:
    repository = StudyRepository(tmp_path / "conceptflow.db")
    deleted_id = repository.create_course("Delete me")
    kept_id = repository.create_course("Keep me")
    source_file = tmp_path / "notes.txt"
    source_file.write_text("notes", encoding="utf-8")
    repository.save_material(
        course_id=deleted_id, source_id="source-1", name="notes.txt", kind="document",
        chunks=[sample_chunk()], stored_path=source_file, source_uri=None,
    )

    conversation_id = repository.save_chat_exchange(
        course_id=deleted_id, question="Explain notes", answer="Saved answer", response_metadata={},
    )
    repository.archive_course(deleted_id)

    assert [course["id"] for course in repository.list_courses()] == [kept_id]
    assert repository.load_course(deleted_id, include_archived_materials=True)["name"] == "Delete me"
    assert repository.get_conversation(conversation_id)["messages"][1]["content"] == "Saved answer"
    assert source_file.exists()
    assert repository.load_course(kept_id)["name"] == "Keep me"


def test_assessment_answers_report_and_mastery_are_persistent(tmp_path: Path) -> None:
    repository = StudyRepository(tmp_path / "conceptflow.db")
    course_id = repository.create_course("Machine Learning")
    draft = AssessmentDraft(
        title="Optimisation quiz",
        questions=[AssessmentQuestion(
            question_type="mcq",
            prompt="Which direction does gradient descent use?",
            topic="Gradient descent",
            difficulty="easy",
            options=["Negative gradient", "Positive gradient", "Random direction", "No direction"],
            correct_answer="Negative gradient",
            explanation="It follows the negative gradient direction.",
            evidence_chunk_ids=["source-1-chunk-1"],
        )],
    )
    assessment_id = repository.save_assessment(course_id, draft, {"difficulty": "easy"})
    question_id = draft.questions[0].question_id
    feedback = [QuestionFeedback(
        question_id=question_id,
        response="Negative gradient",
        correct=True,
        score=1,
        feedback="Correct.",
    )]
    artifact_id = repository.save_assessment_results(
        assessment_id,
        feedback,
        {"percentage": 100.0, "weak_topics": [], "feedback": []},
    )

    restored = StudyRepository(tmp_path / "conceptflow.db")
    assessment = restored.get_assessment(assessment_id)

    assert assessment is not None
    assert assessment["status"] == "completed"
    assert assessment["score"] == 100
    assert restored.topic_masteries(course_id)[0]["mastery"] > 0.2
    assert restored.get_artifact(artifact_id)["kind"] == "assessment_report"
    progress = restored.progress_summary(course_id)
    assert progress["completed_assessments"] == 1
    assert progress["average_score"] == 100
    assert progress["answered_questions"] == 1
