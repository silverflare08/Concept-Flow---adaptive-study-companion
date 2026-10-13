from pathlib import Path
from io import BytesIO

import pytest
from fastapi import HTTPException

from studybuddy import api
from studybuddy.course_map import Concept, CourseMap
from studybuddy.ingestion.models import CitationAnchor, KnowledgeChunk, SourceType


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
    api.run_guide_job(job, "old-course", "Old course", [chunk()])
    assert job["status"] == "cancelled"
    assert api.workspace.course_map is None


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
    monkeypatch.setattr(api, "workspace", api.Workspace())
    monkeypatch.setattr(api, "UPLOAD_ROOT", tmp_path / "uploads")
    client = TestClient(api.app)
    response = client.post("/api/materials", files={"files": ("Biology.pdf", buffer.getvalue(), "application/pdf")})
    assert response.status_code == 200
    assert response.json()["workspace"]["chunk_count"] > 0
    citation = api.workspace.chunks[0].citation
    assert citation.target_uri().endswith("#page=1")
    opened = client.get(citation.source_uri)
    assert opened.status_code == 200
    assert opened.content == buffer.getvalue()
    assert opened.headers["content-type"] == "application/pdf"


def test_uploaded_text_file_reaches_the_connected_workspace(monkeypatch, tmp_path: Path):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.setattr(api, "workspace", api.Workspace())
    monkeypatch.setattr(api, "UPLOAD_ROOT", tmp_path / "uploads")
    client = TestClient(api.app)

    response = client.post(
        "/api/materials",
        files={"files": ("calculus-notes.txt", b"A derivative measures instantaneous change.", "text/plain")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["reports"][0]["status"] == "indexed"
    assert body["reports"][0]["type"] == "document"
    assert body["workspace"]["source_count"] == 1
    assert api.workspace.chunks[0].citation.section == "paragraph 1"


def test_web_link_endpoint_indexes_a_fetched_page(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from studybuddy.ingestion.web import RemoteResource

    monkeypatch.setattr(api, "workspace", api.Workspace())
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
    assert body["report"]["type"] == "web page"
    assert api.workspace.chunks[0].citation.section == "Routing"
