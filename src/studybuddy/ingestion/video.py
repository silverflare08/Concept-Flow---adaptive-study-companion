"""Timestamp-preserving video transcript ingestion.

`faster-whisper` is optional at import time so the core project can be tested
without a model download. Production calls `transcribe_video`, which runs the
model directly on the user-uploaded video--there is no manual transcript step.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .models import CitationAnchor, EvidenceKind, SourceSegment, SourceType


@dataclass(frozen=True)
class TranscriptSpan:
    text: str
    start_seconds: float
    end_seconds: float

    def __post_init__(self) -> None:
        if self.start_seconds < 0 or self.end_seconds < self.start_seconds:
            raise ValueError("transcript timestamps must be non-negative and ordered")
        if not self.text.strip():
            raise ValueError("transcript text cannot be empty")


def segments_from_transcript(
    spans: Iterable[TranscriptSpan],
    *,
    source_id: str,
    source_name: str,
    source_uri: str | None = None,
) -> list[SourceSegment]:
    """Convert timestamped speech into individual, directly citeable segments."""
    return [
        SourceSegment(
            text=span.text.strip(),
            citation=CitationAnchor(
                source_id=source_id,
                source_name=source_name,
                source_type=SourceType.VIDEO,
                source_uri=source_uri,
                start_seconds=span.start_seconds,
                end_seconds=span.end_seconds,
            ),
            evidence_kind=EvidenceKind.TRANSCRIPT,
        )
        for span in spans
    ]


def transcribe_video(
    path: str | Path,
    *,
    source_id: str,
    source_name: str,
    source_uri: str | None = None,
    model_size: str = "base",
) -> list[SourceSegment]:
    """Run local faster-whisper and return timestamp-cited transcript segments."""
    video_path = Path(path)
    if not video_path.is_file():
        raise FileNotFoundError(f"Video not found: {video_path}")
    try:
        from faster_whisper import WhisperModel
    except ImportError as error:
        raise RuntimeError(
            "Video transcription requires the 'ingestion' dependency group. "
            "Install it with: pip install -e '.[ingestion]'"
        ) from error

    model = WhisperModel(model_size, device="auto", compute_type="int8")
    raw_segments, _ = model.transcribe(str(video_path), vad_filter=True)
    spans = [
        TranscriptSpan(text=segment.text, start_seconds=segment.start, end_seconds=segment.end)
        for segment in raw_segments
        if segment.text.strip()
    ]
    return segments_from_transcript(
        spans, source_id=source_id, source_name=source_name, source_uri=source_uri
    )
