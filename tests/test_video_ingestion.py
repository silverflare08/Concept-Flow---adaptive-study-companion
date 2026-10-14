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


def test_transcription_reuses_content_but_rebuilds_citations(tmp_path, monkeypatch) -> None:
    from types import SimpleNamespace
    from studybuddy.ingestion import video
    monkeypatch.setenv("CONCEPTFLOW_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("WHISPER_BEAM_SIZE", "1")
    calls = []
    class Model:
        def transcribe(self, path, **options):
            calls.append(options)
            return iter([SimpleNamespace(text="Energy is conserved.", start=1, end=3)]), None
    monkeypatch.setattr(video, "_speech_model", lambda *args: Model())
    recording = tmp_path / "audio.wav"
    recording.write_bytes(b"mock media for orchestration test")
    first = video.transcribe_video(recording, source_id="a", source_name="First")
    second = video.transcribe_video(recording, source_id="b", source_name="Second")
    assert len(calls) == 1 and calls[0]["beam_size"] == 1
    assert first[0].text == second[0].text
    assert second[0].citation.source_id == "b"
    assert second[0].citation.start_seconds == 1
    recording.write_bytes(b"changed media")
    video.transcribe_video(recording, source_id="c", source_name="Changed")
    assert len(calls) == 2
