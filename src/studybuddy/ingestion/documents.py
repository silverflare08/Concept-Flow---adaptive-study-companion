"""Citation-preserving ingestion for DOCX and plain-text study documents."""

from __future__ import annotations

from dataclasses import dataclass
import csv
import re
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


def ingest_csv_document(
    path: str | Path, *, source_id: str, source_name: str, source_uri: str | None = None,
) -> DocumentIngestionResult:
    """Turn each non-empty CSV row into a labelled, retrievable study block."""
    with Path(path).open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        return _segments_from_blocks([], source_id=source_id, source_name=source_name, source_uri=source_uri)
    headers = [cell.strip() or f"column {index + 1}" for index, cell in enumerate(rows[0])]
    blocks = []
    for row_number, row in enumerate(rows[1:] or rows, start=2 if len(rows) > 1 else 1):
        values = [f"{headers[index] if index < len(headers) else f'column {index + 1}'}: {cell.strip()}" for index, cell in enumerate(row) if cell.strip()]
        if values:
            blocks.append(f"Row {row_number}. " + "; ".join(values))
    return _segments_from_blocks(blocks, source_id=source_id, source_name=source_name, source_uri=source_uri)


def ingest_rtf_document(
    path: str | Path, *, source_id: str, source_name: str, source_uri: str | None = None,
) -> DocumentIngestionResult:
    """Extract readable text from ordinary RTF notes without external converters."""
    raw = Path(path).read_text(encoding="latin-1", errors="replace")
    text_value = re.sub(r"\\par[d]?\b", "\n\n", raw)
    text_value = re.sub(r"\\'[0-9a-fA-F]{2}", " ", text_value)
    text_value = re.sub(r"\\[A-Za-z]+-?\d* ?", "", text_value)
    text_value = text_value.replace("{", "").replace("}", "")
    blocks = [block.strip() for block in text_value.split("\n\n") if block.strip()]
    return _segments_from_blocks(blocks, source_id=source_id, source_name=source_name, source_uri=source_uri)


def ingest_odt_document(
    path: str | Path, *, source_id: str, source_name: str, source_uri: str | None = None,
) -> DocumentIngestionResult:
    """Read paragraphs from the standard OpenDocument content.xml package."""
    try:
        with ZipFile(path) as archive:
            document = ElementTree.fromstring(archive.read("content.xml"))
    except (BadZipFile, KeyError, ElementTree.ParseError) as error:
        raise ValueError("This ODT file is damaged or unsupported. Open it and save a fresh copy, then retry.") from error
    blocks = []
    for node in document.iter():
        if node.tag.endswith(("}p", "}h")):
            value = "".join(node.itertext()).strip()
            if value:
                blocks.append(value)
    return _segments_from_blocks(blocks, source_id=source_id, source_name=source_name, source_uri=source_uri)
