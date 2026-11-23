"""Application settings, read once from environment variables (NFR-8: no secret in code)."""
from __future__ import annotations

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
    whisper_model: str = "base"
    whisper_language: Optional[str] = None

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
            anthropic_api_key=environ.get("ANTHROPIC_API_KEY") or None,
            anthropic_model=environ.get("ANTHROPIC_MODEL") or defaults["anthropic_model"].default,
            whisper_model=environ.get("WHISPER_MODEL") or defaults["whisper_model"].default,
            whisper_language=environ.get("WHISPER_LANGUAGE") or None,
        )
