from threading import Event
import pytest
from studybuddy.local_cache import cache_path, read_cached, save_cached
from studybuddy.cancellation import current_cancel, GenerationStopped

def test_cached_answer_is_content_addressed_and_corruption_is_a_miss(monkeypatch,tmp_path):
    monkeypatch.setenv('CONCEPTFLOW_CACHE_DIR',str(tmp_path))
    first=cache_path('vision',{'model':'a','content':'page'})
    assert first != cache_path('vision',{'model':'b','content':'page'})
    assert first != cache_path('vision',{'model':'a','content':'changed'})
    save_cached(first,'An actual transcription')
    assert read_cached(first)=='An actual transcription'
    first.write_text('invalid JSON')
    assert read_cached(first) is None

def test_cancelled_work_cannot_write_a_cache_entry(monkeypatch,tmp_path):
    monkeypatch.setenv('CONCEPTFLOW_CACHE_DIR',str(tmp_path))
    path=cache_path('lessons',{'prompt':'test'})
    event=Event(); event.set(); token=current_cancel.set(event)
    try:
        with pytest.raises(GenerationStopped): save_cached(path,'cancelled answer')
    finally: current_cancel.reset(token)
    assert not path.exists()
