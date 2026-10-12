"""Local API that connects the ConceptFlow web app to generic course ingestion.

This deliberately starts as a single-process local workspace. Persistence,
authentication, and multi-user storage are later product concerns; keeping this
layer small lets us test real uploads and cited retrieval first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from studybuddy.ingestion.chunker import chunk_segments
from studybuddy.ingestion.models import KnowledgeChunk
from studybuddy.ingestion.pdf import ingest_pdf
from studybuddy.ingestion.slides import ingest_slides
from studybuddy.retrieval.bm25 import BM25Index


UPLOAD_ROOT = Path("data/uploads")
SUPPORTED_DOCUMENT_TYPES = {".pdf", ".pptx"}
SUPPORTED_VIDEO_TYPES = {".mp4", ".mov", ".mkv"}


@dataclass
class Workspace:
    name: str = "My study space"
    chunks: list[KnowledgeChunk] = field(default_factory=list)
    sources: list[dict[str, object]] = field(default_factory=list)


workspace = Workspace()
app = FastAPI(title="ConceptFlow API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class WorkspaceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class SearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    limit: int = Field(default=5, ge=1, le=10)


def workspace_summary() -> dict[str, object]:
    return {
        "name": workspace.name,
        "source_count": len(workspace.sources),
        "chunk_count": len(workspace.chunks),
        "sources": workspace.sources,
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
                parsed = ingest_pdf(stored_path, source_id=source_id, source_name=original_name)
            else:
                parsed = ingest_slides(stored_path, source_id=source_id, source_name=original_name)
            chunks = chunk_segments(parsed.segments)
            workspace.chunks.extend(chunks)
            workspace.sources.append(
                {"name": original_name, "type": suffix.removeprefix("."), "status": "indexed", "chunks": len(chunks)}
            )
            reports.append({"name": original_name, "status": "indexed", "chunks": len(chunks)})
        except Exception as error:
            reports.append({"name": original_name, "status": "failed", "message": str(error)})

    return {"reports": reports, "workspace": workspace_summary()}


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
