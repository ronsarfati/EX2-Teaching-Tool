"""Speech-to-text port and its faster-whisper adapter (F4, FR-4.3, D34)."""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Protocol

from app.errors import TranscriptionUnavailableError, UnreadableVideoError

_LOG = logging.getLogger(__name__)
ProgressCallback = Callable[[float], None]  # a fraction between 0.0 and 1.0


@dataclass(frozen=True)
class Transcript:
    """The recognised text of one recording. Kept in memory only, never stored (FR-4.5)."""

    text: str
    language: Optional[str]
    duration_s: float


class Transcriber(Protocol):
    def transcribe(self, audio_path: Path, on_progress: Optional[ProgressCallback] = None) -> Transcript: ...


class FasterWhisperTranscriber:
    """faster-whisper on CPU. The model is loaded at the first call, so starting the app (and the tests) is free."""

    def __init__(self, model_size: str, language: Optional[str]) -> None:
        self._model_size = model_size
        self._language = language
        self._model = None
        self._lock = threading.Lock()

    def _load_model(self):
        """Load once, under a lock; a failure is not cached, so the next job retries (e.g. after going online)."""
        with self._lock:
            if self._model is None:
                try:
                    from faster_whisper import WhisperModel  # lazy: heavy import, and a download on first use
                    self._model = WhisperModel(self._model_size, device="cpu", compute_type="int8")
                except Exception as exc:  # noqa: BLE001 - import, download, unknown size, disk: one user message
                    _LOG.error("Whisper model could not be loaded: %s", type(exc).__name__)
                    raise TranscriptionUnavailableError() from None
            return self._model

    def transcribe(self, audio_path: Path, on_progress: Optional[ProgressCallback] = None) -> Transcript:
        model = self._load_model()
        try:
            segments, info = model.transcribe(str(audio_path), language=self._language,
                                              beam_size=1, vad_filter=True)
            lines = []
            for segment in segments:  # lazy generator: the real work happens while iterating
                lines.append(segment.text.strip())
                if on_progress is not None and info.duration > 0:
                    on_progress(min(1.0, segment.end / info.duration))
        except Exception as exc:  # noqa: BLE001
            if _is_decode_error(exc):
                _LOG.warning("Audio could not be decoded: %s", type(exc).__name__)
                raise UnreadableVideoError() from None
            raise
        return Transcript("\n".join(lines), info.language, info.duration)


def _is_decode_error(exc: Exception) -> bool:
    """True for a PyAV/FFmpeg decoding failure (imported lazily, like faster-whisper itself)."""
    try:
        from av.error import FFmpegError
    except ImportError:
        return False
    return isinstance(exc, FFmpegError)
