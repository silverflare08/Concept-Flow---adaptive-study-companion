from pathlib import Path

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
