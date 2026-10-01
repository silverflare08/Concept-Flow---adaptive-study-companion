from studybuddy.ingestion.models import CitationAnchor, KnowledgeChunk, SourceType
from studybuddy.retrieval.bm25 import BM25Index


def _chunk(chunk_id: str, text: str, page: int) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=chunk_id,
        text=text,
        token_count=len(text.split()),
        citation=CitationAnchor(
            source_id="graphs", source_name="Graph textbook", source_type=SourceType.PDF, page=page
        ),
    )


def test_bm25_returns_the_cited_chunk_that_discusses_the_query() -> None:
    index = BM25Index(
        [
            _chunk("bfs", "Breadth first search uses a queue and discovers graph layers.", 4),
            _chunk("dfs", "Depth first search uses recursion or an explicit stack.", 8),
        ]
    )

    results = index.search("Which traversal uses a queue?")

    assert results[0].chunk.chunk_id == "bfs"
    assert results[0].chunk.citation.page == 4
    assert results[0].retriever == "bm25"


def test_bm25_returns_no_evidence_for_an_off_material_query() -> None:
    index = BM25Index([_chunk("bfs", "Breadth first search uses a queue.", 4)])
    assert index.search("Explain quantum entanglement") == []
