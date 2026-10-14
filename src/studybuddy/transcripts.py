"""Organize already-extracted speech without generating or translating content."""
from studybuddy.ingestion.models import EvidenceKind, KnowledgeChunk


def timestamp(seconds: float) -> str:
    value = max(0, int(seconds))
    hours, remainder = divmod(value, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"


def organized_transcript(chunks: list[KnowledgeChunk], source_id: str) -> dict[str, object]:
    selected = sorted([chunk for chunk in chunks if chunk.citation.source_id == source_id
                       and chunk.evidence_kind is EvidenceKind.TRANSCRIPT],
                      key=lambda chunk: chunk.citation.start_seconds or 0)
    if not selected:
        raise ValueError("No stored speech transcript was found for this material. Upload and transcribe the recording first.")
    entries = []
    previous = None
    previous_words = []
    for chunk in selected:
        words = chunk.text.split()
        same_location = previous is not None and previous.citation == chunk.citation
        overlap = 0
        if same_location:
            for size in range(min(len(previous_words), len(words)), 0, -1):
                if previous_words[-size:] == words[:size]:
                    overlap = size
                    break
        text = " ".join(words[overlap:]) if overlap else chunk.text.strip()
        if text:
            if same_location:
                entries[-1]["text"] += " " + text
            else:
                start = chunk.citation.start_seconds or 0
                end = chunk.citation.end_seconds
                entries.append({"start_seconds": start, "end_seconds": end,
                    "timestamp": timestamp(start) + (f" - {timestamp(end)}" if end is not None else ""),
                    "text": text, "target_uri": chunk.citation.target_uri()})
        previous, previous_words = chunk, words
    return {"source_id": source_id, "source_name": selected[0].citation.source_name,
            "kind": "original_language_transcript", "entries": entries,
            "notice": "Full stored speech transcript in the recording's original language. Not a summary, translation or verified lesson. Speech recognition can contain errors."}
