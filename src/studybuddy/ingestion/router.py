"""Route supported local files into citation-preserving modality parsers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .documents import ingest_csv_document, ingest_docx, ingest_odt_document, ingest_rtf_document, ingest_text_document
from .images import describe_study_image, ingest_image
from .models import SourceSegment, SourceType
from .pdf import ingest_pdf
from .slides import ingest_slides
from .video import transcribe_video
from .extended import EXTENDED_TYPES, read_extended

PDF_TYPES = {".pdf"}
SLIDE_TYPES = {".pptx"}
DOCUMENT_TYPES = {".docx", ".txt", ".md", ".markdown", ".csv", ".rtf", ".odt"}
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
AUDIO_TYPES = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
VIDEO_TYPES = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
SUPPORTED_FILE_TYPES = PDF_TYPES | SLIDE_TYPES | DOCUMENT_TYPES | IMAGE_TYPES | AUDIO_TYPES | VIDEO_TYPES | EXTENDED_TYPES


@dataclass(frozen=True)
class ParsedMaterial:
    kind: str
    segments: list[SourceSegment]


def parse_study_file(
    path: str | Path, *, source_id: str, source_name: str, source_uri: str | None,
    archive_depth: int = 0, content_sha256: str | None = None,
) -> ParsedMaterial:
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix in EXTENDED_TYPES:
        return ParsedMaterial(suffix.lstrip('.'), read_extended(
            file_path, source_id=source_id, source_name=source_name,
            source_uri=source_uri, depth=archive_depth,
        ))
    if suffix in PDF_TYPES:
        parsed = ingest_pdf(
            file_path, source_id=source_id, source_name=source_name, source_uri=source_uri,
            image_output_dir=file_path.parent / "images" / source_id,
            describe_image=describe_study_image,
        )
        return ParsedMaterial("pdf", parsed.segments)
    if suffix in SLIDE_TYPES:
        parsed = ingest_slides(
            file_path, source_id=source_id, source_name=source_name, source_uri=source_uri,
            image_output_dir=file_path.parent / "images" / source_id,
            describe_image=describe_study_image,
        )
        return ParsedMaterial("slides", parsed.segments)
    if suffix == ".docx":
        return ParsedMaterial("document", ingest_docx(
            file_path, source_id=source_id, source_name=source_name, source_uri=source_uri,
        ).segments)
    if suffix in {".txt", ".md", ".markdown"}:
        return ParsedMaterial("document", ingest_text_document(
            file_path, source_id=source_id, source_name=source_name, source_uri=source_uri,
        ).segments)
    if suffix == ".csv":
        return ParsedMaterial("document", ingest_csv_document(
            file_path, source_id=source_id, source_name=source_name, source_uri=source_uri,
        ).segments)
    if suffix == ".rtf":
        return ParsedMaterial("document", ingest_rtf_document(
            file_path, source_id=source_id, source_name=source_name, source_uri=source_uri,
        ).segments)
    if suffix == ".odt":
        return ParsedMaterial("document", ingest_odt_document(
            file_path, source_id=source_id, source_name=source_name, source_uri=source_uri,
        ).segments)
    if suffix in IMAGE_TYPES:
        return ParsedMaterial("image / handwriting", ingest_image(
            file_path, source_id=source_id, source_name=source_name, source_uri=source_uri,
        ))
    if suffix in AUDIO_TYPES | VIDEO_TYPES:
        source_type = SourceType.AUDIO if suffix in AUDIO_TYPES else SourceType.VIDEO
        segments = transcribe_video(
            file_path, source_id=source_id, source_name=source_name, source_uri=source_uri,
            model_size=os.getenv("WHISPER_MODEL", "base"), source_type=source_type,
            content_sha256=content_sha256,
        )
        return ParsedMaterial(source_type.value, segments)
    raise ValueError("Unsupported file type.")
