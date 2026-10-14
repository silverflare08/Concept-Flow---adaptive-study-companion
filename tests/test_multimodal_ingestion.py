from pathlib import Path
from zipfile import ZipFile

import pytest

from studybuddy.ingestion.documents import ingest_csv_document, ingest_docx, ingest_odt_document, ingest_rtf_document, ingest_text_document
from studybuddy.ingestion.images import ingest_image
from studybuddy.ingestion.models import EvidenceKind, SourceType
from studybuddy.ingestion.router import SUPPORTED_FILE_TYPES
from studybuddy.ingestion.video import TranscriptSpan, segments_from_transcript
from studybuddy.ingestion.web import ingest_web_page, validate_public_url


def test_docx_ingestion_preserves_paragraph_locations(tmp_path: Path) -> None:
    document = tmp_path / "lesson.docx"
    xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body>
        <w:p><w:r><w:t>Gradient descent updates model weights.</w:t></w:r></w:p>
        <w:p><w:r><w:t>A learning rate controls step size.</w:t></w:r></w:p>
      </w:body>
    </w:document>"""
    with ZipFile(document, "w") as archive:
        archive.writestr("word/document.xml", xml)

    result = ingest_docx(document, source_id="doc-1", source_name="lesson.docx")

    assert [segment.text for segment in result.segments] == [
        "Gradient descent updates model weights.",
        "A learning rate controls step size.",
    ]
    assert result.segments[1].citation.section == "paragraph 2"
    assert result.segments[1].citation.source_type is SourceType.DOCUMENT


def test_plain_text_ingestion_splits_readable_blocks(tmp_path: Path) -> None:
    document = tmp_path / "notes.md"
    document.write_text("# Probability\n\nConditional probability depends on known evidence.", encoding="utf-8")

    result = ingest_text_document(document, source_id="text-1", source_name="notes.md")

    assert len(result.segments) == 2
    assert result.segments[1].citation.section == "paragraph 2"


def test_csv_rtf_and_odt_documents_are_readable(tmp_path: Path) -> None:
    csv_path = tmp_path / "marks.csv"
    csv_path.write_text("Topic,Score\nAlgebra,80", encoding="utf-8")
    assert "Topic: Algebra" in ingest_csv_document(csv_path, source_id="csv", source_name=csv_path.name).segments[0].text

    rtf_path = tmp_path / "notes.rtf"
    rtf_path.write_text(r"{\rtf1\ansi Probability\par Conditional probability uses evidence.}", encoding="latin-1")
    assert "Probability" in " ".join(segment.text for segment in ingest_rtf_document(rtf_path, source_id="rtf", source_name=rtf_path.name).segments)

    odt_path = tmp_path / "notes.odt"
    with ZipFile(odt_path, "w") as archive:
        archive.writestr("content.xml", '<office:document-content xmlns:office="urn:o" xmlns:text="urn:t"><office:body><text:p>Eigenvectors preserve direction.</text:p></office:body></office:document-content>')
    assert ingest_odt_document(odt_path, source_id="odt", source_name=odt_path.name).segments[0].text == "Eigenvectors preserve direction."


def test_image_ingestion_uses_injected_local_vision_description(tmp_path: Path) -> None:
    image = tmp_path / "handwritten-note.png"
    image.write_bytes(b"test-image")

    segments = ingest_image(
        image,
        source_id="image-1",
        source_name=image.name,
        source_uri="/api/sources/image-1",
        describe_image=lambda path: "TRANSCRIPTION\nBayes theorem\nVISUAL EXPLANATION\nTwo connected events.",
    )

    assert segments[0].citation.source_type is SourceType.IMAGE
    assert segments[0].evidence_kind is EvidenceKind.VISION
    assert "Bayes theorem" in segments[0].text


def test_audio_transcript_has_timestamp_and_audio_source_type() -> None:
    segments = segments_from_transcript(
        [TranscriptSpan(text="The derivative is a rate of change.", start_seconds=12.5, end_seconds=16.0)],
        source_id="audio-1",
        source_name="voice-note.mp3",
        source_uri="/api/sources/audio-1",
        source_type=SourceType.AUDIO,
    )

    assert segments[0].citation.source_type is SourceType.AUDIO
    assert segments[0].citation.label().endswith("00:12")
    assert segments[0].citation.target_uri().endswith("#t=12")


def test_web_page_ingestion_keeps_heading_as_section() -> None:
    name, segments = ingest_web_page(
        b"<html><head><title>Linear Algebra</title><style>ignore me</style></head>"
        b"<body><h2>Eigenvectors</h2><p>An eigenvector keeps its direction under a linear transformation.</p>"
        b"<script>also ignore me</script></body></html>",
        source_id="web-1",
        source_name="page.html",
        source_uri="https://example.com/linear-algebra",
    )

    assert name == "Linear Algebra"
    assert len(segments) == 1
    assert segments[0].citation.section == "Eigenvectors"
    assert segments[0].citation.target_uri() == "https://example.com/linear-algebra"


def test_private_urls_are_rejected() -> None:
    with pytest.raises(ValueError, match="Private, local and reserved"):
        validate_public_url("http://127.0.0.1/private-notes")


def test_router_advertises_all_student_material_types() -> None:
    expected = {".pdf", ".pptx", ".docx", ".odt", ".rtf", ".txt", ".md", ".csv", ".png", ".jpg", ".mp3", ".wav", ".mp4", ".webm"}
    assert expected <= SUPPORTED_FILE_TYPES
