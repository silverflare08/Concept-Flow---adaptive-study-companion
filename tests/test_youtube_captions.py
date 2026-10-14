import json

from studybuddy.ingestion.youtube import caption_spans


def test_json_captions_keep_timestamps_and_merge_repeated_cues():
    content = json.dumps({"events": [
        {"tStartMs": 1000, "dDurationMs": 2000, "segs": [{"utf8": "Energy is conserved."}]},
        {"tStartMs": 2000, "dDurationMs": 2000, "segs": [{"utf8": "Energy is conserved."}]},
        {"tStartMs": 5000, "dDurationMs": 1500, "segs": [{"utf8": "Mass "}, {"utf8": "is measured."}]},
    ]}).encode()
    spans = caption_spans(content, "json3")
    assert len(spans) == 2
    assert (spans[0].start_seconds, spans[0].end_seconds) == (1, 4)
    assert spans[1].text == "Mass is measured."
    assert spans[1].start_seconds == 5


def test_vtt_captions_remove_markup_without_losing_timing():
    spans = caption_spans(b"WEBVTT\n\n00:01:02.500 --> 00:01:05.000\n<c>Force</c> &amp; motion.\n", "vtt")
    assert spans[0].text == "Force & motion."
    assert spans[0].start_seconds == 62.5
