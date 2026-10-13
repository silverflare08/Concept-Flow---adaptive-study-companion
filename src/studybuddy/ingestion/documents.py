"""Citation-preserving ingestion for DOCX and plain-text study documents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree

from .models import CitationAnchor, EvidenceKind, SourceSegment, SourceType


@dataclass(frozen=True)
class DocumentIngestionResult:
    source_id: str
    segments: list[SourceSegment]


def _segments_from_blocks(
    blocks: list[str], *, source_id: str, source_name: str, source_uri: str | None,
) -> DocumentIngestionResult:
    segments = [
        SourceSegment(
            text=text,
            citation=CitationAnchor(
                source_id=source_id, source_name=source_name, source_type=SourceType.DOCUMENT,
                source_uri=source_uri, section=f"paragraph {number}",
            ),
            evidence_kind=EvidenceKind.TEXT,
        )
        for number, text in enumerate((block.strip() for block in blocks), start=1)
        if text
    ]
    return DocumentIngestionResult(source_id=source_id, segments=segments)


def ingest_docx(
    path: str | Path, *, source_id: str, source_name: str, source_uri: str | None = None,
) -> DocumentIngestionResult:
    """Read Word paragraphs and table cells directly from the DOCX XML package."""
    try:
        with ZipFile(path) as archive:
            document = ElementTree.fromstring(archive.read("word/document.xml"))
    except (BadZipFile, KeyError, ElementTree.ParseError) as error:
        raise ValueError("This DOCX file is damaged or is an older .doc file. Save it as .docx and retry.") from error
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    blocks = []
    for paragraph in document.iter(f"{namespace}p"):
        text = "".join(node.text or "" for node in paragraph.iter(f"{namespace}t")).strip()
        if text:
            blocks.append(text)
    return _segments_from_blocks(blocks, source_id=source_id, source_name=source_name, source_uri=source_uri)


def ingest_text_document(
    path: str | Path, *, source_id: str, source_name: str, source_uri: str | None = None,
) -> DocumentIngestionResult:
    text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    blocks = [block for block in text.replace("\r\n", "\n").split("\n\n") if block.strip()]
    return _segments_from_blocks(blocks, source_id=source_id, source_name=source_name, source_uri=source_uri)
