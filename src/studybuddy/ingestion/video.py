"""Timestamp-preserving video transcript ingestion.

`faster-whisper` is optional at import time so the core project can be tested
without a model download. Production calls `transcribe_video`, which runs the
model directly on the user-uploaded video--there is no manual transcript step.
"""

from __future__ import annotations

import os
import hashlib
import json
from functools import lru_cache
from threading import Lock
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .models import CitationAnchor, EvidenceKind, SourceSegment, SourceType
from studybuddy.cancellation import check_cancelled
from studybuddy.local_cache import cache_path, read_cached, save_cached

_model_lock = Lock()

@lru_cache(maxsize=1)
def _speech_model(model_size: str, device: str, compute_type: str):
    from faster_whisper import WhisperModel
    return WhisperModel(model_size, device=device, compute_type=compute_type)


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
    source_type: SourceType = SourceType.VIDEO,
) -> list[SourceSegment]:
    """Convert timestamped speech into individual, directly citeable segments."""
    return [
        SourceSegment(
            text=span.text.strip(),
            citation=CitationAnchor(
                source_id=source_id,
                source_name=source_name,
                source_type=source_type,
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
    model_size: str | None = None,
    source_type: SourceType = SourceType.VIDEO,
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

    device = os.getenv("WHISPER_DEVICE", "cpu")
    compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    model_size = model_size or os.getenv("WHISPER_MODEL", "base")
    beam_size = int(os.getenv("WHISPER_BEAM_SIZE", "5"))
    if not 1 <= beam_size <= 10:
        raise ValueError("WHISPER_BEAM_SIZE must be between 1 and 10.")
    digest = hashlib.sha256()
    with video_path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            check_cancelled()
            digest.update(block)
    cached_path = cache_path("transcripts", {
        "version": 1, "sha256": digest.hexdigest(), "model": model_size,
        "device": device, "compute_type": compute_type, "beam_size": beam_size,
    })
    spans = None
    cached = read_cached(cached_path)
    if cached:
        try:
            spans = [TranscriptSpan(**item) for item in json.loads(cached)]
            if not spans:
                spans = None
        except (ValueError, TypeError):
            spans = None
    if spans is None:
        # Reuse the loaded model. Serialize inference to avoid CPU/memory contention.
        with _model_lock:
            check_cancelled()
            model = _speech_model(model_size, device, compute_type)
            raw_segments, _ = model.transcribe(str(video_path), vad_filter=True, beam_size=beam_size)
            spans = []
            for segment in raw_segments:
                check_cancelled()
                if segment.text.strip():
                    spans.append(TranscriptSpan(segment.text, segment.start, segment.end))
        if spans:
            save_cached(cached_path, json.dumps([{
                "text": span.text, "start_seconds": span.start_seconds, "end_seconds": span.end_seconds,
            } for span in spans], ensure_ascii=False))
    return segments_from_transcript(
        spans, source_id=source_id, source_name=source_name, source_uri=source_uri,
        source_type=source_type,
    )
