"""SQLite persistence for courses, evidence, conversations and generated work."""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from threading import Lock
from pathlib import Path
from uuid import uuid4
from studybuddy.cancellation import check_cancelled

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, delete, func, inspect, select, text, update
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from studybuddy.course_map import CourseMap
from studybuddy.ingestion.models import KnowledgeChunk
from studybuddy.assessment import AssessmentDraft, AssessmentQuestion, QuestionFeedback, question_fingerprint
from studybuddy.tutor.bkt import update_mastery, update_mastery_from_learning_exposure


_clock_lock = Lock()
_last_timestamp: datetime | None = None

def utc_now() -> datetime:
    """Keep insert order deterministic even on coarse Windows system clocks."""
    global _last_timestamp
    with _clock_lock:
        moment = datetime.now(timezone.utc)
        if _last_timestamp is not None and moment <= _last_timestamp:
            moment = _last_timestamp + timedelta(microseconds=1)
        _last_timestamp = moment
        return moment


def iso_utc(value: datetime | None) -> str | None:
    """Serialize SQLite datetimes as explicit UTC so browsers display local time."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class Base(DeclarativeBase):
    pass


class CourseRecord(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
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
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ArchivedCourseRecord(Base):
    __tablename__ = "archived_courses"

    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True)
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ArchivedMaterialRecord(Base):
    __tablename__ = "archived_materials"

    source_id: Mapped[str] = mapped_column(ForeignKey("materials.id", ondelete="CASCADE"), primary_key=True)
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


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
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
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
    conversation_updates: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class MasteryEventRecord(Base):
    """Auditable learner-model movement produced by one learning signal."""

    __tablename__ = "mastery_events"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    topic: Mapped[str] = mapped_column(String(160), index=True)
    signal: Mapped[str] = mapped_column(String(30))
    mastery_before: Mapped[float] = mapped_column(Float)
    mastery_after: Mapped[float] = mapped_column(Float)
    correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class StudyEventRecord(Base):
    """A learner-created calendar plan with an optional persistent reminder."""

    __tablename__ = "study_events"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    notes: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(30), default="study")
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
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
        if "notes" not in {column["name"] for column in inspect(self.engine).get_columns("materials")}:
            with self.engine.begin() as connection:
                connection.execute(text("ALTER TABLE materials ADD COLUMN notes TEXT NOT NULL DEFAULT ''"))
        columns = {column["name"] for column in inspect(self.engine).get_columns("topic_mastery")}
        if "conversation_updates" not in columns:
            with self.engine.begin() as connection:
                connection.execute(text("ALTER TABLE topic_mastery ADD COLUMN conversation_updates INTEGER NOT NULL DEFAULT 0"))
        for table_name in ("courses", "conversations"):
            table_columns = {column["name"] for column in inspect(self.engine).get_columns(table_name)}
            if "pinned" not in table_columns:
                with self.engine.begin() as connection:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN pinned BOOLEAN NOT NULL DEFAULT 0"))

    def create_course(self, name: str) -> str:
        course_id = uuid4().hex
        with Session(self.engine) as session:
            session.add(CourseRecord(id=course_id, name=name.strip()))
            check_cancelled()
            session.commit()
        return course_id

    def latest_course_id(self) -> str | None:
        with Session(self.engine) as session:
            return session.scalar(
                select(CourseRecord.id)
                .outerjoin(ArchivedCourseRecord, ArchivedCourseRecord.course_id == CourseRecord.id)
                .where(ArchivedCourseRecord.course_id.is_(None))
                .order_by(CourseRecord.updated_at.desc()).limit(1)
            )

    def list_courses(self, *, include_archived: bool = False) -> list[dict[str, object]]:
        with Session(self.engine) as session:
            query = select(CourseRecord, ArchivedCourseRecord.course_id).outerjoin(
                ArchivedCourseRecord, ArchivedCourseRecord.course_id == CourseRecord.id,
            ).order_by(CourseRecord.pinned.desc(), CourseRecord.updated_at.desc())
            if not include_archived:
                query = query.where(ArchivedCourseRecord.course_id.is_(None))
            rows = session.execute(query).all()
            results = []
            for course, archived_course_id in rows:
                active_source_ids = session.scalars(
                    select(MaterialRecord.id)
                    .outerjoin(ArchivedMaterialRecord, ArchivedMaterialRecord.source_id == MaterialRecord.id)
                    .where(MaterialRecord.course_id == course.id, ArchivedMaterialRecord.source_id.is_(None))
                ).all()
                chunk_count = session.scalar(
                    select(func.count(ChunkRecord.id)).where(ChunkRecord.source_id.in_(active_source_ids))
                ) if active_source_ids else 0
                results.append({
                    "id": course.id,
                    "name": course.name,
                    "pinned": course.pinned,
                    "source_count": len(active_source_ids),
                    "chunk_count": chunk_count or 0,
                    "updated_at": course.updated_at.isoformat(),
                    "archived": archived_course_id is not None,
                })
            return results

    def load_course(self, course_id: str, *, include_archived_materials: bool = False) -> dict[str, object] | None:
        with Session(self.engine) as session:
            course = session.get(CourseRecord, course_id)
            if course is None:
                return None
            material_query = select(MaterialRecord).where(MaterialRecord.course_id == course_id)
            chunk_query = select(ChunkRecord).where(ChunkRecord.course_id == course_id)
            if not include_archived_materials:
                material_query = material_query.outerjoin(
                    ArchivedMaterialRecord, ArchivedMaterialRecord.source_id == MaterialRecord.id,
                ).where(ArchivedMaterialRecord.source_id.is_(None))
                chunk_query = chunk_query.outerjoin(
                    ArchivedMaterialRecord, ArchivedMaterialRecord.source_id == ChunkRecord.source_id,
                ).where(ArchivedMaterialRecord.source_id.is_(None))
            materials = session.scalars(material_query.order_by(MaterialRecord.created_at)).all()
            chunk_rows = session.scalars(chunk_query.order_by(ChunkRecord.position)).all()
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
                        "notes": material.notes,
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

    def save_material_notes(self, course_id: str, source_id: str, notes: str) -> None:
        with Session(self.engine) as session:
            material = session.get(MaterialRecord, source_id)
            if material is None or material.course_id != course_id:
                raise ValueError("Study material not found in this workspace.")
            material.notes = notes
            check_cancelled()
            session.commit()

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
            check_cancelled()
            session.commit()

    def archive_material(self, course_id: str, source_id: str) -> Path | None:
        """Hide one material from active study while preserving its file and all history."""
        with Session(self.engine) as session:
            material = session.get(MaterialRecord, source_id)
            if material is None or material.course_id != course_id:
                raise ValueError("Study material not found in the active workspace.")
            stored_path = Path(material.stored_path) if material.stored_path else None
            if session.get(ArchivedMaterialRecord, source_id) is None:
                session.add(ArchivedMaterialRecord(source_id=source_id))
            course = session.get(CourseRecord, course_id)
            if course:
                course.course_map_json = None
                course.updated_at = utc_now()
            check_cancelled()
            session.commit()
        return stored_path

    def archive_course(self, course_id: str) -> None:
        """Hide a workspace from the active library while retaining every related record."""
        with Session(self.engine) as session:
            course = session.get(CourseRecord, course_id)
            if course is None:
                raise ValueError("Course workspace not found.")
            if session.get(ArchivedCourseRecord, course_id) is None:
                session.add(ArchivedCourseRecord(course_id=course_id))
            check_cancelled()
            session.commit()

    def rename_course(self, course_id: str, name: str) -> None:
        with Session(self.engine) as session:
            course = session.get(CourseRecord, course_id)
            if course is None:
                raise ValueError("Course workspace not found.")
            course.name = name.strip()
            course.updated_at = utc_now()
            check_cancelled()
            session.commit()

    def set_course_pinned(self, course_id: str, pinned: bool) -> None:
        with Session(self.engine) as session:
            course = session.get(CourseRecord, course_id)
            if course is None:
                raise ValueError("Course workspace not found.")
            course.pinned = pinned
            check_cancelled()
            session.commit()

    def material_file(self, source_id: str) -> Path | None:
        with Session(self.engine) as session:
            material = session.get(MaterialRecord, source_id)
            return Path(material.stored_path) if material and material.stored_path else None

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
            check_cancelled()
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
            check_cancelled()
            session.commit()
        return conversation_id

    def record_conversation_learning(self, course_id: str, topics: list[str]) -> None:
        """Update learner state with a conservative, non-assessment learning signal."""
        cleaned_topics = list(dict.fromkeys(topic.strip() for topic in topics if topic.strip()))
        if not cleaned_topics:
            return
        with Session(self.engine) as session:
            for topic in cleaned_topics:
                mastery = session.get(TopicMasteryRecord, (course_id, topic))
                if mastery is None:
                    mastery = TopicMasteryRecord(
                        course_id=course_id, topic=topic, mastery=0.2,
                        attempts=0, conversation_updates=0,
                    )
                    session.add(mastery)
                before = mastery.mastery
                mastery.mastery = update_mastery_from_learning_exposure(before)
                mastery.conversation_updates += 1
                mastery.updated_at = utc_now()
                session.add(MasteryEventRecord(
                    id=uuid4().hex, course_id=course_id, topic=topic,
                    signal="grounded_conversation", mastery_before=before,
                    mastery_after=mastery.mastery, correct=None,
                ))
            check_cancelled()
            session.commit()

    def list_conversations(self, course_id: str | None = None) -> list[dict[str, object]]:
        with Session(self.engine) as session:
            query = select(ConversationRecord, CourseRecord.name).join(CourseRecord)
            if course_id:
                query = query.where(ConversationRecord.course_id == course_id)
            rows = session.execute(query.order_by(ConversationRecord.pinned.desc(), ConversationRecord.updated_at.desc())).all()
            return [
                {
                    "id": conversation.id,
                    "course_id": conversation.course_id,
                    "course_name": course_name,
                    "title": conversation.title,
                    "pinned": conversation.pinned,
                    "updated_at": iso_utc(conversation.updated_at),
                }
                for conversation, course_name in rows
            ]

    def rename_conversation(self, conversation_id: str, title: str) -> None:
        with Session(self.engine) as session:
            conversation = session.get(ConversationRecord, conversation_id)
            if conversation is None:
                raise ValueError("Conversation not found.")
            # Preserve last-message activity; renaming should not reorder chats.
            session.execute(update(ConversationRecord).where(
                ConversationRecord.id == conversation_id,
            ).values(title=title.strip(), updated_at=conversation.updated_at))
            check_cancelled()
            session.commit()

    def set_conversation_pinned(self, conversation_id: str, pinned: bool) -> None:
        with Session(self.engine) as session:
            conversation = session.get(ConversationRecord, conversation_id)
            if conversation is None:
                raise ValueError("Conversation not found.")
            conversation.pinned = pinned
            check_cancelled()
            session.commit()

    def delete_conversation(self, conversation_id: str) -> None:
        with Session(self.engine) as session:
            conversation = session.get(ConversationRecord, conversation_id)
            if conversation is None:
                raise ValueError("Conversation not found.")
            session.execute(delete(MessageRecord).where(MessageRecord.conversation_id == conversation_id))
            session.delete(conversation)
            check_cancelled()
            session.commit()

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
                        "created_at": iso_utc(message.created_at),
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
            results = []
            for artifact, course_name in rows:
                content = json.loads(artifact.content_json)
                results.append({
                    "id": artifact.id,
                    "course_id": artifact.course_id,
                    "course_name": course_name,
                    "kind": artifact.kind,
                    "title": artifact.title,
                    "created_at": artifact.created_at.isoformat(),
                    "concept_count": len(content.get("concepts", [])) if artifact.kind == "study_guide" else None,
                })
            return results

    def get_artifact(self, artifact_id: str) -> dict[str, object] | None:
        with Session(self.engine) as session:
            artifact = session.get(ArtifactRecord, artifact_id)
            if artifact is None:
                return None
            return {
                "id": artifact.id,
                "course_id": artifact.course_id,
                "created_at": artifact.created_at.isoformat(),
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
            check_cancelled()
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
                "completed_at": assessment.completed_at.isoformat() if assessment.completed_at else None,
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
                    "completed_at": assessment.completed_at.isoformat() if assessment.completed_at else None,
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
                before = mastery.mastery
                mastery.mastery = update_mastery(before, item.correct)
                mastery.attempts += 1
                mastery.updated_at = utc_now()
                session.add(MasteryEventRecord(
                    id=uuid4().hex, course_id=assessment.course_id, topic=question.topic,
                    signal="quiz_answer", mastery_before=before,
                    mastery_after=mastery.mastery, correct=item.correct,
                ))
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
            check_cancelled()
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
                {"topic": row.topic, "mastery": row.mastery, "attempts": row.attempts,
                 "conversation_updates": row.conversation_updates}
                for row in rows
            ]

    @staticmethod
    def _study_event_view(row: StudyEventRecord, course_name: str | None = None) -> dict[str, object]:
        view: dict[str, object] = {
            "id": row.id,
            "course_id": row.course_id,
            "title": row.title,
            "notes": row.notes,
            "kind": row.kind,
            "scheduled_for": row.scheduled_for.isoformat(),
            "reminder_at": row.reminder_at.isoformat() if row.reminder_at else None,
            "completed": row.completed,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
        }
        if course_name is not None:
            view["course_name"] = course_name
        return view

    def create_study_event(
        self, course_id: str, *, title: str, scheduled_for: datetime,
        notes: str = "", kind: str = "study", reminder_at: datetime | None = None,
    ) -> dict[str, object]:
        event_id = uuid4().hex
        with Session(self.engine) as session:
            course = session.get(CourseRecord, course_id)
            if course is None:
                raise ValueError("Course not found.")
            row = StudyEventRecord(
                id=event_id, course_id=course_id, title=title.strip(), notes=notes.strip(),
                kind=kind, scheduled_for=scheduled_for, reminder_at=reminder_at,
            )
            session.add(row)
            check_cancelled()
            session.commit()
            session.refresh(row)
            return self._study_event_view(row, course.name)

    def list_study_events(self, course_id: str | None = None) -> list[dict[str, object]]:
        with Session(self.engine) as session:
            query = select(StudyEventRecord, CourseRecord.name).join(
                CourseRecord, StudyEventRecord.course_id == CourseRecord.id,
            )
            if course_id is not None:
                query = query.where(StudyEventRecord.course_id == course_id)
            rows = session.execute(query.order_by(StudyEventRecord.scheduled_for, StudyEventRecord.id)).all()
            return [self._study_event_view(row, course_name) for row, course_name in rows]

    def update_study_event(self, event_id: str, **changes: object) -> dict[str, object]:
        allowed = {"title", "notes", "kind", "scheduled_for", "reminder_at", "completed"}
        with Session(self.engine) as session:
            row = session.get(StudyEventRecord, event_id)
            if row is None:
                raise ValueError("Study event not found.")
            for key, value in changes.items():
                if key in allowed:
                    if key in {"title", "notes"} and isinstance(value, str):
                        value = value.strip()
                    setattr(row, key, value)
            row.updated_at = utc_now()
            course_name = session.scalar(select(CourseRecord.name).where(CourseRecord.id == row.course_id))
            check_cancelled()
            session.commit()
            session.refresh(row)
            return self._study_event_view(row, course_name)

    def delete_study_event(self, event_id: str) -> None:
        with Session(self.engine) as session:
            row = session.get(StudyEventRecord, event_id)
            if row is None:
                raise ValueError("Study event not found.")
            session.delete(row)
            check_cancelled()
            session.commit()

    def due_reminders(self, now: datetime | None = None) -> list[dict[str, object]]:
        moment = now or utc_now()
        with Session(self.engine) as session:
            rows = session.execute(
                select(StudyEventRecord, CourseRecord.name)
                .join(CourseRecord, StudyEventRecord.course_id == CourseRecord.id)
                .where(
                    StudyEventRecord.completed.is_(False),
                    StudyEventRecord.reminder_at.is_not(None),
                    StudyEventRecord.reminder_at <= moment,
                )
                .order_by(StudyEventRecord.reminder_at, StudyEventRecord.id)
            ).all()
            return [self._study_event_view(row, course_name) for row, course_name in rows]

    def progress_summary(self, course_id: str) -> dict[str, object]:
        assessments = self.list_assessments(course_id)
        completed = [item for item in assessments if item["status"] == "completed"]
        scores = [float(item["score"]) for item in completed if item["score"] is not None]
        masteries = self.topic_masteries(course_id)
        score_history = [
            {
                "id": item["id"], "title": item["title"], "score": float(item["score"]),
                "date": item["completed_at"] or item["created_at"],
            }
            for item in reversed(completed) if item["score"] is not None
        ]
        daily: dict[str, dict[str, object]] = {}
        assessment_insights: list[dict[str, object]] = []
        topic_totals: dict[str, dict[str, float | int]] = {}
        correct_questions = 0
        total_questions = 0

        def mark(moment: datetime, kind: str, activity: dict[str, object] | None = None) -> None:
            day = moment.date().isoformat()
            entry = daily.setdefault(day, {
                "date": day, "assessments": 0, "chats": 0, "materials": 0,
                "total": 0, "activities": [], "assessment_scores": [], "mastery_gain": 0.0,
            })
            entry[kind] = int(entry[kind]) + 1
            entry["total"] = int(entry["total"]) + 1
            if activity:
                entry["activities"].append(activity)

        with Session(self.engine) as session:
            finished = session.scalars(
                select(AssessmentRecord)
                .where(AssessmentRecord.course_id == course_id, AssessmentRecord.completed_at.is_not(None))
            ).all()
            chat_events = session.execute(
                select(MessageRecord, ConversationRecord.title)
                .join(ConversationRecord, MessageRecord.conversation_id == ConversationRecord.id)
                .where(ConversationRecord.course_id == course_id, MessageRecord.role == "user")
            ).all()
            material_events = session.scalars(
                select(MaterialRecord).where(MaterialRecord.course_id == course_id)
            ).all()
            mastery_events = session.scalars(
                select(MasteryEventRecord)
                .where(MasteryEventRecord.course_id == course_id)
                .order_by(MasteryEventRecord.created_at, MasteryEventRecord.id)
            ).all()
            report_rows = session.scalars(
                select(AssessmentRecord)
                .where(
                    AssessmentRecord.course_id == course_id,
                    AssessmentRecord.status == "completed",
                    AssessmentRecord.report_json.is_not(None),
                )
                .order_by(AssessmentRecord.completed_at, AssessmentRecord.created_at)
            ).all()
        for row in report_rows:
            report = json.loads(row.report_json or "{}")
            report_correct = int(report.get("correct_questions", 0))
            report_total = int(report.get("total_questions", 0))
            correct_questions += report_correct
            total_questions += report_total
            summaries = report.get("topic_summary", [])
            for item in summaries:
                topic = str(item.get("topic", "Untitled topic"))
                questions = int(item.get("questions", 0))
                correct = float(item.get("accuracy", 0)) / 100 * questions
                aggregate = topic_totals.setdefault(topic, {"correct": 0.0, "questions": 0})
                aggregate["correct"] = float(aggregate["correct"]) + correct
                aggregate["questions"] = int(aggregate["questions"]) + questions
            assessment_insights.append({
                "id": row.id,
                "title": row.title,
                "score": float(row.score or report.get("percentage", 0)),
                "correct_questions": report_correct,
                "total_questions": report_total,
                "weak_topics": list(report.get("weak_topics", [])),
                "misconceptions": list(report.get("misconceptions", [])),
                "topic_summary": summaries,
                "date": (row.completed_at or row.created_at).isoformat(),
            })
        for row in finished:
            moment = row.completed_at or row.created_at
            mark(moment, "assessments", {
                "type": "assessment", "id": row.id, "title": row.title,
                "time": moment.isoformat(), "score": row.score,
            })
            entry = daily[moment.date().isoformat()]
            if row.score is not None:
                entry["assessment_scores"].append(float(row.score))
        for message, conversation_title in chat_events:
            mark(message.created_at, "chats", {
                "type": "chat", "id": message.conversation_id,
                "title": conversation_title, "time": message.created_at.isoformat(),
                "preview": message.content[:120],
            })
        for row in material_events:
            mark(row.created_at, "materials", {
                "type": "material", "id": row.id, "title": row.name,
                "time": row.created_at.isoformat(),
            })
        for event in mastery_events:
            day = event.created_at.date().isoformat()
            entry = daily.setdefault(day, {
                "date": day, "assessments": 0, "chats": 0, "materials": 0,
                "total": 0, "activities": [], "assessment_scores": [], "mastery_gain": 0.0,
            })
            entry["mastery_gain"] = round(
                float(entry["mastery_gain"]) + (event.mastery_after - event.mastery_before) * 100, 2,
            )

        for entry in daily.values():
            scores_for_day = list(entry.pop("assessment_scores"))
            entry["assessment_score"] = (
                round(sum(scores_for_day) / len(scores_for_day), 1) if scores_for_day else None
            )
            entry["activities"].sort(key=lambda item: str(item["time"]))

        topic_performance = [
            {
                "topic": topic,
                "correct": round(float(values["correct"]), 1),
                "questions": int(values["questions"]),
                "accuracy": round(float(values["correct"]) / int(values["questions"]) * 100, 1)
                if int(values["questions"]) else 0.0,
            }
            for topic, values in topic_totals.items()
        ]
        topic_performance.sort(key=lambda item: (float(item["accuracy"]), str(item["topic"])))
        mastery_by_topic = {str(item["topic"]): item for item in masteries}
        weak_topics = {
            str(item["topic"]) for item in masteries if float(item["mastery"]) < 0.7
        }
        for insight in assessment_insights:
            weak_topics.update(str(topic) for topic in insight["weak_topics"])
        weak = [mastery_by_topic[topic] for topic in weak_topics if topic in mastery_by_topic]
        weak.sort(key=lambda item: float(item["mastery"]))
        revision_plan = [
            {
                "topic": item["topic"], "mastery": item["mastery"],
                "action": "Review the cited explanation, make five flashcards, then take a focused 5-question quiz.",
                "priority": "urgent" if float(item["mastery"]) < 0.45 else "review",
            }
            for item in weak[:5]
        ]
        first_by_topic: dict[str, float] = {}
        latest_by_topic: dict[str, float] = {}
        mastery_history = []
        for event in mastery_events:
            first_by_topic.setdefault(event.topic, event.mastery_before)
            latest_by_topic[event.topic] = event.mastery_after
            mastery_history.append({
                "id": event.id, "topic": event.topic, "signal": event.signal,
                "before": event.mastery_before, "after": event.mastery_after,
                "correct": event.correct, "date": event.created_at.isoformat(),
            })
        mastery_gain = None
        if latest_by_topic:
            mastery_gain = round(sum(
                latest_by_topic[topic] - first_by_topic[topic] for topic in latest_by_topic
            ) / len(latest_by_topic) * 100, 1)
        return {
            "completed_assessments": len(completed),
            "average_score": round(sum(scores) / len(scores), 1) if scores else None,
            "answered_questions": sum(int(item["attempts"]) for item in masteries),
            "correct_questions": correct_questions,
            "total_questions": total_questions,
            "tutoring_interactions": sum(int(item["conversation_updates"]) for item in masteries),
            "mastery": masteries,
            "mastery_history": mastery_history,
            "mastery_gain": mastery_gain,
            "recent_assessments": completed[:8],
            "score_history": score_history,
            "topic_performance": topic_performance,
            "assessment_insights": list(reversed(assessment_insights)),
            "daily_activity": sorted(daily.values(), key=lambda item: str(item["date"])),
            "study_events": self.list_study_events(course_id),
            "weak_topics": [item["topic"] for item in weak],
            "revision_plan": revision_plan,
            "score_change": round(score_history[-1]["score"] - score_history[0]["score"], 1) if len(score_history) > 1 else None,
        }
