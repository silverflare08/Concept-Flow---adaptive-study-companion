"""Local API that connects the ConceptFlow web app to generic course ingestion.

This deliberately starts as a single-process local workspace. Persistence,
authentication, and multi-user storage are later product concerns; keeping this
layer small lets us test real uploads and cited retrieval first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from studybuddy.course_map import CourseMap
from studybuddy.ingestion.chunker import chunk_segments
from studybuddy.ingestion.models import KnowledgeChunk
from studybuddy.ingestion.pdf import ingest_pdf
from studybuddy.ingestion.slides import ingest_slides
from studybuddy.retrieval.bm25 import BM25Index
from studybuddy.tutor.course_map_generator import generate_course_map
from studybuddy.tutor.grounded import call_ollama_json, tutor_answer


UPLOAD_ROOT = Path("data/uploads")
SUPPORTED_DOCUMENT_TYPES = {".pdf", ".pptx"}
SUPPORTED_VIDEO_TYPES = {".mp4", ".mov", ".mkv"}


@dataclass
class Workspace:
    name: str = "My study space"
    chunks: list[KnowledgeChunk] = field(default_factory=list)
    sources: list[dict[str, object]] = field(default_factory=list)
    course_map: CourseMap | None = None
    source_files: dict[str, Path] = field(default_factory=dict)
    revision: str = field(default_factory=lambda: uuid4().hex)
    guide_job: dict[str, object] | None = None


workspace = Workspace()
guide_executor = ThreadPoolExecutor(max_workers=1)
app = FastAPI(title="ConceptFlow API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)


class WorkspaceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class SearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    limit: int = Field(default=5, ge=1, le=10)


class TutorRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


def workspace_summary() -> dict[str, object]:
    return {
        "name": workspace.name,
        "source_count": len(workspace.sources),
        "chunk_count": len(workspace.chunks),
        "sources": workspace.sources,
        "course_map_ready": workspace.course_map is not None,
    }


def course_map_view(course_map: CourseMap) -> dict[str, object]:
    """Enrich a map with human-readable evidence and a useful learning route."""
    chunks_by_id = {chunk.chunk_id: chunk for chunk in workspace.chunks}
    order = course_map.learning_order()
    concepts = []
    for concept_id in order:
        concept = course_map.concept_by_id(concept_id)
        concepts.append(
            {
                **concept.model_dump(),
                "prerequisite_ids": sorted(course_map.prerequisites_of(concept_id)),
                "evidence": [
                    {
                        "label": chunks_by_id[chunk_id].citation.label(),
                        "excerpt": chunks_by_id[chunk_id].text[:220],
                        "source_name": chunks_by_id[chunk_id].citation.source_name,
                        "page": chunks_by_id[chunk_id].citation.page,
                        "slide": chunks_by_id[chunk_id].citation.slide,
                        "target_uri": chunks_by_id[chunk_id].citation.target_uri(),
                    }
                    for chunk_id in concept.evidence_chunk_ids
                    if chunk_id in chunks_by_id
                ],
            }
        )
    return {
        "title": course_map.title,
        "concepts": concepts,
        "prerequisite_edges": [edge.model_dump() for edge in course_map.prerequisite_edges],
        "learning_order": order,
        "recommended_concept_id": order[0] if order else None,
        "revision_concepts": [concept.model_dump() for concept in course_map.concepts],
        "coverage": {
            "indexed_chunks": len(workspace.chunks),
            "mapped_chunks": len({cid for concept in course_map.concepts for cid in concept.evidence_chunk_ids}),
            "scope": "Extracted document text; images and scanned pages require the upcoming vision/OCR pipeline.",
        },
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/workspace")
def get_workspace() -> dict[str, object]:
    return workspace_summary()


@app.post("/api/workspace")
def create_workspace(request: WorkspaceRequest) -> dict[str, object]:
    """Start a new local course workspace without mixing previous material."""
    workspace.name = request.name.strip()
    workspace.chunks.clear()
    workspace.sources.clear()
    workspace.course_map = None
    workspace.source_files.clear()
    workspace.revision = uuid4().hex
    workspace.guide_job = None
    return workspace_summary()


@app.post("/api/materials")
async def upload_materials(files: list[UploadFile] = File(...)) -> dict[str, object]:
    """Save and parse arbitrary study documents into the active workspace."""
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    reports: list[dict[str, object]] = []

    for uploaded in files:
        original_name = Path(uploaded.filename or "untitled").name
        suffix = Path(original_name).suffix.lower()
        if suffix not in SUPPORTED_DOCUMENT_TYPES | SUPPORTED_VIDEO_TYPES:
            reports.append({"name": original_name, "status": "unsupported", "message": "Use PDF, PPTX, MP4, MOV, or MKV."})
            continue

        stored_path = UPLOAD_ROOT / f"{uuid4().hex}-{original_name}"
        stored_path.write_bytes(await uploaded.read())
        source_id = f"source-{uuid4().hex[:12]}"

        if suffix in SUPPORTED_VIDEO_TYPES:
            workspace.sources.append({"name": original_name, "type": "video", "status": "queued for transcription"})
            reports.append({"name": original_name, "status": "queued", "message": "Video saved; transcription is the next ingestion feature."})
            continue

        try:
            if suffix == ".pdf":
                parsed = ingest_pdf(stored_path, source_id=source_id, source_name=original_name, source_uri=f"/api/sources/{source_id}")
            else:
                parsed = ingest_slides(stored_path, source_id=source_id, source_name=original_name, source_uri=f"/api/sources/{source_id}")
            chunks = chunk_segments(parsed.segments)
            workspace.chunks.extend(chunks)
            workspace.course_map = None
            workspace.source_files[source_id] = stored_path
            workspace.revision = uuid4().hex
            workspace.guide_job = None
            workspace.sources.append(
                {"name": original_name, "type": suffix.removeprefix("."), "status": "indexed", "chunks": len(chunks)}
            )
            reports.append({"name": original_name, "status": "indexed", "chunks": len(chunks)})
        except Exception as error:
            reports.append({"name": original_name, "status": "failed", "message": str(error)})

    return {"reports": reports, "workspace": workspace_summary()}


@app.get("/api/sources/{source_id}")
def open_source(source_id: str) -> FileResponse:
    """Serve only a registered file in this workspace, never a caller-supplied path."""
    path = workspace.source_files.get(source_id)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Source unavailable. Upload the original material again.")
    if path.suffix.lower() == ".pdf":
        return FileResponse(path, media_type="application/pdf", content_disposition_type="inline")
    return FileResponse(path, filename=path.name.split("-", 1)[-1])


def run_guide_job(job: dict[str, object], revision: str, title: str, chunks: list[KnowledgeChunk]) -> None:
    def progress(completed: int, total: int) -> None:
        job.update(completed_batches=completed, total_batches=total)
    try:
        generated = generate_course_map(title, chunks, generate_json=call_ollama_json, on_progress=progress)
        if workspace.revision != revision:
            job.update(status="cancelled", error="Material changed. Generate a guide for your current material.")
            return
        workspace.course_map = generated
        job.update(status="complete")
    except Exception as error:
        job.update(status="failed", error=str(error))


@app.post("/api/study-guide/generate", status_code=202)
def start_study_guide() -> dict[str, object]:
    if not workspace.chunks:
        raise HTTPException(status_code=400, detail="Upload a readable PDF or slide deck first.")
    if workspace.guide_job and workspace.guide_job["status"] == "running":
        return {"job": dict(workspace.guide_job)}
    job: dict[str, object] = {"job_id": uuid4().hex, "status": "running", "completed_batches": 0, "total_batches": 0}
    workspace.guide_job = job
    guide_executor.submit(run_guide_job, job, workspace.revision, workspace.name, list(workspace.chunks))
    return {"job": dict(job)}


@app.get("/api/study-guide/status")
def study_guide_status() -> dict[str, object]:
    return {"job": dict(workspace.guide_job) if workspace.guide_job else None}


@app.get("/api/course-map")
def get_course_map() -> dict[str, object]:
    """Return the current validated map, if a learner has generated one."""
    return {"course_map": course_map_view(workspace.course_map) if workspace.course_map else None}


@app.post("/api/course-map/generate")
def create_course_map() -> dict[str, object]:
    """Generate a source-linked concept/prerequisite map from active material."""
    try:
        workspace.course_map = generate_course_map(
            workspace.name,
            workspace.chunks,
            generate_json=call_ollama_json,
        )
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
        reply = tutor_answer(request.question, workspace.chunks)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {
        "answer": reply.answer,
        "citations": reply.citations,
        "follow_up": reply.follow_up,
        "coverage": reply.coverage,
    }
