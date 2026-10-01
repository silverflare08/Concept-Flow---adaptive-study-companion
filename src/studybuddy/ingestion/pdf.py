"""PDF ingestion with page-accurate source anchors.

The implementation starts with robust text extraction via pypdf. Visual assets
are extracted as individual files and represented as evidence segments; an
OCR/vision description stage can enrich those segments without breaking the
citation contract.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from pypdf import PdfReader

from .models import CitationAnchor, EvidenceKind, SourceSegment, SourceType

ImageDescriber = Callable[[Path], str | None]


@dataclass(frozen=True)
class PdfIngestionResult:
    """Parser output plus traceability data needed by the upload workflow."""

    source_id: str
    source_sha256: str
    segments: list[SourceSegment]
    extracted_images: list[Path]


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _safe_image_extension(image_name: str) -> str:
    suffix = Path(image_name).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".jp2", ".tiff"} else ".bin"


def ingest_pdf(
    path: str | Path,
    *,
    source_id: str,
    source_name: str,
    source_uri: str | None = None,
    image_output_dir: str | Path | None = None,
    describe_image: ImageDescriber | None = None,
) -> PdfIngestionResult:
    """Extract text and figures from one PDF without losing page citations.

    `describe_image` is deliberately injected. In production it may be an OCR
    plus multimodal-model pipeline; in tests it can be a deterministic stub.
    The parser only stores a description when it came from that real pipeline.
    """
    pdf_path = Path(path)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    image_dir = Path(image_output_dir) if image_output_dir else pdf_path.parent / "images"
    reader = PdfReader(str(pdf_path))
    segments: list[SourceSegment] = []
    extracted_images: list[Path] = []

    for page_number, page in enumerate(reader.pages, start=1):
        anchor = CitationAnchor(
            source_id=source_id,
            source_name=source_name,
            source_type=SourceType.PDF,
            source_uri=source_uri,
            page=page_number,
        )
        text = (page.extract_text() or "").strip()
        if text:
            segments.append(SourceSegment(text=text, citation=anchor, evidence_kind=EvidenceKind.TEXT))

        for image_index, image in enumerate(page.images, start=1):
            image_dir.mkdir(parents=True, exist_ok=True)
            output = image_dir / f"{source_id}-p{page_number}-img{image_index}{_safe_image_extension(image.name)}"
            output.write_bytes(image.data)
            extracted_images.append(output)

            if describe_image is None:
                continue
            description = describe_image(output)
            if description and description.strip():
                segments.append(
                    SourceSegment(
                        text=description.strip(),
                        citation=anchor,
                        evidence_kind=EvidenceKind.FIGURE_DESCRIPTION,
                        image_path=str(output),
                    )
                )

    return PdfIngestionResult(
        source_id=source_id,
        source_sha256=_sha256(pdf_path),
        segments=segments,
        extracted_images=extracted_images,
    )
