"""Deterministic citation-preserving chunking for course materials."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

from .models import KnowledgeChunk, SourceSegment


def _tokens(text: str) -> list[str]:
    return re.findall(r"\S+", text.strip())


def _chunk_id(segment: SourceSegment, ordinal: int, text: str) -> str:
    fingerprint = hashlib.sha256(
        f"{segment.citation.source_id}:{ordinal}:{text}".encode()
    ).hexdigest()[:12]
    return f"{segment.citation.source_id}-{fingerprint}"


def chunk_segments(
    segments: Iterable[SourceSegment], *, chunk_size: int = 280, overlap: int = 40
) -> list[KnowledgeChunk]:
    """Split parser output into overlapping word windows without losing anchors.

    Chunks never cross parser segments. This deliberately avoids citations that
    point to two PDF pages or two video timestamp ranges at once.
    """
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    if not 0 <= overlap < chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")

    output: list[KnowledgeChunk] = []
    ordinal = 0
    step = chunk_size - overlap
    for segment in segments:
        words = _tokens(segment.text)
        for start in range(0, len(words), step):
            window = words[start : start + chunk_size]
            if not window:
                continue
            text = " ".join(window)
            output.append(
                KnowledgeChunk(
                    chunk_id=_chunk_id(segment, ordinal, text),
                    text=text,
                    citation=segment.citation,
                    token_count=len(window),
                    evidence_kind=segment.evidence_kind,
                    concepts=segment.concepts,
                )
            )
            ordinal += 1
            if start + chunk_size >= len(words):
                break
    return output
