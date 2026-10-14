"""Reduce duplicated retrieval overlap without altering stored text or citations."""
from studybuddy.ingestion.models import KnowledgeChunk


def evidence_texts(chunks: list[KnowledgeChunk]) -> list[str]:
    output = []
    previous = None
    previous_words = []
    for chunk in chunks:
        words = chunk.text.split()
        overlap = 0
        if previous is not None and previous.citation == chunk.citation and previous.evidence_kind == chunk.evidence_kind:
            for size in range(min(len(previous_words), len(words)), 7, -1):
                if previous_words[-size:] == words[:size]:
                    overlap = size
                    break
        # Keep every evidence unit addressable. Only exact, adjacent duplicated words
        # at the same source location are omitted from the model context.
        output.append(" ".join(words[overlap:]) if overlap else chunk.text)
        previous, previous_words = chunk, words
    return output
