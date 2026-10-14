import io
import json
from PIL import Image
from studybuddy.ingestion import images

def test_handwriting_reader_uses_instruction_model_and_indexes_answer(monkeypatch, tmp_path):
    photo = tmp_path / 'notes.jpg'
    Image.new('RGB', (100, 100), 'white').save(photo)
    monkeypatch.delenv('OLLAMA_VISION_MODEL', raising=False)
    monkeypatch.setenv('CONCEPTFLOW_CACHE_DIR', str(tmp_path / 'cache'))
    payloads = []

    def response(request, **kwargs):
        payloads.append(json.loads(request.data))
        return io.BytesIO(json.dumps({'message': {'content': 'BFS uses a queue. Mark visited vertices.'}}).encode())

    monkeypatch.setattr(images, 'urlopen', response)
    segments = images.ingest_image(photo, source_id='notes', source_name='Notes.jpg', source_uri='/api/sources/notes')
    assert payloads[0]['model'] == 'qwen3-vl:2b-instruct'
    assert payloads[0]['messages'][0]['images']
    assert 'BFS uses a queue' in segments[0].text
    assert segments[0].citation.target_uri() == '/api/sources/notes'


def test_repeated_image_uses_cached_text_with_fresh_citations(monkeypatch, tmp_path):
    photo = tmp_path / 'notes.jpg'
    Image.new('RGB', (100, 100), 'white').save(photo)
    monkeypatch.setenv('CONCEPTFLOW_CACHE_DIR', str(tmp_path / 'cache'))
    calls = []
    def response(request, **kwargs):
        calls.append(request)
        return io.BytesIO(json.dumps({'message': {'content': 'BFS uses a queue.'}}).encode())
    monkeypatch.setattr(images, 'urlopen', response)
    first = images.ingest_image(photo, source_id='first', source_name='First.jpg')
    second = images.ingest_image(photo, source_id='second', source_name='Second.jpg')
    assert len(calls) == 1
    assert first[0].text == second[0].text
    assert second[0].citation.source_id == 'second'


def test_repetition_loop_is_retried_and_never_cached(monkeypatch, tmp_path):
    photo = tmp_path / 'notes.jpg'
    Image.new('RGB', (100, 100), 'white').save(photo)
    monkeypatch.setenv('CONCEPTFLOW_CACHE_DIR', str(tmp_path / 'cache'))
    attempts = []
    def response(request, **kwargs):
        attempts.append(request)
        text = 'Repeated line\n' * 50 if len(attempts) == 1 else 'BFS uses a queue.'
        return io.BytesIO(json.dumps({'message': {'content': text}}).encode())
    monkeypatch.setattr(images, 'urlopen', response)
    assert images.describe_study_image(photo) == 'BFS uses a queue.'
    assert len(attempts) == 2
    assert images.describe_study_image(photo) == 'BFS uses a queue.'
    assert len(attempts) == 2
