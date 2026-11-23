"""Composition root: `create_app` builds the Flask app and its error handling (D2, D23)."""
from __future__ import annotations

import logging
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from app.adapters.audio import AudioExtractor, FfmpegAudioExtractor
from app.adapters.head_counter import HeadCounter, YuNetHeadCounter
from app.adapters.jobs import JobRunner, ThreadJobRunner
from app.adapters.llm import ClaudeClient, LLMClient
from app.adapters.repo_fetcher import GitHubRepoFetcher, RepoFetcher
from app.adapters.transcriber import FasterWhisperTranscriber, Transcriber
from app.clock import Clock, SystemClock
from app.config import Config
from app.db import Database
from app.errors import AppError
from app.repositories.comments import CommentRepository
from app.repositories.checkins import CheckInRepository
from app.repositories.polls import PollRepository
from app.repositories.sessions import SessionRepository
from app.repositories.settings import SettingsRepository
from app.repositories.summaries import SummaryRepository
from app.repositories.windows import CheckInWindowRepository
from app.services.comments import CommentService
from app.services.checkin import CheckInService
from app.services.export import AttendanceExporter
from app.services.homework import HomeworkReviewer
from app.services.lecture_summary import LectureSummariser
from app.services.credentials import RotatingCredentials
from app.services.polls import PollService
from app.services.sessions import SessionService
from app.services.video import VideoSummaryService
from app.web.api_routes import bp as api_bp
from app.web.lecturer_routes import bp as lecturer_bp
from app.web.student_routes import bp as student_bp

MAX_PHOTO_BYTES = 25 * 1024 * 1024  # a phone photo is a few MB; refuse absurd uploads
GENERIC_MESSAGE = "Something went wrong. Please try again."
SUMMARY_LLM_TIMEOUT_S = 180  # F4 runs in the background (no tunnel limit), a long map-reduce call needs time
logger = logging.getLogger(__name__)


def create_app(config: Config, *, clock: Clock | None = None,
               head_counter: HeadCounter | None = None, llm: LLMClient | None = None,
               fetcher: RepoFetcher | None = None, transcriber: Transcriber | None = None,
               audio_extractor: AudioExtractor | None = None, job_runner: JobRunner | None = None,
               **fakes: object) -> Flask:
    """Build the app. Anything left out (clock, adapters) gets its real implementation.

    `fakes` overrides any other entry of the services registry; tests inject doubles there.
    """
    app = Flask(__name__)
    app.config.update(SECRET_KEY=config.secret_key, DEBUG=False, SESSION_COOKIE_SAMESITE="Lax", MAX_CONTENT_LENGTH=MAX_PHOTO_BYTES)  # NFR-8: never debug
    db = Database(config.database_path)
    db.init_schema()
    clock = clock or SystemClock()
    head_counter = head_counter or YuNetHeadCounter(config.yunet_model_path, config.face_score_threshold)
    summary_llm = llm or ClaudeClient(config.anthropic_api_key, config.anthropic_model, SUMMARY_LLM_TIMEOUT_S)
    llm = llm or ClaudeClient(config.anthropic_api_key, config.anthropic_model)
    transcriber = transcriber or FasterWhisperTranscriber(config.whisper_model, config.whisper_language)  # loads nothing yet
    audio_extractor = audio_extractor or FfmpegAudioExtractor()
    job_runner = job_runner or ThreadJobRunner()
    fetcher = fetcher or GitHubRepoFetcher()
    sessions = SessionRepository(db)
    credentials = RotatingCredentials(config.secret_key, clock)
    check_ins = CheckInRepository(db)
    windows = CheckInWindowRepository(db)
    settings = SettingsRepository(db)
    app.extensions["services"] = {
        "config": config,
        "clock": clock,
        "db": db,
        "sessions": sessions,
        "session_service": SessionService(
            sessions, clock, credentials, config.base_url, check_ins, head_counter
        ),
        "checkin_service": CheckInService(
            credentials, sessions, check_ins, windows, db, clock
        ),
        "comment_service": CommentService(CommentRepository(db), clock),
        "poll_service": PollService(PollRepository(db), clock),
        "reviewer": HomeworkReviewer(fetcher, llm, settings),
        "exporter": AttendanceExporter(sessions, check_ins),
        "video_service": VideoSummaryService(
            SummaryRepository(db), audio_extractor, transcriber, LectureSummariser(summary_llm),
            job_runner, clock, Path(config.video_work_dir),
        ),
        "head_counter": head_counter,
        "check_ins": check_ins,
        "windows": windows,
        "settings": settings,
        **fakes,
    }

    # Werkzeug's access log prints the peer address and the QR token in the URL (D21: never logged).
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Frame-Options"] = "DENY"  # no clickjacking of the lecturer's forms
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/ping")
    def ping() -> str:
        return "ok"

    app.register_blueprint(lecturer_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(student_bp)
    _register_error_handlers(app)
    app.extensions["services"]["video_service"].recover_interrupted()  # no job thread can exist yet (D34)
    return app


def _render_error(message: str, status: int):
    """JSON under /api/ (polled by scripts), a page otherwise."""
    if request.path.startswith("/api/"):
        return jsonify(error=message), status
    return render_template("error.html", message=message), status


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(AppError)
    def handle_app_error(error: AppError):
        return _render_error(error.user_message, error.http_status)

    @app.errorhandler(Exception)
    def handle_unexpected(error: Exception):
        if isinstance(error, HTTPException):  # 404, 405...: keep the status, use plain wording
            return _render_error(error.description or GENERIC_MESSAGE, error.code or 500)
        logger.exception("Unhandled error on %s", request.path)  # traceback goes to the log only
        return _render_error(GENERIC_MESSAGE, 500)
