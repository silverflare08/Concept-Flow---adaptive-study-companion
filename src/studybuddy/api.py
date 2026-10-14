"""Local API that connects the ConceptFlow web app to generic course ingestion.

The API keeps local course workspaces, source metadata, chats, assessments and
learner progress in SQLite while uploaded binaries remain in ignored local storage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import mimetypes
from pathlib import Path
from typing import Literal
from uuid import uuid4
from threading import Event
from studybuddy.cancellation import current_cancel, requests as cancellable_requests, check_cancelled, GenerationStopped

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from studybuddy.course_map import CourseMap
from studybuddy.database import StudyRepository
from studybuddy.exports import export_response
from studybuddy.assessment import (
    AssessmentQuestion,
    generate_assessment,
    grade_objective,
    grade_short_answer,
    humanize_math_text,
)
from studybuddy.ingestion.chunker import chunk_segments
from studybuddy.ingestion.models import EvidenceKind, KnowledgeChunk
from studybuddy.ingestion.router import SUPPORTED_FILE_TYPES, parse_study_file
from studybuddy.ingestion.video import transcribe_video
from studybuddy.ingestion.web import fetch_public_resource, ingest_web_page, is_youtube_url
from studybuddy.ingestion.youtube import download_youtube_audio
from studybuddy.retrieval.bm25 import BM25Index
from studybuddy.tutor.course_map_generator import generate_course_map
from studybuddy.tutor.grounded import call_ollama_json, call_ollama_long, ollama_available, tutor_answer
from studybuddy.tutor.material_overview import generate_material_overview


UPLOAD_ROOT = Path("data/uploads")
@dataclass
class Workspace:
    course_id: str = ""
    name: str = "My study space"
    chunks: list[KnowledgeChunk] = field(default_factory=list)
    sources: list[dict[str, object]] = field(default_factory=list)
    course_map: CourseMap | None = None
    source_files: dict[str, Path] = field(default_factory=dict)
    revision: str = field(default_factory=lambda: uuid4().hex)
    guide_job: dict[str, object] | None = None
    guide_source_ids: list[str] = field(default_factory=list)
    guide_evidence: dict[str, KnowledgeChunk] = field(default_factory=dict)
    overview_job: dict[str, object] | None = None


repository = StudyRepository()


def workspace_from_record(record: dict[str, object]) -> Workspace:
    return Workspace(
        course_id=str(record["id"]),
        name=str(record["name"]),
        chunks=list(record["chunks"]),
        sources=list(record["sources"]),
        course_map=record["course_map"],
        source_files=dict(record["source_files"]),
    )


def load_or_create_workspace() -> Workspace:
    course_id = repository.latest_course_id()
    if course_id is None:
        course_id = repository.create_course("My study space")
    record = repository.load_course(course_id)
    if record is None:
        raise RuntimeError("Could not initialise the local course database.")
    return workspace_from_record(record)


workspace = load_or_create_workspace()
guide_executor = ThreadPoolExecutor(max_workers=1)
overview_executor = ThreadPoolExecutor(max_workers=1)
overview_jobs: dict[str, dict[str, object]] = {}
app = FastAPI(title="ConceptFlow API", version="0.1.0")

@app.middleware("http")
async def cancellation_context(request, call_next):
    request_id = request.headers.get("X-Generation-Id")
    event = Event() if request_id else None
    if request_id:
        cancellable_requests[request_id] = event
    token = current_cancel.set(event)
    try:
        return await call_next(request)
    finally:
        current_cancel.reset(token)
        if request_id:
            cancellable_requests.pop(request_id, None)

@app.post("/api/generation/{request_id}/stop")
def stop_request(request_id: str):
    event = cancellable_requests.get(request_id)
    if event:
        event.set()
    return {"status": "cancelled"}

@app.post("/api/jobs/{job_id}/stop")
def stop_background_job(job_id: str):
    job = overview_jobs.get(job_id)
    if job is None and workspace.guide_job and workspace.guide_job.get("job_id") == job_id:
        job = workspace.guide_job
    if job is None:
        raise HTTPException(status_code=404, detail="Generation not found.")
    if job.get("status") == "running":
        job.update(status="cancelled", error="Stopped by you.")
    return {"job": dict(job)}
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)


class WorkspaceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class LibraryItemUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    pinned: bool | None = None


class SearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    limit: int = Field(default=5, ge=1, le=10)


class TutorRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    conversation_id: str | None = None
    language: Literal["english", "hindi", "hinglish"] = "english"


class UrlMaterialRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)


class MaterialNotesRequest(BaseModel):
    notes: str = Field(max_length=20000)


class GuideRequest(BaseModel):
    source_ids: list[str] = Field(default_factory=list, max_length=100)


class OverviewRequest(BaseModel):
    source_ids: list[str] = Field(default_factory=list, max_length=100)
    language: Literal["english", "hindi", "hinglish"] = "english"


class AssessmentCreateRequest(BaseModel):
    scope: list[str] = Field(default_factory=list, max_length=12)
    question_count: int = Field(default=5, ge=1, le=12)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    question_types: list[Literal["mcq", "short_answer", "numerical", "true_false", "fill_blank"]] = Field(min_length=1)
    language: Literal["english", "hindi", "hinglish"] = "english"


class AssessmentSubmitRequest(BaseModel):
    answers: dict[str, str]


class StudyEventCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    notes: str = Field(default="", max_length=2000)
    kind: Literal["study", "revision", "assessment", "deadline"] = "study"
    scheduled_for: datetime
    reminder_at: datetime | None = None


class StudyEventUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    notes: str | None = Field(default=None, max_length=2000)
    kind: Literal["study", "revision", "assessment", "deadline"] | None = None
    scheduled_for: datetime | None = None
    reminder_at: datetime | None = None
    completed: bool | None = None


DownloadFormat = Literal["md", "txt", "pdf", "docx", "json"]


def add_indexed_material(
    *, source_id: str, name: str, kind: str, segments: list, stored_path: Path | None = None,
) -> dict[str, object]:
    chunks = chunk_segments(segments)
    if not chunks:
        raise ValueError("No readable study content was found in this source.")
    if not workspace.course_id:
        workspace.course_id = repository.create_course(workspace.name)
    source_uri = segments[0].citation.source_uri if segments else None
    repository.save_material(
        course_id=workspace.course_id,
        source_id=source_id,
        name=name,
        kind=kind,
        chunks=chunks,
        stored_path=stored_path,
        source_uri=source_uri,
    )
    workspace.chunks.extend(chunks)
    workspace.course_map = None
    if stored_path is not None:
        workspace.source_files[source_id] = stored_path
    workspace.revision = uuid4().hex
    workspace.guide_job = None
    source = {"id": source_id, "name": name, "type": kind, "status": "indexed", "chunks": len(chunks), "downloadable": stored_path is not None}
    workspace.sources.append(source)
    return source


def workspace_summary() -> dict[str, object]:
    return {
        "id": workspace.course_id,
        "name": workspace.name,
        "source_count": len(workspace.sources),
        "chunk_count": len(workspace.chunks),
        "sources": workspace.sources,
        "course_map_ready": workspace.course_map is not None,
    }


def learner_context(course_id: str) -> str:
    masteries = repository.topic_masteries(course_id)
    if not masteries:
        return "New learner: no mastery history yet. Teach clearly and use a gentle diagnostic check."
    weakest = sorted(masteries, key=lambda item: float(item["mastery"]))[:4]
    strongest = sorted(masteries, key=lambda item: float(item["mastery"]), reverse=True)[:3]
    describe = lambda item: f"{item['topic']} {round(float(item['mastery']) * 100)}%"
    return (
        "Weak or developing topics: " + ", ".join(describe(item) for item in weakest)
        + ". Stronger topics: " + ", ".join(describe(item) for item in strongest) + "."
    )


def topics_for_chunks(chunks: list[KnowledgeChunk], *, use_active_map: bool = True) -> list[str]:
    chunk_ids = {chunk.chunk_id for chunk in chunks}
    if use_active_map and workspace.course_map:
        mapped = [
            concept.topic for concept in workspace.course_map.concepts
            if chunk_ids.intersection(concept.evidence_chunk_ids)
        ]
        if mapped:
            return list(dict.fromkeys(mapped))
    explicit = [concept for chunk in chunks for concept in chunk.concepts]
    if explicit:
        return list(dict.fromkeys(explicit))
    return list(dict.fromkeys(chunk.citation.source_name for chunk in chunks))


def selected_guide_chunks(source_ids: list[str]) -> list[KnowledgeChunk]:
    if not source_ids:
        return list(workspace.chunks)
    known_ids = {str(source["id"]) for source in workspace.sources}
    unknown = set(source_ids) - known_ids
    if unknown:
        raise ValueError(f"Unknown study material: {', '.join(sorted(unknown))}")
    chosen = set(source_ids)
    chunks = [chunk for chunk in workspace.chunks if chunk.citation.source_id in chosen]
    if not chunks:
        raise ValueError("The selected material does not contain readable study content.")
    return chunks


def course_map_view(
    course_map: CourseMap,
    *,
    chunks: list[KnowledgeChunk] | None = None,
    selected_source_ids: list[str] | None = None,
) -> dict[str, object]:
    """Enrich a map with human-readable evidence and a useful learning route."""
    available_chunks = list(chunks) if chunks is not None else list(workspace.chunks)
    chunks_by_id = {chunk.chunk_id: chunk for chunk in available_chunks}
    if chunks is None:
        chunks_by_id.update(workspace.guide_evidence)
    order = course_map.learning_order()
    concepts = []
    for concept_id in order:
        concept = course_map.concept_by_id(concept_id)
        clean_name = humanize_math_text(concept.name).replace("**", "").strip("#* /\\")
        clean_topic = humanize_math_text(concept.topic).replace("**", "").strip("#* /\\")
        concepts.append(
            {
                **concept.model_dump(),
                "name": clean_name,
                "topic": clean_topic,
                "description": humanize_math_text(concept.description).replace("**", "").strip(),
                "key_points": [humanize_math_text(point).replace("**", "").strip("#* ") for point in concept.key_points],
                "study_steps": [humanize_math_text(step).replace("**", "").strip("#* ") for step in concept.study_steps],
                "prerequisite_ids": sorted(course_map.prerequisites_of(concept_id)),
                "evidence": [
                    {
                        "label": chunks_by_id[chunk_id].citation.label(),
                        "excerpt": chunks_by_id[chunk_id].text[:220],
                        "source_name": chunks_by_id[chunk_id].citation.source_name,
                        "page": chunks_by_id[chunk_id].citation.page,
                        "slide": chunks_by_id[chunk_id].citation.slide,
                        "start_seconds": chunks_by_id[chunk_id].citation.start_seconds,
                        "section": chunks_by_id[chunk_id].citation.section,
                        "evidence_kind": chunks_by_id[chunk_id].evidence_kind.value,
                        "target_uri": chunks_by_id[chunk_id].citation.target_uri(),
                    }
                    for chunk_id in concept.evidence_chunk_ids
                    if chunk_id in chunks_by_id
                ],
            }
        )
    selected_ids = set(workspace.guide_source_ids if selected_source_ids is None else selected_source_ids)
    scoped_chunks = [
        chunk for chunk in available_chunks
        if not selected_ids or chunk.citation.source_id in selected_ids
    ]
    source_names = {}
    for chunk in chunks_by_id.values():
        source_names.setdefault(chunk.citation.source_id, chunk.citation.source_name)
    return {
        "title": course_map.title,
        "concepts": concepts,
        "prerequisite_edges": [edge.model_dump() for edge in course_map.prerequisite_edges],
        "learning_order": order,
        "recommended_concept_id": order[0] if order else None,
        "revision_concepts": concepts,
        "coverage": {
            "indexed_chunks": len(scoped_chunks),
            "mapped_chunks": len({cid for concept in course_map.concepts for cid in concept.evidence_chunk_ids}),
            "scope": "Indexed text, transcripts, web content, and locally interpreted visual material.",
        },
        "selected_source_ids": list(selected_ids),
        "selected_source_names": [source_names[source_id] for source_id in selected_ids if source_id in source_names],
    }


def assessment_view(record: dict[str, object]) -> dict[str, object]:
    course = repository.load_course(str(record["course_id"]))
    chunks = list(course["chunks"]) if course else []
    chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}
    completed = record["status"] == "completed"
    report = record["report"]
    if report:
        report = {**report, "feedback": [
            {
                **item,
                "prompt": humanize_math_text(str(item.get("prompt", ""))).replace("**", ""),
                "correct_answer": humanize_math_text(str(item.get("correct_answer", ""))).replace("**", ""),
                "feedback": humanize_math_text(str(item.get("feedback", ""))).replace("**", ""),
                "explanation": humanize_math_text(str(item.get("explanation", ""))).replace("**", ""),
            }
            for item in report.get("feedback", [])
        ]}
    questions = []
    for question in record["questions"]:
        public = {
            "question_id": question.question_id,
            "question_type": question.question_type,
            "prompt": humanize_math_text(question.prompt),
            "topic": question.topic,
            "difficulty": question.difficulty,
            "options": [humanize_math_text(option) for option in question.options],
            "evidence": [
                {
                    "label": chunks_by_id[chunk_id].citation.label(),
                    "source_name": chunks_by_id[chunk_id].citation.source_name,
                    "page": chunks_by_id[chunk_id].citation.page,
                    "slide": chunks_by_id[chunk_id].citation.slide,
                    "start_seconds": chunks_by_id[chunk_id].citation.start_seconds,
                    "section": chunks_by_id[chunk_id].citation.section,
                    "target_uri": chunks_by_id[chunk_id].citation.target_uri(),
                    "excerpt": chunks_by_id[chunk_id].text[:240],
                }
                for chunk_id in question.evidence_chunk_ids if chunk_id in chunks_by_id
            ],
        }
        if completed:
            public.update(correct_answer=humanize_math_text(question.correct_answer), explanation=humanize_math_text(question.explanation))
        questions.append(public)
    return {
        "id": record["id"],
        "course_id": record["course_id"],
        "title": record["title"],
        "config": record["config"],
        "status": record["status"],
        "score": record["score"],
        "report": report,
        "questions": questions,
        "answers": record["answers"] if completed else [],
        "created_at": record["created_at"],
        "completed_at": record.get("completed_at"),
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/workspace")
def get_workspace() -> dict[str, object]:
    return workspace_summary()


@app.post("/api/workspace")
def create_workspace(request: WorkspaceRequest) -> dict[str, object]:
    """Create and activate a durable course without deleting earlier workspaces."""
    global workspace
    course_id = repository.create_course(request.name)
    record = repository.load_course(course_id)
    if record is None:
        raise HTTPException(status_code=500, detail="Could not create the course workspace.")
    workspace = workspace_from_record(record)
    return workspace_summary()


@app.get("/api/courses")
def list_courses() -> dict[str, object]:
    return {"active_course_id": workspace.course_id, "courses": repository.list_courses()}


@app.post("/api/courses/{course_id}/activate")
def activate_course(course_id: str) -> dict[str, object]:
    global workspace
    record = repository.load_course(course_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Course workspace not found.")
    workspace = workspace_from_record(record)
    return workspace_summary()


@app.patch("/api/courses/{course_id}")
def update_course(course_id: str, request: LibraryItemUpdateRequest) -> dict[str, object]:
    global workspace
    try:
        if request.name is not None:
            repository.rename_course(course_id, request.name)
        if request.pinned is not None:
            repository.set_course_pinned(course_id, request.pinned)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    if workspace.course_id == course_id and request.name is not None:
        workspace.name = request.name.strip()
    return {"workspace": workspace_summary(), "courses": repository.list_courses()}


def remove_registered_source_files(files: list[tuple[str, Path]]) -> None:
    for source_id, stored_path in files:
        if stored_path.is_file():
            stored_path.unlink()
        image_dir = UPLOAD_ROOT / "images" / source_id
        if image_dir.is_dir():
            for child in image_dir.iterdir():
                if child.is_file():
                    child.unlink()
            image_dir.rmdir()


@app.delete("/api/courses/{course_id}")
def delete_course(course_id: str) -> dict[str, object]:
    """Archive a workspace from active study while preserving all of its history."""
    global workspace
    deleting_active = workspace.course_id == course_id
    try:
        repository.archive_course(course_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    if deleting_active:
        next_course_id = repository.latest_course_id()
        if next_course_id is None:
            next_course_id = repository.create_course("My study space")
        record = repository.load_course(next_course_id)
        if record is None:
            raise HTTPException(status_code=500, detail="Could not activate a remaining workspace.")
        workspace = workspace_from_record(record)
    return {"workspace": workspace_summary(), "courses": repository.list_courses()}


@app.post("/api/materials")
async def upload_materials(files: list[UploadFile] = File(...)) -> dict[str, object]:
    """Save and parse arbitrary study documents into the active workspace."""
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    reports: list[dict[str, object]] = []
    upload_course_id = workspace.course_id
    upload_revision = workspace.revision

    for uploaded in files:
        original_name = Path(uploaded.filename or "untitled").name
        suffix = Path(original_name).suffix.lower()
        if suffix not in SUPPORTED_FILE_TYPES:
            reports.append({"name": original_name, "status": "unsupported", "message": "Supported extensions: " + ', '.join(sorted(SUPPORTED_FILE_TYPES))})
            continue

        stored_path = UPLOAD_ROOT / f"{uuid4().hex}-{original_name}"
        stored_path.write_bytes(await uploaded.read())
        source_id = f"source-{uuid4().hex[:12]}"

        try:
            # Vision/transcription can take minutes; never block the async API
            # loop, which must still serve status and cancellation requests.
            parsed = await run_in_threadpool(parse_study_file,
                stored_path, source_id=source_id, source_name=original_name,
                source_uri=f"/api/sources/{source_id}",
            )
            if workspace.course_id != upload_course_id or workspace.revision != upload_revision:
                raise ValueError("The workspace changed while reading this file. Reupload it in the intended workspace.")
            source = add_indexed_material(
                source_id=source_id, name=original_name, kind=parsed.kind,
                segments=parsed.segments, stored_path=stored_path,
            )
            reports.append(source)
            upload_revision = workspace.revision
        except Exception as error:
            reports.append({"name": original_name, "status": "failed", "message": str(error)})

    return {"reports": reports, "workspace": workspace_summary()}


@app.post("/api/materials/url")
def import_material_url(request: UrlMaterialRequest) -> dict[str, object]:
    """Import a YouTube lecture, direct study file, PDF book, or public web page."""
    source_id = f"source-{uuid4().hex[:12]}"
    try:
        if is_youtube_url(request.url):
            path, title, canonical_url = download_youtube_audio(request.url, UPLOAD_ROOT / "youtube")
            segments = transcribe_video(
                path, source_id=source_id, source_name=title, source_uri=canonical_url,
            )
            source = add_indexed_material(
                source_id=source_id, name=title, kind="youtube video",
                segments=segments, stored_path=path,
            )
        else:
            resource = fetch_public_resource(request.url)
            suffix = Path(resource.filename).suffix.lower()
            is_html = resource.content_type in {"text/html", "application/xhtml+xml"}
            if is_html:
                display_name, segments = ingest_web_page(
                    resource.content, source_id=source_id, source_name=resource.filename,
                    source_uri=resource.final_url,
                )
                source = add_indexed_material(
                    source_id=source_id, name=display_name, kind="web page", segments=segments,
                )
            else:
                if suffix not in SUPPORTED_FILE_TYPES:
                    content_suffixes = {
                        "application/pdf": ".pdf",
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
                        "image/png": ".png", "image/jpeg": ".jpg", "text/plain": ".txt",
                    }
                    suffix = content_suffixes.get(resource.content_type, "")
                if suffix not in SUPPORTED_FILE_TYPES:
                    raise ValueError(f"Unsupported link content type: {resource.content_type}")
                name = resource.filename if Path(resource.filename).suffix else f"linked-material{suffix}"
                stored_path = UPLOAD_ROOT / f"{uuid4().hex}-{Path(name).name}"
                stored_path.parent.mkdir(parents=True, exist_ok=True)
                stored_path.write_bytes(resource.content)
                parsed = parse_study_file(
                    stored_path, source_id=source_id, source_name=name, source_uri=resource.final_url,
                )
                source = add_indexed_material(
                    source_id=source_id, name=name, kind=parsed.kind,
                    segments=parsed.segments, stored_path=stored_path,
                )
    except Exception as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"report": source, "workspace": workspace_summary()}


@app.get("/api/sources/{source_id}")
def open_source(source_id: str, download: bool = False) -> FileResponse:
    """Serve a registered active or archived source, never a caller-supplied path."""
    path = workspace.source_files.get(source_id) or repository.material_file(source_id)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Source unavailable. Upload the original material again.")
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    inline_types = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".mp3", ".wav", ".m4a", ".mp4", ".webm", ".mov"}
    if path.suffix.lower() in inline_types and not download:
        return FileResponse(path, media_type=media_type, content_disposition_type="inline")
    return FileResponse(path, media_type=media_type, filename=path.name.split("-", 1)[-1])


@app.patch("/api/materials/{source_id}/notes")
def save_material_notes(source_id: str, request: MaterialNotesRequest) -> dict[str, object]:
    source = next((item for item in workspace.sources if item["id"] == source_id), None)
    if source is None:
        raise HTTPException(status_code=404, detail="Study material not found in the active workspace.")
    repository.save_material_notes(workspace.course_id, source_id, request.notes)
    source["notes"] = request.notes
    return {"notes": request.notes}


@app.delete("/api/materials/{source_id}")
def delete_material(source_id: str) -> dict[str, object]:
    """Archive one source from active study while retaining generated work and citations."""
    source = next((item for item in workspace.sources if item["id"] == source_id), None)
    if source is None:
        raise HTTPException(status_code=404, detail="Study material not found in the active workspace.")
    try:
        repository.archive_material(workspace.course_id, source_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    workspace.sources = [item for item in workspace.sources if item["id"] != source_id]
    workspace.chunks = [chunk for chunk in workspace.chunks if chunk.citation.source_id != source_id]
    workspace.source_files.pop(source_id, None)
    workspace.course_map = None
    workspace.guide_source_ids = []
    workspace.revision = uuid4().hex
    workspace.guide_job = None
    return {"archived": {"id": source_id, "name": source["name"]}, "workspace": workspace_summary()}


def compact_transcript_chunks(
    chunks: list[KnowledgeChunk], *, max_characters: int = 1800,
) -> list[KnowledgeChunk]:
    """Merge tiny adjacent transcript chunks for fast map extraction, preserving time ranges."""
    output: list[KnowledgeChunk] = []
    group: list[KnowledgeChunk] = []

    def flush() -> None:
        nonlocal group
        if not group:
            return
        if len(group) == 1:
            output.append(group[0])
        else:
            first, last = group[0], group[-1]
            citation = first.citation.model_copy(update={"end_seconds": last.citation.end_seconds})
            output.append(first.model_copy(update={
                "text": " ".join(item.text for item in group),
                "token_count": sum(item.token_count for item in group),
                "citation": citation,
            }))
        group = []

    for chunk in chunks:
        is_transcript = chunk.evidence_kind is EvidenceKind.TRANSCRIPT
        same_source = group and group[-1].citation.source_id == chunk.citation.source_id
        projected = sum(len(item.text) for item in group) + len(chunk.text) + len(group)
        if not is_transcript:
            flush()
            output.append(chunk)
        elif group and (not same_source or projected > max_characters):
            flush()
            group = [chunk]
        else:
            group.append(chunk)
    flush()
    return output


def run_guide_job(
    job: dict[str, object], course_id: str, revision: str, title: str,
    chunks: list[KnowledgeChunk], source_ids: list[str],
) -> None:
    def progress(completed: int, total: int) -> None:
        if job.get("status") == "cancelled":
            raise GenerationStopped("Stopped by you.")
        job.update(completed_batches=completed, total_batches=total)
    try:
        generated = generate_course_map(title, chunks, generate_json=call_ollama_json, on_progress=progress)
        if job.get("status") == "cancelled":
            return
        if workspace.course_id != course_id or workspace.revision != revision:
            job.update(status="cancelled", error="Material changed. Generate a guide for your current material.")
            return
        workspace.course_map = generated
        workspace.guide_source_ids = source_ids
        workspace.guide_evidence = {chunk.chunk_id: chunk for chunk in chunks}
        artifact_id = repository.save_course_map(course_id, generated)
        job.update(status="complete", artifact_id=artifact_id)
    except Exception as error:
        job.update(status="cancelled" if isinstance(error, GenerationStopped) else "failed", error=str(error))


@app.post("/api/study-guide/generate", status_code=202)
def start_study_guide(request: GuideRequest | None = None) -> dict[str, object]:
    if not workspace.chunks:
        raise HTTPException(status_code=400, detail="Upload or import readable study material first.")
    if workspace.guide_job and workspace.guide_job["status"] == "running":
        return {"job": dict(workspace.guide_job)}
    source_ids = list(dict.fromkeys(request.source_ids if request else []))
    try:
        chunks = selected_guide_chunks(source_ids)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    compacted_chunks = compact_transcript_chunks(chunks)
    job: dict[str, object] = {
        "job_id": uuid4().hex, "status": "running", "completed_batches": 0,
        "total_batches": 0, "source_ids": source_ids, "source_chunks": len(chunks),
        "analysis_chunks": len(compacted_chunks),
    }
    workspace.guide_job = job
    guide_executor.submit(
        run_guide_job, job, workspace.course_id, workspace.revision,
        workspace.name, compacted_chunks, source_ids,
    )
    return {"job": dict(job)}


@app.get("/api/study-guide/status")
def study_guide_status() -> dict[str, object]:
    return {"job": dict(workspace.guide_job) if workspace.guide_job else None}


@app.get("/api/study-guides")
def list_study_guides() -> dict[str, object]:
    return {"guides": [
        artifact for artifact in repository.list_artifacts(workspace.course_id)
        if artifact["kind"] == "study_guide"
    ]}


@app.get("/api/study-guides/{artifact_id}")
def get_study_guide(artifact_id: str) -> dict[str, object]:
    artifact = repository.get_artifact(artifact_id)
    if artifact is None or artifact["kind"] != "study_guide":
        raise HTTPException(status_code=404, detail="Saved study guide not found.")
    record = repository.load_course(str(artifact["course_id"]), include_archived_materials=True)
    if record is None:
        raise HTTPException(status_code=404, detail="The guide's workspace no longer exists.")
    course_map = CourseMap.model_validate(artifact["content"])
    evidence_ids = {cid for concept in course_map.concepts for cid in concept.evidence_chunk_ids}
    all_chunks = list(record["chunks"])
    source_ids = list(dict.fromkeys(
        chunk.citation.source_id for chunk in all_chunks if chunk.chunk_id in evidence_ids
    ))
    return {
        "artifact": {key: artifact[key] for key in ("id", "title", "created_at")},
        "course_map": course_map_view(course_map, chunks=all_chunks, selected_source_ids=source_ids),
    }


@app.get("/api/course-map")
def get_course_map() -> dict[str, object]:
    """Return the current validated map, if a learner has generated one."""
    return {"course_map": course_map_view(workspace.course_map) if workspace.course_map else None}


@app.post("/api/course-map/generate")
def create_course_map(request: GuideRequest | None = None) -> dict[str, object]:
    """Generate a source-linked concept/prerequisite map from active material."""
    try:
        source_ids = list(dict.fromkeys(request.source_ids if request else []))
        chunks = compact_transcript_chunks(selected_guide_chunks(source_ids))
        workspace.course_map = generate_course_map(
            workspace.name,
            chunks,
            generate_json=call_ollama_json,
        )
        workspace.guide_source_ids = source_ids
        workspace.guide_evidence = {chunk.chunk_id: chunk for chunk in chunks}
        repository.save_course_map(workspace.course_id, workspace.course_map)
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {"course_map": course_map_view(workspace.course_map)}


@app.post("/api/search")
def search_course(request: SearchRequest) -> dict[str, object]:
    """Return only cited chunks from currently uploaded study material."""
    if not workspace.chunks:
        raise HTTPException(status_code=400, detail="Upload and index study material before searching.")
    results = BM25Index(workspace.chunks).search(request.question, limit=request.limit)
    return {
        "results": [
            {
                "text": result.chunk.text,
                "score": round(result.score, 3),
                "concepts": result.chunk.concepts,
                "citation": {
                    "label": result.chunk.citation.label(),
                    "source_name": result.chunk.citation.source_name,
                    "page": result.chunk.citation.page,
                    "slide": result.chunk.citation.slide,
                    "start_seconds": result.chunk.citation.start_seconds,
                    "section": result.chunk.citation.section,
                    "target_uri": result.chunk.citation.target_uri(),
                },
            }
            for result in results
        ]
    }


@app.post("/api/tutor")
def teach_course(request: TutorRequest) -> dict[str, object]:
    """Teach from retrieved course evidence using the configured LLM provider."""
    if not workspace.chunks:
        raise HTTPException(status_code=400, detail="Upload and index study material before asking the tutor.")
    try:
        reply = tutor_answer(
            request.question, workspace.chunks, language=request.language,
            learner_context=learner_context(workspace.course_id),
        )
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    response_metadata = {
        "citations": reply.citations,
        "follow_up": reply.follow_up,
        "coverage": reply.coverage,
    }
    conversation_id = repository.save_chat_exchange(
        course_id=workspace.course_id,
        question=request.question,
        answer=reply.answer,
        response_metadata=response_metadata,
        conversation_id=request.conversation_id,
    )
    if reply.coverage == "course_backed":
        used_chunks = [chunk for chunk in workspace.chunks if chunk.chunk_id in set(reply.evidence_chunk_ids)]
        repository.record_conversation_learning(workspace.course_id, topics_for_chunks(used_chunks))
    return {
        "answer": reply.answer,
        "citations": reply.citations,
        "follow_up": reply.follow_up,
        "coverage": reply.coverage,
        "conversation_id": conversation_id,
    }


def run_overview_job(
    job: dict[str, object], course_id: str, revision: str, title: str,
    chunks: list[KnowledgeChunk], source_names: list[str], language: str,
) -> None:
    def progress(completed: int, total: int) -> None:
        if job.get("status") == "cancelled":
            raise GenerationStopped("Stopped by you.")
        job.update(completed_batches=completed, total_batches=total)
    try:
        lesson = generate_material_overview(
            title, chunks, generate=call_ollama_long, on_progress=progress,
            model_available=ollama_available(), language=language,
        )
        if job.get("status") == "cancelled":
            return
        question = "Teach me everything in " + (", ".join(source_names) if source_names else title)
        conversation_id = repository.save_chat_exchange(
            course_id=course_id, question=question, answer=str(lesson["answer"]),
            response_metadata={
                "citations": lesson["citations"], "follow_up": lesson["follow_up"],
                "coverage": lesson["coverage"], "mode": "full_material_lesson",
            },
        )
        repository.record_conversation_learning(course_id, topics_for_chunks(chunks, use_active_map=False))
        job.update(status="complete", result={**lesson, "conversation_id": conversation_id})
    except Exception as error:
        job.update(status="cancelled" if isinstance(error, GenerationStopped) else "failed", error=str(error))


@app.post("/api/tutor/overview", status_code=202)
def start_material_overview(request: OverviewRequest) -> dict[str, object]:
    if workspace.overview_job and workspace.overview_job.get("status") == "running":
        return {"job": dict(workspace.overview_job)}
    source_ids = list(dict.fromkeys(request.source_ids))
    try:
        raw_chunks = selected_guide_chunks(source_ids)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    chunks = compact_transcript_chunks(raw_chunks, max_characters=1400)
    names = [str(source["name"]) for source in workspace.sources if not source_ids or source["id"] in source_ids]
    job: dict[str, object] = {
        "job_id": uuid4().hex, "status": "running", "completed_batches": 0,
        "total_batches": 0, "source_ids": source_ids, "language": request.language,
    }
    workspace.overview_job = job
    overview_jobs[str(job["job_id"])] = job
    overview_executor.submit(
        run_overview_job, job, workspace.course_id, workspace.revision,
        workspace.name, chunks, names, request.language,
    )
    return {"job": dict(job)}


@app.get("/api/tutor/overview/status")
def material_overview_status(job_id: str | None = None) -> dict[str, object]:
    job = overview_jobs.get(job_id) if job_id else workspace.overview_job
    return {"job": dict(job) if job else None}


@app.post("/api/assessments", status_code=201)
def create_assessment(request: AssessmentCreateRequest) -> dict[str, object]:
    if not workspace.chunks:
        raise HTTPException(status_code=400, detail="Upload study material before generating an assessment.")
    try:
        adaptive_scope = request.scope
        if not adaptive_scope:
            adaptive_scope = [
                str(item["topic"]) for item in repository.topic_masteries(workspace.course_id)
                if float(item["mastery"]) < 0.7
            ][:3]
        draft = generate_assessment(
            course_name=workspace.name,
            chunks=workspace.chunks,
            count=request.question_count,
            difficulty=request.difficulty,
            question_types=request.question_types,
            scope=adaptive_scope,
            previous_prompts=repository.previous_question_prompts(workspace.course_id),
            generate_json=call_ollama_json,
            verify_json=call_ollama_json,
            language=request.language,
        )
        assessment_id = repository.save_assessment(
            workspace.course_id,
            draft,
            config={**request.model_dump(), "adaptive_scope": adaptive_scope},
        )
        record = repository.get_assessment(assessment_id)
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    if record is None:
        raise HTTPException(status_code=500, detail="The generated assessment could not be saved.")
    return assessment_view(record)


@app.get("/api/assessments")
def list_assessments() -> dict[str, object]:
    return {
        "assessments": repository.list_assessments(workspace.course_id),
        "mastery": repository.topic_masteries(workspace.course_id),
    }


@app.get("/api/progress")
def get_progress() -> dict[str, object]:
    return repository.progress_summary(workspace.course_id)


@app.get("/api/progress/all")
def get_all_progress() -> dict[str, object]:
    """Expose small per-workspace summaries so saved work never appears to vanish."""
    summaries = []
    for course in repository.list_courses():
        summary = repository.progress_summary(str(course["id"]))
        summaries.append({"course_id": course["id"], "course_name": course["name"], **summary})
    return {"workspaces": summaries}


@app.get("/api/study-events")
def list_study_events() -> dict[str, object]:
    return {"events": repository.list_study_events(workspace.course_id)}


@app.post("/api/study-events")
def create_study_event(request: StudyEventCreateRequest) -> dict[str, object]:
    try:
        event = repository.create_study_event(workspace.course_id, **request.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"event": event}


@app.patch("/api/study-events/{event_id}")
def update_study_event(event_id: str, request: StudyEventUpdateRequest) -> dict[str, object]:
    try:
        event = repository.update_study_event(event_id, **request.model_dump(exclude_unset=True))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"event": event}


@app.delete("/api/study-events/{event_id}")
def delete_study_event(event_id: str) -> dict[str, object]:
    try:
        repository.delete_study_event(event_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"deleted_id": event_id}


@app.get("/api/reminders/due")
def due_reminders() -> dict[str, object]:
    return {"reminders": repository.due_reminders()}


@app.get("/api/flashcards/download")
def download_flashcards(format: DownloadFormat = "pdf") -> Response:
    if workspace.course_map is None:
        raise HTTPException(status_code=404, detail="Generate a Learning Flow before downloading flashcards.")
    sections = []
    for number, concept in enumerate(workspace.course_map.concepts, start=1):
        paragraphs = [f"Question: Explain {concept.name}", f"Answer: {concept.description}"]
        paragraphs.extend(f"- {point}" for point in concept.key_points)
        paragraphs.extend(f"- Evidence ID: {chunk_id}" for chunk_id in concept.evidence_chunk_ids)
        sections.append((f"Flashcard {number} · {concept.topic}", paragraphs))
    return export_response(
        title=f"{workspace.name} flashcards", sections=sections, format=format,
        structured={"course": workspace.name, "flashcards": [concept.model_dump() for concept in workspace.course_map.concepts]},
    )


@app.get("/api/assessments/{assessment_id}")
def get_assessment(assessment_id: str) -> dict[str, object]:
    record = repository.get_assessment(assessment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    return assessment_view(record)


@app.post("/api/assessments/{assessment_id}/submit")
def submit_assessment(assessment_id: str, request: AssessmentSubmitRequest) -> dict[str, object]:
    record = repository.get_assessment(assessment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    if record["status"] == "completed":
        raise HTTPException(status_code=409, detail="This assessment has already been submitted.")
    course = repository.load_course(str(record["course_id"]))
    if course is None:
        raise HTTPException(status_code=404, detail="The assessment course no longer exists.")
    chunks_by_id = {chunk.chunk_id: chunk for chunk in course["chunks"]}
    feedback = []
    try:
        for question in record["questions"]:
            response = request.answers.get(question.question_id, "")
            if question.question_type == "short_answer":
                result = grade_short_answer(
                    question,
                    response,
                    chunks_by_id,
                    grade_json=call_ollama_json,
                    language=str(record["config"].get("language", "english")),
                )
            else:
                result = grade_objective(question, response)
            feedback.append(result)
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    question_lookup: dict[str, AssessmentQuestion] = {item.question_id: item for item in record["questions"]}
    topic_scores: dict[str, list[float]] = {}
    for item in feedback:
        topic_scores.setdefault(question_lookup[item.question_id].topic, []).append(item.score)
    topic_summary = [
        {"topic": topic, "accuracy": round(sum(scores) / len(scores) * 100, 1), "questions": len(scores)}
        for topic, scores in topic_scores.items()
    ]
    topic_summary.sort(key=lambda item: item["accuracy"])
    percentage = round(sum(item.score for item in feedback) / len(feedback) * 100, 1)
    report = {
        "assessment_id": assessment_id,
        "title": record["title"],
        "course_name": course["name"],
        "percentage": percentage,
        "correct_questions": sum(1 for item in feedback if item.correct),
        "total_questions": len(feedback),
        "topic_summary": topic_summary,
        "weak_topics": [item["topic"] for item in topic_summary if item["accuracy"] < 70],
        "misconceptions": [item.misconception for item in feedback if item.misconception],
        "feedback": [
            {
                **item.model_dump(),
                "prompt": question_lookup[item.question_id].prompt,
                "topic": question_lookup[item.question_id].topic,
                "correct_answer": question_lookup[item.question_id].correct_answer,
                "explanation": question_lookup[item.question_id].explanation,
                "citations": [
                    {
                        "label": chunks_by_id[chunk_id].citation.label(),
                        "target_uri": chunks_by_id[chunk_id].citation.target_uri(),
                    }
                    for chunk_id in question_lookup[item.question_id].evidence_chunk_ids
                    if chunk_id in chunks_by_id
                ],
            }
            for item in feedback
        ],
    }
    artifact_id = repository.save_assessment_results(assessment_id, feedback, report)
    return {"report": report, "artifact_id": artifact_id, "mastery": repository.topic_masteries(str(record["course_id"]))}


def assessment_export_sections(record: dict[str, object]) -> list[tuple[str, list[str]]]:
    report = record.get("report")
    sections: list[tuple[str, list[str]]] = [("Assessment details", [
        f"Status: {record['status']}",
        f"Difficulty: {record['config'].get('difficulty', 'mixed')}",
        f"Question count: {len(record['questions'])}",
    ])]
    if report:
        sections[0][1].extend([
            f"Course: {report['course_name']}", f"Score: {report['percentage']}%",
            "Weak topics: " + (", ".join(report["weak_topics"]) or "None identified"),
        ])
        for number, item in enumerate(report["feedback"], start=1):
            paragraphs = [
                f"Topic: {item['topic']}", f"Question: {item['prompt']}",
                f"Your answer: {item['response'] or '(no answer)'}",
                f"Correct answer: {item['correct_answer']}",
                f"Result: {'Correct' if item['correct'] else 'Needs review'}",
                f"Feedback: {item['feedback']}",
                f"Worked explanation: {item.get('explanation', '')}",
            ]
            if item.get("misconception"):
                paragraphs.append(f"Likely misconception: {item['misconception']}")
            paragraphs.extend(f"- Source: {citation['label']}" for citation in item.get("citations", []))
            sections.append((f"Question {number}", paragraphs))
    else:
        for number, question in enumerate(record["questions"], start=1):
            paragraphs = [
                f"Topic: {question.topic}", f"Difficulty: {question.difficulty}",
                f"Type: {question.question_type.replace('_', ' ')}", question.prompt,
            ]
            paragraphs.extend(f"- {option}" for option in question.options)
            sections.append((f"Question {number}", paragraphs))
    return sections


def course_map_export_sections(content: dict[str, object], view: str) -> list[tuple[str, list[str]]]:
    concepts = content.get("concepts", [])
    sections: list[tuple[str, list[str]]] = []
    for number, concept in enumerate(concepts, start=1):
        paragraphs = [f"Topic: {concept['topic']}", str(concept["description"])]
        if view == "learning":
            paragraphs.extend(f"{index}. {step}" for index, step in enumerate(concept.get("study_steps", []), start=1))
        else:
            paragraphs.extend(f"- {point}" for point in concept.get("key_points", []))
        evidence = concept.get("evidence", [])
        if evidence:
            paragraphs.extend(
                f"- Source: {item.get('label', item.get('source_name', 'Course material'))}"
                for item in evidence
            )
        else:
            paragraphs.extend(
                f"- Source reference: {chunk_id}"
                for chunk_id in concept.get("evidence_chunk_ids", [])
            )
        sections.append((f"{number}. {concept['name']}", paragraphs))
    return sections


def generated_artifact_sections(artifact: dict[str, object], view: str) -> list[tuple[str, list[str]]]:
    content = artifact["content"]
    if artifact["kind"] == "study_guide":
        return course_map_export_sections(content, view)
    if artifact["kind"] == "assessment_report":
        sections = [("Result", [
            f"Score: {content.get('percentage', 'Not available')}%",
            "Weak topics: " + (", ".join(content.get("weak_topics", [])) or "None identified"),
        ])]
        for number, item in enumerate(content.get("feedback", []), start=1):
            paragraphs = [
                item.get("prompt", ""), f"Your answer: {item.get('response') or '(no answer)'}",
                f"Correct answer: {item.get('correct_answer', '')}",
                f"Feedback: {item.get('feedback', '')}",
                f"Worked explanation: {item.get('explanation', '')}",
            ]
            if item.get("misconception"):
                paragraphs.append(f"Likely misconception: {item['misconception']}")
            paragraphs.extend(
                f"- Source: {citation.get('label', 'Course material')}"
                for citation in item.get("citations", [])
            )
            sections.append((f"Question {number}", paragraphs))
        return sections
    return [("Saved data", [json.dumps(content, indent=2, ensure_ascii=False)])]


@app.get("/api/assessments/{assessment_id}/download")
def download_assessment(assessment_id: str, format: DownloadFormat = "md") -> Response:
    record = repository.get_assessment(assessment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    try:
        return export_response(
            title=str(record["title"]), sections=assessment_export_sections(record),
            format=format, structured={
                **{key: value for key, value in record.items() if key != "questions"},
                "questions": [question.model_dump() for question in record["questions"]],
            },
        )
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/history")
def history() -> dict[str, object]:
    return {
        "conversations": repository.list_conversations(),
        "artifacts": repository.list_artifacts(),
        "assessments": repository.list_assessments(),
        "archived_courses": [course for course in repository.list_courses(include_archived=True) if course["archived"]],
    }


@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: str) -> dict[str, object]:
    conversation = repository.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conversation


@app.patch("/api/conversations/{conversation_id}")
def update_conversation(conversation_id: str, request: LibraryItemUpdateRequest) -> dict[str, object]:
    try:
        if request.name is not None:
            repository.rename_conversation(conversation_id, request.name)
        if request.pinned is not None:
            repository.set_conversation_pinned(conversation_id, request.pinned)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"conversations": repository.list_conversations()}


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str) -> dict[str, object]:
    try:
        repository.delete_conversation(conversation_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"deleted_id": conversation_id, "conversations": repository.list_conversations()}


@app.get("/api/conversations/{conversation_id}/download")
def download_conversation(conversation_id: str, format: DownloadFormat = "md") -> Response:
    conversation = repository.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    sections = []
    for message in conversation["messages"]:
        speaker = "You" if message["role"] == "user" else "ConceptFlow"
        paragraphs = [str(message["content"])]
        metadata = message.get("metadata", {})
        for citation in metadata.get("citations", []):
            paragraphs.append(f"- Source: {citation.get('label', citation.get('source_name', 'Course material'))}")
        sections.append((speaker, paragraphs))
    try:
        return export_response(
            title=str(conversation["title"]), sections=sections, format=format, structured=conversation,
        )
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/artifacts/{artifact_id}/download")
def download_artifact(
    artifact_id: str, format: DownloadFormat = "json",
    view: Literal["learning", "revision"] = "learning",
) -> Response:
    artifact = repository.get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Generated item not found.")
    title = str(artifact["title"])
    if artifact["kind"] == "study_guide":
        title = f"{title} - {'Learning Flow' if view == 'learning' else 'Revision Mind Map'}"
        record = repository.load_course(str(artifact["course_id"]), include_archived_materials=True)
        if record is not None:
            course_map = CourseMap.model_validate(artifact["content"])
            artifact = {
                **artifact,
                "content": course_map_view(course_map, chunks=list(record["chunks"])),
            }
    try:
        return export_response(
            title=title, sections=generated_artifact_sections(artifact, view),
            format=format, structured=artifact["content"],
        )
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
