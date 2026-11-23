"""Application settings, read once from environment variables (NFR-8: no secret in code)."""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from typing import Mapping, Optional

REQUIRED_VARS = ("LECTURER_PIN", "SECRET_KEY", "BASE_URL")


class ConfigError(Exception):
    """Invalid start-up configuration. Not an AppError: shown on the console only, never to a user."""


@dataclass(frozen=True)
class Config:
    """All settings of the application. Secrets have no default value."""

    lecturer_pin: str
    secret_key: str
    base_url: str
    database_path: str = "instance/app.db"
    yunet_model_path: str = "models/face_detection_yunet_2023mar.onnx"
    face_score_threshold: float = 0.4
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-sonnet-5-5"
    whisper_model: str = "small"  # D34: chosen for Hebrew quality
    whisper_language: Optional[str] = None  # None = Whisper detects the language
    video_max_bytes: int = 2 * 1024**3  # upload limit of the F4 route only (2 GiB)
    # Outside the repository, so a recording can never be committed by accident (D34).
    video_work_dir: str = os.path.join(tempfile.gettempdir(), "ex2-video-summary")

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> "Config":
        """Build a Config from `environ`; raise ConfigError if a required variable is missing or empty."""
        missing = [name for name in REQUIRED_VARS if not environ.get(name, "").strip()]
        if missing:
            raise ConfigError("Missing required environment variable(s): " + ", ".join(missing))
        defaults = cls.__dataclass_fields__
        try:
            threshold = float(environ.get("FACE_SCORE_THRESHOLD") or defaults["face_score_threshold"].default)
        except ValueError as exc:
            raise ConfigError("FACE_SCORE_THRESHOLD must be a number") from exc
        return cls(
            lecturer_pin=environ["LECTURER_PIN"],
            secret_key=environ["SECRET_KEY"],
            base_url=environ["BASE_URL"].rstrip("/"),
            database_path=environ.get("DATABASE_PATH") or defaults["database_path"].default,
            yunet_model_path=environ.get("YUNET_MODEL_PATH") or defaults["yunet_model_path"].default,
            face_score_threshold=threshold,
            anthropic_api_key=environ.get("ANTHROPIC_API_KEY", "").strip() or None,
            anthropic_model=environ.get("ANTHROPIC_MODEL") or defaults["anthropic_model"].default,
            whisper_model=environ.get("WHISPER_MODEL") or defaults["whisper_model"].default,
            whisper_language=(environ.get("WHISPER_LANGUAGE", "").strip().lower() or None),
            video_max_bytes=_positive_int(environ, "VIDEO_MAX_BYTES", defaults["video_max_bytes"].default),
            video_work_dir=environ.get("VIDEO_WORK_DIR") or defaults["video_work_dir"].default,
        )


def _positive_int(environ: Mapping[str, str], name: str, default: int) -> int:
    """Read an integer > 0 from `environ[name]` (empty or missing = `default`), else raise ConfigError."""
    raw = environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a whole number of bytes") from exc
    if value < 1:
        raise ConfigError(f"{name} must be greater than 0")
    return value
