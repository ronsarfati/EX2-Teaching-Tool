"""Optional end-to-end check with the real ffmpeg and the cached Whisper model.

Opt-in: set RUN_F4_INTEGRATION=1 (it also needs ffmpeg and the cached `small` model, else it is skipped).
"""
import os
import shutil
import subprocess
import wave

import pytest

from app.adapters.audio import FfmpegAudioExtractor

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_F4_INTEGRATION") or shutil.which("ffmpeg") is None,
    reason="opt-in test: set RUN_F4_INTEGRATION=1 and install ffmpeg",
)


def _cached_model():
    try:
        from faster_whisper import WhisperModel
        return WhisperModel("small", device="cpu", compute_type="int8", local_files_only=True)
    except Exception:  # noqa: BLE001 - any failure means the model is not cached
        return None


def test_real_extraction_and_transcription(tmp_path):
    if _cached_model() is None:
        pytest.skip("the Whisper 'small' model is not in the local cache")
    clip, wav = tmp_path / "input.mp4", tmp_path / "audio.wav"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                    "-f", "lavfi", "-i", "color=c=blue:s=64x64:d=3", "-shortest", str(clip)], check=True)
    FfmpegAudioExtractor().extract(clip, wav)
    with wave.open(str(wav)) as audio:
        assert (audio.getnchannels(), audio.getframerate()) == (1, 16000)
    from app.adapters.transcriber import FasterWhisperTranscriber
    assert FasterWhisperTranscriber("small", None).transcribe(wav).duration_s > 0
