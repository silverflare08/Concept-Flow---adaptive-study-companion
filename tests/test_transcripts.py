import pytest
from studybuddy import api
from studybuddy.ingestion.models import CitationAnchor, EvidenceKind, KnowledgeChunk, SourceType
from studybuddy.transcripts import organized_transcript


def speech(text, start=60, source_id="lecture", chunk_id="speech"):
    return KnowledgeChunk(chunk_id=chunk_id, text=text, token_count=len(text.split()), evidence_kind=EvidenceKind.TRANSCRIPT,
        citation=CitationAnchor(source_id=source_id, source_name="Physics.mp4", source_type=SourceType.VIDEO,
                               source_uri="/api/sources/lecture", start_seconds=start, end_seconds=start + 30))


def test_transcript_keeps_all_speech_and_timestamps_without_repeating_chunk_overlap():
    chunks = [speech("one two three", chunk_id="first"), speech("three four five", chunk_id="second"),
              speech("Next concept.", start=120, chunk_id="third"), speech("Other source.", source_id="other")]
    result = organized_transcript(chunks, "lecture")
    assert [entry["text"] for entry in result["entries"]] == ["one two three four five", "Next concept."]
    assert result["entries"][0]["timestamp"] == "01:00 - 01:30"
    assert result["entries"][0]["target_uri"] == "/api/sources/lecture#t=60"
    assert result["kind"] == "original_language_transcript"


def test_transcript_endpoints_download_stored_text_without_model_calls(monkeypatch):
    monkeypatch.setattr(api, "workspace", api.Workspace(chunks=[speech("Waves transfer energy.")]))
    monkeypatch.setattr(api, "call_ollama_long", lambda *args: pytest.fail("Transcript preview must not generate a lesson"))
    assert api.get_material_transcript("lecture")["entries"][0]["text"] == "Waves transfer energy."
    response = api.download_material_transcript("lecture", format="txt")
    assert b"Waves transfer energy." in response.body and b"01:00" in response.body
    assert "transcript.txt" in response.headers["content-disposition"]


def test_missing_transcript_is_not_presented_as_a_lesson():
    with pytest.raises(ValueError, match="No stored speech transcript"):
        organized_transcript([], "missing")
