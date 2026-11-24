"""Audio extraction port and its ffmpeg adapter (F4, FR-4.2, D34)."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional, Protocol

from app.errors import TranscriptionUnavailableError, UnreadableVideoError, VideoTooLongError

_LOG = logging.getLogger(__name__)
PROBE_TIMEOUT_S = 30  # reading a container header is instant; a hang must not block the upload
WAV_HEADER_BYTES = 44  # a WAV of this size or less holds no samples


class AudioExtractor(Protocol):
    """Turn any recording into a mono 16 kHz WAV file."""

    def extract(self, media_path: Path, wav_path: Path) -> None: ...

    def duration_seconds(self, media_path: Path) -> Optional[float]:
        """Length of the recording in seconds, or None when it cannot be measured."""
        ...


class FfmpegAudioExtractor:
    """Calls the system `ffmpeg` (not reimplemented, R18). The command is an argument list, never a shell string."""

    def __init__(self, ffmpeg: str = "ffmpeg", timeout_s: float = 1800, ffprobe: str = "ffprobe") -> None:
        self._ffmpeg = ffmpeg
        self._ffprobe = ffprobe
        self._timeout_s = timeout_s  # a stuck process must not block the single job slot forever

    def extract(self, media_path: Path, wav_path: Path) -> None:
        """Write `wav_path`; raise UnreadableVideoError (bad file), VideoTooLongError (timeout) or TranscriptionUnavailableError (no ffmpeg)."""
        command = [
            self._ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(media_path),
            "-map", "0:a:0",  # first audio stream; fails cleanly when there is none
            "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
            str(wav_path),
        ]
        try:
            result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                                    timeout=self._timeout_s, check=False)
        except (FileNotFoundError, PermissionError):
            _LOG.error("ffmpeg could not be started")
            raise TranscriptionUnavailableError() from None
        except subprocess.TimeoutExpired:
            _LOG.warning("ffmpeg timed out")
            raise VideoTooLongError() from None
        if result.returncode != 0:
            # The tail of stderr names the codec problem; it holds no speech content.
            _LOG.warning("ffmpeg failed (exit %s): %s", result.returncode,
                         result.stderr.decode("utf-8", "replace")[-500:])
            raise UnreadableVideoError()
        if not wav_path.is_file() or wav_path.stat().st_size <= WAV_HEADER_BYTES:
            raise UnreadableVideoError()

    def duration_seconds(self, media_path: Path) -> Optional[float]:
        """Container duration via `ffprobe` (D36-a). Any failure gives None: the caller then accepts the file."""
        command = [self._ffprobe, "-v", "error", "-show_entries", "format=duration",
                   "-of", "default=noprint_wrappers=1:nokey=1", str(media_path)]
        try:
            result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                                    timeout=PROBE_TIMEOUT_S, check=False)
            seconds = float(result.stdout.decode("ascii", "replace").strip())
        except (OSError, subprocess.TimeoutExpired, ValueError):  # no ffprobe, hang, or "N/A"
            _LOG.warning("ffprobe could not measure the duration")
            return None
        # nan / inf / negative values are not a duration; the ffmpeg timeout still covers such a file.
        return seconds if result.returncode == 0 and 0 <= seconds < float("inf") else None
