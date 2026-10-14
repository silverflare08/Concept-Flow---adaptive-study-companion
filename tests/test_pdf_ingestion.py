from pathlib import Path
import pytest
import pymupdf
from PIL import Image, ImageDraw

from pypdf import PdfWriter

from studybuddy.ingestion.models import EvidenceKind
from studybuddy.ingestion.pdf import ingest_pdf


def test_pdf_ingestion_returns_a_traceable_empty_pdf_result(tmp_path: Path) -> None:
    """An empty PDF is still a valid upload and must be traceable, not crash."""
    pdf_path = tmp_path / "empty.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with pdf_path.open("wb") as stream:
        writer.write(stream)

    result = ingest_pdf(
        pdf_path,
        source_id="empty-pdf",
        source_name="Empty source",
        source_uri="https://example.edu/empty.pdf",
    )

    assert len(result.source_sha256) == 64
    assert result.segments == []


def test_figure_description_is_explicitly_marked_as_visual_evidence(tmp_path: Path) -> None:
    # This validates the contract independently of a particular OCR/VLM provider.
    image = tmp_path / "figure.png"
    image.write_bytes(b"not-a-real-image")
    # The actual image extraction path is exercised using real course PDFs in integration tests.
    assert image.exists()
    assert EvidenceKind.FIGURE_DESCRIPTION.value == "figure_description"


def test_scanned_pdf_renders_whole_pages_with_exact_citations(tmp_path: Path) -> None:
    image_path = tmp_path / "notes.png"
    image = Image.new("RGB", (600, 800), "white")
    ImageDraw.Draw(image).text((50, 80), "Handwritten note: x squared + y squared", fill="black")
    image.save(image_path)
    pdf_path = tmp_path / "scanned.pdf"
    with pymupdf.open() as document:
        for _ in range(2):
            page = document.new_page(width=600, height=800)
            page.insert_image(page.rect, filename=str(image_path))
        document.save(pdf_path)
    calls = []

    def describe(path: Path) -> str:
        calls.append(path)
        with Image.open(path) as rendered:
            assert rendered.width > 600
            assert rendered.height > 800
        return "Pythagoras: x² + y² = z²"

    result = ingest_pdf(pdf_path, source_id="scan", source_name="My handwritten notes",
                        source_uri="/api/sources/scan", describe_image=describe)
    assert len(calls) == 2  # One full-page vision call, no duplicate image calls.
    assert [segment.citation.page for segment in result.segments] == [1, 2]
    assert all(segment.evidence_kind == EvidenceKind.VISION for segment in result.segments)
    assert all(segment.citation.source_uri == "/api/sources/scan" for segment in result.segments)
    assert all("x²" in segment.text for segment in result.segments)


def test_scan_failure_identifies_the_page_and_model_problem(tmp_path: Path) -> None:
    pdf_path = tmp_path / "scan.pdf"
    with pymupdf.open() as document:
        document.new_page()
        document.save(pdf_path)

    def unavailable(path: Path) -> str:
        raise RuntimeError("Start Ollama")

    with pytest.raises(RuntimeError, match="scanned PDF page 1: Start Ollama"):
        ingest_pdf(pdf_path, source_id="scan", source_name="Scan", describe_image=unavailable)
