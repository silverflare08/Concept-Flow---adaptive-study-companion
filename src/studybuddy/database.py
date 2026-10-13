"""SQLite persistence for courses, evidence, conversations and generated work."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, delete, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from studybuddy.course_map import CourseMap
from studybuddy.ingestion.models import KnowledgeChunk
from studybuddy.assessment import AssessmentDraft, AssessmentQuestion, QuestionFeedback, question_fingerprint
from studybuddy.tutor.bkt import update_mastery


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class CourseRecord(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    course_map_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class MaterialRecord(Base):
    __tablename__ = "materials"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(30), default="indexed")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    stored_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ChunkRecord(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("materials.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    payload_json: Mapped[str] = mapped_column(Text)


class ConversationRecord(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class MessageRecord(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ArtifactRecord(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(160))
    content_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AssessmentRecord(Base):
    __tablename__ = "assessments"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    config_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="ready")
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    report_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AssessmentQuestionRecord(Base):
    __tablename__ = "assessment_questions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    payload_json: Mapped[str] = mapped_column(Text)


class StudentAnswerRecord(Base):
    __tablename__ = "student_answers"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("assessment_questions.id", ondelete="CASCADE"), index=True)
    response: Mapped[str] = mapped_column(Text)
    correct: Mapped[bool] = mapped_column(Boolean)
    score: Mapped[float] = mapped_column(Float)
    feedback_json: Mapped[str] = mapped_column(Text)


class TopicMasteryRecord(Base):
    __tablename__ = "topic_mastery"

    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True)
    topic: Mapped[str] = mapped_column(String(160), primary_key=True)
    mastery: Mapped[float] = mapped_column(Float, default=0.2)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class StudyRepository:
    """Small repository boundary so API code never contains raw SQL."""

    def __init__(self, database_path: str | Path = "data/conceptflow.db") -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            f"sqlite:///{self.database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self.engine)

    def create_course(self, name: str) -> str:
        course_id = uuid4().hex
        with Session(self.engine) as session:
            session.add(CourseRecord(id=course_id, name=name.strip()))
            session.commit()
        return course_id

    def latest_course_id(self) -> str | None:
        with Session(self.engine) as session:
            return session.scalar(select(CourseRecord.id).order_by(CourseRecord.updated_at.desc()).limit(1))

    def list_courses(self) -> list[dict[str, object]]:
        with Session(self.engine) as session:
            rows = session.execute(
                select(
                    CourseRecord,
                    func.count(func.distinct(MaterialRecord.id)).label("source_count"),
                    func.count(func.distinct(ChunkRecord.id)).label("chunk_count"),
                )
                .outerjoin(MaterialRecord, MaterialRecord.course_id == CourseRecord.id)
                .outerjoin(ChunkRecord, ChunkRecord.course_id == CourseRecord.id)
                .group_by(CourseRecord.id)
                .order_by(CourseRecord.updated_at.desc())
            ).all()
            return [
                {
                    "id": course.id,
                    "name": course.name,
                    "source_count": source_count,
                    "chunk_count": chunk_count,
                    "updated_at": course.updated_at.isoformat(),
                }
                for course, source_count, chunk_count in rows
            ]

    def load_course(self, course_id: str) -> dict[str, object] | None:
        with Session(self.engine) as session:
            course = session.get(CourseRecord, course_id)
            if course is None:
                return None
            materials = session.scalars(
                select(MaterialRecord).where(MaterialRecord.course_id == course_id).order_by(MaterialRecord.created_at)
            ).all()
            chunk_rows = session.scalars(
                select(ChunkRecord).where(ChunkRecord.course_id == course_id).order_by(ChunkRecord.position)
            ).all()
            return {
                "id": course.id,
                "name": course.name,
                "sources": [
                    {
                        "id": material.id,
                        "name": material.name,
                        "type": material.kind,
                        "status": material.status,
                        "chunks": material.chunk_count,
                        "downloadable": bool(material.stored_path),
                    }
                    for material in materials
                ],
                "source_files": {
                    material.id: Path(material.stored_path)
                    for material in materials
                    if material.stored_path
                },
                "chunks": [KnowledgeChunk.model_validate_json(row.payload_json) for row in chunk_rows],
                "course_map": CourseMap.model_validate_json(course.course_map_json) if course.course_map_json else None,
            }

    def save_material(
        self,
        *,
        course_id: str,
        source_id: str,
        name: str,
        kind: str,
        chunks: list[KnowledgeChunk],
        stored_path: Path | None,
        source_uri: str | None,
    ) -> None:
        with Session(self.engine) as session:
            course = session.get(CourseRecord, course_id)
            if course is None:
                raise ValueError("The active course no longer exists.")
            session.add(MaterialRecord(
                id=source_id,
                course_id=course_id,
                name=name,
                kind=kind,
                status="indexed",
                chunk_count=len(chunks),
                stored_path=str(stored_path) if stored_path else None,
                source_uri=source_uri,
            ))
            session.add_all([
                ChunkRecord(
                    id=chunk.chunk_id,
                    course_id=course_id,
                    source_id=source_id,
                    position=position,
                    payload_json=chunk.model_dump_json(),
                )
                for position, chunk in enumerate(chunks)
            ])
            course.course_map_json = None
            course.updated_at = utc_now()
            session.commit()

    def delete_material(self, course_id: str, source_id: str) -> Path | None:
        """Delete one material and its searchable chunks, returning its registered file path."""
        with Session(self.engine) as session:
            material = session.get(MaterialRecord, source_id)
            if material is None or material.course_id != course_id:
                raise ValueError("Study material not found in the active workspace.")
            stored_path = Path(material.stored_path) if material.stored_path else None
            session.execute(delete(ChunkRecord).where(ChunkRecord.source_id == source_id))
            session.delete(material)
            course = session.get(CourseRecord, course_id)
            if course:
                course.course_map_json = None
                course.updated_at = utc_now()
            session.commit()
        return stored_path

    def save_course_map(self, course_id: str, course_map: CourseMap) -> str:
        artifact_id = uuid4().hex
        with Session(self.engine) as session:
            course = session.get(CourseRecord, course_id)
            if course is None:
                raise ValueError("The active course no longer exists.")
            payload = course_map.model_dump_json()
            course.course_map_json = payload
            course.updated_at = utc_now()
            session.add(ArtifactRecord(
                id=artifact_id,
                course_id=course_id,
                kind="study_guide",
                title=f"{course.name} study guide",
                content_json=payload,
            ))
            session.commit()
        return artifact_id

    def save_chat_exchange(
        self,
        *,
        course_id: str,
        question: str,
        answer: str,
        response_metadata: dict[str, object],
        conversation_id: str | None = None,
    ) -> str:
        with Session(self.engine) as session:
            conversation = session.get(ConversationRecord, conversation_id) if conversation_id else None
            if conversation is None or conversation.course_id != course_id:
                conversation_id = uuid4().hex
                conversation = ConversationRecord(
                    id=conversation_id,
                    course_id=course_id,
                    title=question.strip()[:80] or "Study conversation",
                )
                session.add(conversation)
            session.add_all([
                MessageRecord(id=uuid4().hex, conversation_id=conversation_id, role="user", content=question),
                MessageRecord(
                    id=uuid4().hex,
                    conversation_id=conversation_id,
                    role="assistant",
                    content=answer,
                    metadata_json=json.dumps(response_metadata),
                ),
            ])
            conversation.updated_at = utc_now()
            course = session.get(CourseRecord, course_id)
            if course:
                course.updated_at = utc_now()
            session.commit()
        return conversation_id

    def list_conversations(self, course_id: str | None = None) -> list[dict[str, object]]:
        with Session(self.engine) as session:
            query = select(ConversationRecord, CourseRecord.name).join(CourseRecord)
            if course_id:
                query = query.where(ConversationRecord.course_id == course_id)
            rows = session.execute(query.order_by(ConversationRecord.updated_at.desc())).all()
            return [
                {
                    "id": conversation.id,
                    "course_id": conversation.course_id,
                    "course_name": course_name,
                    "title": conversation.title,
                    "updated_at": conversation.updated_at.isoformat(),
                }
                for conversation, course_name in rows
            ]

    def get_conversation(self, conversation_id: str) -> dict[str, object] | None:
        with Session(self.engine) as session:
            conversation = session.get(ConversationRecord, conversation_id)
            if conversation is None:
                return None
            messages = session.scalars(
                select(MessageRecord)
                .where(MessageRecord.conversation_id == conversation_id)
                .order_by(MessageRecord.created_at, MessageRecord.id)
            ).all()
            return {
                "id": conversation.id,
                "course_id": conversation.course_id,
                "title": conversation.title,
                "messages": [
                    {
                        "id": message.id,
                        "role": message.role,
                        "content": message.content,
                        "metadata": json.loads(message.metadata_json or "{}"),
                        "created_at": message.created_at.isoformat(),
                    }
                    for message in messages
                ],
            }

    def list_artifacts(self, course_id: str | None = None) -> list[dict[str, object]]:
        with Session(self.engine) as session:
            query = select(ArtifactRecord, CourseRecord.name).join(CourseRecord)
            if course_id:
                query = query.where(ArtifactRecord.course_id == course_id)
            rows = session.execute(query.order_by(ArtifactRecord.created_at.desc())).all()
            return [
                {
                    "id": artifact.id,
                    "course_id": artifact.course_id,
                    "course_name": course_name,
                    "kind": artifact.kind,
                    "title": artifact.title,
                    "created_at": artifact.created_at.isoformat(),
                }
                for artifact, course_name in rows
            ]

    def get_artifact(self, artifact_id: str) -> dict[str, object] | None:
        with Session(self.engine) as session:
            artifact = session.get(ArtifactRecord, artifact_id)
            if artifact is None:
                return None
            return {
                "id": artifact.id,
                "title": artifact.title,
                "kind": artifact.kind,
                "content": json.loads(artifact.content_json),
            }

    def previous_question_prompts(self, course_id: str) -> list[str]:
        with Session(self.engine) as session:
            rows = session.scalars(
                select(AssessmentQuestionRecord.payload_json)
                .join(AssessmentRecord)
                .where(AssessmentRecord.course_id == course_id)
            ).all()
            return [AssessmentQuestion.model_validate_json(payload).prompt for payload in rows]

    def save_assessment(self, course_id: str, draft: AssessmentDraft, config: dict[str, object]) -> str:
        assessment_id = uuid4().hex
        with Session(self.engine) as session:
            session.add(AssessmentRecord(
                id=assessment_id,
                course_id=course_id,
                title=draft.title,
                config_json=json.dumps(config),
            ))
            session.add_all([
                AssessmentQuestionRecord(
                    id=question.question_id,
                    assessment_id=assessment_id,
                    position=position,
                    fingerprint=question_fingerprint(question.prompt),
                    payload_json=question.model_dump_json(),
                )
                for position, question in enumerate(draft.questions)
            ])
            course = session.get(CourseRecord, course_id)
            if course:
                course.updated_at = utc_now()
            session.commit()
        return assessment_id

    def get_assessment(self, assessment_id: str) -> dict[str, object] | None:
        with Session(self.engine) as session:
            assessment = session.get(AssessmentRecord, assessment_id)
            if assessment is None:
                return None
            questions = session.scalars(
                select(AssessmentQuestionRecord)
                .where(AssessmentQuestionRecord.assessment_id == assessment_id)
                .order_by(AssessmentQuestionRecord.position)
            ).all()
            answers = session.scalars(
                select(StudentAnswerRecord).where(StudentAnswerRecord.assessment_id == assessment_id)
            ).all()
            return {
                "id": assessment.id,
                "course_id": assessment.course_id,
                "title": assessment.title,
                "config": json.loads(assessment.config_json),
                "status": assessment.status,
                "score": assessment.score,
                "report": json.loads(assessment.report_json) if assessment.report_json else None,
                "questions": [AssessmentQuestion.model_validate_json(row.payload_json) for row in questions],
                "answers": [json.loads(row.feedback_json) for row in answers],
                "created_at": assessment.created_at.isoformat(),
            }

    def list_assessments(self, course_id: str | None = None) -> list[dict[str, object]]:
        with Session(self.engine) as session:
            query = select(AssessmentRecord, CourseRecord.name).join(CourseRecord)
            if course_id:
                query = query.where(AssessmentRecord.course_id == course_id)
            rows = session.execute(query.order_by(AssessmentRecord.created_at.desc())).all()
            return [
                {
                    "id": assessment.id,
                    "course_id": assessment.course_id,
                    "course_name": course_name,
                    "title": assessment.title,
                    "status": assessment.status,
                    "score": assessment.score,
                    "created_at": assessment.created_at.isoformat(),
                }
                for assessment, course_name in rows
            ]

    def save_assessment_results(
        self, assessment_id: str, feedback: list[QuestionFeedback], report: dict[str, object],
    ) -> str:
        artifact_id = uuid4().hex
        with Session(self.engine) as session:
            assessment = session.get(AssessmentRecord, assessment_id)
            if assessment is None:
                raise ValueError("Assessment not found.")
            questions = {
                row.id: AssessmentQuestion.model_validate_json(row.payload_json)
                for row in session.scalars(
                    select(AssessmentQuestionRecord).where(AssessmentQuestionRecord.assessment_id == assessment_id)
                ).all()
            }
            session.add_all([
                StudentAnswerRecord(
                    id=uuid4().hex,
                    assessment_id=assessment_id,
                    question_id=item.question_id,
                    response=item.response,
                    correct=item.correct,
                    score=item.score,
                    feedback_json=item.model_dump_json(),
                )
                for item in feedback
            ])
            for item in feedback:
                question = questions[item.question_id]
                mastery = session.get(TopicMasteryRecord, (assessment.course_id, question.topic))
                if mastery is None:
                    mastery = TopicMasteryRecord(
                        course_id=assessment.course_id, topic=question.topic, mastery=0.2, attempts=0,
                    )
                    session.add(mastery)
                mastery.mastery = update_mastery(mastery.mastery, item.correct)
                mastery.attempts += 1
                mastery.updated_at = utc_now()
            assessment.status = "completed"
            assessment.score = float(report["percentage"])
            assessment.report_json = json.dumps(report)
            assessment.completed_at = utc_now()
            session.add(ArtifactRecord(
                id=artifact_id,
                course_id=assessment.course_id,
                kind="assessment_report",
                title=f"{assessment.title} report",
                content_json=json.dumps(report),
            ))
            session.commit()
        return artifact_id

    def topic_masteries(self, course_id: str) -> list[dict[str, object]]:
        with Session(self.engine) as session:
            rows = session.scalars(
                select(TopicMasteryRecord)
                .where(TopicMasteryRecord.course_id == course_id)
                .order_by(TopicMasteryRecord.mastery)
            ).all()
            return [
                {"topic": row.topic, "mastery": row.mastery, "attempts": row.attempts}
                for row in rows
            ]

    def progress_summary(self, course_id: str) -> dict[str, object]:
        assessments = self.list_assessments(course_id)
        completed = [item for item in assessments if item["status"] == "completed"]
        scores = [float(item["score"]) for item in completed if item["score"] is not None]
        masteries = self.topic_masteries(course_id)
        return {
            "completed_assessments": len(completed),
            "average_score": round(sum(scores) / len(scores), 1) if scores else None,
            "answered_questions": sum(int(item["attempts"]) for item in masteries),
            "mastery": masteries,
            "recent_assessments": completed[:8],
        }
