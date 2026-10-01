"""Stable data contracts shared by ingestion, retrieval, and citations."""

from __future__ import annotations

from enum import StrEnum
from pydantic import BaseModel, Field, model_validator


class SourceType(StrEnum):
    PDF = "pdf"
    SLIDE = "slide"
    VIDEO = "video"


class EvidenceKind(StrEnum):
    """How the evidence was obtained from a source location."""

    TEXT = "text"
    OCR = "ocr"
    FIGURE_DESCRIPTION = "figure_description"
    TRANSCRIPT = "transcript"


class CitationAnchor(BaseModel):
    """A precise, user-visible location in an original learning resource."""

    source_id: str
    source_name: str
    source_type: SourceType
    source_uri: str | None = None
    page: int | None = Field(default=None, ge=1)
    slide: int | None = Field(default=None, ge=1)
    start_seconds: float | None = Field(default=None, ge=0)
    end_seconds: float | None = Field(default=None, ge=0)
    section: str | None = None

    @model_validator(mode="after")
    def has_location_for_source_type(self) -> "CitationAnchor":
        if self.source_type is SourceType.PDF and self.page is None:
            raise ValueError("A PDF citation needs a page number")
        if self.source_type is SourceType.SLIDE and self.slide is None:
            raise ValueError("A slide citation needs a slide number")
        if self.source_type is SourceType.VIDEO and self.start_seconds is None:
            raise ValueError("A video citation needs a start timestamp")
        return self

    def label(self) -> str:
        if self.source_type is SourceType.PDF:
            location = f"p. {self.page}"
        elif self.source_type is SourceType.SLIDE:
            location = f"slide {self.slide}"
        else:
            minutes, seconds = divmod(int(self.start_seconds or 0), 60)
            location = f"{minutes:02d}:{seconds:02d}"
        return f"{self.source_name}, {location}"

    def target_uri(self) -> str | None:
        """Return a location-aware target the UI can open without inventing one."""
        if self.source_uri is None:
            return None
        if self.source_type is SourceType.PDF:
            return f"{self.source_uri}#page={self.page}"
        if self.source_type is SourceType.SLIDE:
            return f"{self.source_uri}#page={self.slide}"
        return f"{self.source_uri}#t={int(self.start_seconds or 0)}"


class SourceSegment(BaseModel):
    """Text emitted by a parser before it is split for retrieval."""

    text: str = Field(min_length=1)
    citation: CitationAnchor
    evidence_kind: EvidenceKind = EvidenceKind.TEXT
    concepts: list[str] = Field(default_factory=list)
    image_path: str | None = None


class KnowledgeChunk(BaseModel):
    """The atomic evidence object retrievers return and the LLM cites."""

    chunk_id: str
    text: str = Field(min_length=1)
    citation: CitationAnchor
    token_count: int = Field(ge=1)
    evidence_kind: EvidenceKind = EvidenceKind.TEXT
    concepts: list[str] = Field(default_factory=list)
