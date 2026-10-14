from threading import Event
import pytest
from PIL import Image
import io
from studybuddy.cancellation import current_cancel, cancellable, GenerationStopped
from studybuddy.ingestion.images import prepare_vision_image
from studybuddy.database import StudyRepository

def test_cancelled_model_result_is_discarded():
    event = Event()
    token = current_cancel.set(event)
    @cancellable
    def generate():
        event.set()
        return "late model answer"
    try:
        with pytest.raises(GenerationStopped):
            generate()
    finally:
        current_cancel.reset(token)

def test_cancelled_request_does_not_commit_chat(tmp_path):
    repository = StudyRepository(tmp_path / "test.db")
    course = repository.create_course("Notes")
    event = Event(); event.set()
    token = current_cancel.set(event)
    try:
        with pytest.raises(GenerationStopped):
            repository.save_chat_exchange(course_id=course, question="q", answer="a", response_metadata={})
    finally:
        current_cancel.reset(token)
    assert repository.list_conversations() == []

def test_camera_photo_preprocessing_preserves_orientation(tmp_path):
    photo = Image.new("RGB", (3000, 1000), "white")
    exif = Image.Exif(); exif[274] = 6
    path = tmp_path / "camera.jpg"
    photo.save(path, exif=exif)
    with Image.open(io.BytesIO(prepare_vision_image(path))) as result:
        assert result.format == "PNG"
        assert result.height > result.width
        assert max(result.size) <= 2400
