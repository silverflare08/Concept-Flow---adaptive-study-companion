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
    monkeypatch.setenv("WHISPER_BATCH_SIZE", "1")
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


def test_batched_transcription_reports_real_timestamp_progress(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from studybuddy.ingestion import video
    monkeypatch.setenv("CONCEPTFLOW_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("WHISPER_BATCH_SIZE", "4")
    calls, updates = [], []
    class Runner:
        def transcribe(self, path, **options):
            calls.append(options)
            return iter([SimpleNamespace(text="A wave oscillates.", start=2, end=7)]), SimpleNamespace(duration=10)
    monkeypatch.setattr(video, "_speech_model", lambda *args: object())
    monkeypatch.setattr(video, "_transcription_runner", lambda model, batch_size: Runner())
    recording = tmp_path / "lecture.mp4"
    recording.write_bytes(b"mock lecture")
    segments = video.transcribe_video(recording, source_id="lecture", source_name="Lecture",
                                      on_progress=lambda done, total: updates.append((done, total)))
    assert calls[0]["batch_size"] == 4
    assert updates == [(0, 10), (7, 10)]
    assert segments[0].citation.end_seconds == 7


def test_invalid_transcription_batch_size_is_rejected(tmp_path, monkeypatch):
    from studybuddy.ingestion import video
    monkeypatch.setenv("WHISPER_BATCH_SIZE", "0")
    recording = tmp_path / "audio.wav"
    recording.write_bytes(b"mock")
    with pytest.raises(ValueError, match="WHISPER_BATCH_SIZE"):
        video.transcribe_video(recording, source_id="a", source_name="Audio")
