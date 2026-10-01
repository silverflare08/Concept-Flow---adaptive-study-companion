import pytest

from studybuddy.ingestion.video import TranscriptSpan, segments_from_transcript


def test_transcript_segments_keep_precise_video_timestamps() -> None:
    segments = segments_from_transcript(
        [TranscriptSpan(text="DFS explores before backtracking.", start_seconds=65.2, end_seconds=68.8)],
        source_id="dfs-video",
        source_name="DFS lecture",
        source_uri="https://example.edu/dfs",
    )

    citation = segments[0].citation
    assert citation.start_seconds == 65.2
    assert citation.end_seconds == 68.8
    assert citation.target_uri().endswith("#t=65")


def test_transcript_span_rejects_backwards_timestamps() -> None:
    with pytest.raises(ValueError, match="ordered"):
        TranscriptSpan(text="invalid", start_seconds=4, end_seconds=3)
