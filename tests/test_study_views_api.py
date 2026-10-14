from pathlib import Path
from io import BytesIO
import time

import pytest
from fastapi import HTTPException

from studybuddy import api
from studybuddy.course_map import Concept, CourseMap
from studybuddy.database import StudyRepository
from studybuddy.ingestion.models import CitationAnchor, EvidenceKind, KnowledgeChunk, SourceType


@pytest.fixture(autouse=True)
def local_routing_test(monkeypatch):
    # These tests exercise material routing; authentication has its own suite.
    monkeypatch.setattr(api, "AUTH_REQUIRED", False)


def wait_for_material(client, job_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        response = client.get(f"/api/material-jobs/{job_id}")
        job = response.json()["job"]
        if job["status"] != "running":
            assert job["status"] == "complete", job.get("error")
            return job
        time.sleep(0.01)
    pytest.fail("Material reader did not finish the test input")


def chunk():
    return KnowledgeChunk(chunk_id="page-12", text="Definitions on this page", token_count=5,
        citation=CitationAnchor(source_id="notes", source_name="Biology.pdf", source_type=SourceType.PDF,
            page=12, source_uri="/api/sources/notes"))


def guide():
    return CourseMap(course_id="biology", title="Biology", concepts=[Concept(concept_id="cells", name="Cells",
        topic="Cell biology", description="Cell basics", evidence_chunk_ids=["page-12"],
        study_steps=["Read the definition"], key_points=["Cell basics"])])


def test_view_exposes_readable_page_and_exact_open_link(monkeypatch):
    monkeypatch.setattr(api, "workspace", api.Workspace(chunks=[chunk()]))
    view = api.course_map_view(guide())
    evidence = view["concepts"][0]["evidence"][0]
    assert evidence["label"] == "Biology.pdf, PDF page 12"
    assert evidence["target_uri"] == "/api/sources/notes#page=12"
    assert view["concepts"][0]["study_steps"] == ["Read the definition"]
    assert view["coverage"]["mapped_chunks"] == 1


def test_job_does_not_publish_a_guide_into_a_different_workspace(monkeypatch):
    monkeypatch.setattr(api, "workspace", api.Workspace(revision="new-course"))
    monkeypatch.setattr(api, "generate_course_map", lambda *args, **kwargs: guide())
    job = {"status": "running"}
    api.run_guide_job(job, "old-course", "Old course", [chunk()], [])
    assert job["status"] == "failed"
    assert api.workspace.course_map is None


def test_guide_scope_uses_only_selected_material(monkeypatch):
    first = chunk()
    second = first.model_copy(update={
        "chunk_id": "page-20",
        "citation": first.citation.model_copy(update={"source_id": "slides", "source_name": "Lecture.pptx"}),
    })
    monkeypatch.setattr(api, "workspace", api.Workspace(
        chunks=[first, second],
        sources=[{"id": "notes", "name": "Biology.pdf"}, {"id": "slides", "name": "Lecture.pptx"}],
    ))
    selected = api.selected_guide_chunks(["slides"])
    assert [item.chunk_id for item in selected] == ["page-20"]


def test_delete_material_archives_source_and_keeps_original_file(monkeypatch, tmp_path: Path):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    repository = StudyRepository(tmp_path / "test.db")
    course_id = repository.create_course("Biology")
    source_file = tmp_path / "Biology.pdf"
    source_file.write_bytes(b"local source")
    repository.save_material(
        course_id=course_id, source_id="notes", name="Biology.pdf", kind="pdf",
        chunks=[chunk()], stored_path=source_file, source_uri="/api/sources/notes",
    )
    monkeypatch.setattr(api, "repository", repository)
    monkeypatch.setattr(api, "workspace", api.workspace_from_record(repository.load_course(course_id)))
    monkeypatch.setattr(api, "UPLOAD_ROOT", tmp_path / "uploads")

    response = TestClient(api.app).delete("/api/materials/notes")

    assert response.status_code == 200
    assert response.json()["workspace"]["source_count"] == 0
    assert repository.load_course(course_id)["chunks"] == []
    assert repository.load_course(course_id, include_archived_materials=True)["chunks"]
    assert source_file.exists()


def test_archive_active_workspace_activates_a_remaining_course(monkeypatch, tmp_path: Path):
    repository = StudyRepository(tmp_path / "test.db")
    kept_id = repository.create_course("Keep me")
    deleted_id = repository.create_course("Delete me")
    monkeypatch.setattr(api, "repository", repository)
    monkeypatch.setattr(api, "workspace", api.workspace_from_record(repository.load_course(deleted_id)))
    monkeypatch.setattr(api, "UPLOAD_ROOT", tmp_path / "uploads")

    result = api.delete_course(deleted_id)

    assert repository.load_course(deleted_id) is not None
    assert deleted_id not in [course["id"] for course in repository.list_courses()]
    assert result["workspace"]["id"] == kept_id
    assert result["workspace"]["name"] == "Keep me"


def test_saved_guide_can_preview_archived_source_evidence(monkeypatch, tmp_path: Path):
    repository = StudyRepository(tmp_path / "test.db")
    course_id = repository.create_course("Biology")
    source_file = tmp_path / "Biology.pdf"
    source_file.write_bytes(b"local source")
    repository.save_material(
        course_id=course_id, source_id="notes", name="Biology.pdf", kind="pdf",
        chunks=[chunk()], stored_path=source_file, source_uri="/api/sources/notes",
    )
    artifact_id = repository.save_course_map(course_id, guide())
    repository.archive_material(course_id, "notes")
    monkeypatch.setattr(api, "repository", repository)

    saved = api.get_study_guide(artifact_id)

    assert saved["course_map"]["concepts"][0]["evidence"][0]["page"] == 12
    assert saved["course_map"]["selected_source_names"] == ["Biology.pdf"]


def test_transcript_chunks_are_compacted_for_fast_map_generation():
    chunks = [KnowledgeChunk(
        chunk_id=f"video-{index}", text=("concept explanation " * 12).strip(), token_count=24,
        evidence_kind=EvidenceKind.TRANSCRIPT,
        citation=CitationAnchor(
            source_id="video", source_name="Lecture", source_type=SourceType.VIDEO,
            start_seconds=index * 5, end_seconds=(index + 1) * 5,
        ),
    ) for index in range(20)]

    compacted = api.compact_transcript_chunks(chunks, max_characters=1000)

    assert len(compacted) <= len(chunks) / 4
    assert sum(item.token_count for item in compacted) == sum(item.token_count for item in chunks)
    assert compacted[0].citation.start_seconds == 0
    assert compacted[-1].citation.end_seconds == 100


def test_flashcards_download_is_derived_from_validated_course_concepts(monkeypatch):
    monkeypatch.setattr(api, "workspace", api.Workspace(name="Biology", course_map=guide()))

    response = api.download_flashcards(format="txt")

    assert b"Question: Explain Cells" in response.body
    assert b"Answer:" in response.body
    assert response.headers["content-disposition"].endswith('filename="biology-flashcards.txt"')


def test_source_route_rejects_unregistered_paths(monkeypatch):
    monkeypatch.setattr(api, "workspace", api.Workspace())
    with pytest.raises(HTTPException) as caught:
        api.open_source("../../private-document.pdf")
    assert caught.value.status_code == 404


def test_registered_pdf_is_served_inline(monkeypatch, tmp_path: Path):
    source = tmp_path / "notes.pdf"
    source.touch()
    monkeypatch.setattr(api, "workspace", api.Workspace(source_files={"notes": source}))
    response = api.open_source("notes")
    assert response.path == source
    assert response.media_type == "application/pdf"


def test_uploaded_pdf_link_opens_the_original_document(monkeypatch, tmp_path: Path):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 40 700 Td (Cells are the basic units of life.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    buffer = BytesIO()
    writer.write(buffer)
    repository = StudyRepository(tmp_path / "test.db")
    course_id = repository.create_course("Biology")
    monkeypatch.setattr(api, "repository", repository)
    monkeypatch.setattr(api, "workspace", api.workspace_from_record(repository.load_course(course_id)))
    monkeypatch.setattr(api, "UPLOAD_ROOT", tmp_path / "uploads")
    client = TestClient(api.app)
    response = client.post("/api/materials", files={"files": ("Biology.pdf", buffer.getvalue(), "application/pdf")})
    assert response.status_code == 200
    job = wait_for_material(client, response.json()["reports"][0]["job_id"])
    assert job["workspace"]["chunk_count"] > 0
    citation = api.workspace.chunks[0].citation
    assert citation.target_uri().endswith("#page=1")
    opened = client.get(citation.source_uri)
    assert opened.status_code == 200
    assert opened.content == buffer.getvalue()
    assert opened.headers["content-type"] == "application/pdf"


def test_uploaded_text_file_reaches_the_connected_workspace(monkeypatch, tmp_path: Path):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    repository = StudyRepository(tmp_path / "test.db")
    course_id = repository.create_course("Calculus")
    monkeypatch.setattr(api, "repository", repository)
    monkeypatch.setattr(api, "workspace", api.workspace_from_record(repository.load_course(course_id)))
    monkeypatch.setattr(api, "UPLOAD_ROOT", tmp_path / "uploads")
    client = TestClient(api.app)

    response = client.post(
        "/api/materials",
        files={"files": ("calculus-notes.txt", b"A derivative measures instantaneous change.", "text/plain")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["reports"][0]["status"] == "processing"
    job = wait_for_material(client, body["reports"][0]["job_id"])
    assert job["source"]["type"] == "document"
    assert job["workspace"]["source_count"] == 1
    assert api.workspace.chunks[0].citation.section == "paragraph 1"


def test_web_link_endpoint_indexes_a_fetched_page(monkeypatch, tmp_path: Path):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from studybuddy.ingestion.web import RemoteResource

    repository = StudyRepository(tmp_path / "test.db")
    course_id = repository.create_course("Networks")
    monkeypatch.setattr(api, "repository", repository)
    monkeypatch.setattr(api, "workspace", api.workspace_from_record(repository.load_course(course_id)))
    monkeypatch.setattr(
        api,
        "fetch_public_resource",
        lambda url: RemoteResource(
            content=b"<html><title>Networks</title><body><h2>Routing</h2><p>A router forwards packets between networks.</p></body></html>",
            content_type="text/html",
            final_url=url,
            filename="networks.html",
        ),
    )
    client = TestClient(api.app)

    response = client.post("/api/materials/url", json={"url": "https://example.com/networks"})

    assert response.status_code == 200
    body = response.json()
    job = wait_for_material(client, body["job"]["job_id"])
    assert job["source"]["type"] == "web page"
    assert api.workspace.chunks[0].citation.section == "Routing"


def test_slow_reader_does_not_hold_upload_response_or_navigation(monkeypatch, tmp_path):
    from threading import Event
    from fastapi.testclient import TestClient
    from studybuddy.ingestion.router import ParsedMaterial
    from studybuddy.ingestion.models import SourceSegment
    repository = StudyRepository(tmp_path / "slow.db")
    course_id = repository.create_course("Handwriting")
    monkeypatch.setattr(api, "repository", repository)
    monkeypatch.setattr(api, "workspace", api.workspace_from_record(repository.load_course(course_id)))
    monkeypatch.setattr(api, "UPLOAD_ROOT", tmp_path / "uploads")
    reading = Event()
    release = Event()
    def slow_reader(path, *, source_id, source_name, source_uri, **kwargs):
        reading.set()
        assert release.wait(5)
        return ParsedMaterial("image / handwriting", [SourceSegment(text="Energy is conserved in an isolated system.",
            citation=CitationAnchor(source_id=source_id, source_name=source_name, source_type=SourceType.IMAGE, source_uri=source_uri))])
    monkeypatch.setattr(api, "parse_study_file", slow_reader)
    client = TestClient(api.app)
    job_id = None
    try:
        response = client.post("/api/materials", files={"files": ("handwritten.png", b"photo bytes", "image/png")})
        assert response.status_code == 200
        job_id = response.json()["reports"][0]["job_id"]
        assert reading.wait(2)
        assert client.get(f"/api/material-jobs/{job_id}").json()["job"]["status"] == "running"
        assert client.get("/api/workspace").status_code == 200
    finally:
        release.set()
        if job_id:
            wait_for_material(client, job_id)
