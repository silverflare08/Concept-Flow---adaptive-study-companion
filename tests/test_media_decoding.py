import wave
import pytest

def test_real_whisper_audio_decoder_accepts_wav(tmp_path):
    pytest.importorskip('faster_whisper')
    from faster_whisper.audio import decode_audio
    source = tmp_path / 'audio.wav'
    with wave.open(str(source), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b'\0\0' * 16000)
    audio = decode_audio(str(source))
    assert len(audio) == 16000
    assert audio.dtype.name == 'float32'
