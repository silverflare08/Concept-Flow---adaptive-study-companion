from pathlib import Path
from datetime import datetime, timedelta, timezone

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

    restarted_repository.save_material_notes(course_id, "source-1", "Revise this before Friday.\nCheck the formula.")
    reloaded = StudyRepository(database_path).load_course(course_id)
    assert reloaded["sources"][0]["notes"] == "Revise this before Friday.\nCheck the formula."
    import pytest
    with pytest.raises(ValueError, match="not found"):
        restarted_repository.save_material_notes("different-course", "source-1", "Wrong workspace")

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
        {
            "percentage": 100.0, "correct_questions": 1, "total_questions": 1,
            "topic_summary": [{"topic": "Gradient descent", "accuracy": 100.0, "questions": 1}],
            "weak_topics": [], "misconceptions": [], "feedback": [],
        },
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
    assert progress["correct_questions"] == 1
    assert progress["total_questions"] == 1
    assert progress["topic_performance"][0]["accuracy"] == 100
    assert progress["score_history"][0]["score"] == 100
    assert progress["mastery_history"][0]["signal"] == "quiz_answer"
    assert progress["mastery_gain"] > 0
    assert progress["daily_activity"][0]["assessments"] == 1
    assert progress["revision_plan"][0]["topic"] == "Gradient descent"


def test_grounded_conversations_create_conservative_mastery_updates(tmp_path: Path) -> None:
    repository = StudyRepository(tmp_path / "conceptflow.db")
    course_id = repository.create_course("Machine Learning")

    repository.record_conversation_learning(course_id, ["Gradient descent"])
    first = repository.topic_masteries(course_id)[0]
    repository.record_conversation_learning(course_id, ["Gradient descent"])
    second = repository.topic_masteries(course_id)[0]

    assert first["mastery"] > 0.2
    assert second["mastery"] > first["mastery"]
    assert second["attempts"] == 0
    assert second["conversation_updates"] == 2
    progress = repository.progress_summary(course_id)
    assert progress["tutoring_interactions"] == 2
    assert [event["signal"] for event in progress["mastery_history"]] == [
        "grounded_conversation", "grounded_conversation",
    ]
    assert progress["mastery_gain"] > 0


def test_courses_and_chats_can_be_renamed_pinned_and_managed(tmp_path: Path) -> None:
    repository = StudyRepository(tmp_path / "conceptflow.db")
    course_id = repository.create_course("Old course")
    chat_id = repository.save_chat_exchange(
        course_id=course_id, question="Original chat", answer="Saved answer", response_metadata={},
    )

    repository.rename_course(course_id, "Linear Algebra")
    repository.set_course_pinned(course_id, True)
    repository.rename_conversation(chat_id, "Eigenvector revision")
    repository.set_conversation_pinned(chat_id, True)

    assert repository.list_courses()[0]["name"] == "Linear Algebra"
    assert repository.list_courses()[0]["pinned"] is True
    assert repository.list_conversations()[0]["title"] == "Eigenvector revision"
    assert repository.list_conversations()[0]["pinned"] is True

    repository.delete_conversation(chat_id)
    assert repository.get_conversation(chat_id) is None


def test_renaming_an_older_chat_preserves_activity_timestamp_and_order(tmp_path: Path) -> None:
    repository = StudyRepository(tmp_path / "ordering.db")
    course = repository.create_course("Notes")
    older = repository.save_chat_exchange(course_id=course, question="Older", answer="Answer", response_metadata={})
    repository.save_chat_exchange(course_id=course, question="Newer", answer="Answer", response_metadata={})
    before = repository.list_conversations(course)
    repository.rename_conversation(older, "Renamed older chat")
    after = repository.list_conversations(course)
    assert [row["id"] for row in after] == [row["id"] for row in before]
    assert [row["updated_at"] for row in after] == [row["updated_at"] for row in before]
    assert next(row for row in after if row["id"] == older)["title"] == "Renamed older chat"


def test_study_plans_reminders_and_daily_activity_are_persistent(tmp_path: Path) -> None:
    repository = StudyRepository(tmp_path / "conceptflow.db")
    course_id = repository.create_course("Calculus")
    scheduled = datetime.now(timezone.utc) + timedelta(hours=2)
    reminder = datetime.now(timezone.utc) - timedelta(minutes=5)

    event = repository.create_study_event(
        course_id, title="Revise limits", notes="Use chapter two", kind="revision",
        scheduled_for=scheduled, reminder_at=reminder,
    )
    assert repository.list_study_events(course_id)[0]["title"] == "Revise limits"
    assert repository.due_reminders()[0]["id"] == event["id"]

    updated = repository.update_study_event(event["id"], title="Revise limits and continuity")
    assert updated["title"] == "Revise limits and continuity"

    repository.update_study_event(event["id"], completed=True)
    assert repository.due_reminders() == []
    assert repository.progress_summary(course_id)["study_events"][0]["completed"] is True

    repository.delete_study_event(event["id"])
    assert repository.list_study_events(course_id) == []
