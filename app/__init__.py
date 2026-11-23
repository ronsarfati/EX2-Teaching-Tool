"""Composition root: `create_app` builds the Flask app and its error handling (D2, D23)."""
from __future__ import annotations

import logging

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from app.adapters.head_counter import HeadCounter, YuNetHeadCounter
from app.adapters.llm import ClaudeClient, LLMClient
from app.adapters.repo_fetcher import GitHubRepoFetcher, RepoFetcher
from app.clock import Clock, SystemClock
from app.config import Config
from app.db import Database
from app.errors import AppError
from app.repositories.comments import CommentRepository
from app.repositories.checkins import CheckInRepository
from app.repositories.polls import PollRepository
from app.repositories.sessions import SessionRepository
from app.repositories.settings import SettingsRepository
from app.repositories.windows import CheckInWindowRepository
from app.services.comments import CommentService
from app.services.checkin import CheckInService
from app.services.export import AttendanceExporter
from app.services.homework import HomeworkReviewer
from app.services.credentials import RotatingCredentials
from app.services.network import NetworkPolicy
from app.services.polls import PollService
from app.services.sessions import SessionService
from app.web.api_routes import bp as api_bp
from app.web.lecturer_routes import bp as lecturer_bp
from app.web.student_routes import bp as student_bp

MAX_PHOTO_BYTES = 25 * 1024 * 1024  # a phone photo is a few MB; refuse absurd uploads
GENERIC_MESSAGE = "Something went wrong. Please try again."
logger = logging.getLogger(__name__)


def create_app(config: Config, *, clock: Clock | None = None,
               head_counter: HeadCounter | None = None, llm: LLMClient | None = None,
               fetcher: RepoFetcher | None = None, **fakes: object) -> Flask:
    """Build the app. Anything left out (clock, adapters) gets its real implementation.

    `fakes` is where later tasks add the transcriber; tests inject doubles there.
    """
    app = Flask(__name__)
    app.config.update(SECRET_KEY=config.secret_key, DEBUG=False, MAX_CONTENT_LENGTH=MAX_PHOTO_BYTES)  # NFR-8: never debug
    db = Database(config.database_path)
    db.init_schema()
    clock = clock or SystemClock()
    head_counter = head_counter or YuNetHeadCounter(config.yunet_model_path, config.face_score_threshold)
    llm = llm or ClaudeClient(config.anthropic_api_key, config.anthropic_model)
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
            NetworkPolicy(settings), credentials, sessions, check_ins, windows, db, clock
        ),
        "comment_service": CommentService(CommentRepository(db), clock),
        "poll_service": PollService(PollRepository(db), clock),
        "reviewer": HomeworkReviewer(fetcher, llm, settings),
        "exporter": AttendanceExporter(sessions, check_ins),
        "head_counter": head_counter,
        "check_ins": check_ins,
        "windows": windows,
        "settings": settings,
        **fakes,
    }

    @app.get("/ping")
    def ping() -> str:
        return "ok"

    app.register_blueprint(lecturer_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(student_bp)
    _register_error_handlers(app)
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
