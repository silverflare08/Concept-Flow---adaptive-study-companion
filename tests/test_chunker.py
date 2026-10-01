from studybuddy.ingestion.chunker import chunk_segments
from studybuddy.ingestion.models import CitationAnchor, SourceSegment, SourceType


def test_chunks_keep_the_original_page_anchor_and_overlap() -> None:
    segment = SourceSegment(
        text="one two three four five six seven eight",
        citation=CitationAnchor(
            source_id="book-1", source_name="Algorithms", source_type=SourceType.PDF, page=7
        ),
    )

    chunks = chunk_segments([segment], chunk_size=4, overlap=1)

    assert [chunk.text for chunk in chunks] == [
        "one two three four",
        "four five six seven",
        "seven eight",
    ]
    assert all(chunk.citation.page == 7 for chunk in chunks)
    assert len({chunk.chunk_id for chunk in chunks}) == 3


def test_rejects_invalid_chunk_configuration() -> None:
    segment = SourceSegment(
        text="content",
        citation=CitationAnchor(
            source_id="slides", source_name="Week 1", source_type=SourceType.SLIDE, slide=1
        ),
    )

    try:
        chunk_segments([segment], chunk_size=5, overlap=5)
    except ValueError as error:
        assert "overlap" in str(error)
    else:
        raise AssertionError("invalid overlap must fail")
